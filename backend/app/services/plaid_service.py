"""
Plaid integration — connect bank accounts, brokerages, and credit cards
with zero manual effort. Link once, auto-sync forever.
"""

import json
from datetime import date, timedelta
from typing import Optional

import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.investments_transactions_get_request import InvestmentsTransactionsGetRequest
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode

from app.config import settings
from app.database import get_db


def _get_client() -> plaid_api.PlaidApi:
    """Create Plaid API client from settings."""
    config = plaid.Configuration(
        host=_get_plaid_host(),
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
    )
    api_client = plaid.ApiClient(config)
    return plaid_api.PlaidApi(api_client)


def _get_plaid_host():
    env = settings.plaid_env.lower()
    if env == "production":
        return plaid.Environment.Production
    if env == "development":
        return plaid.Environment.Development
    return plaid.Environment.Sandbox


def is_configured() -> bool:
    """Check if Plaid credentials are set."""
    return bool(settings.plaid_client_id and settings.plaid_secret)


def create_link_token(user_id: str = "sentinel-user") -> dict:
    """Create a Plaid Link token for the frontend."""
    client = _get_client()

    products = [Products("transactions")]
    # Add investments if supported
    optional_products = [Products("investments")]

    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
        client_name="Sentinel",
        products=products,
        optional_products=optional_products,
        country_codes=[CountryCode("US")],
        language="en",
    )

    response = client.link_token_create(request)
    return {"link_token": response.link_token, "expiration": str(response.expiration)}


def exchange_public_token(public_token: str, institution_name: str = "") -> dict:
    """Exchange a public token from Plaid Link for an access token and create accounts."""
    client = _get_client()

    exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = client.item_public_token_exchange(exchange_request)

    access_token = response.access_token
    item_id = response.item_id

    # Get account details
    balance_request = AccountsBalanceGetRequest(access_token=access_token)
    balance_response = client.accounts_balance_get(balance_request)

    created_accounts = []

    with get_db() as conn:
        # Store the Plaid item
        conn.execute(
            """INSERT OR REPLACE INTO plaid_items
               (item_id, access_token, institution_name, cursor, created_at)
               VALUES (?, ?, ?, '', datetime('now'))""",
            (item_id, access_token, institution_name),
        )

        # Create accounts for each Plaid account
        for plaid_acct in balance_response.accounts:
            acct_type = _map_plaid_account_type(plaid_acct.type.value)
            acct_name = f"{institution_name} {plaid_acct.name}".strip() or plaid_acct.name

            # Check if already linked
            existing = conn.execute(
                "SELECT id FROM accounts WHERE plaid_account_id = ?",
                (plaid_acct.account_id,),
            ).fetchone()

            if existing:
                account_id = existing["id"]
            else:
                cursor = conn.execute(
                    """INSERT INTO accounts
                       (name, type, institution, plaid_account_id, plaid_item_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (acct_name, acct_type, institution_name.lower() or "plaid",
                     plaid_acct.account_id, item_id),
                )
                account_id = cursor.lastrowid

            # Store initial balance as a holding
            balance = plaid_acct.balances
            current = balance.current or 0
            available = balance.available

            if acct_type in ("checking", "credit_card"):
                # For deposit/credit accounts, store as cash holding
                conn.execute(
                    "DELETE FROM holdings WHERE account_id = ? AND asset = 'CASH'",
                    (account_id,),
                )
                conn.execute(
                    """INSERT INTO holdings (account_id, asset, quantity, current_value)
                       VALUES (?, 'CASH', ?, ?)""",
                    (account_id, current, current),
                )
            conn.execute(
                "UPDATE accounts SET last_import_date = datetime('now') WHERE id = ?",
                (account_id,),
            )

            created_accounts.append({
                "id": account_id,
                "name": acct_name,
                "type": acct_type,
                "balance": current,
                "available": available,
                "plaid_account_id": plaid_acct.account_id,
            })

    return {
        "item_id": item_id,
        "accounts": created_accounts,
    }


def sync_transactions(item_id: Optional[str] = None) -> dict:
    """
    Sync transactions using Plaid's transaction sync endpoint.
    Uses cursor-based pagination for incremental updates.
    """
    client = _get_client()
    total_added = 0
    total_modified = 0
    total_removed = 0
    items_synced = 0

    with get_db() as conn:
        if item_id:
            items = conn.execute(
                "SELECT item_id, access_token, cursor FROM plaid_items WHERE item_id = ?",
                (item_id,),
            ).fetchall()
        else:
            items = conn.execute(
                "SELECT item_id, access_token, cursor FROM plaid_items"
            ).fetchall()

    for item in items:
        access_token = item["access_token"]
        cursor = item["cursor"] or ""
        has_more = True

        while has_more:
            request = TransactionsSyncRequest(
                access_token=access_token,
                cursor=cursor,
            )
            response = client.transactions_sync(request)

            # Process added transactions
            for tx in response.added:
                _upsert_plaid_transaction(tx, item["item_id"])
                total_added += 1

            # Process modified transactions
            for tx in response.modified:
                _upsert_plaid_transaction(tx, item["item_id"])
                total_modified += 1

            # Process removed transactions
            for tx in response.removed:
                _remove_plaid_transaction(tx.transaction_id)
                total_removed += 1

            has_more = response.has_more
            cursor = response.next_cursor

        # Save cursor for next sync
        with get_db() as conn:
            conn.execute(
                "UPDATE plaid_items SET cursor = ?, last_synced = datetime('now') WHERE item_id = ?",
                (cursor, item["item_id"]),
            )

        items_synced += 1

    return {
        "items_synced": items_synced,
        "transactions_added": total_added,
        "transactions_modified": total_modified,
        "transactions_removed": total_removed,
    }


def sync_holdings(item_id: Optional[str] = None) -> dict:
    """Sync investment holdings from Plaid."""
    client = _get_client()
    total_holdings = 0
    total_securities = 0

    with get_db() as conn:
        if item_id:
            items = conn.execute(
                "SELECT item_id, access_token FROM plaid_items WHERE item_id = ?",
                (item_id,),
            ).fetchall()
        else:
            items = conn.execute(
                "SELECT item_id, access_token FROM plaid_items"
            ).fetchall()

    for item in items:
        try:
            request = InvestmentsHoldingsGetRequest(access_token=item["access_token"])
            response = client.investments_holdings_get(request)
        except plaid.ApiException:
            # This item may not have investment products
            continue

        # Build security lookup
        securities = {s.security_id: s for s in response.securities}
        total_securities += len(securities)

        with get_db() as conn:
            for holding in response.holdings:
                security = securities.get(holding.security_id)
                if not security:
                    continue

                symbol = security.ticker_symbol or security.name or "UNKNOWN"
                quantity = holding.quantity or 0
                value = holding.institution_value or 0
                cost_basis = holding.cost_basis or None

                # Find the local account
                acct = conn.execute(
                    "SELECT id FROM accounts WHERE plaid_account_id = ?",
                    (holding.account_id,),
                ).fetchone()

                if not acct:
                    continue

                account_id = acct["id"]

                # Upsert holding
                existing = conn.execute(
                    "SELECT id FROM holdings WHERE account_id = ? AND asset = ?",
                    (account_id, symbol),
                ).fetchone()

                unrealized = (value - cost_basis) if cost_basis else None

                if existing:
                    conn.execute(
                        """UPDATE holdings SET
                           quantity = ?, current_value = ?,
                           cost_basis_total = ?, unrealized_gain_loss = ?,
                           updated_at = datetime('now')
                           WHERE id = ?""",
                        (quantity, value, cost_basis, unrealized, existing["id"]),
                    )
                else:
                    conn.execute(
                        """INSERT INTO holdings
                           (account_id, asset, quantity, current_value,
                            cost_basis_total, unrealized_gain_loss)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (account_id, symbol, quantity, value, cost_basis, unrealized),
                    )

                total_holdings += 1

            conn.execute(
                "UPDATE accounts SET last_import_date = datetime('now') WHERE plaid_item_id = ?",
                (item["item_id"],),
            )

    return {
        "holdings_synced": total_holdings,
        "securities_found": total_securities,
    }


def sync_balances(item_id: Optional[str] = None) -> dict:
    """Refresh account balances."""
    client = _get_client()
    updated = 0

    with get_db() as conn:
        if item_id:
            items = conn.execute(
                "SELECT item_id, access_token FROM plaid_items WHERE item_id = ?",
                (item_id,),
            ).fetchall()
        else:
            items = conn.execute(
                "SELECT item_id, access_token FROM plaid_items"
            ).fetchall()

    for item in items:
        request = AccountsBalanceGetRequest(access_token=item["access_token"])
        response = client.accounts_balance_get(request)

        with get_db() as conn:
            for plaid_acct in response.accounts:
                acct = conn.execute(
                    "SELECT id, type FROM accounts WHERE plaid_account_id = ?",
                    (plaid_acct.account_id,),
                ).fetchone()

                if not acct:
                    continue

                current = plaid_acct.balances.current or 0

                if acct["type"] in ("checking", "credit_card"):
                    conn.execute(
                        "DELETE FROM holdings WHERE account_id = ? AND asset = 'CASH'",
                        (acct["id"],),
                    )
                    conn.execute(
                        """INSERT INTO holdings (account_id, asset, quantity, current_value)
                           VALUES (?, 'CASH', ?, ?)""",
                        (acct["id"], current, current),
                    )

                conn.execute(
                    "UPDATE accounts SET last_import_date = datetime('now') WHERE id = ?",
                    (acct["id"],),
                )
                updated += 1

    return {"accounts_updated": updated}


def get_linked_items() -> list[dict]:
    """Get all linked Plaid items."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT item_id, institution_name, last_synced, created_at FROM plaid_items"
        ).fetchall()
    return [dict(r) for r in rows]


def remove_item(item_id: str):
    """Unlink a Plaid item and remove associated data."""
    with get_db() as conn:
        conn.execute("DELETE FROM plaid_items WHERE item_id = ?", (item_id,))
        # Don't delete accounts/transactions — keep the data, just unlink


def _upsert_plaid_transaction(tx, item_id: str):
    """Insert or update a transaction from Plaid."""
    with get_db() as conn:
        acct = conn.execute(
            "SELECT id FROM accounts WHERE plaid_account_id = ?",
            (tx.account_id,),
        ).fetchone()

        if not acct:
            return

        account_id = acct["id"]
        tx_date = tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date)
        amount = abs(tx.amount) if tx.amount else 0
        # Plaid: positive = money leaving account (expense), negative = money entering (income)
        tx_type = "expense" if tx.amount and tx.amount > 0 else "income"

        merchant = tx.merchant_name or tx.name or ""
        category = _map_plaid_category(tx.personal_finance_category)

        # Check if transaction already exists
        existing = conn.execute(
            "SELECT id FROM transactions WHERE plaid_transaction_id = ?",
            (tx.transaction_id,),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE transactions SET
                   date = ?, total_amount = ?, category = ?,
                   description = ?, type = ?
                   WHERE plaid_transaction_id = ?""",
                (tx_date, amount, category, merchant, tx_type, tx.transaction_id),
            )
        else:
            conn.execute(
                """INSERT INTO transactions
                   (account_id, date, type, total_amount, category,
                    description, source, plaid_transaction_id)
                   VALUES (?, ?, ?, ?, ?, ?, 'plaid', ?)""",
                (account_id, tx_date, tx_type, amount, category,
                 merchant, tx.transaction_id),
            )
            tx_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Create expense record
            if tx_type == "expense":
                conn.execute(
                    """INSERT INTO expenses
                       (transaction_id, merchant, amount, date, category)
                       VALUES (?, ?, ?, ?, ?)""",
                    (tx_id, merchant, amount, tx_date, category),
                )


def _remove_plaid_transaction(transaction_id: str):
    """Remove a transaction that Plaid says was deleted."""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM transactions WHERE plaid_transaction_id = ?",
            (transaction_id,),
        )


def _map_plaid_category(pfc) -> Optional[str]:
    """Map Plaid's personal_finance_category to our categories."""
    if not pfc:
        return None
    primary = pfc.primary.upper() if hasattr(pfc, 'primary') else ""

    mapping = {
        "FOOD_AND_DRINK": "food",
        "GROCERIES": "food",
        "RESTAURANTS": "food",
        "TRANSPORTATION": "transport",
        "TRAVEL": "travel",
        "ENTERTAINMENT": "entertainment",
        "RECREATION": "entertainment",
        "SHOPPING": "shopping",
        "PERSONAL_CARE": "health",
        "MEDICAL": "health",
        "RENT_AND_UTILITIES": "utilities",
        "HOME_IMPROVEMENT": "housing",
        "GENERAL_MERCHANDISE": "shopping",
        "TRANSFER_IN": "transfer",
        "TRANSFER_OUT": "transfer",
        "LOAN_PAYMENTS": "debt",
        "INCOME": "income",
        "BANK_FEES": "fees",
        "GENERAL_SERVICES": "other",
    }
    return mapping.get(primary, "other")


def _map_plaid_account_type(plaid_type: str) -> str:
    """Map Plaid account type to our account types."""
    mapping = {
        "depository": "checking",
        "credit": "credit_card",
        "investment": "brokerage",
        "loan": "checking",
        "brokerage": "brokerage",
    }
    return mapping.get(plaid_type, "checking")

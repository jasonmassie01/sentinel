"""
CSV import service — orchestrates parsing and database ingestion.
"""

from app.database import get_db
from app.parsers.csv_parser import (
    ParseResult,
    parse_fidelity_brokerage,
    parse_schwab_brokerage,
    parse_fidelity_credit_card,
    parse_bank_csv,
)

# Map institution/type combos to their parsers
PARSERS = {
    ("fidelity", "brokerage"): parse_fidelity_brokerage,
    ("schwab", "brokerage"): parse_schwab_brokerage,
    ("fidelity", "credit_card"): parse_fidelity_credit_card,
    ("bank", "checking"): parse_bank_csv,
}


def import_csv(account_id: int, content: str) -> dict:
    """
    Import a CSV file for a given account.
    Returns summary of what was imported.
    """
    # Look up the account to determine which parser to use
    with get_db() as conn:
        row = conn.execute(
            "SELECT institution, type FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()

    if not row:
        return {"error": "Account not found", "success": False}

    institution = row["institution"]
    account_type = row["type"]

    parser_key = (institution, account_type)
    parser = PARSERS.get(parser_key)

    if not parser:
        return {
            "error": f"No parser available for {institution}/{account_type}",
            "success": False,
        }

    result: ParseResult = parser(content)

    # Ingest transactions
    tx_inserted = 0
    with get_db() as conn:
        for tx in result.transactions:
            conn.execute(
                """INSERT INTO transactions
                   (account_id, date, type, asset, quantity, price_per_unit,
                    total_amount, category, description, tax_relevant, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'csv_import')""",
                (
                    account_id,
                    tx.date,
                    tx.type,
                    tx.asset,
                    tx.quantity,
                    tx.price_per_unit,
                    tx.total_amount,
                    tx.category,
                    tx.description,
                    1 if tx.tax_relevant else 0,
                ),
            )
            tx_inserted += 1

            # If it's an expense, also create expense record
            if tx.type == "expense":
                conn.execute(
                    """INSERT INTO expenses
                       (transaction_id, merchant, amount, date, category)
                       VALUES (last_insert_rowid(), ?, ?, ?, ?)""",
                    (tx.description, tx.total_amount, tx.date, tx.category),
                )

        # Ingest holdings (upsert — replace if same account+asset)
        holdings_upserted = 0
        for h in result.holdings:
            conn.execute(
                """INSERT INTO holdings (account_id, asset, quantity, current_value,
                   cost_basis_total, unrealized_gain_loss)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                   quantity=excluded.quantity,
                   current_value=excluded.current_value,
                   cost_basis_total=excluded.cost_basis_total,
                   unrealized_gain_loss=excluded.unrealized_gain_loss,
                   updated_at=datetime('now')""",
                (
                    account_id,
                    h.asset,
                    h.quantity,
                    h.current_value,
                    h.cost_basis_total,
                    h.unrealized_gain_loss,
                ),
            )
            holdings_upserted += 1

        # Update account last_import_date
        conn.execute(
            "UPDATE accounts SET last_import_date = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (account_id,),
        )

    return {
        "success": True,
        "rows_in_file": result.row_count,
        "rows_parsed": result.parsed_count,
        "transactions_imported": tx_inserted,
        "holdings_imported": holdings_upserted,
        "errors": result.errors,
    }

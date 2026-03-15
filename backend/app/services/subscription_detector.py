"""
Subscription detection and creep monitoring.

Scans expense history for recurring charges from the same merchant
at regular intervals and tracks price changes.
"""

from dataclasses import dataclass
from typing import Optional
from collections import defaultdict
from datetime import date

from app.database import get_db


@dataclass
class DetectedSubscription:
    merchant: str
    current_amount: float
    frequency: str  # monthly, annual, quarterly, weekly
    first_seen: str
    last_seen: str
    charge_count: int
    amounts: list[float]
    price_changed: bool
    price_change_amount: Optional[float]  # positive = increase
    annual_cost: float
    status: str  # active, price_increased


def detect_subscriptions(min_occurrences: int = 3) -> list[DetectedSubscription]:
    """
    Scan expense history to identify recurring charges.
    Groups by merchant, detects frequency, flags price changes.
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT merchant, amount, date
               FROM expenses
               WHERE is_recurring = 0
               ORDER BY merchant, date""",
        ).fetchall()

    # Group charges by merchant
    merchant_charges: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        merchant = _normalize_merchant(row["merchant"])
        merchant_charges[merchant].append({
            "amount": row["amount"],
            "date": row["date"],
        })

    subscriptions = []
    for merchant, charges in merchant_charges.items():
        if len(charges) < min_occurrences:
            continue

        amounts = [c["amount"] for c in charges]
        dates = sorted(c["date"] for c in charges)

        # Check if amounts are consistent (within 20% tolerance for same-merchant)
        avg_amount = sum(amounts) / len(amounts)
        if avg_amount == 0:
            continue
        consistent = all(abs(a - avg_amount) / avg_amount < 0.20 for a in amounts)
        if not consistent:
            continue

        # Detect frequency
        frequency = _detect_frequency(dates)
        if not frequency:
            continue

        # Check for price changes
        recent_amount = amounts[-1]
        earliest_amount = amounts[0]
        price_changed = abs(recent_amount - earliest_amount) > 0.50
        price_change = recent_amount - earliest_amount if price_changed else None

        # Annual cost
        multipliers = {"weekly": 52, "monthly": 12, "quarterly": 4, "annual": 1}
        annual_cost = recent_amount * multipliers.get(frequency, 12)

        subscriptions.append(DetectedSubscription(
            merchant=merchant,
            current_amount=recent_amount,
            frequency=frequency,
            first_seen=dates[0],
            last_seen=dates[-1],
            charge_count=len(charges),
            amounts=amounts,
            price_changed=price_changed,
            price_change_amount=price_change,
            annual_cost=annual_cost,
            status="price_increased" if price_changed and (price_change or 0) > 0 else "active",
        ))

    # Sort by annual cost descending
    subscriptions.sort(key=lambda s: -s.annual_cost)
    return subscriptions


def save_detected_subscriptions(subs: list[DetectedSubscription]):
    """Persist detected subscriptions to the database."""
    with get_db() as conn:
        for sub in subs:
            existing = conn.execute(
                "SELECT id FROM subscriptions WHERE merchant = ?",
                (sub.merchant,),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE subscriptions SET
                       amount = ?, frequency = ?, last_seen = ?,
                       status = ?, annual_cost = ?, updated_at = datetime('now')
                       WHERE id = ?""",
                    (sub.current_amount, sub.frequency, sub.last_seen,
                     sub.status, sub.annual_cost, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO subscriptions
                       (merchant, amount, frequency, first_seen, last_seen, status, annual_cost)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (sub.merchant, sub.current_amount, sub.frequency,
                     sub.first_seen, sub.last_seen, sub.status, sub.annual_cost),
                )


def get_subscriptions() -> list[dict]:
    """Get all tracked subscriptions."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM subscriptions ORDER BY annual_cost DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_total_annual_subscription_cost() -> float:
    """Total annual cost of all active subscriptions."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(annual_cost), 0) as total FROM subscriptions WHERE status != 'cancelled'"
        ).fetchone()
    return row["total"]


def _normalize_merchant(merchant: str) -> str:
    """Normalize merchant names for grouping."""
    merchant = merchant.upper().strip()
    # Remove common suffixes/prefixes
    for noise in ["INC", "LLC", "CO", "CORP", ".COM", "WWW.", "HTTP", "*"]:
        merchant = merchant.replace(noise, "")
    return merchant.strip()


def _detect_frequency(dates: list[str]) -> Optional[str]:
    """Detect charge frequency from date patterns."""
    if len(dates) < 2:
        return None

    parsed = [date.fromisoformat(d) for d in dates]
    gaps = [(parsed[i + 1] - parsed[i]).days for i in range(len(parsed) - 1)]
    avg_gap = sum(gaps) / len(gaps)

    if 3 <= avg_gap <= 10:
        return "weekly"
    if 25 <= avg_gap <= 35:
        return "monthly"
    if 80 <= avg_gap <= 100:
        return "quarterly"
    if 340 <= avg_gap <= 400:
        return "annual"

    return None

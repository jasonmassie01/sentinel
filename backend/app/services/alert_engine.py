"""
Smart Alerts — proactive intelligence engine.

Aggregates alerts from all modules into a unified feed.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import date, timedelta

from app.database import get_db
from app.services import tax_engine, subscription_detector, price_monitor


@dataclass
class Alert:
    id: str
    type: str  # lot_aging, price_drop, subscription_increase, bill_due, tax_action, utxo_consolidation
    severity: str  # info, warning, urgent
    title: str
    message: str
    source_module: str
    action_url: Optional[str] = None
    amount: Optional[float] = None
    created_at: Optional[str] = None


def get_all_alerts(prices: Optional[dict[str, float]] = None) -> list[Alert]:
    """Aggregate alerts from all modules."""
    alerts: list[Alert] = []

    # 1. Lot aging alerts
    try:
        aging = tax_engine.get_lot_aging_alerts(prices=prices)
        for a in aging:
            severity = "urgent" if a.urgency == "7d" else "warning" if a.urgency == "14d" else "info"
            savings_msg = f" Waiting saves ~${a.estimated_tax_savings:,.0f}" if a.estimated_tax_savings else ""
            alerts.append(Alert(
                id=f"lot_aging_{a.lot_id}",
                type="lot_aging",
                severity=severity,
                title=f"{a.asset}: {a.days_to_long_term} days to long-term",
                message=f"{a.quantity:.4f} {a.asset} in {a.account_name} crosses the 1-year threshold on {a.long_term_date}.{savings_msg}",
                source_module="tax_brain",
                amount=a.estimated_tax_savings,
            ))
    except Exception:
        pass

    # 2. Price drop alerts
    try:
        drops = price_monitor.get_price_drop_alerts()
        for d in drops:
            alerts.append(Alert(
                id=f"price_drop_{d.item_description[:20]}",
                type="price_drop",
                severity="warning",
                title=f"Price drop: {d.item_description[:50]}",
                message=f"Purchased for ${d.purchase_price:.2f} from {d.purchase_merchant}. "
                        f"Now ${d.current_lowest_price:.2f} at {d.lowest_price_source}. "
                        f"Save ${d.savings:.2f} — {d.days_left_to_return} days left to return.",
                source_module="email_intelligence",
                amount=d.savings,
            ))
    except Exception:
        pass

    # 3. Subscription price increases
    try:
        subs = subscription_detector.get_subscriptions()
        for s in subs:
            if s.get("status") == "price_increased":
                amount = s.get("amount") or 0
                annual = s.get("annual_cost") or 0
                alerts.append(Alert(
                    id=f"sub_increase_{s['merchant']}",
                    type="subscription_increase",
                    severity="info",
                    title=f"{s['merchant']}: price increased",
                    message=f"Subscription now ${amount:.2f}/{s['frequency']}. Annual cost: ${annual:.2f}.",
                    source_module="email_intelligence",
                    amount=annual,
                ))
    except Exception:
        pass

    # 4. Tax-loss harvesting opportunities
    try:
        if prices:
            candidates = tax_engine.find_harvest_candidates(prices=prices, min_loss=500)
            for c in candidates[:3]:  # Top 3 only
                alerts.append(Alert(
                    id=f"harvest_{c.lot_id}",
                    type="tax_action",
                    severity="info",
                    title=f"Harvest opportunity: {c.asset}",
                    message=f"Realize ${abs(c.unrealized_loss):,.2f} in losses from {c.account_name}. "
                            f"{'Wash sale risk — check 30-day window.' if c.wash_sale_risk else 'No wash sale conflict.'}",
                    source_module="tax_brain",
                    amount=abs(c.unrealized_loss),
                ))
    except Exception:
        pass

    # 5. Upcoming bills / cash flow
    try:
        with get_db() as conn:
            upcoming = conn.execute(
                """SELECT merchant, amount, next_due_date, price_change_detected
                   FROM recurring_bills
                   WHERE next_due_date BETWEEN date('now') AND date('now', '+14 days')
                   ORDER BY next_due_date""",
            ).fetchall()

        for bill in upcoming:
            days_until = (date.fromisoformat(bill["next_due_date"]) - date.today()).days
            alerts.append(Alert(
                id=f"bill_{bill['merchant']}_{bill['next_due_date']}",
                type="bill_due",
                severity="warning" if days_until <= 3 else "info",
                title=f"{bill['merchant']}: ${bill['amount']:.2f} due in {days_until} days",
                message=f"Due {bill['next_due_date']}." +
                        (" Price increase detected." if bill["price_change_detected"] else ""),
                source_module="alerts",
                amount=bill["amount"],
            ))
    except Exception:
        pass

    # 6. Wishlist alerts
    try:
        with get_db() as conn:
            wishlist_alerts = conn.execute(
                "SELECT * FROM wishlist WHERE alert_triggered = 1"
            ).fetchall()

        for w in wishlist_alerts:
            cur = w["current_price"] or 0
            target = w["target_price"] or 0
            lowest = w["lowest_price_ever"] or 0
            alerts.append(Alert(
                id=f"wishlist_{w['id']}",
                type="price_drop",
                severity="info",
                title=f"Wishlist: {w['item_description'][:50]} hit target price",
                message=f"Now ${cur:.2f} (target: ${target:.2f}). "
                        f"Lowest ever: ${lowest:.2f} on {w.get('lowest_price_date', 'N/A')}.",
                source_module="email_intelligence",
                amount=target - cur if cur else None,
            ))
    except Exception:
        pass

    # Sort: urgent first, then by amount
    severity_order = {"urgent": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: (severity_order.get(a.severity, 9), -(a.amount or 0)))

    return alerts


def get_value_unlocked_summary(year: Optional[int] = None) -> dict:
    """Get summary of value unlocked by Sentinel."""
    target_year = year or date.today().year

    with get_db() as conn:
        rows = conn.execute(
            """SELECT category, SUM(amount_saved) as total, COUNT(*) as count
               FROM value_unlocked
               WHERE strftime('%Y', date) = ?
               GROUP BY category""",
            (str(target_year),),
        ).fetchall()

        total = conn.execute(
            "SELECT COALESCE(SUM(amount_saved), 0) as total FROM value_unlocked WHERE strftime('%Y', date) = ?",
            (str(target_year),),
        ).fetchone()

    return {
        "year": target_year,
        "total_saved": total["total"],
        "by_category": [
            {"category": r["category"], "total": r["total"], "count": r["count"]}
            for r in rows
        ],
    }

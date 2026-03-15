import sqlite3
from pathlib import Path
from contextlib import contextmanager

from app.config import settings

DB_PATH = settings.data_dir / "sentinel.db"


def get_db_path() -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return DB_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database with the schema."""
    with get_db() as conn:
        conn.executescript(SCHEMA)


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('brokerage', 'crypto', 'checking', 'credit_card')),
    institution TEXT NOT NULL,
    last_import_date TEXT,
    plaid_account_id TEXT,
    plaid_item_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plaid_items (
    item_id TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    institution_name TEXT,
    cursor TEXT DEFAULT '',
    last_synced TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    asset TEXT NOT NULL,
    quantity REAL NOT NULL,
    current_value REAL,
    cost_basis_total REAL,
    unrealized_gain_loss REAL,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    asset TEXT NOT NULL,
    quantity REAL NOT NULL,
    cost_basis_per_unit REAL NOT NULL,
    acquisition_date TEXT NOT NULL,
    acquisition_method TEXT NOT NULL DEFAULT 'buy' CHECK(acquisition_method IN ('buy', 'transfer', 'gift')),
    sold_quantity REAL NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    date TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('buy', 'sell', 'dividend', 'fee', 'expense', 'income', 'transfer')),
    asset TEXT,
    quantity REAL,
    price_per_unit REAL,
    total_amount REAL NOT NULL,
    category TEXT,
    subcategory TEXT,
    description TEXT,
    tax_relevant INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('csv_import', 'email_parsed', 'manual', 'auto_fetch', 'plaid')),
    plaid_transaction_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER REFERENCES transactions(id),
    merchant TEXT NOT NULL,
    amount REAL NOT NULL,
    date TEXT NOT NULL,
    category TEXT,
    is_recurring INTEGER NOT NULL DEFAULT 0,
    is_subscription INTEGER NOT NULL DEFAULT 0,
    tax_deductible INTEGER NOT NULL DEFAULT 0,
    deduction_category TEXT,
    receipt_email_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant TEXT NOT NULL,
    amount REAL NOT NULL,
    frequency TEXT NOT NULL CHECK(frequency IN ('monthly', 'annual', 'quarterly', 'weekly')),
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'cancelled', 'price_increased')),
    annual_cost REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS email_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_message_id TEXT UNIQUE NOT NULL,
    merchant TEXT NOT NULL,
    amount REAL NOT NULL,
    date TEXT NOT NULL,
    items TEXT,  -- JSON array
    return_window_days INTEGER DEFAULT 30,
    return_deadline TEXT,
    warranty_expiration TEXT,
    price_watch_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS price_watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_receipt_id INTEGER REFERENCES email_receipts(id),
    item_description TEXT NOT NULL,
    purchase_price REAL NOT NULL,
    purchase_merchant TEXT NOT NULL,
    return_window_deadline TEXT,
    current_lowest_price REAL,
    lowest_price_source TEXT,
    last_checked TEXT,
    alert_triggered INTEGER NOT NULL DEFAULT 0,
    savings_potential REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS wishlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_description TEXT NOT NULL,
    item_url TEXT,
    target_price REAL,
    added_date TEXT DEFAULT (date('now')),
    source TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual', 'email', 'bookmarklet')),
    current_price REAL,
    current_price_source TEXT,
    price_history TEXT,  -- JSON array
    lowest_price_ever REAL,
    lowest_price_date TEXT,
    alert_triggered INTEGER NOT NULL DEFAULT 0,
    priority INTEGER DEFAULT 3,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS value_unlocked (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL DEFAULT (date('now')),
    category TEXT NOT NULL CHECK(category IN ('tax_harvest', 'price_drop', 'subscription_cut', 'bill_negotiation', 'lot_aging', 'other')),
    description TEXT NOT NULL,
    amount_saved REAL NOT NULL,
    source_module TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tax_projections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tax_year INTEGER NOT NULL,
    filing_status TEXT NOT NULL DEFAULT 'single',
    estimated_income REAL NOT NULL DEFAULT 0,
    realized_short_term_gains REAL NOT NULL DEFAULT 0,
    realized_long_term_gains REAL NOT NULL DEFAULT 0,
    realized_losses REAL NOT NULL DEFAULT 0,
    loss_carryforward REAL NOT NULL DEFAULT 0,
    estimated_liability REAL,
    effective_rate REAL,
    quarterly_payments TEXT,  -- JSON array
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recurring_bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant TEXT NOT NULL,
    amount REAL NOT NULL,
    frequency TEXT NOT NULL,
    next_due_date TEXT,
    category TEXT,
    price_history TEXT,  -- JSON array
    price_change_detected INTEGER NOT NULL DEFAULT 0,
    competitor_rates TEXT,  -- JSON
    created_at TEXT DEFAULT (datetime('now'))
);
"""

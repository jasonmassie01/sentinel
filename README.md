# SENTINEL

**Personal Financial Intelligence System**

Sentinel is a self-hosted, privacy-first financial intelligence platform that unifies investments, expenses, and tax strategy into a single operational dashboard. It replaces Koinly, Mint, Empower, and every other fragmented tool with one system that doesn't just show what happened — it tells you what to do next.

This is not a budgeting app. It's a financial edge — a personal Bloomberg terminal that monitors, analyzes, alerts, and optimizes across every dollar that moves through your life.

![License](https://img.shields.io/badge/license-AGPL--3.0-blue)
![Python](https://img.shields.io/badge/python-3.12-blue)
![React](https://img.shields.io/badge/react-19-blue)
![Docker](https://img.shields.io/badge/docker-compose-blue)

---

## Key Features

### Command Center
- Unified net worth across all accounts (brokerage, crypto, checking, credit card)
- Live BTC price ticker with 24h change
- Account cards with cost basis, unrealized P&L, and allocation percentages
- Asset class breakdown (equities, BTC, cash)
- Alert feed from all modules

### Tax Brain
- **Cross-asset lot tracking** — every tax lot across Fidelity, Schwab, and on-chain BTC in one view
- **Lot-aging countdown timers** — alerts at 30/14/7 days before the long-term capital gains threshold, with estimated tax savings
- **Tax-loss harvesting engine** — scans all accounts for harvestable losses with wash sale detection across accounts
- **Capital gains bracket optimizer** — shows remaining room in your current bracket before the next marginal rate
- **Lot selection modeler** — compare FIFO vs HIFO vs LIFO for any prospective sale, side by side
- **Quarterly tax estimates** — with safe harbor calculations (100%/110% of prior year)
- **Form 8949 / Schedule D CSV export** — ready for your CPA

### Expense Engine
- Transaction import from Fidelity credit card, bank CSVs
- Auto-categorization by merchant name (40+ merchant rules built in)
- Spending by category with trend visualization
- Recurring expense detection

### Email Intelligence
- **Gmail integration** (OAuth2, fully local token storage)
- **Receipt auto-parser** — two-tier: merchant templates for major retailers + local LLM via Ollama
- **Price drop / return window alerts** — monitors prices after purchase, alerts before return window closes
- **Wishlist / deal monitor** — track items with target prices, get alerted on drops
- **Subscription detection** — finds recurring charges, tracks price creep, calculates annual cost
- **Warranty tracker** — alerts before warranty expiration

### Scenario Lab
- **"What if I sell?" simulator** — model any sale with FIFO/HIFO/LIFO comparison and bracket impact
- **"What if I cut this expense?" projector** — shows annual savings, pre-tax cost, hours of work, and 1/5/10yr investment growth
- **Tax year planner** — full-year model with standard deduction, LTCG rates, NIIT, bracket visualization
- **DCA analyzer** — compare your actual cost basis against lump sum

### Smart Alerts
- Unified alert feed from all modules (lot aging, price drops, subscription increases, tax actions, bills)
- Severity ranking (urgent / warning / info)
- **Value Unlocked** — tracks cumulative savings from Sentinel's alerts (tax harvesting, price drops, subscription cuts)

---

## Design Principles

- **Signal over noise.** Every screen answers "What should I do?" not just "What happened?"
- **Tax alpha is real alpha.** A dollar saved in taxes is the highest-conviction return you'll ever get
- **Email is the API.** Gmail is the richest underutilized data source in personal finance
- **Local-first, privacy-default.** All data stays on your machine. API keys connect directly — no third-party aggregators
- **One brain, not five apps.** Every module feeds every other module

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12 (FastAPI) |
| Frontend | React 19 (Vite + TypeScript) |
| Database | SQLite (local-first, single-user) |
| Bank/Brokerage | Plaid API (Link + transaction sync) |
| Crypto | Coinbase API (v2, HMAC auth) |
| BTC Price | CoinGecko API (public, no key) |
| On-chain Data | Mempool.space / Blockstream.info API |
| Email Parsing | Local LLM via Ollama (Llama 3.1 8B) |
| Email | Gmail API (OAuth2, local tokens) |
| Deployment | Docker Compose |

---

## Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Git

### 1. Clone & Configure

```bash
git clone https://github.com/jasonmassie01/sentinel.git
cd sentinel
cp .env.example .env
```

Edit `.env` with your API keys (all optional — add what you have):

```bash
# Plaid — auto-import bank/brokerage/credit card accounts
# Get keys at https://dashboard.plaid.com
SENTINEL_PLAID_CLIENT_ID=your_client_id
SENTINEL_PLAID_SECRET=your_secret
SENTINEL_PLAID_ENV=sandbox   # sandbox, development, or production

# Coinbase — auto-sync crypto holdings & transactions
# Create API key at coinbase.com/settings/api
# Permissions needed: wallet:accounts:read, wallet:transactions:read
SENTINEL_COINBASE_API_KEY=your_key
SENTINEL_COINBASE_API_SECRET=your_secret
```

### 2. Launch

```bash
docker compose up --build
```

### 3. Open

- **Dashboard:** [http://localhost:5173](http://localhost:5173)
- **API docs:** [http://localhost:8001/docs](http://localhost:8001/docs)

### What Happens Automatically

Once running, everything syncs on its own:

| Source | What | How |
|--------|------|-----|
| **Plaid** | Bank accounts, credit cards, brokerage holdings, transactions | Click "Link Account" on the dashboard, connect via Plaid Link. Auto-syncs every 4 hours. |
| **Coinbase** | Crypto wallets, balances, BTC transactions | Set API keys in `.env`. Click "Sync Now" on dashboard or auto-syncs every 4 hours. |
| **On-chain BTC** | Any BTC address balance | Enter address on dashboard. Auto-refreshes every 4 hours via Mempool.space. |
| **BTC Price** | Live price + 24h change | CoinGecko, no key needed. Refreshes on every page load. |

### Without Docker

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

**Frontend:**
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

---

## API Reference

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |
| GET | `/api/accounts` | List all accounts |
| POST | `/api/accounts` | Create account |
| POST | `/api/accounts/:id/import` | Import CSV |
| GET | `/api/portfolio/net-worth` | Net worth across all accounts |
| GET | `/api/portfolio/holdings` | All holdings |
| GET | `/api/portfolio/transactions` | Transaction history |

### Plaid

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plaid/status` | Plaid config status + linked items |
| POST | `/api/plaid/link-token` | Create Plaid Link token |
| POST | `/api/plaid/exchange-token` | Exchange public token |
| POST | `/api/plaid/sync` | Sync all Plaid data |

### Coinbase

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/coinbase/status` | Coinbase config status |
| GET | `/api/coinbase/accounts` | List Coinbase wallets |
| POST | `/api/coinbase/sync` | Sync accounts, holdings, transactions |

### BTC

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/btc/price` | Live BTC price |
| GET | `/api/btc/address/:addr` | On-chain balance + UTXOs |
| GET | `/api/btc/fees` | Mempool fee estimates |
| POST | `/api/btc/track-address` | Track a BTC address |

### Tax Brain

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tax/lots` | All tax lots with aging data |
| POST | `/api/tax/lots` | Create a tax lot manually |
| GET | `/api/tax/lot-aging-alerts` | Lots approaching LT threshold |
| GET | `/api/tax/harvest-candidates` | Tax-loss harvesting opportunities |
| GET | `/api/tax/bracket-position` | Current tax bracket position |
| GET | `/api/tax/model-sale` | Model a sale (single method) |
| GET | `/api/tax/compare-methods` | Compare FIFO/HIFO/LIFO |
| GET | `/api/tax/ytd-realized` | YTD realized gains/losses |
| GET | `/api/tax/quarterly-estimates` | Estimated quarterly payments |
| GET | `/api/tax/form-8949` | Export Form 8949 CSV |

### Email Intelligence

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/email/status` | Gmail connection status |
| POST | `/api/email/setup` | Configure Gmail credentials |
| POST | `/api/email/scan-receipts` | Scan inbox for receipts |
| GET | `/api/email/subscriptions` | Detected subscriptions |
| POST | `/api/email/detect-subscriptions` | Run subscription detection |
| GET | `/api/email/price-drop-alerts` | Price drop alerts |
| GET/POST | `/api/email/wishlist` | Wishlist management |

### Scenario Lab

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scenarios/simulate-sale` | Simulate asset sale |
| GET | `/api/scenarios/cut-expense` | Model expense elimination |
| GET | `/api/scenarios/tax-year-model` | Full tax year model |
| GET | `/api/scenarios/dca-analysis` | DCA performance analysis |

### Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/alerts` | All active alerts |
| GET | `/api/alerts/value-unlocked` | Sentinel savings summary |

Full interactive API docs available at `/docs` when the backend is running.

---

## Supported CSV Formats

| Institution | Type | Notes |
|------------|------|-------|
| Fidelity | Brokerage positions | Symbol, Quantity, Current Value, Cost Basis |
| Fidelity | Brokerage transactions | Run Date, Action, Symbol, Amount |
| Fidelity | Credit card | Date, Transaction, Name, Amount |
| Schwab | Brokerage positions | Symbol, Market Value, Cost Basis |
| Schwab | Brokerage transactions | Date, Action, Symbol, Amount |
| Generic bank | Checking/savings | Date, Description, Amount (or Debit/Credit) |

---

## Architecture

```
sentinel/
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, router registration
│   │   ├── config.py            # Environment-driven settings
│   │   ├── database.py          # SQLite with 13-table schema
│   │   ├── api/                 # REST endpoints (11 routers, 45+ endpoints)
│   │   ├── services/            # Business logic engines
│   │   │   ├── tax_engine.py    # Lot tracking, harvesting, brackets
│   │   │   ├── btc_service.py   # Price feeds, on-chain lookups
│   │   │   ├── coinbase_service.py  # Coinbase API sync
│   │   │   ├── plaid_service.py # Plaid Link + transaction sync
│   │   │   ├── net_worth_service.py
│   │   │   ├── import_service.py
│   │   │   ├── gmail_service.py
│   │   │   ├── receipt_parser.py
│   │   │   ├── subscription_detector.py
│   │   │   ├── price_monitor.py
│   │   │   ├── scenario_engine.py
│   │   │   └── alert_engine.py
│   │   └── parsers/
│   │       └── csv_parser.py    # Fidelity, Schwab, bank parsers
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/                 # TypeScript API client + types
│       ├── components/          # Layout, formatting utilities
│       └── pages/               # 6 pages matching spec modules
└── data/                        # SQLite database (Docker volume)
```

---

## Non-Goals

- No multi-user support — single-user, local-only
- No mobile app — desktop browser at localhost
- No DeFi/altcoin tracking — BTC only for crypto
- No automated trading — Sentinel recommends, you execute
- No cloud hosting — runs on your machine, period

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[AGPL-3.0](LICENSE) — Prevents SaaS forks while keeping community contributions open.

---

*Built by [Jason Massie](https://github.com/jasonmassie01) + Claude*

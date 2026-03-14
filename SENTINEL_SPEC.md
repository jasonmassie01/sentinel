# SENTINEL — Personal Financial Intelligence System

## Product Specification v0.2

**Author:** Jason + Claude
**Date:** March 14, 2026
**Status:** Draft — Ideation & Spec Phase
**License:** AGPL-3.0 (prevents SaaS forks while keeping community contributions open)

---

## 1. Vision

Sentinel is a self-hosted personal financial intelligence system that unifies investments, expenses, and tax strategy into a single operational dashboard. It replaces Koinly, Mint, and every other fragmented tool with one system that doesn't just show what happened — it tells you what to do next.

This is not a budgeting app. It's a financial edge — a personal Bloomberg terminal that monitors, analyzes, alerts, and optimizes across every dollar that moves through your life.

### 1.1 Design Principles

- **Signal over noise.** Every screen answers: "What should I do?" not just "What happened?"
- **Portfolio-first, asset-neutral.** Default views show dollars, inflation-adjusted returns, and hours of work. BTC/sats framing available as an optional toggle for holders.
- **Tax alpha is real alpha.** A dollar saved in taxes is the highest-conviction return you'll ever get. The system should surface every legal edge.
- **Email is the API.** Gmail is the richest, most underutilized data source in personal finance. Receipts, bills, subscriptions, confirmations — it all flows through the inbox.
- **Local-first, privacy-default.** All data stays on your machine. No third-party aggregators. No Plaid. CSV imports, local browser automation, and public blockchain APIs only.
- **One brain, not five apps.** Every module feeds every other module. Expense data informs tax projections. Tax brackets inform harvest decisions. Email receipts auto-populate expenses.
- **Zero friction ingestion.** Manual CSV downloads kill retention. Automate everything possible locally (headless browser, email polling, on-chain lookups) so the system stays current without constant effort.

### 1.2 What This Replaces

| Tool | What it did | What Sentinel does better |
|------|------------|--------------------------|
| Koinly | BTC tax reporting | Unified cross-asset tax optimization with lot-aging alerts and bracket modeling |
| Mint/Monarch | Expense tracking | Tax-aware categorization + opportunity cost framing + anomaly detection |
| Empower | Net worth dashboard | Real-time cross-asset view with forward-looking signals, not just backward reporting |
| TurboTax estimates | Quarterly tax projection | Live estimated liability updated with every realized gain/loss |
| Spreadsheets | Manual tracking | Automated imports, live BTC price, and intelligent alerts |

---

## 2. Architecture

### 2.1 Tech Stack

- **Backend:** Python (FastAPI)
- **Frontend:** React (Vite + TypeScript)
- **Database:** SQLite (local-first, single-user, portable) with optional SQLCipher encryption
- **Task Runner:** APScheduler (upgrade to Celery only if scraper/alert volume demands it)
- **Email Parsing:** Local LLM via Ollama (e.g., Llama 3.1 8B) — fully private, no data leaves your machine. Merchant templates as fallback for common retailers.
- **CSV Automation:** Playwright headless browser — auto-login to Fidelity/Schwab, download CSVs on schedule, ingest automatically. Encrypted local credential storage. Manual CSV upload always available as fallback.
- **Price Monitoring:** Local Playwright scraper for multi-retailer price checks (Amazon, Best Buy, Walmart, etc.) + CamelCamelCamel for Amazon price history. No cloud APIs required.
- **BTC Price Feed:** Public API (CoinGecko / Mempool.space)
- **On-chain Data:** Mempool.space / Blockstream.info API (no API key required)
- **Email:** Gmail API (OAuth2, local token storage)
- **Deployment:** Docker Compose single-command install (`docker compose up`). Containers: FastAPI backend, React frontend, Ollama (optional), SQLite volume mount.
- **Hosting:** Fully local — runs on localhost

### 2.2 Data Sources

| Source | Method | Data |
|--------|--------|------|
| Fidelity Brokerage | CSV import | Holdings, transactions, cost basis |
| Schwab Brokerage | CSV/OFX import | Holdings, transactions, cost basis |
| Fidelity Credit Card | CSV import | All card transactions |
| Bank (ACH) | CSV import | ACH debits/credits |
| On-chain BTC | Public address lookup | UTXOs, balances, tx history |
| Gmail | API (OAuth2) | Receipts, bills, subscriptions, confirmations |
| BTC Price | Public API (live) | Real-time and historical pricing |
| CPI / Inflation Data | BLS API or static dataset | For inflation-adjusted comparisons |

### 2.3 Data Model (High-Level)

```
accounts
  ├── id, name, type (brokerage|crypto|checking|credit_card)
  ├── institution (fidelity|schwab|onchain|bank)
  └── last_import_date

holdings
  ├── account_id, asset, quantity, current_value
  └── cost_basis_total, unrealized_gain_loss

lots (tax lot tracking)
  ├── account_id, asset, quantity, cost_basis_per_unit
  ├── acquisition_date, acquisition_method (buy|transfer|gift)
  ├── is_long_term (computed: acquisition_date + 365 < today)
  └── long_term_threshold_date (computed)

transactions
  ├── account_id, date, type (buy|sell|dividend|fee|expense|income)
  ├── asset, quantity, price_per_unit, total_amount
  ├── category, subcategory, tax_relevant (bool)
  └── source (csv_import|email_parsed|manual)

expenses
  ├── transaction_id, merchant, amount, date
  ├── category, is_recurring, is_subscription
  ├── tax_deductible (bool), deduction_category
  ├── opportunity_cost (computed — portfolio-return default, optional BTC toggle)
  └── receipt_email_id (link to Gmail message)

subscriptions (derived from expenses + email)
  ├── merchant, amount, frequency (monthly|annual|quarterly)
  ├── first_seen, last_seen, price_history[]
  ├── status (active|cancelled|price_increased)
  └── annual_cost (computed)

email_receipts
  ├── gmail_message_id, merchant, amount, date
  ├── items[], return_window_days, return_deadline
  ├── warranty_expiration
  └── price_watch_active (bool)

price_watches (for purchased items in return window)
  ├── email_receipt_id, item_description, purchase_price
  ├── purchase_merchant, return_window_deadline
  ├── current_lowest_price, lowest_price_source (original store or other retailer)
  ├── last_checked
  ├── alert_triggered (bool)
  └── savings_potential

wishlist
  ├── id, item_description, item_url, target_price
  ├── added_date, source (manual|email|bookmarklet)
  ├── current_price, current_price_source
  ├── price_history[] (date, price, source)
  ├── lowest_price_ever, lowest_price_date
  ├── alert_triggered (bool)
  └── priority, notes

value_unlocked (tracks cumulative savings from Sentinel)
  ├── id, date, category (tax_harvest|price_drop|subscription_cut|bill_negotiation|lot_aging|other)
  ├── description, amount_saved
  └── source_module

tax_projections
  ├── tax_year, filing_status, estimated_income
  ├── realized_short_term_gains, realized_long_term_gains
  ├── realized_losses, loss_carryforward
  ├── estimated_liability, effective_rate
  └── quarterly_payment_schedule[]

recurring_bills
  ├── merchant, amount, frequency, next_due_date
  ├── category, price_history[]
  ├── price_change_detected (bool)
  └── competitor_rates (populated on trigger)
```

---

## 3. Module Specifications

---

### MODULE 1: Command Center (Dashboard)

**Purpose:** See everything at a glance. Net worth, account balances, BTC price, active alerts, and key metrics — one screen, updated live.

#### Features

**1.1 Unified Net Worth**
- Total net worth across all accounts (Fidelity + Schwab + on-chain BTC + checking)
- Breakdown by account, by asset class (equities, BTC, cash, other)
- Historical net worth chart (daily granularity from import history)
- Net worth change: today, 7d, 30d, YTD, 1Y

**1.2 Account Cards**
- Per-account summary: current value, cost basis, unrealized P&L, % allocation
- Fidelity brokerage, Schwab brokerage, on-chain BTC, Fidelity credit card, bank/checking
- Quick-glance status: last import date, any alerts pending

**1.3 Asset Ticker**
- Live price feeds for BTC and any tracked assets
- BTC holdings in both BTC and USD with unrealized gain/loss
- Configurable — show what matters, hide what doesn't

**1.4 Alert Feed**
- Chronological feed of active alerts from all modules
- Types: price drop detected, lot aging milestone, subscription increase, bill due, tax action recommended
- Dismiss, snooze, or act on each alert

**1.5 Key Metrics Bar**
- YTD realized gains/losses (short-term + long-term)
- Estimated tax liability (current projection)
- Monthly burn rate (average of last 3 months)
- Savings rate (income - expenses / income)

**1.6 Value Unlocked Widget**
- Running total of money saved by Sentinel this month/YTD
- Breakdown by source: tax harvesting, price drop arbitrage, subscription cuts, bill negotiations, lot-aging saves
- "Sentinel has saved you $X this year" — the system's own ROI tracker

---

### MODULE 2: Tax Brain

**Purpose:** The highest-dollar-value module. Tracks cost basis across all assets, models tax liability in real-time, and surfaces actionable moves that save money.

#### Features

**2.1 Cross-Asset Lot Tracker**
- Every tax lot across Fidelity, Schwab, and on-chain BTC in one view
- Per-lot: asset, quantity, cost basis, acquisition date, current value, unrealized gain/loss
- Long-term vs. short-term classification with countdown to threshold
- Sort/filter by: account, asset, gain/loss, days to long-term

**2.2 Lot-Aging Countdown Timers** ⭐
- Highlight lots approaching the 1-year long-term capital gains threshold
- Alert at 30, 14, and 7 days before crossover
- Show tax savings of waiting: "Holding 14 more days saves $X at your marginal rate"
- Visual timeline of upcoming lot transitions

**2.3 Tax-Loss Harvesting Engine**
- Scan all accounts for unrealized losses
- Rank by harvest potential: "Selling this lot realizes $X in losses, offsetting $Y in gains"
- **Wash sale buffer zones:** Don't just flag wash sales — build a 30-day chronological map. Before recommending a harvest, verify no substantially identical purchase in the prior 30 days across ALL accounts. After harvesting, lock out buy recommendations for that asset for 30 days.
- Note: crypto wash sale rules may now apply post-2025 legislation — track evolving guidance via annual config update
- Cross-account awareness: harvesting in Schwab while monitoring Fidelity and on-chain

**2.4 Capital Gains Bracket Optimizer**
- Model current tax year: W-2 income + realized gains + projected gains = estimated AGI
- Show remaining room in current bracket before next marginal rate kicks in
- "You can realize $X more in long-term gains and stay in the 15% LTCG bracket"
- Model impact of prospective sales before executing
- **State tax awareness:** Configurable per-state. Texas = no state income tax, so all optimization focuses on federal AGI and LTCG brackets. System adapts if you move.

**2.5 Estimated Quarterly Tax Calculator**
- Based on YTD realized gains, dividends, and income
- Project Q1-Q4 estimated payments
- **Underpayment safe harbor toggle:** Auto-calculate whether you've met the 100% of prior year (or 110% if AGI > $150K) threshold to avoid penalties
- Update dynamically as new transactions are imported

**2.6 Lot Selection Modeler** ⭐
- When you need to sell any asset: "Which lot should I sell?"
- Compare FIFO vs. HIFO vs. specific identification for any given sale amount
- Show tax impact of each option side by side
- Factor in lot-aging: "If you wait 18 days, this lot goes long-term, saving $X"
- Works across all accounts — stocks, ETFs, and BTC lots unified

**2.7 Cost Basis Methods**
- Support FIFO, LIFO, HIFO, and Specific Identification
- Per-wallet/per-account tracking (IRS requirement as of 2025)
- Allow user to compare methods side-by-side for any prospective sale
- Lock method per asset per year once first disposal is made (IRS consistency rule)

**2.8 Tax Event Log & Export**
- Chronological record of all realized gains/losses
- Per event: date, asset, quantity, proceeds, cost basis, gain/loss, short/long-term
- Running YTD totals
- **Auto-generate IRS Form 8949 / Schedule D CSV** — ready for CPA or direct filing
- **1099-DA import:** Starting 2026, brokers report digital asset transactions. Import and reconcile against your own records to catch discrepancies.
- Exportable in multiple formats: CSV, Form 8949, TurboTax-compatible

---

### MODULE 3: Expense Engine

**Purpose:** Categorize, analyze, and optimize every dollar going out. Not just "where did my money go" but "what should I do about it."

#### Features

**3.1 Transaction Import & Categorization**
- Fidelity credit card CSV import
- Bank/ACH CSV import
- Auto-categorization by merchant name (rules engine + learning)
- Manual override with category persistence per merchant
- Categories: housing, food/grocery, dining, transport, subscriptions, utilities, health, entertainment, shopping, travel, fees, taxes, other
- Tax-relevance flag per category

**3.2 Spending Dashboard**
- Monthly spending by category (bar chart)
- Trend lines: 3-month, 6-month, 12-month per category
- Month-over-month change with anomaly highlighting
- "Your dining spending is up 34% this month vs. 3-month average"

**3.3 Inflation-Adjusted Spending Comparison** ⭐
- Pull CPI data (BLS API or static dataset, updated periodically)
- Show real vs. nominal spending change per category
- "Grocery spending is up 8% nominally but only 1.2% in real terms — this is mostly inflation, not behavior change"
- Annual comparison: real purchasing power of your spending over time

**3.4 Opportunity Cost Engine** ⭐
- Every expense displayed with a secondary frame: inflation-adjusted dollars, hours of work, or projected portfolio-return equivalent
- Default: "This $150/month subscription, invested at your portfolio's historical return rate, would be worth $X in 5 years"
- **Optional BTC toggle:** For holders, show sats-equivalent at current price
- Configurable projection timeframes and assumed appreciation rates
- Not meant to guilt — meant to make the tradeoff tangible and conscious

**3.5 "What Did This Actually Cost Me?" Calculator** ⭐
- Any expense, viewed through multiple lenses:
  - **Pre-tax dollars:** At your marginal rate, you earned $X before tax to pay for this $Y item
  - **Hours of work:** At your effective hourly rate ($annual_salary / 2080), this cost N hours
  - **Investment opportunity cost:** At your portfolio's historical return over 1/5/10 year horizons (optional BTC toggle)
  - **Real cost:** Inflation-adjusted if comparing to a past purchase
- Accessible on any transaction or as a standalone calculator

**3.6 Recurring Expense Calendar**
- Every subscription, bill, and recurring charge plotted on a monthly timeline
- Aggregate: total monthly recurring obligations
- Cash flow visualization: income deposits vs. recurring outflows by date
- Identify cash flow crunch periods (multiple large bills in same week)

**3.7 Category Budgets (Lightweight)**
- Optional per-category spending targets (not envelope budgeting — just awareness thresholds)
- Alert when approaching or exceeding threshold
- No guilt, no gamification — just signal

---

### MODULE 4: Email Intelligence (Gmail Integration)

**Purpose:** Gmail is the richest underutilized data source in personal finance. Parse it for receipts, bills, subscriptions, price changes, and warranty expirations.

#### Features

**4.1 Gmail Connection**
- OAuth2 authentication (local token storage, no third-party)
- Periodic polling (configurable: every 15min, hourly, daily)
- Message parsing via **local LLM (Ollama)** with strict JSON schema extraction. Feed raw email HTML → get structured data: merchant, items, prices, total, date, return policy. Per-merchant templates as fallback for top retailers. All processing local — no data leaves your machine.

**4.2 Receipt Auto-Parser**
- Detect purchase confirmation emails (Amazon, Best Buy, Target, etc.)
- Extract: merchant, items, prices, order total, order number, date
- Auto-create expense transactions from parsed receipts
- Link email_receipt → expense record for audit trail
- Deduplicate against credit card CSV imports (match by merchant + amount + date)

**4.3 Price Drop / Return Window Alerts** ⭐
- For each parsed receipt, determine return window (default 30 days, configurable per merchant)
- Monitor item prices at **both the original store AND across the internet** via local Playwright scraper (Amazon, Best Buy, Walmart, Target, etc.) + CamelCamelCamel for Amazon price history. No cloud APIs — all scraping runs locally on your schedule.
- Alert: "The $89 item you bought from Amazon 12 days ago is now $62 on Amazon — you have 18 days left to return and rebuy"
- Also alert: "That same item is $54 at Best Buy right now — return the Amazon order and buy from Best Buy instead"
- **Deal Arbitrage Agent:** Calculate net savings including return shipping costs, restocking fees, and price-match policy differences
- Return window countdown: visual timeline per recent purchase
- Track merchant return policies (auto-populate known policies, manual override)

**4.4 Wishlist / Deal Monitor** ⭐
- Maintain a personal wishlist of items you want but aren't ready to buy yet
- Add items via: manual entry (URL + target price), email parse (forward yourself a product link), or browser bookmarklet (future)
- Monitor prices across multiple retailers for each wishlist item
- Set target price per item: "Alert me when this drops below $X"
- Historical price chart per item (track price over time to identify real deals vs. fake markdowns)
- Alert: "The [item] on your wishlist just dropped from $299 to $189 — lowest price in 90 days"
- Seasonal deal awareness: flag items likely to go on sale soon (Black Friday, Prime Day, etc.) based on historical patterns
- Priority ranking: sort wishlist by "closest to target price" or "biggest current discount"

**4.5 Subscription Detection & Creep Monitoring** ⭐
- Scan for recurring charges from same merchant at regular intervals
- Build subscription registry with price history
- Alert on price increases: "Spotify increased from $10.99 to $13.99 — $36/year more"
- Alert on forgotten subscriptions: "You're still paying $14.99/month for [service] — last login was 6 months ago" (if detectable)
- Annual subscription cost total: "You spend $2,847/year on subscriptions"

**4.6 Warranty Tracker**
- Parse warranty information from purchase confirmations
- Default warranty period by product category if not specified
- Alert before warranty expiration: "Your laptop warranty expires in 30 days — any issues to file?"
- Store proof-of-purchase email links for easy claim filing

**4.7 Bill Change Detection**
- Monitor recurring bill confirmation emails (utilities, insurance, telecom)
- Detect amount changes between periods
- Alert: "Your Xfinity bill increased $8/month — up $14/month over the past 18 months"
- Feed into bill negotiation triggers (see Module 6)

---

### MODULE 5: Scenario Lab

**Purpose:** "What if?" modeling. Before making any financial move, simulate the impact across your entire financial picture.

#### Features

**5.1 "What If I Sell?" Simulator**
- Select any holding or lot → model the sale
- Show: proceeds, cost basis, gain/loss, tax impact at current marginal rate
- Compare lot selection methods (FIFO vs. HIFO vs. specific lot)
- Show impact on YTD tax picture and estimated quarterly payment
- For BTC: show lot-aging status and savings from waiting

**5.2 "What If I Cut This Expense?" Projector**
- Select any recurring expense → model elimination
- Show: annual savings in dollars, BTC equivalent, and investment growth over 1/5/10 years
- Show tax impact if expense was pre-tax/deductible
- Compare: "Cutting this $100/month = $X in BTC over 5 years at Y% assumed growth"

**5.3 Tax Year Planner**
- Full-year tax model: income + realized gains + projected gains + deductions
- Slider-based: "What if I realize $X more in gains this year?"
- Bracket visualization: see exactly where you sit and how much room remains
- Optimize: recommended actions to minimize current-year liability

**5.4 DCA Analyzer**
- Historical analysis: your actual cost basis for any asset vs. lump sum vs. different DCA schedules
- Not to second-guess — to calibrate future strategy
- "Your actual BTC DCA has yielded a cost basis of $X/BTC. Weekly DCA over the same period would have been $Y/BTC."
- Works for any holding, not just BTC

---

### MODULE 6: Smart Alerts & Triggers

**Purpose:** Proactive intelligence. The system should tell you things before you think to ask.

#### Features

**6.1 Credit Card Reward Optimization** ⭐
- Track spending by category from Fidelity card (2% flat cash back)
- Periodically model: "Based on your spending pattern, Card X would earn $Y more per year"
- Factor in: annual fees, sign-up bonuses, category multipliers vs. your actual category mix
- Not about churning — about ensuring your primary card is still optimal for your spending

**6.2 Tax + Bill Calendar with Cash Flow Projection** ⭐
- Unified calendar: estimated tax payments, property tax, insurance premiums, annual subscriptions, large known expenses
- Overlay against projected cash balance (checking account)
- 30/60/90 day forward look: "You have $X due in the next 30 days against $Y projected balance"
- Flag liquidity crunches before they happen

**6.3 Bill Negotiation Triggers** ⭐
- When bill change detection (Module 4.6) flags a price increase
- Surface competitive rates: "Your Xfinity bill is now $89/month. T-Mobile Home Internet is $50/month in your area"
- Track cumulative increase over time to quantify urgency
- Provide negotiation talking points (optional: template scripts)

**6.4 UTXO Consolidation Alerts (BTC-Specific)**
- Monitor mempool fee rates via Mempool.space API
- When fees drop below threshold (configurable, e.g., < 5 sat/vB), alert:
  "Network fees are low — good time to consolidate your N small UTXOs to save on future tx fees"
- Show estimated consolidation cost at current fee rate

**6.5 Annual Financial Health Check Report** ⭐
- Auto-generated end-of-year report:
  - Net worth change (absolute + %)
  - Effective tax rate (taxes paid / gross income)
  - Biggest expense categories and YoY changes (inflation-adjusted)
  - Investment performance by account and asset class
  - Total fees paid across all accounts
  - **Value Unlocked summary:** Money saved by Sentinel alerts (price drops caught, taxes optimized, subscriptions cancelled, bills negotiated)
  - **Projected net worth:** Conservative/moderate/aggressive scenarios based on portfolio return + inflation
  - Key ratios: savings rate, expense-to-income, recurring obligations as % of income
- Exportable as PDF

---

## 4. Data Flow Architecture

```
                    ┌─────────────────────┐
                    │     Gmail API        │
                    │  (OAuth2, polling)   │
                    └──────────┬──────────┘
                               │
                               ▼
┌──────────────┐    ┌─────────────────────┐    ┌──────────────┐
│  CSV Imports  │───▶│   PYTHON BACKEND    │◀───│ Public APIs  │
│  (manual or   │    │     (FastAPI)       │    │ (Mempool,    │
│   Playwright  │    │                     │    │  CoinGecko,  │
│   auto-fetch) │    │  ┌───────────────┐  │    │  BLS CPI)    │
└──────────────┘    │  │ Ollama LLM    │  │    └──────────────┘
                    │  │ Receipt Parser │  │
┌──────────────┐    │  │ Tax Engine     │  │    ┌──────────────┐
│  Playwright   │───▶│  │ Alert Engine   │  │◀───│ Retailer     │
│  Price Scraper│    │  │ Categorizer    │  │    │ Scraping     │
│  (local)      │    │  │ Scenario Model │  │    │ (Playwright) │
└──────────────┘    │  └───────┬───────┘  │    └──────────────┘
                    │          │          │
                    │    ┌─────▼─────┐    │
                    │    │  SQLite    │    │
                    │    │ (SQLCipher)│    │
                    │    └───────────┘    │
                    └──────────┬──────────┘
                               │
                          REST API
                               │
                               ▼
                    ┌─────────────────────┐
                    │   REACT FRONTEND    │
                    │   (Vite + TS)       │
                    │                     │
                    │  Dashboard          │
                    │  Tax Brain          │
                    │  Expense Engine     │
                    │  Email Intelligence │
                    │  Scenario Lab       │
                    │  Alert Center       │
                    └─────────────────────┘

Deployment: docker compose up
┌─────────────────────────────────┐
│  Docker Compose                 │
│  ├── sentinel-backend (FastAPI) │
│  ├── sentinel-frontend (React)  │
│  ├── ollama (local LLM)        │
│  └── sqlite volume mount       │
└─────────────────────────────────┘
```

---

## 5. Build Priority & Phasing

### Phase 0: Skeleton (1-2 days)
- Docker Compose stack: FastAPI backend, React frontend, Ollama (optional), SQLite volume
- `docker compose up` → blank dashboard rendering at localhost
- Project structure, CI scaffolding, basic API health check
- **Deliverable:** Running app shell — every subsequent phase has a home

### Phase 1: Foundation + Command Center
- SQLite schema + data model
- CSV import pipeline (Fidelity brokerage, Schwab, Fidelity card, bank)
- Playwright auto-fetch stub (manual CSV upload as primary, auto-download as stretch)
- On-chain BTC balance lookup (public address)
- Live BTC price feed
- React dashboard: net worth, account cards, asset ticker, key metrics, Value Unlocked widget
- **Deliverable:** See everything in one place — something you open every morning

### Phase 2: Tax Brain (Core)
- Tax lot tracking engine (all accounts — stocks, ETFs, BTC)
- Cost basis methods: FIFO, HIFO, specific ID with per-account tracking
- Lot-aging countdown timers with 30/14/7-day alerts
- Wash sale buffer zones (30-day look-back and look-forward across all accounts)
- YTD realized gains/losses tracker
- Estimated quarterly tax calculator with safe harbor toggle
- Capital gains bracket optimizer (federal-focused, Texas = no state income tax)
- Form 8949 / Schedule D CSV export
- **Deliverable:** Know your tax position at all times — this is where it starts paying for itself

### Phase 3: Expense Engine
- Transaction categorization (auto + manual rules engine)
- Spending dashboard with trends and anomaly detection
- Recurring expense identification
- Inflation-adjusted comparisons (CPI data)
- Opportunity cost engine (portfolio-return default, optional BTC toggle)
- "What did this actually cost me?" calculator
- **Deliverable:** Understand and optimize outflows

### Phase 4: Email Intelligence
- Gmail OAuth2 connection
- Receipt parser via Ollama (local LLM) with merchant template fallbacks
- Price drop monitoring + return window alerts (local Playwright scraper, internet-wide)
- Wishlist / deal monitor with multi-retailer tracking
- Subscription detection + creep monitoring
- Warranty tracker
- Bill change detection
- **Deliverable:** Your inbox and wishlist work for you

### Phase 5: Scenario Lab + Smart Alerts
- "What if I sell?" simulator with lot comparison
- Tax year planner with bracket visualization
- Credit card reward optimization
- Tax + bill calendar with cash flow projection
- Bill negotiation triggers
- UTXO consolidation alerts
- Lot selection modeler (all asset types)
- Annual health check report generator (PDF export)
- **Deliverable:** Forward-looking intelligence

---

## 6. Non-Goals (Explicitly Out of Scope)

- **No Plaid or bank API connections.** CSV import only. Privacy-first.
- **No multi-user support.** Single-user, local-only system.
- **No mobile app.** Desktop browser (localhost) is the interface.
- **No DeFi/altcoin tracking.** BTC only for crypto. This isn't a shitcoin portfolio tracker.
- **No automated trading or execution.** Sentinel recommends — you execute.
- **No cloud hosting.** Runs on your machine, period.
- **No envelope budgeting or debt payoff gamification.** This is intelligence, not a coach.

---

## 7. Open Questions

### Resolved
1. **Gmail parsing:** Local LLM via Ollama (Llama 3.1 8B or similar) with strict JSON schema prompting. Per-merchant templates as fallback for top retailers. ✅
2. **Price monitoring:** Local Playwright scraper for multi-retailer checks + CamelCamelCamel for Amazon price history. No cloud APIs. ✅
3. **Open source license:** AGPL-3.0. Prevents SaaS forks while allowing community contributions. ✅
4. **Project name:** Sentinel. Keeping it. ✅
5. **Tax law updates:** Annual JSON config file, updated manually or via community PRs. Attempting to automate tax code changes is error-prone. ✅
6. **State tax:** Texas = no state income tax. Federal-only optimization. Configurable if user moves. ✅
7. **Deployment:** Docker Compose single-command install. ✅

### Still Open
1. **BTC cost basis entry:** Hybrid approach (on-chain tx history + CoinGecko historical price at acquisition timestamp + manual CSV/override). Need to validate this workflow against real data.
2. **Fidelity card CSV format:** Need a real export to confirm column headers, merchant name format, and whether category codes are included.
3. **Fidelity/Schwab brokerage CSV formats:** Need sample exports to build parsers against real column structures.
4. **Ollama model selection:** Llama 3.1 8B is the starting assumption for receipt parsing. May need to benchmark against Mistral 7B or Phi-3 for speed vs. accuracy on structured extraction tasks.

---

## 8. Design Direction

- **Aesthetic:** Dark theme, terminal-inspired but refined. Think Bloomberg meets a well-designed CLI. Not a toy, not a bank.
- **Typography:** Monospace for numbers/data, clean sans-serif for labels. Every number should feel precise.
- **Color palette:** Dark background, muted grays for structure, green for gains, red for losses, amber/gold for BTC, bright accent for alerts/actions.
- **Layout:** Dense but organized. Information-rich screens for someone who wants to see it all. No wizard flows or hand-holding.
- **Charts:** Restrained. No gratuitous animations. Clean, readable, interactive on hover.

---

*This document is a living spec. It will evolve as we build.*

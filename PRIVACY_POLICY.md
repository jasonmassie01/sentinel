# Sentinel — Privacy Policy

**Effective Date:** March 15, 2026
**Last Updated:** March 15, 2026

---

## Overview

Sentinel is a self-hosted, open-source personal financial intelligence application. It runs entirely on your own machine. This privacy policy explains what data Sentinel accesses, how it is stored, and your rights regarding that data.

**The short version:** Your data never leaves your machine. We don't collect, sell, share, or transmit your financial data to anyone.

---

## 1. Data Controller

Jason Massie
jmass0729@gmail.com
https://github.com/jasonmassie01/sentinel

---

## 2. What Data Sentinel Accesses

When you connect financial accounts through Sentinel, the application accesses the following data via third-party APIs:

### From Plaid (bank accounts, brokerages, credit cards)
- Account names, types, and balances
- Transaction history (date, amount, merchant, category)
- Investment holdings (securities, quantities, values, cost basis)
- Account and routing numbers are **not** collected

### From Coinbase (cryptocurrency)
- Wallet names, currencies, and balances
- Transaction history (buys, sells, transfers)

### From Public APIs (no account required)
- Bitcoin price data (CoinGecko)
- On-chain Bitcoin address balances (Mempool.space, Blockstream.info)

### From Gmail (optional, with explicit consent)
- Receipt and bill emails (read-only access)
- No emails are modified, deleted, or sent

---

## 3. How Your Data Is Stored

- All data is stored in a **local SQLite database** on your machine
- The database file is located at `data/sentinel.db` within your Sentinel installation
- **No data is transmitted to any server, cloud service, or third party operated by Sentinel**
- No data is replicated, backed up, or synced to external services unless you configure that yourself
- API credentials (Plaid access tokens, Coinbase keys, Gmail tokens) are stored locally in environment variables and the local database

---

## 4. How Your Data Is Used

Sentinel uses your financial data solely to:
- Display account balances and net worth
- Track investment holdings and cost basis
- Calculate tax lots, capital gains, and tax-loss harvesting opportunities
- Categorize expenses and detect subscriptions
- Generate alerts (lot aging, price drops, bill reminders)
- Model financial scenarios (sale simulation, expense analysis)

Your data is **never** used for:
- Advertising or marketing
- Analytics or telemetry
- Training machine learning models
- Profiling or credit scoring
- Any purpose other than displaying information back to you

---

## 5. Data Sharing

**Sentinel does not share your data with anyone.**

The only external communication is between Sentinel (on your machine) and the financial API providers you explicitly connect:

| Provider | Data Flow | Purpose |
|----------|-----------|---------|
| Plaid | Sentinel requests account/transaction data | Bank, brokerage, credit card sync |
| Coinbase | Sentinel requests wallet/transaction data | Crypto account sync |
| CoinGecko | Sentinel requests BTC price | Price display |
| Mempool.space | Sentinel requests address balance | On-chain BTC tracking |
| Gmail (Google) | Sentinel reads receipt emails | Receipt parsing (optional) |

Each provider has its own privacy policy governing how they handle data on their end. Sentinel does not transmit your financial data to any other destination.

---

## 6. Data Retention

- Your data is retained for as long as you use Sentinel
- You can delete all data at any time by deleting the `sentinel.db` database file
- Uninstalling Sentinel and removing the project directory permanently removes all data
- There are no remote backups or copies to clean up — everything is local

---

## 7. Your Rights

Because Sentinel is self-hosted, you have complete control:

- **Access:** All your data is in `data/sentinel.db` on your machine — you can query it directly
- **Deletion:** Delete the database file to erase all data instantly
- **Portability:** The SQLite database is a standard format you can open with any SQLite tool
- **Revocation:** Disconnect any linked account at any time:
  - Plaid: Revoke access via Plaid's portal or the Sentinel dashboard
  - Coinbase: Delete or regenerate your API key at coinbase.com
  - Gmail: Revoke access at https://myaccount.google.com/permissions
- **Opt-out:** Each integration is optional — use only what you want

---

## 8. Security

- All API communication uses TLS 1.2 or higher (HTTPS)
- API credentials are stored as environment variables, never in source code
- The application binds to localhost only — it is not accessible from external networks
- Disk encryption (BitLocker/FileVault/LUKS) is recommended for the host machine
- See [SECURITY_POLICY.md](SECURITY_POLICY.md) for full security practices

---

## 9. Third-Party Services

Sentinel itself does not operate any servers or services. The third-party APIs accessed are governed by their own privacy policies:

- **Plaid:** https://plaid.com/legal/#end-user-privacy-policy
- **Coinbase:** https://www.coinbase.com/legal/privacy
- **Google (Gmail):** https://policies.google.com/privacy
- **CoinGecko:** https://www.coingecko.com/en/privacy
- **Mempool.space:** https://mempool.space/privacy-policy

---

## 10. Children's Privacy

Sentinel is not intended for use by individuals under the age of 18. We do not knowingly collect financial data from minors.

---

## 11. Changes to This Policy

Updates to this policy will be reflected in this document with an updated "Last Updated" date. As an open-source project, all changes are visible in the public Git history.

---

## 12. Contact

For privacy questions or concerns:

**Jason Massie**
jmass0729@gmail.com
https://github.com/jasonmassie01/sentinel

---

*This privacy policy applies to the Sentinel project: https://github.com/jasonmassie01/sentinel*

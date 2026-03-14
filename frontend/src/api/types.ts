export interface Account {
  id: number
  name: string
  type: 'brokerage' | 'crypto' | 'checking' | 'credit_card'
  institution: string
  last_import_date: string | null
}

export interface Holding {
  id: number
  account_id: number
  account_name: string
  institution: string
  asset: string
  quantity: number
  current_value: number
  cost_basis_total: number | null
  unrealized_gain_loss: number | null
}

export interface Transaction {
  id: number
  account_id: number
  account_name: string
  date: string
  type: string
  asset: string | null
  quantity: number | null
  price_per_unit: number | null
  total_amount: number
  category: string | null
  description: string | null
  source: string
}

export interface AssetClassBreakdown {
  asset_class: string
  value: number
  pct: number
}

export interface AccountSummary {
  id: number
  name: string
  type: string
  institution: string
  current_value: number
  cost_basis: number | null
  unrealized_gain_loss: number | null
  allocation_pct: number
  last_import_date: string | null
}

export interface NetWorth {
  total: number
  total_cost_basis: number | null
  total_unrealized_gain_loss: number | null
  btc_price: number | null
  accounts: AccountSummary[]
  by_asset_class: AssetClassBreakdown[]
}

export interface BTCPrice {
  usd: number
  usd_24h_change: number | null
  usd_market_cap: number | null
}

export interface ImportResult {
  success: boolean
  rows_in_file: number
  rows_parsed: number
  transactions_imported: number
  holdings_imported: number
  errors: string[]
}

export interface HealthStatus {
  status: string
  service: string
  version: string
  database: string
}

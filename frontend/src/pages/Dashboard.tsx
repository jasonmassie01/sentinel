import { useEffect, useState, useCallback } from 'react'
import { api } from '../api/client'
import type { NetWorth, BTCPrice, HealthStatus } from '../api/types'
import { formatUSD, formatPct, gainLossClass } from '../components/FormatUtils'
import './Dashboard.css'

export function Dashboard() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [netWorth, setNetWorth] = useState<NetWorth | null>(null)
  const [btcPrice, setBtcPrice] = useState<BTCPrice | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const [h, nw] = await Promise.all([
        api.health(),
        api.getNetWorth().catch(() => null),
      ])
      setHealth(h)
      setNetWorth(nw)

      // BTC price — fire and forget, non-critical
      api.getBTCPrice().then(setBtcPrice).catch(() => {})
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    // Refresh every 60s
    const interval = setInterval(fetchData, 60_000)
    return () => clearInterval(interval)
  }, [fetchData])

  if (loading) {
    return (
      <div className="dashboard">
        <div className="loading-screen">
          <span className="loading-text">SENTINEL INITIALIZING...</span>
        </div>
      </div>
    )
  }

  const hasAccounts = netWorth && netWorth.accounts.length > 0

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div>
          <h2 className="page-title">Command Center</h2>
          <span className="page-subtitle">
            {hasAccounts
              ? `Tracking ${netWorth.accounts.length} account${netWorth.accounts.length > 1 ? 's' : ''}`
              : 'Import accounts to begin tracking'}
          </span>
        </div>
        {health && (
          <div className="system-badge">
            <div className="status-dot" />
            <span>{health.service} {health.version}</span>
          </div>
        )}
      </header>

      {error && (
        <div className="error-banner">
          Backend unavailable: {error}
        </div>
      )}

      {/* Net Worth Hero */}
      <div className="net-worth-hero">
        <div className="net-worth-label">NET WORTH</div>
        <div className="net-worth-value">
          {hasAccounts ? formatUSD(netWorth.total) : '$0.00'}
        </div>
        {netWorth?.total_unrealized_gain_loss != null && (
          <div className={`net-worth-change ${gainLossClass(netWorth.total_unrealized_gain_loss)}`}>
            {formatUSD(netWorth.total_unrealized_gain_loss)} unrealized
          </div>
        )}
      </div>

      {/* BTC Ticker */}
      {btcPrice && (
        <div className="btc-ticker">
          <span className="btc-label">BTC</span>
          <span className="btc-price">{formatUSD(btcPrice.usd)}</span>
          {btcPrice.usd_24h_change != null && (
            <span className={`btc-change ${gainLossClass(btcPrice.usd_24h_change)}`}>
              {formatPct(btcPrice.usd_24h_change)} 24h
            </span>
          )}
        </div>
      )}

      <div className="card-grid">
        {/* Account Cards */}
        {hasAccounts && netWorth.accounts.map((acct) => (
          <div key={acct.id} className="card account-card">
            <div className="card-header">
              <h3 className="card-title">{acct.name}</h3>
              <span className="card-badge">{acct.institution}</span>
            </div>
            <div className="account-value">{formatUSD(acct.current_value)}</div>
            <div className="account-details">
              {acct.cost_basis != null && (
                <div className="detail-row">
                  <span className="label">Cost Basis</span>
                  <span className="value mono">{formatUSD(acct.cost_basis)}</span>
                </div>
              )}
              {acct.unrealized_gain_loss != null && (
                <div className="detail-row">
                  <span className="label">Unrealized</span>
                  <span className={`value mono ${gainLossClass(acct.unrealized_gain_loss)}`}>
                    {formatUSD(acct.unrealized_gain_loss)}
                  </span>
                </div>
              )}
              <div className="detail-row">
                <span className="label">Allocation</span>
                <span className="value mono">{formatPct(acct.allocation_pct).replace('+', '')}</span>
              </div>
              {acct.last_import_date && (
                <div className="detail-row">
                  <span className="label">Last Import</span>
                  <span className="value mono muted">{acct.last_import_date.split('T')[0]}</span>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Asset Class Breakdown */}
        {hasAccounts && netWorth.by_asset_class.length > 0 && (
          <div className="card">
            <h3 className="card-title">Asset Allocation</h3>
            <div className="allocation-bars">
              {netWorth.by_asset_class.map((ac) => (
                <div key={ac.asset_class} className="allocation-row">
                  <div className="allocation-label">
                    <span className={`asset-dot ${ac.asset_class}`} />
                    <span>{ac.asset_class}</span>
                  </div>
                  <div className="allocation-bar-container">
                    <div
                      className={`allocation-bar ${ac.asset_class}`}
                      style={{ width: `${Math.max(ac.pct, 2)}%` }}
                    />
                  </div>
                  <div className="allocation-values">
                    <span className="mono">{formatUSD(ac.value)}</span>
                    <span className="mono muted">{ac.pct.toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Key Metrics */}
        <div className="card">
          <h3 className="card-title">Key Metrics</h3>
          <div className="metrics-grid">
            <div className="metric">
              <span className="metric-label">YTD Gains</span>
              <span className="metric-value mono">—</span>
            </div>
            <div className="metric">
              <span className="metric-label">Est. Tax Liability</span>
              <span className="metric-value mono">—</span>
            </div>
            <div className="metric">
              <span className="metric-label">Monthly Burn</span>
              <span className="metric-value mono">—</span>
            </div>
            <div className="metric">
              <span className="metric-label">Savings Rate</span>
              <span className="metric-value mono">—</span>
            </div>
          </div>
        </div>

        {/* Value Unlocked */}
        <div className="card">
          <h3 className="card-title">Value Unlocked</h3>
          <div className="value-unlocked-total">
            <span className="vu-amount">{formatUSD(0)}</span>
            <span className="vu-label">saved by Sentinel YTD</span>
          </div>
        </div>

        {/* Active Alerts */}
        <div className="card">
          <h3 className="card-title">Active Alerts</h3>
          <div className="empty-state">No alerts — all clear</div>
        </div>

        {/* Quick Actions — only show when no accounts */}
        {!hasAccounts && (
          <div className="card onboarding-card">
            <h3 className="card-title">Get Started</h3>
            <div className="onboarding-steps">
              <div className="step">
                <span className="step-number">1</span>
                <span>Create accounts via API: POST /api/accounts</span>
              </div>
              <div className="step">
                <span className="step-number">2</span>
                <span>Import CSVs: POST /api/accounts/:id/import</span>
              </div>
              <div className="step">
                <span className="step-number">3</span>
                <span>Track BTC: POST /api/btc/track-address</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

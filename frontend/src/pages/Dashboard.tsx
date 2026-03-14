import { useEffect, useState } from 'react'
import './Dashboard.css'

interface HealthStatus {
  status: string
  service: string
  version: string
  database: string
}

export function Dashboard() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/health')
      .then((res) => res.json())
      .then(setHealth)
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : 'Unknown error'
        setError(message)
      })
  }, [])

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h2 className="page-title">Command Center</h2>
        <span className="page-subtitle">
          Net worth, accounts, alerts — everything at a glance
        </span>
      </header>

      <div className="card-grid">
        <div className="card system-status">
          <h3 className="card-title">System Status</h3>
          {error ? (
            <div className="status-error">
              <span className="label">Backend:</span> Disconnected
              <p className="error-detail">{error}</p>
            </div>
          ) : health ? (
            <div className="status-info">
              <div className="status-row">
                <span className="label">Service</span>
                <span className="value mono">{health.service}</span>
              </div>
              <div className="status-row">
                <span className="label">Version</span>
                <span className="value mono">{health.version}</span>
              </div>
              <div className="status-row">
                <span className="label">Database</span>
                <span className="value mono">{health.database}</span>
              </div>
              <div className="status-row">
                <span className="label">Status</span>
                <span className="value mono green">{health.status}</span>
              </div>
            </div>
          ) : (
            <div className="loading">Connecting...</div>
          )}
        </div>

        <div className="card placeholder">
          <h3 className="card-title">Net Worth</h3>
          <div className="placeholder-content">
            <span className="placeholder-value">—</span>
            <span className="placeholder-label">Import accounts to begin</span>
          </div>
        </div>

        <div className="card placeholder">
          <h3 className="card-title">YTD Gains / Losses</h3>
          <div className="placeholder-content">
            <span className="placeholder-value">—</span>
            <span className="placeholder-label">No tax lots tracked yet</span>
          </div>
        </div>

        <div className="card placeholder">
          <h3 className="card-title">Monthly Burn Rate</h3>
          <div className="placeholder-content">
            <span className="placeholder-value">—</span>
            <span className="placeholder-label">Import expenses to calculate</span>
          </div>
        </div>

        <div className="card placeholder">
          <h3 className="card-title">Active Alerts</h3>
          <div className="placeholder-content">
            <span className="placeholder-value">0</span>
            <span className="placeholder-label">No alerts</span>
          </div>
        </div>

        <div className="card placeholder">
          <h3 className="card-title">Value Unlocked</h3>
          <div className="placeholder-content">
            <span className="placeholder-value">$0</span>
            <span className="placeholder-label">Sentinel savings this year</span>
          </div>
        </div>
      </div>
    </div>
  )
}

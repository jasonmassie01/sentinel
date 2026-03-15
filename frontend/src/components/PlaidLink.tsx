import { useCallback, useEffect, useState } from 'react'
import { usePlaidLink } from 'react-plaid-link'
import './PlaidLink.css'

interface PlaidLinkButtonProps {
  onSuccess: () => void
}

export function PlaidLinkButton({ onSuccess }: PlaidLinkButtonProps) {
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/plaid/link-token', { method: 'POST' })
      .then((res) => {
        if (!res.ok) throw new Error('Failed to create link token')
        return res.json()
      })
      .then((data) => setLinkToken(data.link_token))
      .catch((err) => setError(err.message))
  }, [])

  const onPlaidSuccess = useCallback(
    async (publicToken: string, metadata: { institution?: { name?: string } | null }) => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch('/api/plaid/exchange-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            public_token: publicToken,
            institution_name: metadata.institution?.name || '',
          }),
        })
        if (!res.ok) throw new Error('Failed to link account')

        // Trigger initial sync
        await fetch('/api/plaid/sync', { method: 'POST' })

        onSuccess()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Link failed')
      } finally {
        setLoading(false)
      }
    },
    [onSuccess],
  )

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess: onPlaidSuccess,
  })

  if (error) {
    return (
      <div className="plaid-error">
        <span>{error}</span>
        <button className="btn-secondary" onClick={() => setError(null)}>
          Retry
        </button>
      </div>
    )
  }

  return (
    <button
      className="btn-plaid"
      onClick={() => open()}
      disabled={!ready || loading}
    >
      {loading ? 'Linking...' : 'Connect Account'}
    </button>
  )
}

interface LinkedItem {
  item_id: string
  institution_name: string
  last_synced: string | null
}

export function PlaidManager({ onSync }: { onSync: () => void }) {
  const [status, setStatus] = useState<{
    configured: boolean
    linked_items: LinkedItem[]
  } | null>(null)
  const [syncing, setSyncing] = useState(false)

  const refresh = useCallback(() => {
    fetch('/api/plaid/status')
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => {})
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleSync = async () => {
    setSyncing(true)
    try {
      await fetch('/api/plaid/sync', { method: 'POST' })
      onSync()
      refresh()
    } finally {
      setSyncing(false)
    }
  }

  if (!status) return null

  if (!status.configured) {
    return (
      <div className="plaid-setup-notice">
        <h4>Connect Your Accounts</h4>
        <p>
          Set <code>SENTINEL_PLAID_CLIENT_ID</code> and{' '}
          <code>SENTINEL_PLAID_SECRET</code> environment variables to enable
          automatic account linking.
        </p>
        <p className="muted">
          Get your keys at{' '}
          <a href="https://dashboard.plaid.com" target="_blank" rel="noreferrer">
            dashboard.plaid.com
          </a>
        </p>
      </div>
    )
  }

  return (
    <div className="plaid-manager">
      <div className="plaid-header">
        <h4>Linked Accounts</h4>
        <div className="plaid-actions">
          <PlaidLinkButton
            onSuccess={() => {
              refresh()
              onSync()
            }}
          />
          {status.linked_items.length > 0 && (
            <button
              className="btn-secondary"
              onClick={handleSync}
              disabled={syncing}
            >
              {syncing ? 'Syncing...' : 'Sync Now'}
            </button>
          )}
        </div>
      </div>

      {status.linked_items.length > 0 ? (
        <div className="linked-items">
          {status.linked_items.map((item) => (
            <div key={item.item_id} className="linked-item">
              <div className="linked-item-info">
                <span className="linked-name">
                  {item.institution_name || 'Unknown Institution'}
                </span>
                {item.last_synced && (
                  <span className="linked-synced muted mono">
                    Last synced: {item.last_synced.split('.')[0]}
                  </span>
                )}
              </div>
              <div className="linked-status">
                <div className="status-dot" />
                <span>Connected</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">
          No accounts linked yet. Click "Connect Account" to get started.
        </p>
      )}

      <p className="auto-sync-note muted">
        Accounts sync automatically every 4 hours.
      </p>
    </div>
  )
}

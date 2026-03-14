const BASE = ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<import('./types').HealthStatus>('/health'),

  // Accounts
  getAccounts: () => request<import('./types').Account[]>('/api/accounts'),
  createAccount: (data: { name: string; type: string; institution: string }) =>
    request<import('./types').Account>('/api/accounts', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Portfolio
  getNetWorth: () => request<import('./types').NetWorth>('/api/portfolio/net-worth'),
  getHoldings: () => request<import('./types').Holding[]>('/api/portfolio/holdings'),
  getTransactions: (params?: { limit?: number; offset?: number; account_id?: number }) => {
    const search = new URLSearchParams()
    if (params?.limit) search.set('limit', String(params.limit))
    if (params?.offset) search.set('offset', String(params.offset))
    if (params?.account_id) search.set('account_id', String(params.account_id))
    const qs = search.toString()
    return request<import('./types').Transaction[]>(`/api/portfolio/transactions${qs ? `?${qs}` : ''}`)
  },

  // BTC
  getBTCPrice: () => request<import('./types').BTCPrice>('/api/btc/price'),
  getBTCAddress: (address: string) => request<unknown>(`/api/btc/address/${address}`),
  trackBTCAddress: (address: string, name?: string) => {
    const params = new URLSearchParams({ address })
    if (name) params.set('account_name', name)
    return request<unknown>(`/api/btc/track-address?${params}`, { method: 'POST' })
  },

  // Import
  importCSV: async (accountId: number, file: File): Promise<import('./types').ImportResult> => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${BASE}/api/accounts/${accountId}/import`, {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) {
      const body = await res.text()
      throw new Error(`${res.status}: ${body}`)
    }
    return res.json() as Promise<import('./types').ImportResult>
  },
}

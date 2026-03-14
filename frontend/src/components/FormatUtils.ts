export function formatUSD(value: number | null | undefined): string {
  if (value == null) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

export function formatBTC(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${value.toFixed(8)} BTC`
}

export function formatPct(value: number | null | undefined): string {
  if (value == null) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '—'
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

export function gainLossClass(value: number | null | undefined): string {
  if (value == null || value === 0) return ''
  return value > 0 ? 'positive' : 'negative'
}

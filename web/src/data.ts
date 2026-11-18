import type { DayRow, Meta, Severity, Trust, Role, Cluster } from './types'

export interface Dataset {
  meta: Meta
  trust: Trust
  geo: GeoJSON.FeatureCollection
  byDate: DayRow[][]          // [dateIndex] -> rows for every cluster
  byCluster: Record<string, DayRow[]>  // cluster -> rows ordered by date
  cluster: Record<string, Cluster>
}

async function j<T>(path: string): Promise<T> {
  const r = await fetch(path)
  if (!r.ok) throw new Error(`Failed to load ${path}`)
  return r.json() as Promise<T>
}

export async function loadDataset(): Promise<Dataset> {
  const [meta, daily, trust, geo] = await Promise.all([
    j<Meta>('./data/meta.json'), j<DayRow[]>('./data/daily.json'),
    j<Trust>('./data/trust.json'), j<GeoJSON.FeatureCollection>('./data/geo.json'),
  ])
  const byDate: DayRow[][] = meta.dates.map(() => [])
  const byCluster: Record<string, DayRow[]> = {}
  for (const r of daily) {
    byDate[r.d].push(r)
    ;(byCluster[r.c] ??= []).push(r)
  }
  Object.values(byCluster).forEach(a => a.sort((x, y) => x.d - y.d))
  const cluster = Object.fromEntries(meta.clusters.map(c => [c.code, c]))
  return { meta, trust, geo, byDate, byCluster, cluster }
}

export const SEV_ORDER: Record<Severity, number> = { '': 0, Watch: 1, Warning: 2, Danger: 3 }
export const SEV_COLOR: Record<Severity, string> = { '': '#12a383', Watch: '#d9a400', Warning: '#e8780c', Danger: '#d43d51' }
export const SEV_SOFT: Record<Severity, string> = { '': 'var(--color-brand-soft)', Watch: 'var(--color-watch-soft)', Warning: 'var(--color-warning-soft)', Danger: 'var(--color-danger-soft)' }
export const SEV_LABEL: Record<Severity, string> = { '': 'Normal', Watch: 'Watch', Warning: 'Warning', Danger: 'Danger' }

export const maxSev = (rows: DayRow[]): Severity =>
  rows.reduce<Severity>((m, r) => (SEV_ORDER[r.s] > SEV_ORDER[m] ? r.s : m), '')

/** Small-cell suppression: counts 1..(min-1) are never shown as numbers. */
export function cell(n: number | null | undefined, min = 5): string {
  if (n === null || n === undefined) return 'no data'
  if (n === 0) return '0'
  return n < min ? `<${min}` : n.toLocaleString()
}

export const ROLE_LABEL: Record<Role, string> = {
  regulator: 'Regulator (public-health authority)',
  ohlead: 'Occupational-health lead',
  site: 'Site safety officer · MUS-C1',
}
export const ROLE_SHORT: Record<Role, string> = { regulator: 'Regulator', ohlead: 'OH lead', site: 'Site officer' }
export const SITE_OFFICER_CLUSTERS = ['MUS-C1']

/** Which clusters a role may see at cluster level. */
export function visibleClusters(role: Role, all: Cluster[]): Cluster[] {
  if (role === 'site') return all.filter(c => SITE_OFFICER_CLUSTERS.includes(c.code))
  return all
}

export const fmtDate = (iso: string, opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' }) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', opts)

export const pct = (x: number | null | undefined, d = 0) => (x === null || x === undefined || Number.isNaN(x) ? '–' : `${(x * 100).toFixed(d)}%`)

export function riskMultiple(p: number, base: number) { return base > 0 ? p / base : 0 }

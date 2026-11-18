import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Dataset } from './data'
import type { AuditEntry, Role, Severity, DayRow } from './types'

export type Page = 'situation' | 'alert' | 'trust' | 'governance' | 'data'

interface Ctx {
  ds: Dataset
  page: Page; setPage: (p: Page) => void
  dateIdx: number; setDateIdx: (i: number) => void
  role: Role; setRole: (r: Role) => void
  clusterSel: string; setClusterSel: (c: string) => void
  budget: number; setBudget: (b: number) => void
  thresholds: { watch: number; warning: number; danger: number }
  sevOf: (r: DayRow) => Severity
  audit: AuditEntry[]; addAudit: (e: AuditEntry) => void
  compare: boolean; setCompare: (b: boolean) => void
  dark: boolean; toggleDark: () => void
  K: ChartColors
}

export interface ChartColors { ink: string; text: string; sub: string; line: string; grid: string; surface: string; normal: string; land: string; landStroke: string; land2: string; land2Stroke: string; sea1: string; sea2: string; dots: string }
const LIGHT: ChartColors = { ink: '#14213d', text: '#43536b', sub: '#7a8ca3', line: '#e3e9f1', grid: '#eef2f7', surface: '#ffffff', normal: '#e6f5f1',
  land: '#fbfaf6', landStroke: '#c9c2b3', land2: '#f1efe9', land2Stroke: '#ddd8cd', sea1: '#e4f1fb', sea2: '#eef6fc', dots: '#d9e2ec' }
const DARK: ChartColors = { ink: '#e8eef7', text: '#b4c1d3', sub: '#8394ab', line: '#24324a', grid: '#1b2740', surface: '#121c2e', normal: '#173a35',
  land: '#1a2538', landStroke: '#3a4a63', land2: '#141e30', land2Stroke: '#2a3850', sea1: '#0d1a2c', sea2: '#0f1e33', dots: '#2a3850' }
const THEME_KEY = 'sentinel.theme'

const C = createContext<Ctx | null>(null)
export const useApp = () => {
  const v = useContext(C)
  if (!v) throw new Error('no ctx')
  return v
}

const AUDIT_KEY = 'sentinel.audit.v1'
function loadAudit(): AuditEntry[] {
  try { return JSON.parse(localStorage.getItem(AUDIT_KEY) || '[]') } catch { return [] }
}

/** Alert threshold for a chosen budget, recomputed live from the model's probabilities. */
function thresholdForBudget(ds: Dataset, budget: number): number {
  if (budget === ds.meta.policy.budget_per_cluster_month) return ds.meta.policy.threshold
  const ps = ds.byDate.flat().map(r => r.p).sort((a, b) => b - a)
  const months = ds.meta.clusters.length * ds.meta.dates.length / 30.44
  const k = Math.max(1, Math.min(ps.length, Math.round(budget * months)))
  return ps[k - 1]
}

export function AppProvider({ ds, children }: { ds: Dataset; children: ReactNode }) {
  const params = new URLSearchParams(location.hash.replace(/^#\??/, ''))
  const initDate = ds.meta.dates.indexOf(params.get('date') || '2026-08-09')
  const [page, setPage] = useState<Page>((params.get('page') as Page) || 'situation')
  const [dateIdx, setDateIdx] = useState(initDate >= 0 ? initDate : ds.meta.dates.length - 1)
  const [role, setRole] = useState<Role>((params.get('role') as Role) || 'ohlead')
  const [clusterSel, setClusterSel] = useState(params.get('cluster') || 'AAN-C1')
  const [budget, setBudget] = useState(ds.meta.policy.budget_per_cluster_month)
  const [audit, setAudit] = useState<AuditEntry[]>(loadAudit)
  const [compare, setCompare] = useState(false)
  const [dark, setDark] = useState<boolean>(() => { try { return localStorage.getItem(THEME_KEY) === 'dark' } catch { return false } })
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    try { localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light') } catch { /* storage unavailable */ }
  }, [dark])
  const toggleDark = () => setDark(d => !d)

  useEffect(() => {
    const h = new URLSearchParams({ page, date: ds.meta.dates[dateIdx], role, cluster: clusterSel })
    history.replaceState(null, '', '#' + h.toString())
  }, [page, dateIdx, role, clusterSel, ds])

  const thresholds = useMemo(() => {
    const pol = ds.meta.policy
    const t = thresholdForBudget(ds, budget)
    const scale = t / pol.threshold
    return { watch: t, warning: Math.max(t, pol.warning * scale), danger: Math.max(t, pol.danger * scale) }
  }, [ds, budget])

  const sevOf = useMemo(() => (r: DayRow): Severity =>
    r.p >= thresholds.danger ? 'Danger' : r.p >= thresholds.warning ? 'Warning' : r.p >= thresholds.watch ? 'Watch' : '',
  [thresholds])

  const addAudit = (e: AuditEntry) => {
    const next = [e, ...audit].slice(0, 200)
    setAudit(next)
    try { localStorage.setItem(AUDIT_KEY, JSON.stringify(next)) } catch { /* storage unavailable */ }
  }

  return (
    <C.Provider value={{ ds, page, setPage, dateIdx, setDateIdx, role, setRole, clusterSel, setClusterSel,
      budget, setBudget, thresholds, sevOf, audit, addAudit, compare, setCompare, dark, toggleDark, K: dark ? DARK : LIGHT }}>
      {children}
    </C.Provider>
  )
}

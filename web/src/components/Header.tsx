import { Pause, Play, ChevronLeft, ChevronRight, ShieldCheck, UserRound, Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { fmtDate, ROLE_LABEL } from '../data'
import { useApp, type Page } from '../state'
import type { Role } from '../types'
import { SyntheticTag } from '../ui'

const NAV: { id: Page; label: string }[] = [
  { id: 'situation', label: 'Situation' },
  { id: 'alert', label: 'Alert detail' },
  { id: 'trust', label: 'Trust & validation' },
  { id: 'governance', label: 'Governance' },
  { id: 'data', label: 'Data & method' },
]

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 64 64" className="h-9 w-9 shrink-0" aria-hidden>
        <rect width="64" height="64" rx="16" fill="#0E7C66" />
        <path d="M32 12 48 18v12c0 11-7 19-16 22-9-3-16-11-16-22V18z" fill="#fff" />
        <path d="M24 33h5l3-7 4 13 3-6h4" fill="none" stroke="#0E7C66" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="leading-tight">
        <div className="text-[17px] font-extrabold tracking-tight text-ink">Sentinel</div>
        <div className="text-[11px] font-medium text-ink-3">Workforce heat &amp; dust early warning</div>
      </div>
    </div>
  )
}

export function Header() {
  const { page, setPage, role, setRole, dark, toggleDark } = useApp()
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-6 gap-y-2 px-6 py-3">
        <Logo />
        <nav className="flex flex-wrap items-center gap-1">
          {NAV.map(n => (
            <button key={n.id} onClick={() => setPage(n.id)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${page === n.id ? 'bg-brand-soft text-brand' : 'text-ink-2 hover:bg-paper hover:text-ink'}`}>
              {n.label}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <SyntheticTag />
          <button onClick={toggleDark} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} title={dark ? 'Light mode' : 'Dark mode'}
            className="grid h-9 w-9 place-items-center rounded-xl border border-line bg-white text-ink-2 shadow-sm transition hover:text-brand">
            {dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <label className="flex items-center gap-2 rounded-xl border border-line bg-white px-3 py-1.5 text-sm shadow-sm">
            <UserRound size={15} className="text-brand" />
            <span className="sr-only">Signed-in role</span>
            <select value={role} onChange={e => setRole(e.target.value as Role)}
              className="cursor-pointer bg-transparent font-medium text-ink outline-none">
              {(Object.keys(ROLE_LABEL) as Role[]).map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </select>
          </label>
        </div>
      </div>
    </header>
  )
}

export function DateBar() {
  const { ds, dateIdx, setDateIdx, budget, setBudget, thresholds } = useApp()
  const [playing, setPlaying] = useState(false)
  const n = ds.meta.dates.length
  useEffect(() => {
    if (!playing) return
    const t = setInterval(() => setDateIdx(dateIdx + 1 < n ? dateIdx + 1 : 0), 650)
    return () => clearInterval(t)
  }, [playing, dateIdx, n, setDateIdx])
  const iso = ds.meta.dates[dateIdx]
  return (
    <div className="card flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-3">
      <div className="flex items-center gap-2">
        <button aria-label="Previous day" onClick={() => setDateIdx(Math.max(0, dateIdx - 1))} className="rounded-lg border border-line p-1.5 text-ink-2 hover:bg-paper"><ChevronLeft size={16} /></button>
        <button aria-label={playing ? 'Pause replay' : 'Play replay'} onClick={() => setPlaying(!playing)}
          className="flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-semibold text-[#fff] shadow-sm hover:bg-brand-2">
          {playing ? <Pause size={15} /> : <Play size={15} />} {playing ? 'Pause' : 'Replay'}
        </button>
        <button aria-label="Next day" onClick={() => setDateIdx(Math.min(n - 1, dateIdx + 1))} className="rounded-lg border border-line p-1.5 text-ink-2 hover:bg-paper"><ChevronRight size={16} /></button>
      </div>
      <div className="min-w-[190px]">
        <div className="eyebrow">Situation as of end of day</div>
        <div className="text-lg font-bold text-ink">{fmtDate(iso, { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' })}</div>
      </div>
      <input aria-label="Replay date" type="range" min={0} max={n - 1} value={dateIdx} onChange={e => setDateIdx(+e.target.value)} className="scrub min-w-[240px] flex-1" />
      <div className="flex items-center gap-3 rounded-xl bg-paper px-3 py-2">
        <ShieldCheck size={16} className="text-brand" />
        <div>
          <div className="eyebrow">Alert budget</div>
          <div className="flex items-center gap-2 text-sm">
            <input aria-label="Alert budget" type="range" min={1} max={8} step={0.5} value={budget} onChange={e => setBudget(+e.target.value)} className="scrub w-28" />
            <span className="whitespace-nowrap font-semibold tabular text-ink">{budget} alert days / site / month</span>
          </div>
          <div className="text-[11px] text-ink-3 tabular">Alert line: risk ≥ {(thresholds.watch * 100).toFixed(1)}%</div>
        </div>
      </div>
    </div>
  )
}

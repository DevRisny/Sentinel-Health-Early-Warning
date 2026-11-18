import type { ReactNode } from 'react'
import { SEV_COLOR, SEV_LABEL, SEV_SOFT } from './data'
import type { Severity } from './types'

export function SevBadge({ s, size = 'md' }: { s: Severity; size?: 'sm' | 'md' | 'lg' }) {
  const pad = size === 'lg' ? 'px-3 py-1 text-sm' : size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-0.5 text-xs'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${pad}`}
      style={{ background: SEV_SOFT[s], color: SEV_COLOR[s] }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: SEV_COLOR[s] }} />
      {SEV_LABEL[s]}
    </span>
  )
}

export function SyntheticTag({ text = 'Synthetic health data' }: { text?: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-dashed border-sky/50 bg-sky-soft px-2 py-0.5 text-[11px] font-semibold text-sky"
      title="Clinic, absence and incident feeds are simulated. Weather and dust are real (Open-Meteo).">
      ◇ {text}
    </span>
  )
}

export function Card({ title, right, children, className = '', pad = true }: { title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={`card ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3.5">
          <h2 className="card-title">{title}</h2>
          {right}
        </header>
      )}
      <div className={pad ? 'p-5' : ''}>{children}</div>
    </section>
  )
}

export function Stat({ label, value, sub, tone = 'ink', icon }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string; icon?: ReactNode }) {
  return (
    <div className="card flex items-start gap-3 p-4">
      {icon && <div className="mt-0.5 rounded-xl p-2" style={{ background: `color-mix(in srgb, var(--color-${tone}) 14%, transparent)`, color: `var(--color-${tone})` }}>{icon}</div>}
      <div className="min-w-0">
        <div className="eyebrow">{label}</div>
        <div className="mt-1 text-2xl font-bold tabular" style={{ color: `var(--color-${tone})` }}>{value}</div>
        {sub && <div className="mt-0.5 text-xs text-ink-2">{sub}</div>}
      </div>
    </div>
  )
}

export function Pill({ children, active, onClick }: { children: ReactNode; active?: boolean; onClick?: () => void }) {
  return (
    <button onClick={onClick}
      className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${active ? 'bg-brand text-[#fff] shadow-sm' : 'text-ink-2 hover:bg-brand-soft hover:text-brand'}`}>
      {children}
    </button>
  )
}

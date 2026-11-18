import { Ban, EyeOff, FileLock2, Gavel, ScrollText, UserCheck, Users } from 'lucide-react'
import { cell, fmtDate, ROLE_SHORT } from '../data'
import { useApp } from '../state'
import { Card, SevBadge } from '../ui'

const MATRIX: [string, string, string, string][] = [
  ['District alert level and 48-h outlook', '✓', '✓', 'own site only'],
  ['Site-cluster alerts and explanations', '—', '✓', 'own site only'],
  ['Counts of visits / absence / incidents', 'district totals, <5 hidden', 'site totals, <5 hidden', 'own site, <5 hidden'],
  ['Small sites (<1,000 workers)', 'pooled into district', 'shown', '—'],
  ['Approve / modify / dismiss actions', 'acknowledge only', 'all severities', 'Watch only'],
  ['Individual worker records', 'never', 'never', 'never'],
]

const PRINCIPLES = [
  { icon: <Users size={18} />, title: 'Aggregate only', text: 'Inputs are daily counts per site cluster. No names, IDs or individual records enter Sentinel.' },
  { icon: <EyeOff size={18} />, title: 'Small-cell suppression', text: 'Any count from 1 to 4 is shown as "<5". Sites under 1,000 workers are pooled into their district for the regulator.' },
  { icon: <Ban size={18} />, title: 'Purpose limit', text: 'Outputs may not be used for decisions about individual employment, discipline, insurance or immigration status.' },
  { icon: <UserCheck size={18} />, title: 'Human in the loop', text: 'Sentinel recommends. A named role approves, modifies or dismisses, and every decision is logged with a reason.' },
  { icon: <Gavel size={18} />, title: 'Clinical boundary', text: 'Population-level early warning only. It does not diagnose, triage or replace clinical judgement or emergency care.' },
  { icon: <FileLock2 size={18} />, title: 'Security by design', text: 'Role-based access, audit log, no secrets in the repository, and an API that serves aggregates only.' },
]

export function Governance() {
  const { ds, role, audit, dateIdx } = useApp()
  const today = ds.byDate[dateIdx]
  const demo = today.filter(r => r.hri !== null).slice(0, 6)
  return (
    <div className="grid gap-5">
      <div className="rounded-2xl border border-danger/25 bg-danger-soft px-5 py-4 text-sm text-ink">
        <b className="text-danger">Purpose-limit notice.</b> Sentinel supports population-level prevention. It must not be used to judge, discipline, dismiss, insure or report individual workers. Doing so breaches the data-use terms of this system.
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {PRINCIPLES.map(p => (
          <div key={p.title} className="card flex gap-3 p-4">
            <div className="h-fit rounded-xl bg-brand-soft p-2.5 text-brand">{p.icon}</div>
            <div><div className="font-semibold text-ink">{p.title}</div><p className="mt-0.5 text-[13px] leading-snug text-ink-2">{p.text}</p></div>
          </div>
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.3fr_1fr]">
        <Card title="Who sees what (role-based views)" right={<span className="text-xs text-ink-3">You are: <b className="text-ink">{ROLE_SHORT[role]}</b></span>} pad={false}>
          <table className="w-full text-[13px]">
            <thead className="bg-paper text-left text-[11px] text-ink-3"><tr>
              <th className="px-4 py-2 font-semibold">Information</th>
              {(['regulator', 'ohlead', 'site'] as const).map(r => <th key={r} className={`px-3 py-2 font-semibold ${role === r ? 'text-brand' : ''}`}>{ROLE_SHORT[r]}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-line">
              {MATRIX.map(row => (
                <tr key={row[0]}>
                  <td className="px-4 py-2 text-ink">{row[0]}</td>
                  {row.slice(1).map((v, i) => <td key={i} className={`px-3 py-2 ${['regulator', 'ohlead', 'site'][i] === role ? 'bg-brand-soft/50 font-medium text-ink' : 'text-ink-2'}`}>{v}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card title="Small-cell suppression, live" right={<span className="text-xs text-ink-3">{fmtDate(ds.meta.dates[dateIdx])}</span>} pad={false}>
          <table className="w-full text-[13px]">
            <thead className="bg-paper text-left text-[11px] text-ink-3"><tr><th className="px-4 py-2 font-semibold">Site cluster</th><th className="px-3 py-2 font-semibold">Heat-illness visits shown</th><th className="px-3 py-2 font-semibold">Rule</th></tr></thead>
            <tbody className="divide-y divide-line">
              {demo.map(r => (
                <tr key={r.c}><td className="px-4 py-2 text-ink">{r.c}</td><td className="px-3 py-2 font-semibold tabular">{cell(r.hri)}</td>
                  <td className="px-3 py-2 text-xs text-ink-3">{r.hri !== null && r.hri > 0 && r.hri < 5 ? 'suppressed (1–4)' : 'shown'}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
      <Card title={<span className="flex items-center gap-2"><ScrollText size={15} className="text-brand" />Audit log</span>} right={<span className="text-xs text-ink-3">Stored in this browser for the demo · {audit.length} entries</span>} pad={false}>
        {audit.length === 0 ? <p className="px-5 py-8 text-center text-sm text-ink-3">No decisions yet. Approve, modify or dismiss an alert on the Alert detail page and it appears here.</p> : (
          <table className="w-full text-[13px]">
            <thead className="bg-paper text-left text-[11px] text-ink-3"><tr>{['Logged at', 'By', 'Site cluster', 'Alert date', 'Severity', 'Decision', 'Reason'].map(h => <th key={h} className="px-4 py-2 font-semibold">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {audit.map((a, i) => (
                <tr key={i}>
                  <td className="px-4 py-2 tabular text-ink-3">{new Date(a.ts).toLocaleString('en-GB')}</td><td className="px-4 py-2">{a.user}</td>
                  <td className="px-4 py-2">{a.cluster}</td><td className="px-4 py-2 tabular">{fmtDate(a.date)}</td>
                  <td className="px-4 py-2"><SevBadge s={a.severity} size="sm" /></td>
                  <td className={`px-4 py-2 font-semibold ${a.decision === 'Dismissed' ? 'text-danger' : 'text-brand'}`}>{a.decision}</td>
                  <td className="px-4 py-2 text-ink-2">{a.note || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

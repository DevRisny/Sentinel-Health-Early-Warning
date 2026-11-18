import ReactECharts from 'echarts-for-react'
import { CheckCircle2, ClipboardList, Info, Lock, PencilLine, XCircle } from 'lucide-react'
import { useState } from 'react'
import { cell, fmtDate, SEV_COLOR, SEV_SOFT, visibleClusters } from '../data'
import { useApp } from '../state'
import type { DayRow } from '../types'
import { Card, SevBadge, SyntheticTag } from '../ui'

const FAMILY_COLOR: Record<string, string> = {
  'Heat forecast': '#e8780c', 'Heat so far': '#f29a3f', Acclimatisation: '#d9a400', Dust: '#b08850', Season: '#a7b4c6',
  'Heat-illness visits': '#0e7c66', 'Respiratory visits': '#12a383', 'All-cause visits': '#6fc3b0',
  'Incident reports': '#3e7cb1', 'Sickness absence': '#6b9bd1', 'Site profile': '#a7b4c6', 'Data completeness': '#c9d3df',
}

export function AlertDetail() {
  const { ds, role, clusterSel, setClusterSel, dateIdx } = useApp()
  const allowed = visibleClusters(role, ds.meta.clusters)
  const code = allowed.some(c => c.code === clusterSel) ? clusterSel : allowed[0].code
  if (role === 'regulator') return <RegulatorNotice />
  const r = ds.byCluster[code].find(x => x.d === dateIdx)!
  const c = ds.cluster[code]
  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <select value={code} onChange={e => setClusterSel(e.target.value)} aria-label="Site cluster"
          className="rounded-xl border border-line bg-white px-3 py-2 text-sm font-semibold text-ink shadow-sm">
          {allowed.map(x => <option key={x.code} value={x.code}>{x.code} · {x.name}</option>)}
        </select>
        <span className="text-sm text-ink-2">{c.sector} · {c.workforce.toLocaleString()} workers · {Math.round(c.outdoor_share * 100)}% outdoor work · {ds.meta.districts.find(d => d.code === c.district)!.name}</span>
        <span className="ml-auto"><SyntheticTag /></span>
      </div>
      <div className="grid gap-5 xl:grid-cols-[1fr_1.35fr]">
        <div className="grid content-start gap-5">
          <RiskHero r={r} />
          <WhyPanel r={r} />
        </div>
        <div className="grid content-start gap-5">
          <Timeline code={code} />
          <ActionPanel r={r} />
        </div>
      </div>
    </div>
  )
}

function RiskHero({ r }: { r: DayRow }) {
  const { ds, sevOf } = useApp()
  const s = sevOf(r)
  const mult = r.p / ds.trust.discrimination.base_rate
  const date = ds.meta.dates[r.d]
  return (
    <section className="card overflow-hidden">
      <div className="flex items-stretch">
        <div className="w-2" style={{ background: SEV_COLOR[s] }} />
        <div className="flex-1 p-5" style={{ background: `linear-gradient(120deg, ${SEV_SOFT[s]}, var(--color-white) 65%)` }}>
          <div className="flex items-center gap-2">
            <SevBadge s={s} size="lg" />
            <span className="text-sm text-ink-2">for {fmtDate(date, { day: 'numeric', month: 'short' })} + next 48 hours</span>
          </div>
          <div className="mt-4 flex items-end gap-6">
            <div>
              <div className="eyebrow">Chance of a health-burden surge in 48 h</div>
              <div className="text-5xl font-extrabold tabular" style={{ color: s ? SEV_COLOR[s] : '#0e7c66' }}>{(r.p * 100).toFixed(1)}%</div>
            </div>
            <div className="pb-1.5">
              <div className="text-2xl font-bold tabular text-ink">{mult.toFixed(1)}×</div>
              <div className="text-xs text-ink-3">the usual daily risk ({(ds.trust.discrimination.base_rate * 100).toFixed(1)}%)</div>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
            <Mini label="Heat today / forecast" value={`${r.wbgt.toFixed(1)} → ${r.fcW?.toFixed(1) ?? '–'}`} sub={`normal ${r.wbgtN.toFixed(1)}`} />
            <Mini label="PM10 today / forecast" value={`${Math.round(r.pm10)} → ${r.fcP ?? '–'}`} sub="µg/m³" />
            <Mini label="Data completeness" value={r.comp === null ? '–' : `${Math.round(r.comp * 100)}%`} sub={r.deg ? 'fallback model' : 'clinic feed, 7 days'} warn={r.comp !== null && r.comp < 0.8} />
          </div>
        </div>
      </div>
    </section>
  )
}

function Mini({ label, value, sub, warn }: { label: string; value: string; sub: string; warn?: boolean }) {
  return (
    <div className={`rounded-xl border px-3 py-2 ${warn ? 'border-warning/40 bg-warning-soft' : 'border-line bg-white/80'}`}>
      <div className="text-[11px] font-medium text-ink-3">{label}</div>
      <div className="font-bold tabular text-ink">{value}</div>
      <div className="text-[11px] text-ink-3">{sub}</div>
    </div>
  )
}

function WhyPanel({ r }: { r: DayRow }) {
  const g = Object.entries(r.g).filter(([k]) => k !== 'Data completeness').sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 8)
  const max = Math.max(...g.map(([, v]) => Math.abs(v)), 0.5)
  const shiftCells = [
    ['Heat-illness visits', r.hri, r.hriE], ['Respiratory visits', r.resp, r.respE], ['Incident reports', r.inc, null], ['Sickness absence', r.abs, r.absE],
  ] as const
  return (
    <Card title={<span className="flex items-center gap-2"><Info size={15} className="text-brand" />Why this risk level</span>}
      right={<span className="text-[11px] text-ink-3">SHAP contributions · fixed-template wording</span>}>
      <p className="rounded-xl bg-paper px-4 py-3 text-[15px] leading-relaxed text-ink">{r.why ?? 'Risk is within the normal range for this site and season.'}</p>
      <div className="mt-4 grid gap-2">
        {g.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[150px_1fr_52px] items-center gap-3 text-[13px]">
            <span className="truncate text-ink-2">{k}</span>
            <div className="relative h-3.5 rounded-full bg-paper">
              <div className="absolute top-0 h-3.5 w-px bg-ink-3/40" style={{ left: '50%' }} />
              <div className="absolute top-0 h-3.5 rounded-full" style={{
                background: v >= 0 ? FAMILY_COLOR[k] ?? '#7a8ca3' : '#b8c4d3',
                left: v >= 0 ? '50%' : `${50 - (Math.abs(v) / max) * 50}%`, width: `${(Math.abs(v) / max) * 50}%`,
              }} />
            </div>
            <span className={`text-right font-semibold tabular ${v >= 0 ? 'text-ink' : 'text-ink-3'}`}>{v >= 0 ? '+' : '−'}{Math.abs(v).toFixed(2)}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-ink-3"><span>← lowers risk</span><span>raises risk →</span></div>
      <div className="mt-4 border-t border-line pt-4">
        <div className="eyebrow mb-2">Evidence on file today (aggregated, small cells suppressed)</div>
        <div className="grid grid-cols-2 gap-2 text-[13px]">
          {shiftCells.map(([k, obs, exp]) => (
            <div key={k} className="flex justify-between rounded-lg bg-paper px-3 py-1.5">
              <span className="text-ink-2">{k}</span>
              <span className="font-semibold tabular text-ink">{cell(obs)}{exp !== null ? <span className="font-normal text-ink-3"> / exp {exp.toFixed(exp < 10 ? 1 : 0)}</span> : null}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

function Timeline({ code }: { code: string }) {
  const { K, ds, dateIdx, sevOf, compare, setCompare, thresholds } = useApp()
  const rows = ds.byCluster[code].filter(r => r.d <= dateIdx && r.d > dateIdx - 42)
  const later = compare ? ds.byCluster[code].filter(r => r.d > dateIdx && r.d <= dateIdx + 7) : []
  const all = [...rows, ...later]
  const x = all.map(r => fmtDate(ds.meta.dates[r.d], { day: 'numeric', month: 'short' }))
  const burden = all.map(r => (r.d <= dateIdx - 1 || compare) && r.hri !== null && r.resp !== null ? r.hri + r.resp : null)
  const expv = all.map(r => +(r.hriE + r.respE).toFixed(2))
  const option = {
    grid: { left: 44, right: 50, top: 56, bottom: 30 },
    legend: { top: 0, left: 0, itemWidth: 14, itemHeight: 8, textStyle: { color: K.text, fontSize: 11 } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: x, axisLabel: { color: K.sub, fontSize: 10 }, axisLine: { lineStyle: { color: K.line } }, axisTick: { show: false } },
    yAxis: [
      { type: 'value', name: 'visits', nameTextStyle: { color: K.sub, fontSize: 10 }, splitLine: { lineStyle: { color: K.grid } }, axisLabel: { color: K.sub, fontSize: 10 } },
      { type: 'value', name: 'risk %', max: (v: { max: number }) => Math.max(30, Math.ceil(v.max / 10) * 10), nameTextStyle: { color: K.sub, fontSize: 10 }, splitLine: { show: false }, axisLabel: { color: K.sub, fontSize: 10 } },
    ],
    series: [
      { name: 'Expected (seasonal normal)', type: 'line', data: expv, symbol: 'none', lineStyle: { color: '#a7b4c6', type: 'dashed', width: 1.5 }, areaStyle: { color: 'rgba(167,180,198,0.12)' } },
      { name: 'Heat + respiratory visits (reported)', type: 'bar', data: burden, barWidth: '55%', color: '#12a383',
        itemStyle: { color: (p: { dataIndex: number }) => (all[p.dataIndex].ev && compare ? '#d43d51' : '#12a383'), borderRadius: [3, 3, 0, 0] } },
      { name: '48-h risk (Sentinel)', type: 'line', yAxisIndex: 1, data: all.map(r => +(r.p * 100).toFixed(1)), smooth: true, symbol: 'circle', symbolSize: (_: number, p: { dataIndex: number }) => (sevOf(all[p.dataIndex]) ? 7 : 3),
        lineStyle: { color: K.ink, width: 2 }, itemStyle: { color: (p: { dataIndex: number }) => SEV_COLOR[sevOf(all[p.dataIndex])] },
        markLine: { silent: true, symbol: 'none', label: { formatter: 'alert line', color: '#d9a400', fontSize: 10 }, lineStyle: { color: '#d9a400', type: 'dotted' }, data: [{ yAxis: +(thresholds.watch * 100).toFixed(1) }] },
        markArea: compare && later.length ? { silent: true, itemStyle: { color: 'rgba(62,124,177,0.06)' }, label: { show: true, position: 'insideTop', color: '#3e7cb1', fontSize: 10, formatter: 'hindsight: what happened next' }, data: [[{ xAxis: x[rows.length] }, { xAxis: x[x.length - 1] }]] } : undefined },
      ...(compare ? [{ name: "Today's fixed heat rule alert", type: 'scatter', yAxisIndex: 1, symbol: 'triangle', symbolSize: 10, itemStyle: { color: '#e08a1e' },
        data: all.map(r => (r.a ? 2 : null)) }] : []),
    ],
  }
  return (
    <Card title="Signals and risk · last 6 weeks" right={
      <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-ink-2">
        <input type="checkbox" checked={compare} onChange={e => setCompare(e.target.checked)} className="accent-[#0e7c66]" />
        Replay with hindsight + today's fixed rule
      </label>}>
      <ReactECharts option={option} style={{ height: 300 }} notMerge />
      {compare && <p className="mt-2 text-xs text-ink-2">Red bars = days that turned out to be a health-burden surge (known only afterwards). Orange triangles = days the fixed heat/dust threshold would have alerted.</p>}
    </Card>
  )
}

function ActionPanel({ r }: { r: DayRow }) {
  const { ds, sevOf, role, addAudit, audit } = useApp()
  const s = sevOf(r)
  const [note, setNote] = useState('')
  const [done, setDone] = useState<string | null>(null)
  const kind = r.k ?? 'heat'
  const actions = s ? ds.meta.playbook[kind][s] : []
  const date = ds.meta.dates[r.d]
  const prior = audit.filter(a => a.cluster === r.c && a.date === date)
  const canDecide = role === 'ohlead' || (role === 'site' && s === 'Watch')
  const decide = (decision: 'Approved' | 'Modified' | 'Dismissed') => {
    if ((decision !== 'Approved') && !note.trim()) { setDone('Please add a reason: modifications and dismissals must be explained.'); return }
    addAudit({ ts: new Date().toISOString(), role, user: role === 'ohlead' ? 'OH lead (demo user)' : 'Site officer (demo user)', cluster: r.c, date, severity: s, decision, note: note.trim() })
    setDone(`${decision} and logged to the audit trail.`); setNote('')
  }
  return (
    <Card title={<span className="flex items-center gap-2"><ClipboardList size={15} className="text-brand" />Action card</span>}
      right={s ? <span className="text-xs text-ink-3">Responsible: <b className="text-ink">{ds.meta.responsible[s]}</b></span> : null}>
      {!s ? <p className="text-sm text-ink-2">No alert for this site cluster today. Routine heat-safety measures apply (water, shade, rest, buddy checks).</p> : (
        <>
          <div className="mb-2 flex items-center gap-2"><SevBadge s={s} /><span className="text-sm font-semibold text-ink">Recommended {kind === 'dust' ? 'dust-protection' : kind === 'signal' ? 'verification' : 'heat-protection'} measures</span></div>
          <ol className="grid gap-2">
            {actions.map((a, i) => (
              <li key={a} className="flex gap-3 rounded-xl border border-line px-3 py-2.5 text-sm text-ink">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-soft text-xs font-bold text-brand">{i + 1}</span>{a}
              </li>
            ))}
          </ol>
          <div className="mt-4 grid gap-1.5 rounded-xl bg-paper px-4 py-3 text-xs text-ink-2">
            <b className="text-ink">Evidence</b><span>{r.why}</span>
            <b className="mt-1 text-ink">Assumptions</b>
            {ds.meta.assumptions.map(a => <span key={a}>• {a}</span>)}
          </div>
          {canDecide ? (
            <div className="mt-4">
              <textarea value={note} onChange={e => setNote(e.target.value)} rows={2} placeholder="Note or reason (required to modify or dismiss)"
                className="w-full rounded-xl border border-line px-3 py-2 text-sm outline-none focus:border-brand" />
              <div className="mt-2 flex flex-wrap gap-2">
                <button onClick={() => decide('Approved')} className="flex items-center gap-1.5 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-[#fff] hover:bg-brand-2"><CheckCircle2 size={16} />Approve</button>
                <button onClick={() => decide('Modified')} className="flex items-center gap-1.5 rounded-lg border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-paper"><PencilLine size={16} />Modify</button>
                <button onClick={() => decide('Dismissed')} className="flex items-center gap-1.5 rounded-lg border border-line bg-white px-4 py-2 text-sm font-semibold text-danger hover:bg-danger-soft"><XCircle size={16} />Dismiss</button>
              </div>
            </div>
          ) : <p className="mt-4 flex items-center gap-2 text-xs text-ink-3"><Lock size={13} />Only the occupational-health lead can approve {s} actions. Site officers can act on Watch alerts.</p>}
          {done && <p className="mt-2 text-sm font-medium text-brand fade-in">{done}</p>}
          {prior.length > 0 && <div className="mt-3 text-xs text-ink-3">Logged today: {prior.map(p => `${p.decision} by ${p.user}`).join(' · ')}</div>}
        </>
      )}
    </Card>
  )
}

function RegulatorNotice() {
  return (
    <Card>
      <div className="flex items-start gap-4">
        <div className="rounded-xl bg-sky-soft p-3 text-sky"><Lock size={22} /></div>
        <div>
          <h2 className="text-lg font-bold text-ink">Site-level detail is not shown to the regulator role</h2>
          <p className="mt-1 max-w-2xl text-sm text-ink-2">By design, the public-health authority sees district totals only, with small site clusters pooled and counts below 5 suppressed. Site explanations and action cards are for the occupational-health lead. Switch role in the header to see them.</p>
        </div>
      </div>
    </Card>
  )
}

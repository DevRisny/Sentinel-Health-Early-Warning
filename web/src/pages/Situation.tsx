import ReactECharts from 'echarts-for-react'
import { Activity, AlertTriangle, Database, Thermometer, Wind } from 'lucide-react'
import { SEV_COLOR, SEV_ORDER, fmtDate, visibleClusters } from '../data'
import { MapView } from '../components/MapView'
import { useApp } from '../state'
import type { DayRow, Severity } from '../types'
import { Card, SevBadge, Stat } from '../ui'

export function Situation() {
  const { ds, dateIdx, role, sevOf } = useApp()
  const rows = ds.byDate[dateIdx]
  const vis = new Set(visibleClusters(role, ds.meta.clusters).map(c => c.code))
  const mine = rows.filter(r => vis.has(r.c))
  const alerts = mine.filter(r => sevOf(r)).sort((a, b) => SEV_ORDER[sevOf(b)] - SEV_ORDER[sevOf(a)] || b.p - a.p)
  const workersAtRisk = alerts.reduce((s, r) => s + ds.cluster[r.c].workforce, 0)
  const maxW = Math.max(...rows.map(r => r.fcW ?? r.wbgt))
  const maxP = Math.max(...rows.map(r => r.fcP ?? r.pm10))
  const comp = mine.reduce((s, r) => s + (r.comp ?? 0), 0) / Math.max(1, mine.length)
  const degraded = mine.some(r => r.deg)

  return (
    <div className="grid gap-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Stat icon={<AlertTriangle size={18} />} label={role === 'regulator' ? 'Districts on alert' : 'Active alerts'} tone={alerts.length ? 'danger' : 'brand'}
          value={role === 'regulator' ? new Set(alerts.map(a => ds.cluster[a.c].district)).size : alerts.length}
          sub={(() => {
            const sevs = role === 'regulator'
              ? ds.meta.districts.map(d => alerts.filter(a => ds.cluster[a.c].district === d.code).reduce<Severity>((m, r) => (SEV_ORDER[sevOf(r)] > SEV_ORDER[m] ? sevOf(r) : m), ''))
              : alerts.map(a => sevOf(a))
            return `${sevs.filter(x => x === 'Danger').length} Danger · ${sevs.filter(x => x === 'Warning').length} Warning · ${sevs.filter(x => x === 'Watch').length} Watch`
          })()} />
        <Stat icon={<Activity size={18} />} label="Workers covered by alerts" tone="warning" value={workersAtRisk.toLocaleString()} sub="in site clusters on Watch or above" />
        <Stat icon={<Thermometer size={18} />} label="Peak heat next 48 h" tone="warning" value={maxW.toFixed(1)} sub="WBGT proxy, worst district" />
        <Stat icon={<Wind size={18} />} label="Peak dust next 48 h" tone="sky" value={`${Math.round(maxP)}`} sub="PM10 µg/m³, worst district" />
        <Stat icon={<Database size={18} />} label="Clinic data completeness" tone={comp > 0.85 ? 'brand' : 'warning'} value={`${Math.round(comp * 100)}%`}
          sub={degraded ? 'Weather feed missing: fallback model' : 'last 7 reported days'} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.45fr_1fr]">
        <Card title="Situation map · 48-hour outlook" right={<span className="text-xs text-ink-3">{role === 'regulator' ? 'District view: site identities pooled' : 'Click a site cluster for the full explanation'}</span>}>
          <MapView />
        </Card>
        <AlertQueue alerts={alerts} />
      </div>

      <RiskCalendar />
    </div>
  )
}

function AlertQueue({ alerts }: { alerts: DayRow[] }) {
  const { ds, role, sevOf, setClusterSel, setPage } = useApp()
  if (role === 'regulator') {
    const byD = ds.meta.districts.map(d => {
      const a = alerts.filter(r => ds.cluster[r.c].district === d.code)
      const s = a.reduce<Severity>((m, r) => (SEV_ORDER[sevOf(r)] > SEV_ORDER[m] ? sevOf(r) : m), '')
      return { d, a, s, workers: a.reduce((t, r) => t + ds.cluster[r.c].workforce, 0) }
    }).sort((x, y) => SEV_ORDER[y.s] - SEV_ORDER[x.s])
    return (
      <Card title="District alert summary" right={<span className="text-xs text-ink-3">Aggregated · small cells suppressed</span>} pad={false}>
        <ul className="divide-y divide-line">
          {byD.map(({ d, a, s, workers }) => (
            <li key={d.code} className="flex items-center gap-3 px-5 py-3.5">
              <div className="h-9 w-1.5 rounded-full" style={{ background: SEV_COLOR[s] }} />
              <div className="flex-1">
                <div className="font-semibold text-ink">{d.name}</div>
                <div className="text-xs text-ink-3">{a.length ? `${a.length} of ${ds.meta.clusters.filter(c => c.district === d.code).length} site clusters on alert · ${workers.toLocaleString()} workers` : 'No alert'}</div>
              </div>
              <SevBadge s={s} />
            </li>
          ))}
        </ul>
        <p className="border-t border-line px-5 py-3 text-xs text-ink-3">Regulator view shows districts only. Site-level detail and actions sit with the occupational-health lead.</p>
      </Card>
    )
  }
  return (
    <Card title={`Alert queue · ${alerts.length}`} right={<span className="text-xs text-ink-3">Highest severity first</span>} pad={false}>
      {alerts.length === 0 && <div className="px-5 py-10 text-center text-sm text-ink-3">No site cluster above the alert line today. Risk is within normal range.</div>}
      <ul className="max-h-[520px] divide-y divide-line overflow-auto">
        {alerts.map(r => {
          const c = ds.cluster[r.c]
          const s = sevOf(r)
          return (
            <li key={r.c}>
              <button onClick={() => { setClusterSel(r.c); setPage('alert') }} className="flex w-full gap-3 px-5 py-3.5 text-left transition hover:bg-paper">
                <div className="mt-1 h-10 w-1.5 shrink-0 rounded-full" style={{ background: SEV_COLOR[s] }} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-ink">{c.name}</span>
                    <span className="text-xs text-ink-3">{r.c}</span>
                    <span className="ml-auto"><SevBadge s={s} size="sm" /></span>
                  </div>
                  <div className="mt-0.5 line-clamp-2 text-[13px] leading-snug text-ink-2">{r.why}</div>
                  <div className="mt-1 flex gap-3 text-[11px] text-ink-3 tabular">
                    <span>Risk {(r.p * 100).toFixed(1)}% · {(r.p / ds.trust.discrimination.base_rate).toFixed(1)}× usual</span>
                    <span>{c.workforce.toLocaleString()} workers · {Math.round(c.outdoor_share * 100)}% outdoor</span>
                  </div>
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

function RiskCalendar() {
  const { K, ds, dateIdx, role, setDateIdx, setClusterSel, setPage } = useApp()
  const span = 56
  const start = Math.max(0, dateIdx - span + 1)
  const days = ds.meta.dates.slice(start, dateIdx + 1)
  const clusters = role === 'regulator' ? [] : visibleClusters(role, ds.meta.clusters)
  const ylab = role === 'regulator' ? ds.meta.districts.map(d => d.name) : clusters.map(c => `${c.code}  ${c.name}`)
  const data: [number, number, number][] = []
  if (role === 'regulator') {
    ds.meta.districts.forEach((d, yi) => days.forEach((_, xi) => {
      const rs = ds.byDate[start + xi].filter(r => ds.cluster[r.c].district === d.code)
      data.push([xi, yi, Math.max(...rs.map(r => r.p))])
    }))
  } else {
    clusters.forEach((c, yi) => days.forEach((_, xi) => {
      const r = ds.byDate[start + xi].find(q => q.c === c.code)
      data.push([xi, yi, r ? r.p : 0])
    }))
  }
  const t = ds.meta.policy
  const option = {
    grid: { left: 230, right: 96, top: 10, bottom: 34 },
    tooltip: { formatter: (p: { value: [number, number, number] }) => `${ylab[p.value[1]]}<br/>${fmtDate(days[p.value[0]])}: <b>${(p.value[2] * 100).toFixed(1)}%</b> 48-h risk` },
    xAxis: { type: 'category', data: days.map(d => fmtDate(d, { day: 'numeric', month: 'short' })), axisLabel: { color: K.sub, fontSize: 10, interval: 6 }, axisLine: { lineStyle: { color: K.line } }, axisTick: { show: false } },
    yAxis: { type: 'category', data: ylab, axisLabel: { color: K.text, fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false }, inverse: true },
    visualMap: {
      type: 'piecewise', orient: 'vertical', right: 0, top: 'middle', itemWidth: 12, itemHeight: 12, textStyle: { color: K.text, fontSize: 10 },
      pieces: [
        { lt: t.threshold, color: K.normal, label: 'Normal' },
        { gte: t.threshold, lt: t.warning, color: '#f7d15a', label: 'Watch' },
        { gte: t.warning, lt: t.danger, color: '#f29a3f', label: 'Warning' },
        { gte: t.danger, color: '#d43d51', label: 'Danger' },
      ],
    },
    series: [{ type: 'heatmap', data, itemStyle: { borderColor: K.surface, borderWidth: 2, borderRadius: 3 }, emphasis: { itemStyle: { borderColor: K.ink, borderWidth: 1.5 } } }],
  }
  const onEvents = { click: (p: { value: [number, number, number] }) => {
    setDateIdx(start + p.value[0])
    if (role !== 'regulator') { setClusterSel(clusters[p.value[1]].code); setPage('alert') }
  } }
  return (
    <Card title="Risk timeline · last 8 weeks" right={<span className="text-xs text-ink-3">Each cell = one day's 48-hour risk. Click to open.</span>}>
      <ReactECharts option={option} onEvents={onEvents} style={{ height: Math.max(170, ylab.length * 30 + 50) }} notMerge />
    </Card>
  )
}

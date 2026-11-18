import ReactECharts from 'echarts-for-react'
import { BadgeCheck, CircleSlash, FlaskConical, Scale } from 'lucide-react'
import { fmtDate, pct } from '../data'
import { useApp, type ChartColors } from '../state'
import { Card } from '../ui'

const M = {
  sentinel: { name: 'Sentinel', color: '#0e7c66' },
  baseline_a: { name: "Today's rule: fixed heat/dust line", color: '#e08a1e' },
  baseline_b: { name: 'Clinic z-score rule', color: '#7a8ca3' },
} as const
type Key = keyof typeof M
const axisOf = (K: ChartColors) => ({ axisLabel: { color: K.sub, fontSize: 10 }, axisLine: { lineStyle: { color: K.line } }, splitLine: { lineStyle: { color: K.grid } } })

export function Trust() {
  const { ds } = useApp()
  const t = ds.trust
  const h = t.headline
  const fa = (k: Key) => h[k].false_alarms_per_cluster_month
  const faCut = 1 - fa('sentinel') / fa('baseline_a')
  const ppvX = h.sentinel.ppv / h.baseline_a.ppv
  return (
    <div className="grid gap-5">
      <section className="card overflow-hidden">
        <div className="grid gap-6 p-6 lg:grid-cols-[1.2fr_1fr]" style={{ background: 'linear-gradient(120deg,var(--color-brand-soft),var(--color-white) 60%)' }}>
          <div>
            <div className="eyebrow text-brand">Frozen hold-out · {fmtDate(t.periods.test[0])} to {fmtDate(t.periods.test[1])} · scored once</div>
            <h1 className="mt-2 text-2xl font-extrabold leading-tight text-ink md:text-3xl">At the same alert workload as today's fixed heat rule, Sentinel cuts false alarms by {Math.round(faCut * 100)}% and makes alerts {ppvX.toFixed(1)}× as likely to be real.</h1>
            <p className="mt-3 max-w-2xl text-sm text-ink-2">{h.sentinel.n_events} health-burden events across 12 site clusters in 2026, a year the model never saw. Environment data are real; health feeds are synthetic, so these numbers show the method works, not real-world accuracy.</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Big label="Events caught" s={pct(h.sentinel.sensitivity)} b={pct(h.baseline_a.sensitivity)} ci={h.sentinel.sensitivity_ci} />
            <Big label="Alerts that were real (PPV)" s={pct(h.sentinel.ppv)} b={pct(h.baseline_a.ppv)} ci={h.sentinel.ppv_ci} />
            <Big label="False alarms / site / month" s={fa('sentinel').toFixed(2)} b={fa('baseline_a').toFixed(2)} />
            <Big label="Ranking quality (average precision)" s={t.discrimination.average_precision.toFixed(2)} b={(t.discrimination.ap_baseline_a ?? 0).toFixed(2)} sub={`ROC-AUC ${t.discrimination.roc_auc.toFixed(2)} · base rate ${pct(t.discrimination.base_rate, 1)}`} />
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Fair comparison: every alert workload" right={<span className="text-xs text-ink-3">thresholds set for equal alert days</span>}>
          <Curves />
        </Card>
        <Card title="Hidden scenarios in 2026" right={<span className="text-xs text-ink-3">dates never shown to the model</span>} pad={false}>
          <Scenarios />
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card title={<span className="flex items-center gap-2"><FlaskConical size={15} className="text-brand" />What each signal family adds</span>}><Ablation /></Card>
        <Card title={<span className="flex items-center gap-2"><CircleSlash size={15} className="text-brand" />Stress tests: degrades safely</span>} pad={false}><Stress /></Card>
        <Card title={<span className="flex items-center gap-2"><Scale size={15} className="text-brand" />Calibration &amp; fairness</span>}><Calibration /></Card>
      </div>

      <Card title="Full comparison table (2026 hold-out)" pad={false}>
        <table className="w-full text-sm">
          <thead className="bg-paper text-left text-xs text-ink-3"><tr>
            {['Method', 'Events caught', '95% CI', 'PPV', '95% CI', 'False alarms / site / month', 'Alert days / site / month', 'Warned before onset', 'Mean lead to peak'].map(c => <th key={c} className="px-4 py-2.5 font-semibold">{c}</th>)}
          </tr></thead>
          <tbody className="divide-y divide-line">
            {(Object.keys(M) as Key[]).map(k => (
              <tr key={k} className={k === 'sentinel' ? 'bg-brand-soft/40 font-semibold' : ''}>
                <td className="px-4 py-2.5"><span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ background: M[k].color }} />{M[k].name}</td>
                <td className="px-4 py-2.5 tabular">{pct(h[k].sensitivity)}</td>
                <td className="px-4 py-2.5 tabular text-ink-3">{h[k].sensitivity_ci?.map(v => pct(v)).join('–')}</td>
                <td className="px-4 py-2.5 tabular">{pct(h[k].ppv)}</td>
                <td className="px-4 py-2.5 tabular text-ink-3">{h[k].ppv_ci?.map(v => pct(v)).join('–')}</td>
                <td className="px-4 py-2.5 tabular">{h[k].false_alarms_per_cluster_month.toFixed(2)}</td>
                <td className="px-4 py-2.5 tabular">{h[k].alert_days_per_cluster_month.toFixed(1)}</td>
                <td className="px-4 py-2.5 tabular">{pct(h[k].share_warned_before_onset)}</td>
                <td className="px-4 py-2.5 tabular">{h[k].mean_lead_hours.toFixed(0)} h</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="border-t border-line px-4 py-3 text-xs text-ink-3">Discrimination on every 2026 cluster-day: ROC-AUC {t.discrimination.roc_auc.toFixed(3)}, average precision {t.discrimination.average_precision.toFixed(3)} (base rate {pct(t.discrimination.base_rate, 1)}), Brier score {t.discrimination.brier.toFixed(3)}. Confidence intervals: bootstrap over whole events and whole alert episodes.</p>
      </Card>
    </div>
  )
}

function Big({ label, s, b, ci, sub }: { label: string; s: string; b: string; ci?: number[]; sub?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="text-xs font-medium text-ink-3">{label}</div>
      <div className="mt-1 flex items-baseline gap-2"><span className="text-3xl font-extrabold tabular text-brand">{s}</span><span className="text-sm text-ink-3 tabular">vs {b}</span></div>
      <div className="mt-0.5 text-[11px] text-ink-3">{ci ? `95% CI ${ci.map(v => pct(v)).join('–')}` : sub ?? "Sentinel vs today's rule"}</div>
    </div>
  )
}

function Curves() {
  const { K, ds } = useApp()
  const c = ds.trust.budget_curves
  const series = (metric: 'sensitivity' | 'false_alarms_per_cluster_month', idx: number) => (Object.keys(M) as Key[]).map(k => ({
    name: M[k].name, type: 'line', xAxisIndex: idx, yAxisIndex: idx, symbolSize: 6, smooth: true,
    lineStyle: { width: k === 'sentinel' ? 3 : 2, color: M[k].color }, itemStyle: { color: M[k].color },
    data: c[k].map(r => [+r.alert_days_per_cluster_month.toFixed(2), +(metric === 'sensitivity' ? r.sensitivity * 100 : r[metric]).toFixed(2)]),
  }))
  const option = {
    legend: { top: 0, textStyle: { fontSize: 11, color: K.text }, itemWidth: 14 },
    tooltip: { trigger: 'axis' },
    grid: [{ left: 44, right: '53%', top: 52, bottom: 40 }, { left: '58%', right: 10, top: 52, bottom: 40 }],
    title: [{ text: 'Events caught (%)', left: 40, top: 26, textStyle: { fontSize: 12, color: K.ink } }, { text: 'False alarms / site / month', left: '57%', top: 26, textStyle: { fontSize: 12, color: K.ink } }],
    xAxis: [0, 1].map(i => ({ type: 'value', gridIndex: i, name: 'alert days / site / month', nameLocation: 'middle', nameGap: 26, nameTextStyle: { fontSize: 10, color: K.sub }, ...axisOf(K) })),
    yAxis: [{ type: 'value', gridIndex: 0, max: 100, ...axisOf(K) }, { type: 'value', gridIndex: 1, ...axisOf(K) }],
    series: [...series('sensitivity', 0), ...series('false_alarms_per_cluster_month', 1).map(s => ({ ...s, name: s.name }))],
  }
  return <ReactECharts option={option} style={{ height: 320 }} notMerge />
}

function Scenarios() {
  const { ds } = useApp()
  return (
    <table className="w-full text-[13px]">
      <thead className="bg-paper text-left text-[11px] text-ink-3"><tr>
        <th className="px-4 py-2 font-semibold">Scenario</th><th className="px-2 py-2 font-semibold">Site</th><th className="px-2 py-2 font-semibold">Starts</th>
        <th className="px-2 py-2 font-semibold">Sentinel</th><th className="px-4 py-2 font-semibold">Fixed rule</th></tr></thead>
      <tbody className="divide-y divide-line">
        {ds.trust.scenarios_test.map(s => {
          const look = s.kind === 'lookalike'
          const fmt = (d: string | null) => {
            if (look) return d ? <span className="font-semibold text-danger">false alert</span> : <span className="font-semibold text-brand">correctly silent</span>
            if (!d) return <span className="text-ink-3">missed</span>
            const days = (new Date(s.start).getTime() - new Date(d).getTime()) / 864e5
            return <span className={days > 0 ? 'font-semibold text-brand' : 'text-ink-2'}>{days > 0 ? `${days} d before` : days === 0 ? 'on onset day' : `${-days} d after onset`}</span>
          }
          return (
            <tr key={s.key}>
              <td className="px-4 py-2 text-ink">{s.label}</td><td className="px-2 py-2 text-ink-3">{s.cluster}</td>
              <td className="px-2 py-2 tabular text-ink-3">{fmtDate(s.start, { day: 'numeric', month: 'short' })}</td>
              <td className="px-2 py-2">{fmt(s.sentinel_first_alert)}</td><td className="px-4 py-2">{fmt(s.baseline_a_first_alert)}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function Ablation() {
  const { K, ds } = useApp()
  const a = ds.trust.ablation
  const option = {
    grid: { left: 8, right: 40, top: 10, bottom: 10, containLabel: true },
    xAxis: { type: 'value', show: false },
    yAxis: { type: 'category', inverse: true, data: a.map(r => r.variant.replace(' (full Sentinel)', '')), axisLabel: { color: K.text, fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: 'bar', data: a.map((r, i) => ({ value: +r.average_precision.toFixed(3), itemStyle: { color: ['#9fd8cb', '#4fb39e', '#0e7c66'][i], borderRadius: 6 } })), barWidth: 22, label: { show: true, position: 'right', color: K.ink, fontWeight: 700 } }],
  }
  return (
    <>
      <ReactECharts option={option} style={{ height: 150 }} notMerge />
      <p className="text-xs text-ink-2">Average precision on 2026 as signal families are added. Clinic feeds add {Math.round((a[1].average_precision / a[0].average_precision - 1) * 100)}% over weather and dust alone. Workplace feeds add little accuracy here but keep Sentinel working when the clinic feed fails (see stress tests).</p>
    </>
  )
}

function Stress() {
  const { ds } = useApp()
  return (
    <table className="w-full text-[13px]">
      <thead className="bg-paper text-left text-[11px] text-ink-3"><tr><th className="px-4 py-2 font-semibold">Condition</th><th className="px-2 py-2 font-semibold">Caught</th><th className="px-4 py-2 font-semibold">PPV</th></tr></thead>
      <tbody className="divide-y divide-line">
        {ds.trust.stress_tests.map(s => (
          <tr key={s.scenario}><td className="px-4 py-2 text-ink">{s.scenario}</td><td className="px-2 py-2 tabular">{pct(s.sensitivity)}</td><td className="px-4 py-2 tabular">{pct(s.ppv)}</td></tr>
        ))}
      </tbody>
    </table>
  )
}

function Calibration() {
  const { K, ds } = useApp()
  const rel = ds.trust.discrimination.reliability
  const mx = Math.max(...rel.map(r => Math.max(r.pred, r.obs))) * 110
  const option = {
    grid: { left: 40, right: 12, top: 12, bottom: 34 },
    xAxis: { type: 'value', name: 'predicted %', nameLocation: 'middle', nameGap: 22, max: Math.ceil(mx), nameTextStyle: { fontSize: 10, color: K.sub }, ...axisOf(K) },
    yAxis: { type: 'value', name: 'observed %', max: Math.ceil(mx), nameTextStyle: { fontSize: 10, color: K.sub }, ...axisOf(K) },
    series: [
      { type: 'line', data: [[0, 0], [Math.ceil(mx), Math.ceil(mx)]], symbol: 'none', lineStyle: { type: 'dashed', color: K.line } },
      { type: 'line', data: rel.map(r => [+(r.pred * 100).toFixed(2), +(r.obs * 100).toFixed(2)]), lineStyle: { color: '#0e7c66', width: 2.5 }, itemStyle: { color: '#0e7c66' } },
    ],
  }
  return (
    <>
      <ReactECharts option={option} style={{ height: 160 }} notMerge />
      <div className="mt-2 grid gap-1.5">
        {ds.trust.by_site_size.map(b => (
          <div key={b.band} className="flex items-center justify-between rounded-lg bg-paper px-3 py-1.5 text-xs">
            <span className="flex items-center gap-1.5 text-ink-2"><BadgeCheck size={13} className="text-brand" />{b.band}</span>
            <span className="tabular text-ink">caught {pct(b.sensitivity)} · PPV {pct(b.ppv)}</span>
          </div>
        ))}
      </div>
    </>
  )
}

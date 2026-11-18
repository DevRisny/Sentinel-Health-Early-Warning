export type Severity = '' | 'Watch' | 'Warning' | 'Danger'
export type Role = 'regulator' | 'ohlead' | 'site'

export interface Driver { group: string; weight: number; text: string }
export interface ActionCard { kind: 'heat' | 'dust' | 'signal'; actions: string[]; responsible: string; assumptions: string[] }

export interface DayRow {
  d: number; c: string; p: number; s: Severity
  wbgt: number; wbgtN: number; fcW: number | null; pm10: number; fcP: number | null
  hri: number | null; hriE: number; resp: number | null; respE: number
  abs: number | null; absE: number; inc: number | null; shift: number
  comp: number | null; ev: number; a: number; b: number; deg: number
  g: Record<string, number>
  why?: string; drv?: Driver[]; act?: ActionCard
}

export interface Cluster {
  code: string; district: string; name: string; sector: string
  workforce: number; outdoor_share: number; pooled_for_regulator: boolean
}
export interface District { code: string; name: string; lat: number; lon: number }

export interface Meta {
  region: string; dates: string[]; clusters: Cluster[]; districts: District[]
  policy: { threshold: number; warning: number; danger: number; budget_per_cluster_month: number; cooldown_days: number }
  groups: string[]
  privacy: { small_cell_min: number; pool_workforce_min: number }
  events: { id: string; c: string; start: string; end: string; peak: string }[]
  sources: Record<string, string>
}

export interface Summary {
  n_events: number; sensitivity: number; median_lead_hours: number; mean_lead_hours: number
  median_onset_lead_hours: number; share_warned_before_onset: number; n_alert_episodes: number
  ppv: number; false_alarms_per_cluster_month: number; alert_days_per_cluster_month: number
  sensitivity_ci?: number[]; ppv_ci?: number[]; median_lead_hours_ci?: number[]
}

export interface Trust {
  headline: Record<'sentinel' | 'baseline_a' | 'baseline_b', Summary>
  budget_curves: Record<string, (Summary & { budget: number })[]>
  ablation: (Summary & { variant: string; average_precision: number })[]
  stress_tests: (Summary & { scenario: string })[]
  by_site_size: { band: string; events: number; sensitivity: number; ppv: number | null }[]
  scenarios_test: { key: string; label: string; cluster: string; kind: string; start: string; days: number; expected: string; sentinel_first_alert: string | null; baseline_a_first_alert: string | null }[]
  discrimination: { roc_auc: number; average_precision: number; brier: number; base_rate: number; reliability: { pred: number; obs: number; n: number }[] }
  global_importance: { group: string; mean_abs_shap: number; family: string }[]
  periods: Record<string, string[]>
}

export interface AuditEntry {
  ts: string; role: Role; user: string; cluster: string; date: string
  severity: Severity; decision: 'Approved' | 'Modified' | 'Dismissed'; note: string
}

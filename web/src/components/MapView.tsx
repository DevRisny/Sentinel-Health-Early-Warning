import { geoMercator, geoPath } from 'd3-geo'
import { useMemo, useState } from 'react'
import { SEV_COLOR, SEV_ORDER, visibleClusters } from '../data'
import { useApp } from '../state'
import type { Severity } from '../types'

const W = 760, H = 470
// cluster dot offsets around their district centre (in px)
const RING = [[-26, -14], [24, -16], [0, 26]]
// small display nudges so neighbouring districts do not overlap
const NUDGE: Record<string, [number, number]> = { AUH: [-26, -18], MUS: [26, 30] }
const LABEL_POS: Record<string, [number, number, 'start' | 'end' | 'middle']> = {
  AUH: [-30, -32, 'end'], MUS: [34, 44, 'start'], KZD: [20, -30, 'start'], AAN: [0, 54, 'middle'], RUW: [0, 52, 'middle'],
}

export function MapView() {
  const { ds, dateIdx, role, sevOf, setClusterSel, setPage, clusterSel, K } = useApp()
  const [hover, setHover] = useState<string | null>(null)
  const rows = ds.byDate[dateIdx]
  const projection = useMemo(() => geoMercator().fitExtent([[10, 10], [W - 10, H - 10]], {
    type: 'MultiPoint', coordinates: [[52.2, 23.1], [56.4, 23.1], [56.4, 25.25], [52.2, 25.25]],
  } as GeoJSON.MultiPoint), [])
  const path = geoPath(projection)
  const vis = new Set(visibleClusters(role, ds.meta.clusters).map(c => c.code))

  const bySev = (codes: string[]): Severity => codes.reduce<Severity>((m, c) => {
    const r = rows.find(x => x.c === c); const s = r ? sevOf(r) : ''
    return SEV_ORDER[s] > SEV_ORDER[m] ? s : m
  }, '')

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full rounded-xl" role="img" aria-label="Map of Abu Dhabi site clusters coloured by alert level">
        <defs>
          <linearGradient id="sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={K.sea1} /><stop offset="1" stopColor={K.sea2} /></linearGradient>
          <pattern id="dots" width="10" height="10" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.8" fill={K.dots} /></pattern>
        </defs>
        <rect width={W} height={H} fill="url(#sea)" />
        {ds.geo.features.map((f, i) => {
          const uae = (f.properties as { name: string }).name === 'United Arab Emirates'
          return <path key={i} d={path(f) || ''} fill={uae ? K.land : K.land2} stroke={uae ? K.landStroke : K.land2Stroke} strokeWidth={uae ? 1.2 : 0.8} />
        })}
        {ds.geo.features.filter(f => (f.properties as { name: string }).name === 'United Arab Emirates').map((f, i) =>
          <path key={'p' + i} d={path(f) || ''} fill="url(#dots)" opacity={0.7} />)}
        <text x={W - 24} y={H - 18} textAnchor="end" className="fill-ink-3" fontSize="11" fontWeight={600} letterSpacing="0.08em">ABU DHABI EMIRATE · UAE</text>
        <text x={60} y={40} className="fill-sky" fontSize="12" fontStyle="italic" opacity={0.7}>Arabian Gulf</text>

        {ds.meta.districts.map(d => {
          const [px, py] = projection([d.lon, d.lat]) as [number, number]
          const [nx, ny] = NUDGE[d.code] ?? [0, 0]
          const x = px + nx, y = py + ny
          const clusters = ds.meta.clusters.filter(c => c.district === d.code)
          const dsev = bySev(clusters.filter(c => vis.has(c.code)).map(c => c.code))
          const [lx, ly, anchor] = LABEL_POS[d.code]
          const showClusters = role !== 'regulator'
          return (
            <g key={d.code}>
              {role === 'regulator' && (
                <g onMouseEnter={() => setHover(d.code)} onMouseLeave={() => setHover(null)}>
                  {dsev === 'Danger' && <circle cx={x} cy={y} r={22} fill={SEV_COLOR[dsev]} className="pulse" />}
                  <circle cx={x} cy={y} r={22} fill={SEV_COLOR[dsev]} fillOpacity={0.9} stroke={K.surface} strokeWidth={3} />
                  <text x={x} y={y + 4} textAnchor="middle" fontSize="11" fontWeight={700} fill="#fff">{d.code}</text>
                </g>
              )}
              {showClusters && <circle cx={x} cy={y} r={34} fill="none" stroke={K.landStroke} strokeDasharray="3 4" />}
              {showClusters && clusters.map((c, k) => {
                if (!vis.has(c.code)) return null
                const r = rows.find(q => q.c === c.code)
                const s = r ? sevOf(r) : ''
                const [ox, oy] = RING[k % RING.length]
                const rad = 8 + Math.sqrt(c.workforce) / 9
                const sel = clusterSel === c.code
                return (
                  <g key={c.code} className="cursor-pointer" onClick={() => { setClusterSel(c.code); setPage('alert') }}
                    onMouseEnter={() => setHover(c.code)} onMouseLeave={() => setHover(null)}>
                    {s === 'Danger' && <circle cx={x + ox} cy={y + oy} r={rad} fill={SEV_COLOR[s]} className="pulse" />}
                    <circle cx={x + ox} cy={y + oy} r={rad} fill={SEV_COLOR[s]} fillOpacity={s ? 0.92 : 0.55}
                      stroke={sel ? K.ink : K.surface} strokeWidth={sel ? 3 : 2.5} />
                  </g>
                )
              })}
              <text x={x + lx} y={y + ly} textAnchor={anchor} fontSize="12.5" fontWeight={700} className="fill-ink" paintOrder="stroke" stroke={K.land} strokeWidth={4}>{d.name}</text>
            </g>
          )
        })}
      </svg>
      {hover && <HoverCard code={hover} />}
      <Legend />
    </div>
  )
}

function HoverCard({ code }: { code: string }) {
  const { ds, dateIdx, sevOf } = useApp()
  const rows = ds.byDate[dateIdx]
  const isDistrict = code.length === 3
  const name = isDistrict ? ds.meta.districts.find(d => d.code === code)!.name : ds.cluster[code].name
  const rs = isDistrict ? rows.filter(r => ds.cluster[r.c].district === code) : rows.filter(r => r.c === code)
  const top = [...rs].sort((a, b) => b.p - a.p)[0]
  return (
    <div className="pointer-events-none absolute left-4 top-4 w-72 rounded-xl border border-line bg-white/95 p-3 text-sm shadow-lg fade-in">
      <div className="font-semibold text-ink">{name}</div>
      <div className="text-xs text-ink-3">{isDistrict ? `District · ${rs.length} site clusters (pooled)` : `${ds.cluster[code].sector} · ${ds.cluster[code].workforce.toLocaleString()} workers`}</div>
      {top && <div className="mt-2 flex items-center justify-between text-xs"><span>48-h risk {isDistrict ? '(highest cluster)' : ''}</span><b style={{ color: SEV_COLOR[sevOf(top)] }}>{(top.p * 100).toFixed(1)}%</b></div>}
      {top && <div className="mt-1 flex items-center justify-between text-xs"><span>Heat stress (WBGT proxy)</span><b>{top.wbgt.toFixed(1)}</b></div>}
      {top && <div className="mt-1 flex items-center justify-between text-xs"><span>PM10 dust</span><b>{top.pm10} µg/m³</b></div>}
    </div>
  )
}

function Legend() {
  return (
    <div className="absolute bottom-3 left-3 flex flex-wrap gap-3 rounded-xl border border-line bg-white/90 px-3 py-2 text-[11px] font-medium text-ink-2">
      {(['', 'Watch', 'Warning', 'Danger'] as Severity[]).map(s => (
        <span key={s} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: SEV_COLOR[s] }} />{s || 'Normal'}</span>
      ))}
      <span className="text-ink-3">· dot size = workforce</span>
    </div>
  )
}

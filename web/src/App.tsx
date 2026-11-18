import { useEffect, useState } from 'react'
import { DateBar, Header, Logo } from './components/Header'
import { loadDataset, type Dataset } from './data'
import { AlertDetail } from './pages/AlertDetail'
import { DataMethod } from './pages/DataMethod'
import { Governance } from './pages/Governance'
import { Situation } from './pages/Situation'
import { Trust } from './pages/Trust'
import { AppProvider, useApp } from './state'

function Shell() {
  const { page } = useApp()
  const showDate = page === 'situation' || page === 'alert' || page === 'governance'
  return (
    <div className="min-h-full">
      <Header />
      <main className="mx-auto grid max-w-[1440px] gap-5 px-6 py-5">
        {showDate && <DateBar />}
        <div key={page} className="fade-in">
          {page === 'situation' && <Situation />}
          {page === 'alert' && <AlertDetail />}
          {page === 'trust' && <Trust />}
          {page === 'governance' && <Governance />}
          {page === 'data' && <DataMethod />}
        </div>
      </main>
      <footer className="mx-auto max-w-[1440px] px-6 pb-8 pt-2 text-xs text-ink-3">
        Sentinel prototype · Future Health Digital Innovation Challenge 2026 · Population &amp; Workforce Health Early Warning · Built by Risny Suha.
        Replay of the 2026 hold-out year. Weather and dust: Open-Meteo (CC BY 4.0). Health feeds are synthetic. Not a medical device.
      </footer>
    </div>
  )
}

export default function App() {
  const [ds, setDs] = useState<Dataset | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { loadDataset().then(setDs).catch(e => setErr(String(e))) }, [])
  if (err) return <div className="p-10 text-danger">Could not load data: {err}</div>
  if (!ds) return (
    <div className="grid h-full place-items-center">
      <div className="flex flex-col items-center gap-4"><Logo /><div className="h-1 w-40 overflow-hidden rounded-full bg-line"><div className="h-full w-1/2 animate-pulse rounded-full bg-brand" /></div></div>
    </div>
  )
  return <AppProvider ds={ds}><Shell /></AppProvider>
}

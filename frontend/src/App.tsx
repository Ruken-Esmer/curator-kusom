import { useState } from 'react'
import Header from '@/components/ui/Header'
import ChatPanel from '@/components/chat/ChatPanel'
import MimarApp from '@/mimar/MimarApp'
import MimarAnalyze from '@/mimar/MimarAnalyze'
import ReviewPanel from '@/mimar/ReviewPanel'

export type AppMode = 'curator' | 'mimar' | 'uzman'

export default function App() {
  const [mode, setMode] = useState<AppMode>(() =>
    typeof window === 'undefined' ? 'curator'
      : window.location.hash.startsWith('#mimar') ? 'mimar'
      : window.location.hash === '#uzman' ? 'uzman' : 'curator')
  // the research-protocol workspace stays available for the study team at #mimar-yonetim, but is not linked
  const protocolWorkspace = typeof window !== 'undefined' && window.location.hash === '#mimar-yonetim'

  const switchMode = (m: AppMode) => {
    setMode(m)
    try { window.location.hash = m === 'curator' ? '' : m } catch { /* ignore */ }
  }

  return (
    <div className="h-screen flex flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 overflow-hidden">
      <Header mode={mode} onModeChange={switchMode} />
      {mode === 'uzman' ? (
        <div className="flex-1 min-h-0"><ReviewPanel /></div>
      ) : mode === 'mimar' ? (
        <div className="flex-1 min-h-0">{protocolWorkspace ? <MimarApp /> : <MimarAnalyze />}</div>
      ) : (
        <main className="flex-1 min-h-0">
          <ChatPanel />
        </main>
      )}
    </div>
  )
}

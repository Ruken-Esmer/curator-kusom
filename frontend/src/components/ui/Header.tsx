import { useState } from 'react'
import { Globe, GitBranch, Activity } from 'lucide-react'
import { useStore } from '@/store'
import { healthApi } from '@/services/api'
import type { HealthStatus, Language } from '@/types'

type Mode = 'curator' | 'mimar' | 'uzman'

export default function Header({ mode = 'curator', onModeChange }: { mode?: Mode; onModeChange?: (m: Mode) => void }) {
  const { language, setLanguage, graphPanelOpen, setGraphPanelOpen } = useStore()
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [healthErr, setHealthErr] = useState(false)
  const checkHealth = () =>
    healthApi.check().then((h) => { setHealth(h); setHealthErr(false) }).catch(() => { setHealth(null); setHealthErr(true) })

  return (
    <header className="h-12 border-b border-zinc-200 dark:border-zinc-700 flex items-center justify-between px-4 shrink-0 bg-white dark:bg-zinc-950">
      <div className="flex items-center gap-3">
        <span className="font-serif text-base font-semibold tracking-tight">CURATOR</span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-100 dark:bg-teal-900/40 text-teal-700 dark:text-teal-300 font-medium">
          v1.1
        </span>
        <nav className="flex items-center gap-1 ml-2" aria-label="Modules">
          {(['curator', 'mimar', 'uzman'] as Mode[]).map((m) => (
            <button key={m} onClick={() => onModeChange?.(m)} aria-current={mode === m ? 'page' : undefined}
              className={`px-2.5 py-1 rounded-md text-xs border transition-colors ${mode === m
                ? 'border-[#7A1F2B] bg-[#F4E7E9] text-[#7A1F2B] font-semibold'
                : 'border-transparent text-zinc-500 hover:border-zinc-200'}`}>
              {m === 'curator' ? 'Chat' : m === 'mimar' ? 'MİMAR' : 'Uzman değerlendirmesi'}
            </button>
          ))}
        </nav>
        <span className="text-[10px] text-zinc-400 hidden sm:block">
          KU School of Medicine · AI Curriculum Intelligence
        </span>
      </div>

      <div className="flex items-center gap-2">
        {mode === 'curator' && <>
        {/* Language toggle */}
        <button
          onClick={() => setLanguage(language === 'en' ? 'tr' : 'en' as Language)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-zinc-200 dark:border-zinc-700 text-xs hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
        >
          <Globe size={12} className="text-zinc-400" />
          {language === 'en' ? 'TR' : 'EN'}
        </button>

        {/* Graph toggle */}
        <button
          onClick={() => setGraphPanelOpen(!graphPanelOpen)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs transition-colors ${
            graphPanelOpen
              ? 'border-teal-400 bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300'
              : 'border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800'
          }`}
        >
          <GitBranch size={12} />
          Graph
        </button>
        </>}

        {/* Health / API status */}
        <button
          onClick={checkHealth}
          title={health ? `Neo4j: ${health.neo4j ? 'up' : 'down'} · vectors: ${health.vector_store ? 'ready' : 'not ready'} · LLM: ${health.llm}` : 'Check API status'}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-zinc-200 dark:border-zinc-700 text-xs hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
        >
          <Activity size={12} className={health ? 'text-teal-500' : healthErr ? 'text-red-500' : 'text-zinc-400'} />
          {health ? `API ${health.version} · ${health.llm}` : healthErr ? 'API down' : 'API'}
        </button>
      </div>
    </header>
  )
}

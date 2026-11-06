import { useStore } from '@/store'
import type { Language } from '@/types'

type Mode = 'konu' | 'curator' | 'mimar' | 'uzman'

const TABS: { id: Mode; tr: string; en: string }[] = [
  { id: 'konu', tr: 'Konu incelemesi', en: 'Topic review' },
  { id: 'curator', tr: 'Serbest soru', en: 'Ask' },
  { id: 'uzman', tr: 'Uzman incelemesi', en: 'Expert review' },
  { id: 'mimar', tr: 'Müfredat analizi', en: 'Curriculum analysis' },
]

export default function Header({ mode = 'konu', onModeChange }: { mode?: Mode; onModeChange?: (m: Mode) => void }) {
  const { language, setLanguage } = useStore()

  return (
    <header className="app-header shrink-0 border-t-4 border-[#7A1F2B] border-b border-b-zinc-200 bg-white">
      <div className="h-12 flex items-stretch justify-between px-6">
        <div className="flex items-center gap-3">
          <span className="text-[15px] font-bold tracking-wide text-[#7A1F2B]">CURATOR</span>
          <span className="text-xs text-zinc-500 hidden md:block border-l border-zinc-300 pl-3">
            {language === 'tr' ? 'Koç Üniversitesi Tıp Fakültesi' : 'Koç University School of Medicine'}
          </span>
        </div>

        <nav className="flex items-stretch gap-6" aria-label="Bölümler">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => onModeChange?.(t.id)} aria-current={mode === t.id ? 'page' : undefined}
              className={`text-sm border-b-2 -mb-px transition-colors ${mode === t.id
                ? 'border-[#7A1F2B] text-zinc-900 font-semibold'
                : 'border-transparent text-zinc-500 hover:text-zinc-800'}`}>
              {t[language]}
            </button>
          ))}
          <button onClick={() => setLanguage((language === 'tr' ? 'en' : 'tr') as Language)}
            className="text-xs text-zinc-400 hover:text-zinc-700 self-center ml-2"
            title={language === 'tr' ? 'English' : 'Türkçe'}>
            {language === 'tr' ? 'English' : 'Türkçe'}
          </button>
        </nav>
      </div>
    </header>
  )
}

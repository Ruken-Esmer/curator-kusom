import { useStore } from '@/store'
import type { Language } from '@/types'

type Mode = 'curator' | 'mimar' | 'uzman'

const TABS: { id: Mode; tr: string; en: string }[] = [
  { id: 'curator', tr: 'Soru sor', en: 'Ask' },
  { id: 'uzman', tr: 'Uzman incelemesi', en: 'Expert review' },
  { id: 'mimar', tr: 'Araştırma', en: 'Research' },
]

export default function Header({ mode = 'curator', onModeChange }: { mode?: Mode; onModeChange?: (m: Mode) => void }) {
  const { language, setLanguage } = useStore()

  return (
    <header className="h-14 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between px-6 shrink-0 bg-white dark:bg-zinc-950">
      <div className="flex items-baseline gap-3">
        <span className="font-serif text-lg font-semibold tracking-tight text-[#7A1F2B]">CURATOR</span>
        <span className="text-xs text-zinc-500 hidden md:block">
          {language === 'tr' ? 'Koç Üniversitesi Tıp Fakültesi · Müfredat asistanı' : 'Koç University School of Medicine · Curriculum assistant'}
        </span>
      </div>

      <nav className="flex items-center gap-1" aria-label="Bölümler">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => onModeChange?.(t.id)} aria-current={mode === t.id ? 'page' : undefined}
            className={`px-3 py-1.5 rounded-full text-sm transition-colors ${mode === t.id
              ? 'bg-[#7A1F2B] text-white'
              : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800'}`}>
            {t[language]}
          </button>
        ))}
        <span className="w-px h-5 bg-zinc-200 dark:bg-zinc-700 mx-2" />
        <button onClick={() => setLanguage((language === 'tr' ? 'en' : 'tr') as Language)}
          className="px-2 py-1 text-xs text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
          title={language === 'tr' ? 'Switch to English' : 'Türkçeye geç'}>
          {language === 'tr' ? 'EN' : 'TR'}
        </button>
      </nav>
    </header>
  )
}

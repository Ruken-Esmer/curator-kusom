import { useState } from 'react'
import { ChevronRight, ChevronDown, BookOpen, Search } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '@/store'
import { useCurriculum } from '@/hooks'
import type { BlockInfo, YearInfo } from '@/types'

const YEAR_COLOURS = [
  '#0F6E56', '#185FA5', '#993C1D',
  '#854F0B', '#3B6D11', '#533AB7',
]

// ── Language strings ──────────────────────────────────────

const L = {
  curriculum:    { en: 'Curriculum', tr: 'Müfredat' },
  search:        { en: 'Search topics…', tr: 'Konu ara…' },
  noResults:     { en: 'No results', tr: 'Sonuç yok' },
  prerequisites: { en: 'Prerequisites', tr: 'Ön koşullar' },
  dept:          { en: 'Departments', tr: 'Bölümler' },
  weeks:         { en: 'Weeks', tr: 'Haftalar' },
}

// ── Sub-components ────────────────────────────────────────

function BlockRow({
  block,
  yearColour,
  yearIndex,
  onSelect,
}: {
  block: BlockInfo
  yearColour: string
  yearIndex: number
  onSelect: (block: BlockInfo) => void
}) {
  const { activeBlockId } = useStore()
  const active = activeBlockId === block.id

  return (
    <button
      onClick={() => onSelect(block)}
      className={clsx(
        'w-full text-left px-4 py-2 text-xs leading-snug transition-colors',
        'border-l-2',
        active
          ? 'bg-white dark:bg-zinc-800 font-medium'
          : 'hover:bg-zinc-50 dark:hover:bg-zinc-800/60 text-zinc-500 dark:text-zinc-400',
      )}
      style={{
        paddingLeft: '44px',
        borderLeftColor: active ? yearColour : 'transparent',
        color: active ? 'inherit' : undefined,
      }}
    >
      <span className="font-mono mr-2" style={{ color: yearColour, fontSize: 10 }}>
        {block.id}
      </span>
      {block.name}
    </button>
  )
}

function YearRow({
  yearData,
  index,
  onSelectBlock,
}: {
  yearData: YearInfo
  index: number
  onSelectBlock: (block: BlockInfo) => void
}) {
  const { activeYear, setActiveYear } = useStore()
  const colour = YEAR_COLOURS[index] ?? '#888'
  const open = activeYear === yearData.year

  return (
    <div>
      <button
        onClick={() => setActiveYear(open ? null : yearData.year)}
        className={clsx(
          'w-full flex items-center gap-2 px-4 py-2 text-sm transition-colors',
          'border-l-2',
          open
            ? 'bg-white dark:bg-zinc-800 font-medium'
            : 'hover:bg-zinc-50 dark:hover:bg-zinc-800/60',
        )}
        style={{ borderLeftColor: open ? colour : 'transparent' }}
      >
        <span
          className="flex items-center justify-center rounded-full text-white shrink-0"
          style={{ width: 22, height: 22, background: colour, fontSize: 10, fontWeight: 600 }}
        >
          Y{yearData.year}
        </span>
        <span className="flex-1 text-left leading-tight">{yearData.name}</span>
        {open
          ? <ChevronDown size={14} className="text-zinc-400 shrink-0" />
          : <ChevronRight size={14} className="text-zinc-400 shrink-0" />
        }
      </button>

      {open && yearData.blocks.map((b) => (
        <BlockRow
          key={b.id}
          block={b}
          yearColour={colour}
          yearIndex={index}
          onSelect={onSelectBlock}
        />
      ))}
    </div>
  )
}

// ── Main Sidebar ──────────────────────────────────────────

interface Props {
  onBlockQuery: (block: BlockInfo) => void
}

export default function CurriculumSidebar({ onBlockQuery }: Props) {
  const { language } = useStore()
  const curriculum = useCurriculum()
  const [search, setSearch] = useState('')

  const t = (k: keyof typeof L) => L[k][language]

  const filteredYears = search.trim()
    ? curriculum?.years.map((y) => ({
        ...y,
        blocks: y.blocks.filter(
          (b) =>
            b.name.toLowerCase().includes(search.toLowerCase()) ||
            b.id.toLowerCase().includes(search.toLowerCase()) ||
            b.topics?.some((tp) => tp.toLowerCase().includes(search.toLowerCase())),
        ),
      })).filter((y) => y.blocks.length > 0)
    : curriculum?.years

  return (
    <aside className="flex flex-col h-full bg-zinc-50 dark:bg-zinc-900 border-r border-zinc-200 dark:border-zinc-700">
      {/* Header */}
      <div className="px-4 py-4 border-b border-zinc-200 dark:border-zinc-700 shrink-0">
        <div className="flex items-center gap-2 mb-1">
          <BookOpen size={16} className="text-teal-700" />
          <span className="text-xs font-semibold uppercase tracking-widest text-zinc-400">
            {t('curriculum')}
          </span>
        </div>
        <p className="text-[10px] text-zinc-400 leading-tight">
          Koç University School of Medicine
        </p>
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b border-zinc-200 dark:border-zinc-700 shrink-0">
        <div className="relative">
          <Search size={12} className="absolute left-2.5 top-2.5 text-zinc-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('search')}
            className="w-full pl-7 pr-3 py-1.5 text-xs rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:outline-none focus:border-teal-500"
          />
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto">
        {filteredYears?.length === 0 && (
          <p className="px-4 py-3 text-xs text-zinc-400">{t('noResults')}</p>
        )}
        {filteredYears?.map((y, i) => (
          <YearRow
            key={y.year}
            yearData={y}
            index={i}
            onSelectBlock={onBlockQuery}
          />
        ))}
      </div>
    </aside>
  )
}

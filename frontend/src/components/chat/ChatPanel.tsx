import { useEffect, useRef, useState } from 'react'
import { Send, Trash2, Loader2, ChevronRight, Clock } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import clsx from 'clsx'
import { useChat } from '@/hooks'
import { useStore } from '@/store'
import type { Citation, PathwayStep } from '@/types'

// ── i18n ─────────────────────────────────────────────────

const SAMPLES = {
  en: [
    'What should I study before the Cardiovascular block?',
    'How does anatomy build through the 6 years?',
    'Where is diabetes covered and what are its prerequisites?',
    'What competencies does Year 4 develop?',
    'Explain the difference between Year 2 and Year 3 organ systems.',
  ],
  tr: [
    'Osteoartrit hangi sınıflarda, hangi bloklarda veya stajlarda öğretiliyor?',
    'Kardiyovasküler blok öncesinde ne çalışmalıyım?',
    'Anatomi 6 yıl boyunca nasıl gelişiyor?',
    'Diyabet müfredatta nerede kapsanıyor ve ön koşullar neler?',
    '4. yıl hangi yetkinlikleri geliştiriyor?',
    'Nöroloji rotasyonu için ön koşullar nelerdir?',
  ],
}

const L = {
  welcome:     { en: 'Welcome to CURATOR', tr: "CURATOR'a Hoş Geldiniz" },
  welcomeDesc: {
    en: 'Navigate the KU School of Medicine curriculum through natural language. Ask about learning pathways, prerequisites, topics, or competencies.',
    tr: 'Doğal dil ile KU Tıp Fakültesi müfredatını keşfedin. Öğrenme yolları, ön koşullar, konular veya yetkinlikler hakkında sorun.',
  },
  samples:     { en: 'Try a sample query', tr: 'Örnek sorgu deneyin' },
  placeholder: { en: 'Ask about the curriculum…', tr: 'Müfredat hakkında sorun…' },
  citations:   { en: 'Sources', tr: 'Kaynaklar' },
  pathway:     { en: 'Learning pathway', tr: 'Öğrenme yolu' },
  queryType:   { en: 'Query type', tr: 'Sorgu türü' },
  ms:          { en: 'ms', tr: 'ms' },
}

// ── Citation panel ────────────────────────────────────────

function CitationBar({ citations }: { citations: Citation[] }) {
  const { language } = useStore()
  if (!citations.length) return null

  return (
    <div className="px-4 py-2 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">
        {L.citations[language]}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c) => (
          <span
            key={c.block_id}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300 border border-teal-200 dark:border-teal-800"
          >
            <span className="font-semibold">{c.block_id}</span>
            <span className="text-teal-500">{c.block_name}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Pathway panel ─────────────────────────────────────────

function PathwayPanel({ steps }: { steps: PathwayStep[] }) {
  const { language } = useStore()
  if (!steps.length) return null

  return (
    <div className="px-4 py-3 border-t border-zinc-100 dark:border-zinc-800">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 mb-2">
        {L.pathway[language]}
      </p>
      <ol className="flex items-center gap-1 flex-wrap">
        {steps.map((s, i) => (
          <li key={s.order} className="flex items-center gap-1">
            <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
              <span className="font-mono font-semibold">{s.block_id || String(s.order)}</span>
              {s.block_name && <span className="text-blue-500">{s.block_name.slice(0, 20)}</span>}
            </span>
            {i < steps.length - 1 && <ChevronRight size={12} className="text-zinc-300 shrink-0" />}
          </li>
        ))}
      </ol>
    </div>
  )
}

// ── Message bubble ────────────────────────────────────────

function Bubble({ role, content }: { role: string; content: string }) {
  const isUser = role === 'user'
  return (
    <div className={clsx('flex gap-3', isUser && 'flex-row-reverse')}>
      <div
        className={clsx(
          'shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold',
          isUser
            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
            : 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300',
        )}
      >
        {isUser ? 'U' : 'C'}
      </div>
      <div
        className={clsx(
          'max-w-[78%] px-4 py-3 rounded-xl text-sm leading-relaxed',
          isUser
            ? 'bg-blue-50 dark:bg-blue-900/20 rounded-tr-sm'
            : 'bg-zinc-100 dark:bg-zinc-800 rounded-tl-sm',
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code: ({ children }) => (
                <code className="font-mono text-xs bg-zinc-200 dark:bg-zinc-700 px-1 py-0.5 rounded">
                  {children}
                </code>
              ),
              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              ol: ({ children }) => <ol className="list-decimal pl-4 mb-2">{children}</ol>,
              ul: ({ children }) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
              li: ({ children }) => <li className="mb-0.5">{children}</li>,
              table: ({ children }) => (
                <div className="overflow-x-auto my-2">
                  <table className="w-full text-[12.5px] border-collapse bg-white dark:bg-zinc-900 rounded">{children}</table>
                </div>
              ),
              th: ({ children }) => (
                <th className="text-left font-semibold px-2 py-1.5 border-b-2 border-[#7A1F2B]/40 bg-zinc-50 dark:bg-zinc-800 align-bottom">{children}</th>
              ),
              td: ({ children }) => <td className="px-2 py-1.5 border-b border-zinc-200 dark:border-zinc-700 align-top">{children}</td>,
            }}
          >
            {content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  )
}

// ── Main Chat Panel ───────────────────────────────────────

export default function ChatPanel() {
  const { language } = useStore()
  const {
    messages, isLoading, lastCitations, lastPathway,
    lastQueryType, lastProcessingMs, sendQuery, clearChat,
  } = useChat()

  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const submit = () => {
    if (!input.trim()) return
    sendQuery(input)
    setInput('')
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200 dark:border-zinc-700 shrink-0">
        <div>
          <h1 className="font-serif text-lg font-medium tracking-tight">CURATOR</h1>
          <p className="text-[10px] text-zinc-400">
            {language === 'en'
              ? 'AI Curriculum Intelligence'
              : 'Yapay Zeka Müfredat Asistanı'}
          </p>
        </div>
        {messages.length > 0 && (
          <div className="flex items-center gap-3">
            {lastQueryType && lastQueryType !== 'unknown' && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-500 font-mono capitalize">
                {({ audit: language === 'tr' ? 'akreditasyon' : 'accreditation', pathway: language === 'tr' ? 'öğrenme yolu' : 'pathway' } as Record<string, string>)[lastQueryType] ?? lastQueryType}
              </span>
            )}
            {lastProcessingMs > 0 && (
              <span className="flex items-center gap-1 text-[10px] text-zinc-400">
                <Clock size={10} />
                {Math.round(lastProcessingMs)}ms
              </span>
            )}
            <button
              onClick={clearChat}
              className="p-1.5 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-400 hover:text-zinc-600 transition-colors"
              title="Clear chat"
            >
              <Trash2 size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
        {messages.length === 0 ? (
          /* Welcome state */
          <div className="m-auto text-center max-w-sm py-8">
            <div className="w-12 h-12 rounded-2xl bg-teal-100 dark:bg-teal-900/30 flex items-center justify-center mx-auto mb-4">
              <span className="font-serif text-xl font-semibold text-teal-700 dark:text-teal-400">C</span>
            </div>
            <h2 className="text-base font-medium mb-2">{L.welcome[language]}</h2>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed mb-6">
              {L.welcomeDesc[language]}
            </p>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 mb-3">
              {L.samples[language]}
            </p>
            <div className="flex flex-col gap-2">
              {SAMPLES[language].map((q) => (
                <button
                  key={q}
                  onClick={() => sendQuery(q)}
                  className="text-left text-xs px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-teal-400 hover:bg-teal-50 dark:hover:bg-teal-900/20 transition-colors text-zinc-600 dark:text-zinc-300"
                >
                  {q} ↗
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((m, i) => (
              <Bubble key={i} role={m.role} content={m.content} />
            ))}
            {isLoading && (
              <div className="flex gap-3">
                <div className="shrink-0 w-7 h-7 rounded-full bg-teal-100 dark:bg-teal-900/40 flex items-center justify-center text-[11px] font-semibold text-teal-700 dark:text-teal-300">
                  C
                </div>
                <div className="px-4 py-3 rounded-xl rounded-tl-sm bg-zinc-100 dark:bg-zinc-800 flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin text-zinc-400" />
                  <span className="text-sm text-zinc-400">
                    {language === 'en' ? 'Searching curriculum…' : 'Müfredat aranıyor…'}
                  </span>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={endRef} />
      </div>

      {/* Citations + Pathway */}
      {messages.length > 0 && (
        <>
          <CitationBar citations={lastCitations} />
          <PathwayPanel steps={lastPathway} />
        </>
      )}

      {/* Input */}
      <div className="px-4 py-3 border-t border-zinc-200 dark:border-zinc-700 shrink-0">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), submit())}
            placeholder={L.placeholder[language]}
            disabled={isLoading}
            className="flex-1 px-3 py-2 text-sm rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:outline-none focus:border-teal-500 placeholder-zinc-400 disabled:opacity-50"
          />
          <button
            onClick={submit}
            disabled={isLoading || !input.trim()}
            className="px-3 py-2 rounded-lg bg-teal-700 hover:bg-teal-600 disabled:opacity-40 disabled:cursor-default text-white transition-colors"
          >
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  )
}

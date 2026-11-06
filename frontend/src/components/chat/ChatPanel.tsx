import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Loader2, ChevronRight, RotateCcw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useChat } from '@/hooks'
import { useStore } from '@/store'
import type { Citation, PathwayStep } from '@/types'

// ── content ──────────────────────────────────────────────

// guided example: the four questions an accreditation reviewer asks, in order
const SCENARIO = {
  tr: {
    title: 'Örnek inceleme: Osteoartrit',
    desc: 'Akreditasyon değerlendiricisinin sorduğu dört soru. Sırayla tıklayın.',
    steps: [
      { label: 'Nerede öğretiliyor?', q: 'Osteoartrit hangi sınıflarda, hangi bloklarda veya stajlarda öğretiliyor?' },
      { label: 'Öğrenme hedefleri', q: 'Osteoartritle ilgili öğrenme hedefleri neler?' },
      { label: 'Tekrarlar', q: 'Tekrar eden hedefler var mı? Varsa bu hedefleri, bulundukları sınıf ve blok/staj bilgileriyle yan yana göster.' },
      { label: 'UÇEP uyumu', q: 'UÇEP’te osteoartrit için beklenen bilgi ve beceriler arasında, müfredatımızdaki öğrenme hedeflerinde karşılığı bulunmayanlar var mı?' },
    ],
  },
  en: {
    title: 'Example review: Osteoarthritis',
    desc: 'The four questions an accreditation reviewer asks. Click them in order.',
    steps: [
      { label: 'Where is it taught?', q: 'Osteoartrit hangi sınıflarda, hangi bloklarda veya stajlarda öğretiliyor?' },
      { label: 'Learning objectives', q: 'Osteoartritle ilgili öğrenme hedefleri neler?' },
      { label: 'Repetitions', q: 'Tekrar eden hedefler var mı? Varsa bu hedefleri, bulundukları sınıf ve blok/staj bilgileriyle yan yana göster.' },
      { label: 'UÇEP alignment', q: 'UÇEP’te osteoartrit için beklenen bilgi ve beceriler arasında, müfredatımızdaki öğrenme hedeflerinde karşılığı bulunmayanlar var mı?' },
    ],
  },
}

const OTHER = {
  tr: ['Diyabet müfredatta nerede işleniyor?', 'Kardiyovasküler blok öncesinde ne çalışmalıyım?'],
  en: ['Where is diabetes covered in the curriculum?', 'What should I study before the Cardiovascular block?'],
}

const L = {
  heading:     { tr: 'Müfredat hakkında ne öğrenmek istersiniz?', en: 'What would you like to know about the curriculum?' },
  sub:         { tr: 'Cevaplar KUSOM 2025–2026 ders programlarına ve UÇEP-2020’ye dayanır.', en: 'Answers are based on the KUSOM 2025–2026 schedules and UÇEP-2020.' },
  placeholder: { tr: 'Sorunuzu yazın…', en: 'Type your question…' },
  other:       { tr: 'Başka örnekler', en: 'Other examples' },
  next:        { tr: 'Sıradaki soru', en: 'Next question' },
  newChat:     { tr: 'Yeni soru', en: 'New question' },
  sources:     { tr: 'Kaynak bloklar', en: 'Source blocks' },
  pathway:     { tr: 'Önerilen sıra', en: 'Suggested order' },
  loading:     { tr: 'Müfredat taranıyor…', en: 'Searching the curriculum…' },
}

const ACCENT = '#7A1F2B'

// ── pieces ───────────────────────────────────────────────

function Answer({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-zinc-900 dark:text-white">{children}</strong>,
        em: ({ children }) => <em className="not-italic text-zinc-500 text-[13px]">{children}</em>,
        ol: ({ children }) => <ol className="list-decimal pl-5 mb-3">{children}</ol>,
        ul: ({ children }) => <ul className="list-disc pl-5 mb-3">{children}</ul>,
        li: ({ children }) => <li className="mb-1">{children}</li>,
        code: ({ children }) => <code className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded">{children}</code>,
        table: ({ children }) => (
          <div className="overflow-x-auto my-3 rounded-lg border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-[13px] border-collapse">{children}</table>
          </div>
        ),
        th: ({ children }) => <th className="text-left font-medium text-zinc-500 px-3 py-2 bg-zinc-50 dark:bg-zinc-800/60 border-b border-zinc-200 dark:border-zinc-700 align-bottom">{children}</th>,
        td: ({ children }) => <td className="px-3 py-2 border-b border-zinc-100 dark:border-zinc-800 align-top">{children}</td>,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

function Extras({ citations, steps }: { citations: Citation[]; steps: PathwayStep[] }) {
  const { language } = useStore()
  if (!citations.length && !steps.length) return null
  return (
    <div className="mt-3 flex flex-col gap-2 text-xs">
      {steps.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-zinc-400 mr-1">{L.pathway[language]}:</span>
          {steps.map((s, i) => (
            <span key={s.order} className="flex items-center gap-1">
              <span className="px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800">{s.block_id || s.order}</span>
              {i < steps.length - 1 && <ChevronRight size={12} className="text-zinc-300" />}
            </span>
          ))}
        </div>
      )}
      {citations.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-zinc-400 mr-1">{L.sources[language]}:</span>
          {citations.map((c) => (
            <span key={c.block_id} title={c.block_name} className="px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800">{c.block_id}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function InputBox({ onSend, disabled, big }: { onSend: (q: string) => void; disabled: boolean; big?: boolean }) {
  const { language } = useStore()
  const [value, setValue] = useState('')
  const send = () => { if (value.trim()) { onSend(value); setValue('') } }
  return (
    <div className={`flex items-center gap-2 rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 shadow-sm focus-within:border-[#7A1F2B] ${big ? 'px-4 py-3' : 'px-3 py-2'}`}>
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), send())}
        placeholder={L.placeholder[language]}
        disabled={disabled}
        aria-label={L.placeholder[language]}
        className={`flex-1 bg-transparent focus:outline-none placeholder-zinc-400 ${big ? 'text-base' : 'text-sm'}`}
      />
      <button onClick={send} disabled={disabled || !value.trim()} aria-label="Gönder"
        className="w-8 h-8 rounded-full flex items-center justify-center text-white disabled:opacity-30 transition-opacity"
        style={{ background: ACCENT }}>
        <ArrowUp size={16} />
      </button>
    </div>
  )
}

// ── main ─────────────────────────────────────────────────

export default function ChatPanel() {
  const { language } = useStore()
  const { messages, isLoading, lastCitations, lastPathway, sendQuery, clearChat } = useChat()
  const endRef = useRef<HTMLDivElement>(null)
  const sc = SCENARIO[language]

  useEffect(() => {
    if (isLoading) { endRef.current?.scrollIntoView({ behavior: 'smooth' }); return }
    // after an answer arrives, bring the question that produced it to the top
    const qs = document.querySelectorAll('[data-role="user"]')
    qs[qs.length - 1]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [messages, isLoading])

  // where we are in the guided example
  const lastUser = [...messages].reverse().find((m) => m.role === 'user')?.content
  const stepIdx = sc.steps.findIndex((s) => s.q === lastUser)
  const next = stepIdx >= 0 && stepIdx < sc.steps.length - 1 && !isLoading ? sc.steps[stepIdx + 1] : null
  const lastAssistant = messages.length - 1 - [...messages].reverse().findIndex((m) => m.role === 'assistant')

  if (messages.length === 0) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="max-w-2xl mx-auto px-6 pt-[12vh] pb-12">
          <h1 className="font-serif text-3xl text-center tracking-tight mb-2">{L.heading[language]}</h1>
          <p className="text-sm text-zinc-500 text-center mb-8">{L.sub[language]}</p>
          <InputBox onSend={sendQuery} disabled={isLoading} big />

          <div className="mt-10 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-5">
            <p className="font-medium">{sc.title}</p>
            <p className="text-sm text-zinc-500 mb-4">{sc.desc}</p>
            <ol className="flex flex-col gap-2">
              {sc.steps.map((s, i) => (
                <li key={s.q}>
                  <button onClick={() => sendQuery(s.q)}
                    className="w-full text-left flex items-start gap-3 px-3 py-2.5 rounded-xl hover:bg-[#F7EEEF] dark:hover:bg-zinc-800 transition-colors group">
                    <span className="shrink-0 w-6 h-6 rounded-full text-xs font-semibold flex items-center justify-center text-white" style={{ background: ACCENT }}>{i + 1}</span>
                    <span className="flex-1">
                      <span className="block text-sm font-medium">{s.label}</span>
                      <span className="block text-xs text-zinc-500">{s.q}</span>
                    </span>
                    <ChevronRight size={16} className="mt-1 text-zinc-300 group-hover:text-[#7A1F2B]" />
                  </button>
                </li>
              ))}
            </ol>
          </div>

          <div className="mt-6 text-center">
            <span className="text-xs text-zinc-400 mr-2">{L.other[language]}:</span>
            {OTHER[language].map((q) => (
              <button key={q} onClick={() => sendQuery(q)}
                className="text-xs text-zinc-600 dark:text-zinc-300 underline decoration-zinc-300 underline-offset-4 hover:decoration-[#7A1F2B] mx-2">
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-6 flex flex-col gap-6">
          <div className="flex justify-end -mb-2">
            <button onClick={clearChat} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200">
              <RotateCcw size={12} /> {L.newChat[language]}
            </button>
          </div>
          {messages.map((m, i) =>
            m.role === 'user' ? (
              <div key={i} data-role="user" className="flex justify-end scroll-mt-4">
                <div className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-br-md text-[15px] bg-[#F7EEEF] dark:bg-zinc-800">{m.content}</div>
              </div>
            ) : (
              <div key={i} className="text-[15px] leading-relaxed text-zinc-800 dark:text-zinc-200">
                <Answer content={m.content} />
                {i === lastAssistant && <Extras citations={lastCitations} steps={lastPathway} />}
              </div>
            ),
          )}
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <Loader2 size={14} className="animate-spin" /> {L.loading[language]}
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="shrink-0 border-t border-zinc-100 dark:border-zinc-800">
        <div className="max-w-3xl mx-auto px-6 py-3 flex flex-col gap-2">
          {next && (
            <button onClick={() => sendQuery(next.q)}
              className="self-start flex items-center gap-2 text-sm px-3 py-1.5 rounded-full border border-[#7A1F2B]/30 text-[#7A1F2B] hover:bg-[#F7EEEF]">
              <span className="text-xs text-zinc-500">{L.next[language]} ({stepIdx + 2}/4):</span>
              {next.label}
              <ChevronRight size={14} />
            </button>
          )}
          <InputBox onSend={sendQuery} disabled={isLoading} />
        </div>
      </div>
    </div>
  )
}

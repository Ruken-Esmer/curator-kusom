import { useEffect, useRef, useState } from 'react'
import { Loader2, ChevronRight } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useChat } from '@/hooks'
import { useStore } from '@/store'
import type { Citation, PathwayStep } from '@/types'

const SCENARIO = {
  tr: {
    title: 'Örnek: osteoartrit için akreditasyon soruları',
    desc: 'Bir akreditasyon değerlendiricisinin sırayla sorduğu dört soru.',
    steps: [
      { label: 'Nerede öğretiliyor?', q: 'Osteoartrit hangi sınıflarda, hangi bloklarda veya stajlarda öğretiliyor?' },
      { label: 'Öğrenme hedefleri', q: 'Osteoartritle ilgili öğrenme hedefleri neler?' },
      { label: 'Tekrarlar', q: 'Tekrar eden hedefler var mı? Varsa bu hedefleri, bulundukları sınıf ve blok/staj bilgileriyle yan yana göster.' },
      { label: 'UÇEP uyumu', q: 'UÇEP’te osteoartrit için beklenen bilgi ve beceriler arasında, müfredatımızdaki öğrenme hedeflerinde karşılığı bulunmayanlar var mı?' },
    ],
  },
  en: {
    title: 'Example: accreditation questions on osteoarthritis',
    desc: 'Four questions an accreditation reviewer asks in order.',
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
  heading:     { tr: 'Müfredat sorgusu', en: 'Curriculum query' },
  sub:         { tr: 'Bir konunun hangi sınıf ve bloklarda işlendiğini, öğrenim hedeflerini, tekrarlarını ve UÇEP-2020 ile uyumunu sorgulayabilirsiniz. Veriler KUSOM 2025–2026 ders programlarından alınmıştır.',
                 en: 'Look up where a topic is taught, its learning objectives, repetitions and alignment with UÇEP-2020. Data: KUSOM 2025–2026 schedules.' },
  placeholder: { tr: 'Örneğin: Osteoartrit hangi sınıflarda öğretiliyor?', en: 'e.g. Where is osteoarthritis taught?' },
  ask:         { tr: 'Sor', en: 'Ask' },
  other:       { tr: 'Diğer örnekler', en: 'Other examples' },
  next:        { tr: 'Sonraki soru', en: 'Next question' },
  newChat:     { tr: 'Yeni sorgu', en: 'New query' },
  question:    { tr: 'Soru', en: 'Question' },
  sources:     { tr: 'Bloklar', en: 'Blocks' },
  pathway:     { tr: 'Önerilen sıra', en: 'Suggested order' },
  loading:     { tr: 'Ders programları taranıyor…', en: 'Searching the schedules…' },
}

const ACCENT = '#7A1F2B'

function Answer({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-zinc-900 dark:text-white">{children}</strong>,
        em: ({ children }) => <em>{children}</em>,
        ol: ({ children }) => <ol className="list-decimal pl-5 mb-3">{children}</ol>,
        ul: ({ children }) => <ul className="list-disc pl-5 mb-3">{children}</ul>,
        li: ({ children }) => <li className="mb-1">{children}</li>,
        code: ({ children }) => <code className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded">{children}</code>,
        table: ({ children }) => (
          <div className="overflow-x-auto my-3">
            <table className="w-full text-[13px] border-collapse border-y border-zinc-300">{children}</table>
          </div>
        ),
        th: ({ children }) => <th className="text-left font-semibold text-zinc-700 px-2.5 py-1.5 bg-zinc-100 border-b border-zinc-300 align-bottom">{children}</th>,
        td: ({ children }) => <td className="px-2.5 py-1.5 border-b border-zinc-200 align-top">{children}</td>,
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
              <span className="px-1.5 py-0.5 rounded-sm border border-zinc-300">{s.block_id || s.order}</span>
              {i < steps.length - 1 && <ChevronRight size={12} className="text-zinc-300" />}
            </span>
          ))}
        </div>
      )}
      {citations.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-zinc-400 mr-1">{L.sources[language]}:</span>
          {citations.map((c) => (
            <span key={c.block_id} title={c.block_name} className="px-1.5 py-0.5 rounded-sm border border-zinc-300">{c.block_id}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function InputBox({ onSend, disabled }: { onSend: (q: string) => void; disabled: boolean }) {
  const { language } = useStore()
  const [value, setValue] = useState('')
  const send = () => { if (value.trim()) { onSend(value); setValue('') } }
  return (
    <div className="flex gap-2">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), send())}
        placeholder={L.placeholder[language]}
        disabled={disabled}
        aria-label={L.question[language]}
        className="flex-1 rounded-md border border-zinc-300 bg-white px-3 py-2 text-[15px] focus:outline-none focus:border-[#7A1F2B] focus:ring-1 focus:ring-[#7A1F2B] placeholder-zinc-400"
      />
      <button onClick={send} disabled={disabled || !value.trim()}
        className="rounded-md px-5 text-sm font-semibold text-white disabled:opacity-40" style={{ background: ACCENT }}>
        {L.ask[language]}
      </button>
    </div>
  )
}

export default function ChatPanel() {
  const { language } = useStore()
  const { messages, isLoading, lastCitations, lastPathway, sendQuery, clearChat } = useChat()
  const endRef = useRef<HTMLDivElement>(null)
  const sc = SCENARIO[language]

  useEffect(() => {
    if (isLoading) { endRef.current?.scrollIntoView({ behavior: 'smooth' }); return }
    // scroll so the question behind the latest answer sits at the top
    const qs = document.querySelectorAll('[data-role="user"]')
    qs[qs.length - 1]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [messages, isLoading])

  const lastUser = [...messages].reverse().find((m) => m.role === 'user')?.content
  const stepIdx = sc.steps.findIndex((s) => s.q === lastUser)
  const next = stepIdx >= 0 && stepIdx < sc.steps.length - 1 && !isLoading ? sc.steps[stepIdx + 1] : null
  const lastAssistant = messages.length - 1 - [...messages].reverse().findIndex((m) => m.role === 'assistant')

  if (messages.length === 0) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 pt-10 pb-12">
          <h1 className="text-2xl font-semibold mb-2">{L.heading[language]}</h1>
          <p className="text-[15px] text-zinc-600 leading-relaxed mb-6">{L.sub[language]}</p>
          <InputBox onSend={sendQuery} disabled={isLoading} />

          <h2 className="mt-10 mb-1 text-[15px] font-semibold">{sc.title}</h2>
          <p className="text-sm text-zinc-500 mb-3">{sc.desc}</p>
          <ol className="flex flex-col gap-1.5 text-[15px]">
            {sc.steps.map((s, i) => (
              <li key={s.q} className="flex gap-2">
                <span className="w-4 shrink-0 text-right text-zinc-400">{i + 1}.</span>
                <button onClick={() => sendQuery(s.q)} className="text-left text-[#7A1F2B] hover:underline underline-offset-2">{s.q}</button>
              </li>
            ))}
          </ol>

          <h2 className="mt-8 mb-2 text-[15px] font-semibold">{L.other[language]}</h2>
          <ul className="flex flex-col gap-1.5 text-[15px]">
            {OTHER[language].map((q) => (
              <li key={q} className="flex gap-2"><span className="w-4 shrink-0 text-right text-zinc-400">–</span><button onClick={() => sendQuery(q)} className="text-left text-[#7A1F2B] hover:underline underline-offset-2">{q}</button></li>
            ))}
          </ul>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-6">
          <div className="flex justify-between items-baseline mb-4">
            <h1 className="text-lg font-semibold">{L.heading[language]}</h1>
            <button onClick={clearChat} className="text-sm text-zinc-500 hover:text-zinc-900 underline-offset-2 hover:underline">{L.newChat[language]}</button>
          </div>
          {messages.map((m, i) =>
            m.role === 'user' ? (
              <div key={i} data-role="user" className="scroll-mt-4 mt-6 first:mt-0 border-l-4 border-[#7A1F2B] bg-zinc-50 px-4 py-2.5">
                <span className="block text-xs text-zinc-500 mb-0.5">{L.question[language]}</span>
                <span className="text-[15px] font-semibold">{m.content}</span>
              </div>
            ) : (
              <div key={i} className="mt-4 text-[15px] leading-relaxed text-zinc-800">
                <Answer content={m.content} />
                {i === lastAssistant && <Extras citations={lastCitations} steps={lastPathway} />}
              </div>
            ),
          )}
          {isLoading && (
            <div className="mt-4 flex items-center gap-2 text-sm text-zinc-500">
              <Loader2 size={14} className="animate-spin" /> {L.loading[language]}
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="shrink-0 border-t border-zinc-200 bg-white">
        <div className="max-w-3xl mx-auto px-6 py-3">
          {next && (
            <p className="mb-2 text-sm">
              <span className="text-zinc-500">{L.next[language]} ({stepIdx + 2}/4): </span>
              <button onClick={() => sendQuery(next.q)} className="text-[#7A1F2B] hover:underline underline-offset-2">{next.q}</button>
            </p>
          )}
          <InputBox onSend={sendQuery} disabled={isLoading} />
        </div>
      </div>
    </div>
  )
}

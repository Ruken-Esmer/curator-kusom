import { useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'

const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? '') + '/api/v1/audit'
const ACCENT = '#7A1F2B'
const QUICK = ['Osteoartrit', 'Astım', 'Diabetes mellitus']

type Session = { year: number; block: string; block_name: string; title: string; kind: string; date: string | null; fields: string[]; role: string }
type Report = {
  topic: { code: string; no: number; name: string; name_en: string; levels: string[]; curated: boolean }
  summary: { where: string; objectives: string; repetitions: string; ucep: string }
  where: { years: number[]; direct: Session[]; related: Session[] }
  objectives: { items: { year: number; block: string; title: string; objective: string }[]; docs_for: string[]; missing_docs: string[]; sessions: Session[] }
  repetitions: { by_objective: boolean; counts: Record<string, number>; pairs: { early: Session; late: Session; relation: string; why: string; shared_objectives: string[] }[] }
  ucep: { rows: { level: string; expected: string; status: string; sessions: string[] }[]; in_objectives: boolean }
  plain: Record<'where' | 'objectives' | 'repetitions' | 'ucep', { text: string; flag: string }>
  source: string
}

const QUESTIONS: { key: 'where' | 'objectives' | 'repetitions' | 'ucep'; q: (n: string) => string }[] = [
  { key: 'where', q: (n) => `${n} hangi sınıf ve bloklarda öğretiliyor?` },
  { key: 'objectives', q: (n) => `${n} ile ilgili öğrenim hedefleri neler?` },
  { key: 'repetitions', q: () => 'Tekrar eden konular var mı?' },
  { key: 'ucep', q: () => 'UÇEP’in beklediklerinden müfredatta olmayan var mı?' },
]
const FLAG_CLS = (f: string) => (/eksik$/.test(f) && /^\d/.test(f) ? 'text-red-700 border-red-300 bg-red-50' : 'text-amber-800 border-amber-300 bg-amber-50')

const d = (iso: string | null) => (iso ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}` : '')
const STATUS_CLS: Record<string, string> = {
  'hedefte var': 'text-emerald-700', 'ders başlığında var': 'text-zinc-700',
  'dolaylı': 'text-amber-700', 'karşılığı bulunamadı': 'text-red-700 font-semibold',
}
const REL_CLS: Record<string, string> = { 'olası tekrar': 'text-red-700', 'pekiştirme': 'text-amber-700', 'derinleşme': 'text-emerald-700' }

const Th = ({ children, w }: { children?: any; w?: string }) => (
  <th className={`text-left font-semibold text-zinc-700 px-2.5 py-1.5 bg-zinc-100 border-b border-zinc-300 align-bottom ${w ?? ''}`}>{children}</th>
)
const Td = ({ children, className = '' }: { children?: any; className?: string }) => (
  <td className={`px-2.5 py-1.5 border-b border-zinc-200 align-top ${className}`}>{children}</td>
)
const Table = ({ children }: { children: any }) => (
  <div className="overflow-x-auto"><table className="w-full text-[13px] border-collapse border-t border-zinc-300">{children}</table></div>
)

function Answer({ n, question, plain, children }: { n: number; question: string; plain: { text: string; flag: string }; children?: any }) {
  const [open, setOpen] = useState(false)
  return (
    <section className="py-6 border-b border-zinc-200 break-inside-avoid">
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-[17px] font-semibold">{n}. {question}</h2>
        {plain.flag && <span className={`shrink-0 text-xs font-semibold border rounded px-2 py-0.5 ${FLAG_CLS(plain.flag)}`}>{plain.flag}</span>}
      </div>
      <p className="mt-2 text-[16px] leading-relaxed text-zinc-800 max-w-3xl">{plain.text}</p>
      {children && <>
        <button onClick={() => setOpen(!open)} className="print:hidden mt-3 text-sm text-[#7A1F2B] hover:underline underline-offset-2">
          {open ? 'Ayrıntıları gizle' : 'Ayrıntıları göster'}
        </button>
        <div className={`${open ? 'block' : 'hidden'} print:block mt-4 text-[14px]`}>{children}</div>
      </>}
    </section>
  )
}

function Where({ r }: { r: Report }) {
  const w = r.where
  if (!w.direct.length) return <p>2025–2026 ders programlarında bu konuya ayrılmış bir oturum bulunamadı.</p>
  return <>
    <Table>
      <thead><tr><Th w="w-12">Sınıf</Th><Th>Blok / staj</Th><Th>Oturum</Th><Th>Tür</Th><Th>Tarih</Th><Th>Anabilim dalı</Th></tr></thead>
      <tbody>{w.direct.map((s, i) => (
        <tr key={i}><Td>{s.year}</Td><Td><b>{s.block}</b> {s.block_name}</Td><Td>{s.title}</Td><Td>{s.kind}</Td><Td className="whitespace-nowrap">{d(s.date)}</Td><Td>{s.fields.join(', ')}</Td></tr>))}</tbody>
    </Table>
    {w.related.length > 0 && (
      <details className="mt-3 text-[14px]">
        <summary className="cursor-pointer">Konuya bağlı diğer oturumlar ({w.related.length})</summary>
        <p className="text-[13px] text-zinc-500 my-2">Başlıklarına göre seçildi; ilgili anabilim dallarıyla teyit edilmesi gerekir.</p>
        <Table>
          <thead><tr><Th w="w-12">Sınıf</Th><Th>Blok / staj</Th><Th>Oturum</Th><Th>Konuyla ilişkisi</Th></tr></thead>
          <tbody>{w.related.map((s, i) => <tr key={i}><Td>{s.year}</Td><Td>{s.block}</Td><Td>{s.title}</Td><Td>{s.role}</Td></tr>)}</tbody>
        </Table>
      </details>
    )}
  </>
}

function Objectives({ r }: { r: Report }) {
  const o = r.objectives
  if (o.items.length) return (
    <Table>
      <thead><tr><Th w="w-12">Sınıf</Th><Th>Blok</Th><Th>Oturum</Th><Th>Öğrenim hedefi</Th></tr></thead>
      <tbody>{o.items.map((x, i) => <tr key={i}><Td>{x.year}</Td><Td>{x.block}</Td><Td>{x.title}</Td><Td>{x.objective}</Td></tr>)}</tbody>
    </Table>
  )
  return <>
    <p className="mb-2">Elimizdeki öğrenim hedefi belgelerinde {r.topic.name.toLowerCase()} ile ilgili yazılı bir hedef yok.</p>
    <p className="mb-3 text-zinc-600">
      Hedef belgeleri şu ana kadar yalnızca {o.docs_for.join(', ')} blokları için iletildi.
      {o.missing_docs.length > 0 && <> Konunun işlendiği {o.missing_docs.join(' ve ')} için belge henüz elimizde değil; aşağıda hedefler yerine oturum başlıkları var.</>}
    </p>
    {o.sessions.length > 0 && (
      <Table>
        <thead><tr><Th w="w-12">Sınıf</Th><Th>Blok</Th><Th>Oturum başlığı</Th><Th>Tür</Th></tr></thead>
        <tbody>{o.sessions.map((s, i) => <tr key={i}><Td>{s.year}</Td><Td>{s.block}</Td><Td>{s.title}</Td><Td>{s.kind}</Td></tr>)}</tbody>
      </Table>
    )}
  </>
}

function Repetitions({ r }: { r: Report }) {
  const t = r.repetitions
  if (!t.pairs.length) return <p>Bu konu için birden fazla oturumda geçen bir içerik bulunamadı.</p>
  return <>
    <p className="mb-3">
      {!t.by_objective && 'Yazılı hedef olmadığı için karşılaştırma oturumlar üzerinden yapıldı. '}
      {t.counts['olası tekrar']} olası tekrar, {t.counts['pekiştirme']} pekiştirme, {t.counts['derinleşme']} derinleşme var.
      Derinleşmeler sarmal programın beklenen sonucu; bakılması gerekenler olası tekrarlar.
    </p>
    <Table>
      <thead><tr><Th>Önce</Th><Th>Sonra</Th><Th w="w-[34%]">Değerlendirme</Th></tr></thead>
      <tbody>{t.pairs.map((p, i) => (
        <tr key={i}>
          <Td><span className="text-zinc-500">{p.early.year}. sınıf, {p.early.block}</span><br />{p.early.title} <span className="text-zinc-500">({p.early.kind})</span></Td>
          <Td><span className="text-zinc-500">{p.late.year}. sınıf, {p.late.block}</span><br />{p.late.title} <span className="text-zinc-500">({p.late.kind})</span></Td>
          <Td><span className={`font-semibold ${REL_CLS[p.relation] ?? ''}`}>{p.relation}</span><br />{p.why}</Td>
        </tr>))}</tbody>
    </Table>
  </>
}

function Ucep({ r }: { r: Report }) {
  const u = r.ucep
  const unmet = u.rows.filter((x) => x.status === 'karşılığı bulunamadı')
  return <>
    <p className="mb-3">
      UÇEP-2020 bu konu için <b>{r.topic.levels.join('-')}</b> düzeyini bekliyor (madde {r.topic.no}).{' '}
      {unmet.length ? <>Müfredatta karşılığı bulunamayan: <b>{unmet.map((x) => x.expected.toLowerCase()).join(', ')}</b>.</> : 'Her beklentinin müfredatta bir karşılığı var.'}
      {!u.in_objectives && ' Yazılı hedef olmadığı için karşılıklar oturum başlıklarından arandı.'}
    </p>
    <Table>
      <thead><tr><Th w="w-20">Düzey</Th><Th>Beklenen</Th><Th>Müfredatta</Th><Th w="w-[45%]">Nerede</Th></tr></thead>
      <tbody>{u.rows.map((x) => (
        <tr key={x.level}><Td>{x.level}</Td><Td>{x.expected}</Td><Td className={STATUS_CLS[x.status]}>{x.status}</Td>
          <Td>{x.sessions.length ? <ul className="flex flex-col gap-0.5">{x.sessions.map((s, i) => <li key={i}>{s}</li>)}</ul> : ''}</Td></tr>))}</tbody>
    </Table>
    <p className="mt-3 text-[13px] text-zinc-500">
      Bir oturum başlığının bulunması konunun işlendiğini gösterir; hedefin UÇEP düzeyinde yazıldığını göstermez.
      UÇEP’in semptom ve temel hekimlik uygulamaları listeleri bu karşılaştırmaya henüz dahil değil.
    </p>
  </>
}

export default function TopicReport() {
  const [names, setNames] = useState<{ name: string }[]>([])
  const [q, setQ] = useState('')
  const [rep, setRep] = useState<Report | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const top = useRef<HTMLDivElement>(null)

  useEffect(() => { fetch(`${BASE}/topics`).then((r) => (r.ok ? r.json() : [])).then(setNames).catch(() => setNames([])) }, [])

  const load = async (topic: string) => {
    if (!topic.trim()) return
    setQ(topic); setBusy(true); setErr(null)
    try {
      const r = await fetch(`${BASE}/report?q=${encodeURIComponent(topic)}`)
      const body = await r.json()
      if (!r.ok) throw new Error(body.detail ?? 'Rapor alınamadı.')
      setRep(body)
      top.current?.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e: any) { setErr(e.message); setRep(null) } finally { setBusy(false) }
  }
  
  return (
    <div ref={top} className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-6 pt-8 pb-16">
        <div className="print:hidden">
          <h1 className="text-2xl font-semibold mb-2">Konu incelemesi</h1>
          <p className="text-[15px] text-zinc-600 mb-5">
            Bir hastalık adı yazın. Akreditasyonda sorulan dört sorunun cevabı aşağıda çıkar.
          </p>
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); load(q) }}>
            <input list="topic-names" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Konu"
              placeholder="Örneğin: Osteoartrit"
              className="flex-1 rounded-md border border-zinc-300 bg-white px-3 py-2 text-[15px] focus:outline-none focus:border-[#7A1F2B] focus:ring-1 focus:ring-[#7A1F2B]" />
            <datalist id="topic-names">{names.map((n) => <option key={n.name} value={n.name} />)}</datalist>
            <button type="submit" disabled={busy || !q.trim()} className="rounded-md px-5 text-sm font-semibold text-white disabled:opacity-40" style={{ background: ACCENT }}>İncele</button>
          </form>
          <p className="mt-2 text-sm text-zinc-500">
            Örnek:{' '}
            {QUICK.map((t, i) => (
              <span key={t}>{i > 0 && ', '}<button onClick={() => load(t)} className="text-[#7A1F2B] hover:underline underline-offset-2">{t}</button></span>
            ))}
          </p>
          {err && <p role="alert" className="mt-4 text-sm text-red-800 border-l-4 border-red-700 bg-red-50 px-3 py-2">{err}</p>}
        </div>

        {busy && !rep && <p className="mt-8 flex items-center gap-2 text-sm text-zinc-500"><Loader2 size={14} className="animate-spin" /> Ders programları taranıyor…</p>}

        {rep && (
          <article className={`mt-10 print:mt-0 ${busy ? 'opacity-50' : ''}`}>
            <header className="flex items-end justify-between gap-4 border-b-2 border-[#7A1F2B] pb-2">
              <div>
                <h1 className="text-[28px] font-semibold leading-tight">{rep.topic.name}</h1>
                <p className="text-sm text-zinc-500">UÇEP-2020 çekirdek hastalıklar listesi, madde {rep.topic.no}</p>
              </div>
              <button onClick={() => window.print()} className="print:hidden shrink-0 text-sm text-zinc-600 underline underline-offset-2 hover:text-zinc-900">Yazdır / PDF</button>
            </header>

            <Answer n={1} question={QUESTIONS[0].q(rep.topic.name)} plain={rep.plain.where}>{rep.where.direct.length > 0 && <Where r={rep} />}</Answer>
            <Answer n={2} question={QUESTIONS[1].q(rep.topic.name)} plain={rep.plain.objectives}><Objectives r={rep} /></Answer>
            <Answer n={3} question={QUESTIONS[2].q(rep.topic.name)} plain={rep.plain.repetitions}>
              {rep.topic.curated ? (rep.repetitions.pairs.length > 0 && <Repetitions r={rep} />) : (rep.where.direct.length > 1 && <Where r={rep} />)}
            </Answer>
            <Answer n={4} question={QUESTIONS[3].q(rep.topic.name)} plain={rep.plain.ucep}>{rep.topic.curated && <Ucep r={rep} />}</Answer>

            <p className="mt-6 text-[13px] text-zinc-500">Kaynak: KUSOM 2025–2026 ders programları (2.–5. sınıf).</p>
          </article>
        )}
      </div>
    </div>
  )
}

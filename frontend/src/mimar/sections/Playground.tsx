import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Button, Field, Note, Page, Pill } from '../ui'

const EXAMPLE_LOS = `MSK-A-01 | 2 | MSK Anatomi | Describe the muscles of the rotator cuff and their innervation.
MSK-O-07 | 5 | Ortopedi Stajı | Identify the rotator cuff muscles and their nerve supply during shoulder examination.
MSK-F-04 | 2 | Hareket Fizyolojisi | Explain the regulation of calcium by parathyroid hormone and vitamin D.
MSK-P-02 | 3 | MSK Patoloji | Explain the control of serum calcium by parathyroid hormone and vitamin D.
MSK-P-05 | 3 | MSK Patoloji | Explain the pathogenesis of osteoporosis and bone loss.
MSK-O-11 | 5 | Ortopedi Stajı | Evaluate fracture risk and plan treatment in a patient with osteoporosis and bone loss.
MSK-A-09 | 2 | MSK Anatomi | Describe the boundaries and contents of the carpal tunnel.
MSK-R-03 | 5 | FTR Stajı | Diagnose and manage carpal tunnel syndrome using clinical tests.
MSK-H-06 | 3 | MSK Farmakoloji | Explain the mechanism of action and adverse effects of NSAIDs.
MSK-RH-02 | 5 | Romatoloji Stajı | Describe the adverse effects and mechanism of action of NSAIDs.
MSK-X-01 | 2 | MSK Anatomi | Explain bone.`

const EXAMPLE_UCEP = `UCEP-OST | Osteoporoz: tanı koyar, önleme ve tedaviyi planlar | Diagnose osteoporosis and plan prevention and treatment of bone loss
UCEP-KTS | Karpal tünel sendromu: ön tanı koyar | Make a preliminary diagnosis of carpal tunnel syndrome
UCEP-GUT | Gut: ön tanı koyar ve sevk eder | Make a preliminary diagnosis of gout and refer`

const CAT: Record<string, string> = { redundancy: 'Gereksiz tekrar adayı', gap_ucep: 'UÇEP karşılığı eksik', integration: 'Entegrasyon fırsatı' }
const REASON: Record<string, string> = {
  empty_text: 'boş metin', missing_persistent_id: 'kimlik yok', duplicate_id: 'yinelenen kimlik', missing_source: 'kaynak yok',
  missing_activity: 'etkinlik yok', not_reviewable_too_short: 'incelemeye yetecek içerik yok', duplicate_text_in_same_activity: 'aynı etkinlikte aynı metin',
}
const UCEP_ST: Record<string, [string, 'ok' | 'warn' | 'bad']> = {
  explicit_link: ['kayıtlı bağlantı', 'ok'], candidate_correspondence: ['karşılık bulundu', 'ok'],
  weak_correspondence: ['zayıf karşılık', 'warn'], no_clear_correspondence: ['açık karşılık yok', 'bad'],
}
const METHOD: Record<string, string> = { bm25: 'BM25', embedding: 'Gömme', graph: 'Kavram grafiği' }

function parseLos(txt: string) {
  return txt.split('\n').map((l) => l.trim()).filter(Boolean).map((l, i) => {
    const p = l.split('|').map((x) => x.trim())
    const [uid, year, course, ...rest] = p.length >= 4 ? p : [`L${String(i + 1).padStart(2, '0')}`, '0', '—', p.join(' ')]
    return { uid, year: Number(year) || 0, course, text: rest.join(' | '), activity: uid, source: 'deneme alanı' }
  })
}
function parseUcep(txt: string) {
  return txt.split('\n').map((l) => l.trim()).filter(Boolean).map((l, i) => {
    const [code, tr, en] = l.split('|').map((x) => x.trim())
    return en !== undefined || tr !== undefined ? { code, text_tr: tr ?? '', text_en: en ?? '' } : { code: `U${i + 1}`, text_tr: code, text_en: code }
  })
}

type Turn = { id: number; input: { los: any[]; ucep: any[]; depth: number }; output?: any; error?: string; at: string }

function Output({ o }: { o: any }) {
  return (
    <div className="pg-out">
      <h4>Kalite kontrolü</h4>
      <p>{o.qc.rows_received} hedef alındı · <b>{o.qc.included} analize girdi</b> · {o.qc.excluded} dışlandı
        {o.ucep_qc?.included ? ` · ${o.ucep_qc.included} UÇEP maddesi` : ''}</p>
      {o.qc.excluded_rows.length > 0 && (
        <ul className="pg-list">{o.qc.excluded_rows.map((e: any) => <li key={e.row}><b>{e.uid || `satır ${e.row}`}</b> — {REASON[e.reason] ?? e.reason}{e.text ? `: “${e.text}”` : ''}</li>)}</ul>
      )}
      {o.message && <Note tone="warn">{o.message}</Note>}

      {o.pairs.length > 0 && <>
        <h4>Örtüşebilecek hedef çiftleri</h4>
        <ol className="pg-pairs">
          {o.pairs.map((p: any) => (
            <li key={p.rank}>
              <div className="pg-pair-texts">
                <div><span className="pg-id">{p.a.uid} · {p.a.year}. sınıf · {p.a.course}</span>{p.a.text}</div>
                <div><span className="pg-id">{p.b.uid} · {p.b.year}. sınıf · {p.b.course}</span>{p.b.text}</div>
              </div>
              <div className="pg-why">
                {['bm25', 'embedding', 'graph'].map((m) => <Pill key={m} tone={p.method_ranks[m] ? (p.method_ranks[m] <= 3 ? 'brand' : 'plain') : 'plain'}>{METHOD[m]} {p.method_ranks[m] ? `${p.method_ranks[m]}.` : '—'}</Pill>)}
                {p.evidence.shared_concepts.length > 0 && <span className="m-muted">ortak kavramlar: {p.evidence.shared_concepts.slice(0, 3).join(', ')}</span>}
              </div>
            </li>
          ))}
        </ol>
      </>}

      {o.findings.length > 0 && <>
        <h4>Aday bulgular</h4>
        <ul className="pg-list">{o.findings.map((f: any, i: number) => <li key={i}><Pill tone="brand">{CAT[f.category]}</Pill> {f.statement}</li>)}</ul>
      </>}
      {o.spiral.length > 0 && <>
        <h4>Tekrar sayılmayanlar (olası spiral ilerleme)</h4>
        <ul className="pg-list">{o.spiral.map((s: any) => <li key={s.pair}>{s.pair.replace('|', ' → ')}: {s.years[0]}. sınıftan {s.years[1]}. sınıfa beklenen düzey yükseliyor</li>)}</ul>
      </>}
      {o.ucep_map.length > 0 && <>
        <h4>UÇEP eşlemesi</h4>
        <ul className="pg-list">{o.ucep_map.map((u: any) => <li key={u.code}><Pill tone={UCEP_ST[u.status][1]}>{UCEP_ST[u.status][0]}</Pill> <b>{u.code}</b> {u.text_tr}{u.status !== 'no_clear_correspondence' && u.closest ? ` → ${u.closest}` : ''}</li>)}</ul>
      </>}
      {o.engine && <p className="m-muted m-text-sm">{o.engine.n_los} hedef · {o.engine.embedding} · {o.engine.concepts} kavram · {o.seconds} sn. Deneme alanında yapılan analizler kaydedilmez ve çalışma protokolüne girmez.</p>}
    </div>
  )
}

export default function Playground() {
  const [los, setLos] = useState('')
  const [ucep, setUcep] = useState('')
  const [depth, setDepth] = useState(6)
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [turns])

  const run = async () => {
    const input = { los: parseLos(los), ucep: parseUcep(ucep), depth }
    const id = Date.now()
    setTurns((t) => [...t, { id, input, at: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) }])
    setBusy(true)
    try {
      const output = await api.post('/playground/analyze', input)
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, output } : x)))
    } catch (e: any) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: e.message } : x)))
    } finally { setBusy(false) }
  }

  return (
    <Page title="Deneme alanı" lead="Öğrenme hedeflerini ve UÇEP maddelerini yazın ya da yapıştırın; MİMAR aynı üç yöntemle analiz edip sonucu hemen gösterir. Burada yapılan analizler kaydedilmez.">
      <div className="pg-grid">
        <section className="m-panel pg-input">
          <h3 className="pg-h">Girdi</h3>
          <Field label="Öğrenme hedefleri" hint="Her satıra bir hedef: kimlik | sınıf | ders | hedef metni. Yalnız metin de yazabilirsiniz.">
            <textarea className="m-input pg-ta" rows={11} value={los} onChange={(e) => setLos(e.target.value)}
              placeholder="MSK-A-01 | 2 | MSK Anatomi | Describe the muscles of the rotator cuff…" />
          </Field>
          <Field label="UÇEP maddeleri (isteğe bağlı)" hint="kod | Türkçe metin | İngilizce karşılık">
            <textarea className="m-input pg-ta" rows={4} value={ucep} onChange={(e) => setUcep(e.target.value)}
              placeholder="UCEP-GUT | Gut: ön tanı koyar | Make a preliminary diagnosis of gout" />
          </Field>
          <div className="m-row">
            <Field label="Gösterilecek çift sayısı"><input className="m-input" type="number" min={3} max={50} value={depth} onChange={(e) => setDepth(+e.target.value)} /></Field>
            <Button onClick={() => { setLos(EXAMPLE_LOS); setUcep(EXAMPLE_UCEP) }}>Örnek veriyi doldur</Button>
            <Button kind="primary" busy={busy} disabled={!los.trim()} onClick={run}>Analiz et</Button>
          </div>
        </section>

        <section className="pg-thread" aria-live="polite">
          {turns.length === 0 && <p className="m-empty pg-empty">Girdi yazıp “Analiz et”e bastığınızda sistemin çıktısı burada görünecek.</p>}
          {turns.map((t) => (
            <div key={t.id} className="pg-turn">
              <div className="pg-msg pg-user">
                <div className="pg-who">Girdi · {t.at}</div>
                <p><b>{t.input.los.length} öğrenme hedefi</b>{t.input.ucep.length ? `, ${t.input.ucep.length} UÇEP maddesi` : ''}</p>
                <ul className="pg-list pg-small">
                  {t.input.los.slice(0, 4).map((l) => <li key={l.uid}>{l.uid}: {l.text || <i>(boş)</i>}</li>)}
                  {t.input.los.length > 4 && <li className="m-muted">… ve {t.input.los.length - 4} hedef daha</li>}
                </ul>
              </div>
              <div className="pg-msg pg-system">
                <div className="pg-who">MİMAR çıktısı</div>
                {t.error ? <Note tone="error">{t.error}</Note> : t.output ? <Output o={t.output} /> : <p className="m-muted"><span className="m-spinner" /> Analiz ediliyor…</p>}
              </div>
            </div>
          ))}
          <div ref={end} />
        </section>
      </div>
    </Page>
  )
}

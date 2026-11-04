import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { Button, Field, Note, Pill } from './ui'
import './mimar.css'

const EX_LOS = `MSK-A-01 | 2 | MSK Anatomi | Describe the muscles of the rotator cuff and their innervation.
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
const EX_UCEP = `UCEP-OST | Osteoporoz: tanı koyar, önleme ve tedaviyi planlar | Diagnose osteoporosis and plan prevention and treatment of bone loss
UCEP-KTS | Karpal tünel sendromu: ön tanı koyar | Make a preliminary diagnosis of carpal tunnel syndrome
UCEP-GUT | Gut: ön tanı koyar ve sevk eder | Make a preliminary diagnosis of gout and refer`
const EX_MAT = `MSK-H-06 | Slayt 12: NSAİİ'lerin gastrointestinal yan etkileri; romatolojik hastalarda güvenli reçeteleme.`

const CAT: Record<string, string> = { redundancy: 'Olası gereksiz tekrar', gap_ucep: 'UÇEP karşılığı eksik', integration: 'Bütünleştirme fırsatı' }
const UST: Record<string, [string, 'ok' | 'warn' | 'bad']> = {
  explicit_link: ['kayıtlı bağlantı', 'ok'], candidate_correspondence: ['karşılığı var', 'ok'],
  weak_correspondence: ['zayıf karşılık', 'warn'], no_clear_correspondence: ['açık karşılık yok', 'bad'],
}
const PRI: Record<string, 'bad' | 'warn' | 'plain'> = { yüksek: 'bad', orta: 'warn', düşük: 'plain' }

const parseLos = (t: string) => t.split('\n').map((l) => l.trim()).filter(Boolean).map((l, i) => {
  const p = l.split('|').map((x) => x.trim())
  const [uid, year, course, ...rest] = p.length >= 4 ? p : [`H${String(i + 1).padStart(2, '0')}`, '0', '—', p.join(' ')]
  return { uid, year: Number(year) || 0, course, text: rest.join(' | '), activity: uid, source: 'kullanıcı girdisi' }
})
const parseUcep = (t: string) => t.split('\n').map((l) => l.trim()).filter(Boolean).map((l, i) => {
  const [code, tr, en] = l.split('|').map((x) => x.trim())
  return tr === undefined ? { code: `U${i + 1}`, text_tr: code, text_en: code } : { code, text_tr: tr, text_en: en ?? '' }
})
const parseMat = (t: string) => t.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
  const [uid, ...rest] = l.split('|').map((x) => x.trim())
  return { uid, text: rest.join(' ') }
})

function Output({ o }: { o: any }) {
  const ic = o.input_check
  return (
    <div className="pg-out">
      <p className="ms-summary">{o.summary}</p>
      {ic.excluded.length > 0 && (
        <details className="m-details m-text-sm">
          <summary>{ic.excluded.length} girdi analize alınmadı</summary>
          <ul className="pg-list pg-small">{ic.excluded.slice(0, 60).map((e: any, i: number) => <li key={i}>{e.uid}: {e.text} — {e.reason}</li>)}</ul>
        </details>
      )}

      {o.findings?.length > 0 && <>
        <h4>Önerilen düzenlemeler (öncelik sırasıyla)</h4>
        <div className="ms-cards">
          {o.findings.map((f: any, i: number) => (
            <article key={i} className="ms-card">
              <div className="ms-card-head">
                <Pill tone={PRI[f.priority.level]}>{f.priority.level} öncelik</Pill>
                <Pill>{({ kolay: 'kolay uygulanır', orta: 'orta güçlükte', zor: 'zor uygulanır' } as Record<string, string>)[f.priority.feasibility]}</Pill>
                <span className="ms-cat">{CAT[f.category]}{f.from_material ? ' · ders materyalinden' : ''}</span>
              </div>
              <p className="ms-statement">{f.statement}</p>
              {f.objectives.length > 0 && <ul className="pg-list pg-small">{f.objectives.map((x: any) => <li key={x.uid}><b>{x.uid}</b> · {x.year}. sınıf · {x.course}: {x.text}</li>)}</ul>}
              <p className="ms-proposal"><b>Öneri:</b> {f.proposal.text}</p>
              <details className="m-details">
                <summary>Neden ve paydaşlara sorulacaklar</summary>
                <p className="m-text-sm">{f.rationale} Öncelik gerekçesi: {f.priority.why.join('; ')}; {f.priority.feasibility_reason}.</p>
                <p className="m-text-sm"><b>Öğrencilere:</b> {f.questions['öğrenci']}</p>
                <p className="m-text-sm"><b>Öğretim üyelerine:</b> {f.questions['öğretim_üyesi']}</p>
              </details>
            </article>
          ))}
        </div>
      </>}

      {o.impact && <>
        <h4>Öneriler uygulanırsa</h4>
        <p className="m-text-sm">Kaldırılan: {o.impact.applied.removed_objectives.join(', ') || '—'} · Eklenen: {o.impact.applied.added_objectives.join(', ') || '—'} · Hedef sayısı {o.impact.objectives_before_after[0]} → {o.impact.objectives_before_after[1]}</p>
        <ul className="pg-list">
          <li>{o.impact.removed_links} tekrar bağlantısı ortadan kalkar{o.impact.new_links ? `, ${o.impact.new_links} yeni bağlantı oluşur` : ''}.</li>
          {o.impact.ucep_gained.length > 0 && <li>UÇEP karşılığı kazanan: {o.impact.ucep_gained.join(', ')}.</li>}
          <li>{o.impact.ucep_lost.length ? `UÇEP karşılığı kaybolan: ${o.impact.ucep_lost.join(', ')}.` : 'Hiçbir UÇEP maddesi karşılığını kaybetmez.'}</li>
        </ul>
        {o.impact.warning && <Note tone="warn">{o.impact.warning}</Note>}
      </>}

      {o.overlaps?.length > 0 && <>
        <h4>Örtüşen hedefler</h4>
        <ol className="pg-pairs">
          {o.overlaps.map((p: any, i: number) => (
            <li key={i}>
              <div className="pg-pair-texts">
                <div><span className="pg-id">{p.a.uid} · {p.a.year}. sınıf · {p.a.course} · {p.a.level}</span>{p.a.text}</div>
                <div><span className="pg-id">{p.b.uid} · {p.b.year}. sınıf · {p.b.course} · {p.b.level}</span>{p.b.text}</div>
              </div>
              <div className="pg-why"><Pill tone={p.strength === 'güçlü' ? 'brand' : 'plain'}>{p.strength} örtüşme</Pill><span className="m-muted">{p.agreement} buldu{p.shared.length ? ` · ortak kavramlar: ${p.shared.slice(0, 3).join(', ')}` : ''}</span></div>
            </li>
          ))}
        </ol>
      </>}

      {o.not_problems?.length > 0 && <>
        <h4>Sorun sayılmayan tekrarlar</h4>
        <ul className="pg-list">{o.not_problems.map((s: any) => <li key={s.pair}>{s.pair}: {s.years[0]}. sınıfta {s.levels[0]}, {s.years[1]}. sınıfta {s.levels[1]} düzeyinde — konu ilerleyerek derinleşiyor.</li>)}</ul>
      </>}

      {o.parallel?.length > 0 && <>
        <h4>Aynı kalıpla yazılmış ama farklı içerik öğreten hedefler</h4>
        <ul className="pg-list">{o.parallel.map((p: any, i: number) => <li key={i}>{p.objectives.join(' / ')} — ayıran: {p.differ_by.join(', ')}</li>)}</ul>
      </>}

      {o.reinforcements?.length > 0 && <>
        <h4>Ders ve uygulamada bilinçli pekiştirme (sorun sayılmadı)</h4>
        <ul className="pg-list">{o.reinforcements.map((r: any, i: number) => <li key={i}><b>{r.course}</b>: {r.objectives.join(' / ')}</li>)}</ul>
      </>}

      {o.ucep?.length > 0 && <>
        <h4>UÇEP karşılıkları</h4>
        <ul className="pg-list">{o.ucep.map((u: any) => <li key={u.code}><Pill tone={UST[u.status][1]}>{UST[u.status][0]}</Pill> <b>{u.code}</b> {u.text}{u.closest && u.status !== 'no_clear_correspondence' ? ` → ${u.closest}` : ''}</li>)}</ul>
      </>}

      {o.material && <p className="m-text-sm">Ders materyali: {o.material.objectives_with_material} hedefin materyali kullanıldı, {o.material.new_candidates} ek aday bulundu.</p>}

      {o.reliability && <p className="m-muted m-text-sm ms-rel">{o.reliability.method_agreement} {o.reliability.stability} {o.reliability.note} ({o.seconds} sn)</p>}
    </div>
  )
}

type KBlock = { id: string; code: string; year: number; name: string; topics: number; objectives: number }

function KusomPicker({ onLoad }: { onLoad: (text: string, info: string, rows: any[]) => void }) {
  const [blocks, setBlocks] = useState<KBlock[]>([])
  const [sel, setSel] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.get('/kusom/blocks').then((r) => setBlocks(r.blocks ?? [])).catch(() => setBlocks([])) }, [])
  if (!blocks.length) return null
  const years = Array.from(new Set(blocks.map((b) => b.year)))
  const toggle = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
  const load = async () => {
    setBusy(true)
    try {
      const r = await api.get(`/kusom/los?blocks=${sel.join(',')}`)
      const text = r.rows.map((x: any) => `${x.uid} | ${x.year} | ${x.course} | ${x.text}`).join('\n')
      const nObj = r.rows.filter((x: any) => x.from === 'öğrenim hedefi').length
      onLoad(text, `${r.rows.length} satır yüklendi: ${nObj} öğrenim hedefi, ${r.rows.length - nObj} ders başlığı${r.truncated ? ' (ilk 3000 satır)' : ''}.`, r.rows)
    } finally { setBusy(false) }
  }
  return (
    <div className="ms-kusom">
      <div className="ms-kusom-h">KUSOM 2025–2026 programından yükle</div>
      {years.map((y) => (
        <div key={y} className="ms-kusom-row">
          <span className="ms-kusom-y">{y}. sınıf</span>
          {blocks.filter((b) => b.year === y).map((b) => (
            <button key={b.id} type="button" title={`${b.name} · ${b.topics} konu${b.objectives ? ` · ${b.objectives} öğrenim hedefi` : ''}`}
              className={`ms-chip${sel.includes(b.id) ? ' on' : ''}${b.objectives ? ' lo' : ''}`} onClick={() => toggle(b.id)}>
              {b.code}
            </button>
          ))}
        </div>
      ))}
      <div className="m-row">
        <Button disabled={!sel.length} busy={busy} onClick={load}>Seçili blokları yükle</Button>
        <span className="m-muted m-text-sm">Altı çizili bloklarda yazılı öğrenim hedefi var; diğerlerinde ders başlıkları kullanılır.</span>
      </div>
    </div>
  )
}

type Turn = { id: number; nLos: number; nU: number; nM: number; preview: any[]; at: string; out?: any; err?: string }

export default function MimarAnalyze() {
  const [los, setLos] = useState('')
  const [ucep, setUcep] = useState('')
  const [mat, setMat] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState('')
  const [kusom, setKusom] = useState<{ text: string; rows: any[] } | null>(null)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [turns])

  const run = async () => {
    // rows loaded from the KUSOM data keep their session and session type, unless the text was edited
    const lr = kusom && kusom.text === los ? kusom.rows : parseLos(los)
    const body = { los: lr, ucep: parseUcep(ucep), material: parseMat(mat) }
    const id = Date.now()
    setTurns((t) => [...t, { id, nLos: body.los.length, nU: body.ucep.length, nM: body.material.length, preview: body.los.slice(0, 3),
      at: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) }])
    setBusy(true)
    try {
      const out = await api.post('/analyze', body)
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, out } : x)))
    } catch (e: any) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, err: e.message } : x)))
    } finally { setBusy(false) }
  }

  return (
    <div className="mimar ms-root">
      <main className="m-main">
        <div className="m-page ms-page">
          <div className="pg-grid">
            <section className="m-panel pg-input">
              <h3 className="pg-h">Girdi</h3>
              <KusomPicker onLoad={(t, info, rows) => { setLos(t); setLoaded(info); setKusom({ text: t, rows }) }} />
              {loaded && <p className="m-text-sm ms-loaded">{loaded}</p>}
              <Field label="Öğrenme hedefleri" hint="Her satıra bir hedef: kimlik | sınıf | ders | hedef metni">
                <textarea className="m-input pg-ta" rows={12} value={los} onChange={(e) => setLos(e.target.value)}
                  placeholder="MSK-A-01 | 2 | MSK Anatomi | Describe the muscles of the rotator cuff…" />
              </Field>
              <div className="m-row ms-ucep-row">
                <Button onClick={async () => {
                  const r = await api.get('/ucep2020')
                  setUcep(r.rows.map((x: any) => `${x.code} | ${x.text_tr} | ${x.text_en}`).join('\n'))
                }}>UÇEP 2020 çekirdek hastalıklarını yükle (342 madde)</Button>
              </div>
              <Field label="UÇEP maddeleri (isteğe bağlı)" hint="kod | Türkçe metin | İngilizce karşılık">
                <textarea className="m-input pg-ta" rows={3} value={ucep} onChange={(e) => setUcep(e.target.value)} />
              </Field>
              <Field label="Ders materyali (isteğe bağlı)" hint="hedef kimliği | slayt veya ders notu metni">
                <textarea className="m-input pg-ta" rows={2} value={mat} onChange={(e) => setMat(e.target.value)} />
              </Field>
              <div className="m-row">
                <Button onClick={() => { setLos(EX_LOS); setUcep(EX_UCEP); setMat(EX_MAT) }}>Örnek veriyi doldur</Button>
                <Button kind="primary" busy={busy} disabled={!los.trim()} onClick={run}>Analiz et</Button>
              </div>
            </section>
            <section className="pg-thread" aria-live="polite">
              <h3 className="pg-h">Çıktı</h3>
              {turns.length === 0 && <p className="m-empty pg-empty">Öğrenme hedeflerini girip “Analiz et”e bastığınızda sonuç burada görünecek.</p>}
              {turns.map((t) => (
                <div key={t.id} className="pg-turn">
                  <div className="pg-msg pg-user">
                    <div className="pg-who">Girdi · {t.at}</div>
                    <p><b>{t.nLos} öğrenme hedefi</b>{t.nU ? `, ${t.nU} UÇEP maddesi` : ''}{t.nM ? `, ${t.nM} materyal notu` : ''}</p>
                    <ul className="pg-list pg-small">{t.preview.map((l) => <li key={l.uid}>{l.uid}: {l.text}</li>)}{t.nLos > 3 && <li className="m-muted">… ve {t.nLos - 3} hedef daha</li>}</ul>
                  </div>
                  <div className="pg-msg pg-system">
                    <div className="pg-who">MİMAR</div>
                    {t.err ? <Note tone="error">{t.err}</Note> : t.out ? <Output o={t.out} /> : <p className="m-muted"><span className="m-spinner" /> Analiz ediliyor…</p>}
                  </div>
                </div>
              ))}
              <div ref={end} />
            </section>
          </div>
        </div>
      </main>
    </div>
  )
}

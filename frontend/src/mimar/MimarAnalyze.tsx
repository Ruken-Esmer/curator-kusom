import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { Note, Pill } from './ui'
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
  const main = (o.findings ?? []).filter((f: any) => f.category !== 'gap_ucep')
  const gaps = (o.findings ?? []).filter((f: any) => f.category === 'gap_ucep')
  return (
    <div className="pg-out">
      <p className="ms-summary">{o.summary}</p>
      {ic.excluded.length > 0 && (
        <details className="m-details m-text-sm">
          <summary>{ic.excluded.length} girdi analize alınmadı</summary>
          <ul className="pg-list pg-small">{ic.excluded.slice(0, 60).map((e: any, i: number) => <li key={i}>{e.uid}: {e.text} ({e.reason})</li>)}</ul>
        </details>
      )}

      {main.length > 0 && <>
        <h4>Önerilen düzenlemeler (öncelik sırasıyla)</h4>
        <div className="ms-cards">
          {main.map((f: any, i: number) => (
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
                <summary>Gerekçe ve paydaşlara sorulacaklar</summary>
                <p className="m-text-sm">{f.rationale} Öncelik gerekçesi: {f.priority.why.join('; ')}; {f.priority.feasibility_reason}.</p>
                <p className="m-text-sm"><b>Öğrencilere:</b> {f.questions['öğrenci']}</p>
                <p className="m-text-sm"><b>Öğretim üyelerine:</b> {f.questions['öğretim_üyesi']}</p>
              </details>
            </article>
          ))}
        </div>
      </>}

      {gaps.length > 0 && (
        <details className="m-details" style={{ marginTop: 12 }}>
          <summary>UÇEP’te olup bu hedeflerde açık karşılığı bulunmayan {gaps.length} madde</summary>
          <p className="m-text-sm m-muted">Yalnız bir kısım blok seçildiyse bu liste doğal olarak uzundur; UÇEP karşılaştırması tüm program seçildiğinde anlamlıdır.</p>
          <ul className="pg-list pg-small">{gaps.map((f: any, i: number) => <li key={i}>{f.statement}</li>)}</ul>
        </details>
      )}

      {o.impact && <>
        <h4>Öneriler uygulanırsa</h4>
        <p className="m-text-sm">Kaldırılan hedefler: {o.impact.applied.removed_objectives.join(', ') || 'yok'}. Eklenen hedefler: {o.impact.applied.added_objectives.join(', ') || 'yok'}. Hedef sayısı {o.impact.objectives_before_after[0]} → {o.impact.objectives_before_after[1]}</p>
        <ul className="pg-list">
          <li>{o.impact.removed_links} tekrar bağlantısı ortadan kalkar{o.impact.new_links ? `, ${o.impact.new_links} yeni bağlantı oluşur` : ''}.</li>
          {o.impact.ucep_gained.length > 0 && <li>UÇEP karşılığı kazanan: {o.impact.ucep_gained.join(', ')}.</li>}
          <li>{o.impact.ucep_lost.length ? `UÇEP karşılığı kaybolan: ${o.impact.ucep_lost.join(', ')}.` : 'Hiçbir UÇEP maddesi karşılığını kaybetmez.'}</li>
        </ul>
        {o.impact.warning && <Note tone="warn">{o.impact.warning}</Note>}
      </>}

      <details className="m-details" style={{ marginTop: 16 }}>
        <summary>Diğer sonuçlar (örtüşen hedefler, sorun sayılmayan tekrarlar, UÇEP karşılıkları)</summary>
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
        <ul className="pg-list">{o.not_problems.map((s: any) => <li key={s.pair}>{s.pair}: {s.years[0]}. sınıfta {s.levels[0]}, {s.years[1]}. sınıfta {s.levels[1]} düzeyinde; konu ilerleyerek derinleşiyor.</li>)}</ul>
      </>}

      {o.parallel?.length > 0 && <>
        <h4>Aynı kalıpla yazılmış ama farklı içerik öğreten hedefler</h4>
        <ul className="pg-list">{o.parallel.map((p: any, i: number) => <li key={i}>{p.objectives.join(' / ')} (ayıran: {p.differ_by.join(', ')})</li>)}</ul>
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

      </details>
      {o.reliability && <p className="m-muted m-text-sm ms-rel">{o.reliability.method_agreement} {o.reliability.stability} {o.reliability.note} ({o.seconds} sn)</p>}
    </div>
  )
}


type KBlock = { id: string; code: string; year: number; name: string; topics: number; objectives: number }
const ACCENT = '#7A1F2B'
const Step = ({ n, title, children }: { n: number; title: string; children: any }) => (
  <div className="py-4 border-b border-zinc-200 last:border-b-0">
    <p className="text-[15px] font-semibold mb-2">{n}. {title}</p>{children}
  </div>
)

export default function MimarAnalyze() {
  const [blocks, setBlocks] = useState<KBlock[]>([])
  const [sel, setSel] = useState<string[]>([])
  const [withUcep, setWithUcep] = useState(false)
  const [own, setOwn] = useState({ los: '', ucep: '', mat: '' })
  const [busy, setBusy] = useState('')
  const [out, setOut] = useState<any>(null)
  const [info, setInfo] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const res = useRef<HTMLDivElement>(null)
  useEffect(() => { api.get('/kusom/blocks').then((r) => setBlocks(r.blocks ?? [])).catch(() => setBlocks([])) }, [])
  useEffect(() => { if (out) res.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }, [out])

  const years = Array.from(new Set(blocks.map((b) => b.year)))
  const toggle = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
  const useOwn = own.los.trim().length > 0
  const ready = useOwn || sel.length > 0

  const run = async () => {
    setErr(null); setOut(null)
    try {
      let los: any[]; let ucep: any[] = []
      if (useOwn) {
        los = parseLos(own.los); ucep = parseUcep(own.ucep)
      } else {
        setBusy('Öğrenim hedefleri yükleniyor…')
        const r = await api.get(`/kusom/los?blocks=${sel.join(',')}`)
        los = r.rows
        const nObj = los.filter((x: any) => x.from === 'öğrenim hedefi').length
        setInfo(`${sel.map((id) => blocks.find((b) => b.id === id)?.code).join(', ')}: ${nObj} öğrenim hedefi, ${los.length - nObj} oturum başlığı${r.truncated ? ' (ilk 3000 satır)' : ''}`)
        if (withUcep) ucep = (await api.get('/ucep2020')).rows
      }
      if (useOwn) setInfo(`${los.length} hedef (kendi girdiniz)`)
      setBusy('Hedefler karşılaştırılıyor…')
      setOut(await api.post('/analyze', { los, ucep, material: useOwn ? parseMat(own.mat) : [] }))
    } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-semibold">Müfredat analizi</h1>
        <p className="text-[15px] text-zinc-600 mb-4">Seçilen blokların öğrenim hedefleri birbiriyle ve istenirse UÇEP-2020 ile karşılaştırılır. Olası gereksiz tekrarlar ve eksikler öneri olarak listelenir; son karar müfredat komitesinindir.</p>

        <div className="rounded-md border border-zinc-300 bg-white px-5">
          <Step n={1} title="Bloklar">
            {blocks.length === 0 ? <p className="text-sm text-zinc-400">Blok listesi yüklenemedi.</p> : (
              <div className="flex flex-col gap-2">
                {years.map((y) => (
                  <div key={y} className="flex items-baseline gap-2 flex-wrap">
                    <span className="w-14 shrink-0 text-xs text-zinc-600">{y}. sınıf</span>
                    {blocks.filter((b) => b.year === y).map((b) => (
                      <button key={b.id} type="button" onClick={() => toggle(b.id)} disabled={useOwn}
                        title={`${b.name} · ${b.topics} konu${b.objectives ? ` · ${b.objectives} öğrenim hedefi` : ''}`}
                        className={`ms-chip px-2 py-0.5 rounded-sm text-xs border transition-colors disabled:opacity-40 ${sel.includes(b.id)
                          ? 'border-[#7A1F2B] bg-[#7A1F2B] text-white' : 'border-zinc-300 text-zinc-700 hover:border-zinc-500'}`}>
                        {b.code}{b.objectives ? ' •' : ''}
                      </button>
                    ))}
                  </div>
                ))}
                <p className="text-xs text-zinc-500 mt-1">Nokta (•) işaretli bloklar için yazılı öğrenim hedefi belgesi var. Diğerlerinde oturum başlıkları kullanılır.</p>
              </div>
            )}
          </Step>

          <Step n={2} title="UÇEP-2020 karşılaştırması">
            <label className="flex items-center gap-2 text-sm text-zinc-700">
              <input type="checkbox" checked={withUcep} onChange={(e) => setWithUcep(e.target.checked)} disabled={useOwn} className="accent-[#7A1F2B]" />
              UÇEP-2020 çekirdek hastalıklarıyla karşılaştır (342 madde)
            </label>
            <p className="text-xs text-zinc-500 mt-1">Tüm program ya da bir sınıfın tamamı seçildiğinde anlamlı sonuç verir. Tek blokla yapılan karşılaştırmada maddelerin çoğu eksik görünür.</p>
          </Step>

          <Step n={3} title="Analiz">
            <button onClick={run} disabled={!ready || !!busy}
              className="px-5 py-1.5 rounded-md text-white text-sm font-semibold disabled:opacity-40" style={{ background: ACCENT }}>
              {busy ? 'Analiz sürüyor…' : 'Analiz et'}
            </button>
            {busy && <p className="text-sm text-zinc-500 mt-2"><span className="inline-block w-3 h-3 mr-2 rounded-full border-2 border-zinc-300 border-t-[#7A1F2B] animate-spin align-[-1px]" />{busy}</p>}
            {!ready && !busy && <p className="text-xs text-zinc-500 mt-2">En az bir blok seçin.</p>}
          </Step>
        </div>

        <details className="mt-4 rounded-md border border-zinc-300 bg-white px-5 py-3">
          <summary className="cursor-pointer text-sm">Hedef listesini elle girmek için</summary>
          <div className="flex flex-col gap-3 mt-3 text-sm">
            <p className="text-xs text-zinc-500">Bu alan doluysa blok seçimi yerine buradaki hedefler kullanılır.</p>
            <label>Öğrenim hedefleri <span className="text-zinc-500">(her satırda: kimlik | sınıf | ders | hedef metni)</span>
              <textarea rows={6} value={own.los} onChange={(e) => setOwn({ ...own, los: e.target.value })}
                className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-xs" placeholder="MSK-A-01 | 2 | MSK Anatomi | Describe the muscles of the rotator cuff…" /></label>
            <label>UÇEP maddeleri <span className="text-zinc-500">(isteğe bağlı; kod | Türkçe | İngilizce)</span>
              <textarea rows={2} value={own.ucep} onChange={(e) => setOwn({ ...own, ucep: e.target.value })} className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-xs" /></label>
            <label>Ders materyali <span className="text-zinc-500">(isteğe bağlı; hedef kimliği | metin)</span>
              <textarea rows={2} value={own.mat} onChange={(e) => setOwn({ ...own, mat: e.target.value })} className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-xs" /></label>
            <div className="flex gap-3">
              <button className="text-xs underline text-zinc-600" onClick={() => setOwn({ los: EX_LOS, ucep: EX_UCEP, mat: EX_MAT })}>Örnek veriyi doldur</button>
              {useOwn && <button className="text-xs underline text-zinc-600" onClick={() => setOwn({ los: '', ucep: '', mat: '' })}>Temizle</button>}
            </div>
          </div>
        </details>

        {err && <p role="alert" className="mt-4 text-sm text-red-800 border-l-4 border-red-700 bg-red-50 px-3 py-2">{err}</p>}

        {out && (
          <div ref={res} className="mt-6 scroll-mt-4">
            <h2 className="text-lg font-semibold mb-1">Sonuç</h2>
            <p className="text-xs text-zinc-500 mb-3">{info}</p>
            <div className="mimar rounded-md border border-zinc-300 bg-white p-5" style={{ display: 'block', height: 'auto', overflow: 'visible', background: '#fff' }}>
              <Output o={out} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

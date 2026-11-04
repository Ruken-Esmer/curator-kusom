import { useEffect, useState } from 'react'
import { api } from '../api'
import { useMimar } from '../state'
import { Button, Feedback, Field, Note, Page, Panel, Pill, Select, useAction, useLoad } from '../ui'

const AS1_CHOICES = [['overlap', 'Örtüşme var'], ['no_overlap', 'Örtüşme yok'], ['insufficient', 'Metin yetersiz']]
const TRI = [['yes', 'Evet'], ['no', 'Hayır'], ['insufficient', 'Veri yetersiz']]
const CAT: Record<string, string> = { redundancy: 'Gereksiz tekrar', gap_ucep: 'Eksiklik / UÇEP karşılığı', integration: 'Entegrasyon fırsatı' }

function Progress({ done, total }: { done: number; total: number }) {
  return <><div className="m-progress"><span style={{ width: `${total ? (100 * done) / total : 0}%` }} /></div>
    <span className="m-muted m-text-sm">{done} / {total} karar</span></>
}

function AS1Review({ id, adjudicate }: { id: string; adjudicate?: boolean }) {
  const q = useLoad(() => api.get(adjudicate ? `/samples/${id}/adjudication` : `/samples/${id}/queue`), [id, adjudicate])
  const act = useAction()
  const [i, setI] = useState(0)
  const [local, setLocal] = useState<Record<string, string>>({})
  const items = q.data?.items ?? []
  const it = items[i]
  const val = it ? local[it.code] ?? it.decision : null
  const decide = async (v: string) => {
    if (!it || q.data?.locked) return
    setLocal((l) => ({ ...l, [it.code]: v }))
    try {
      await api.post(`/samples/${id}/${adjudicate ? 'adjudications' : 'decisions'}`, { code: it.code, value: v })
      if (i < items.length - 1) setI(i + 1)
    } catch (e: any) { act.setError(e.message) }
  }
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === 'INPUT' || (e.target as HTMLElement)?.tagName === 'TEXTAREA') return
      if (e.key === '1') decide('overlap'); if (e.key === '2') decide('no_overlap'); if (e.key === '3') decide('insufficient')
      if (e.key === 'ArrowRight') setI((x) => Math.min(items.length - 1, x + 1)); if (e.key === 'ArrowLeft') setI((x) => Math.max(0, x - 1))
    }
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h)
  })
  if (q.error) return <Note tone="error">{q.error}</Note>
  if (!items.length) return <p className="m-empty">{adjudicate ? 'Sonuçlandırılacak uyuşmazlık yok.' : 'Kuyruk boş.'}</p>
  const done = items.filter((x: any) => local[x.code] ?? x.decision).length
  return (
    <Panel title={adjudicate ? 'Uyuşmazlıkları sonuçlandır' : 'Kör inceleme'} aside={q.data?.locked ? <Pill tone="lock">kararlar kilitli</Pill> : <span>{it.code}</span>}>
      <Note tone="info">Yalnız iki hedef metnini inceleyin. Yöntem, puan, sıra ve diğer değerlendiricinin kararı gizlidir. Soru: bu iki hedef aynı veya belirgin ölçüde örtüşen içeriği mi ele alıyor? Eğitsel gereksizlik kararı burada verilmez.</Note>
      <Progress done={done} total={items.length} />
      <div className="m-pair">
        <div className="m-pair-side"><small>Hedef A</small>{it.text_a}</div>
        <div className="m-pair-side"><small>Hedef B</small>{it.text_b}</div>
      </div>
      <div className="m-choice">
        {AS1_CHOICES.map(([v, l], k) => (
          <button key={v} className={val === v ? 'is-on' : ''} onClick={() => decide(v)} disabled={q.data?.locked}>
            {l} <span className="m-kbd">{k + 1}</span></button>))}
      </div>
      <div className="m-row" style={{ marginTop: 12, justifyContent: 'space-between' }}>
        <div className="m-row">
          <Button onClick={() => setI(Math.max(0, i - 1))} disabled={i === 0}>Önceki</Button>
          <Button onClick={() => setI(Math.min(items.length - 1, i + 1))} disabled={i === items.length - 1}>Sonraki</Button>
          <span className="m-muted m-text-sm">{i + 1} / {items.length} · klavye: 1–3, ← →</span>
        </div>
        {!adjudicate && !q.data?.locked && (
          <Button kind="primary" busy={act.busy} disabled={done < items.length}
            onClick={() => act.run(() => api.post(`/samples/${id}/lock`), 'Kararlarınız zaman damgasıyla kilitlendi.')}>Kararlarımı kilitle</Button>)}
      </div>
      <Feedback a={act} />
    </Panel>
  )
}

function PoolValidate({ id }: { id: string }) {
  const q = useLoad(() => api.get(`/pools/${id}/entries`), [id])
  const act = useAction()
  const [i, setI] = useState(0)
  const [form, setForm] = useState<any>({})
  const entries = q.data?.entries ?? []
  const e = entries[i]
  useEffect(() => { if (e) setForm(e.my_decision ?? { support: '', meaningful: '', category_ok: '', suggested_category: '', rationale: '' }) }, [e?.code])
  if (!e) return <p className="m-empty">Havuz boş.</p>
  const locked = e.my_decision?.locked
  const done = entries.filter((x: any) => x.my_decision).length
  const save = async () => {
    const r = await act.run(() => api.post(`/pools/${id}/validations`, { code: e.code, ...form }))
    if (r && i < entries.length - 1) setI(i + 1)
  }
  return (
    <Panel title="Bağımsız doğrulama" aside={<span>{e.code}</span>}>
      <Note tone="info">Bulgunun MİMAR’dan mı uzmanlardan mı geldiği gizlidir. Doğrulanmış sayılması için üç koşul birlikte gerekir: çekirdek veri desteği, eğitsel anlamlılık ve kategori uygunluğu. Uygulanabilirlik bu kararın koşulu değildir.</Note>
      <Progress done={done} total={entries.length} />
      <h4 style={{ margin: '12px 0 4px' }}>{CAT[e.category]}</h4>
      <p style={{ fontSize: 15, margin: '0 0 8px' }}>{e.statement}</p>
      <ul className="m-text-sm">{e.support.map((s: any, k: number) => <li key={k}>{s.lo ? <><b>{s.lo}</b> ({s.year}. sınıf, {s.course}): {s.text}</> : <><b>{s.ucep}</b> {s.text_tr} {s.text_en && <span className="m-muted">/ {s.text_en}</span>}</>}</li>)}</ul>
      <p className="m-muted m-text-sm">Gerekçe: {e.rationale}</p>
      <div className="m-grid m-grid-3">
        <Field label="Çekirdek veri desteği"><Select value={form.support} onChange={(v) => setForm({ ...form, support: v })} options={TRI.map(([v, l]) => ({ value: v, label: l }))} /></Field>
        <Field label="Eğitsel anlamlılık"><Select value={form.meaningful} onChange={(v) => setForm({ ...form, meaningful: v })} options={TRI.map(([v, l]) => ({ value: v, label: l }))} /></Field>
        <Field label="Kategori uygun mu"><Select value={form.category_ok} onChange={(v) => setForm({ ...form, category_ok: v })} options={[{ value: 'yes', label: 'Uygun' }, { value: 'no', label: 'Uygun değil' }]} /></Field>
      </div>
      {form.category_ok === 'no' && <Field label="Önerilen kategori"><Select value={form.suggested_category} onChange={(v) => setForm({ ...form, suggested_category: v })} options={Object.entries(CAT).map(([v, l]) => ({ value: v, label: l }))} /></Field>}
      <Field label="Kısa gerekçe"><textarea className="m-input" value={form.rationale ?? ''} onChange={(x) => setForm({ ...form, rationale: x.target.value })} /></Field>
      <div className="m-row" style={{ marginTop: 10, justifyContent: 'space-between' }}>
        <div className="m-row">
          <Button onClick={() => setI(Math.max(0, i - 1))} disabled={i === 0}>Önceki</Button>
          <Button kind="primary" onClick={save} busy={act.busy} disabled={locked || !form.support || !form.meaningful || !form.category_ok}>Kaydet ve ilerle</Button>
          <Button onClick={() => setI(Math.min(entries.length - 1, i + 1))} disabled={i === entries.length - 1}>Sonraki</Button>
        </div>
        <Button busy={act.busy} disabled={done < entries.length || locked}
          onClick={() => act.run(() => api.post(`/pools/${id}/lock`), 'Doğrulama kararlarınız kilitlendi.')}>Kararlarımı kilitle</Button>
      </div>
      <Feedback a={act} />
    </Panel>
  )
}

function PoolAdjudicate({ id }: { id: string }) {
  const q = useLoad(() => api.get(`/pools/${id}/conflicts`), [id])
  const act = useAction()
  const [sel, setSel] = useState<Record<string, Record<string, string>>>({})
  if (!q.data?.length) return <p className="m-empty">Sonuçlandırılacak uyuşmazlık yok.</p>
  return (
    <Panel title="Doğrulama uyuşmazlıkları">
      {q.data.map((c: any) => (
        <div key={c.code} style={{ borderTop: '1px solid var(--line-2)', padding: '10px 0' }}>
          <b>{c.code}</b> · {CAT[c.entry.category]} — {c.entry.statement}
          <div className="m-row">
            {c.dimensions.map((d: string) => (
              <Field key={d} label={{ support: 'Veri desteği', meaningful: 'Eğitsel anlamlılık', category_ok: 'Kategori' }[d] ?? d}>
                <Select value={sel[c.code]?.[d] ?? ''} onChange={(v) => setSel({ ...sel, [c.code]: { ...sel[c.code], [d]: v } })}
                  options={(d === 'category_ok' ? [['yes', 'Uygun'], ['no', 'Uygun değil']] : TRI).map(([v, l]) => ({ value: v, label: l }))} /></Field>))}
            <Button busy={act.busy} disabled={c.dimensions.some((d: string) => !sel[c.code]?.[d])}
              onClick={() => act.run(() => api.post(`/pools/${id}/adjudications`, { code: c.code, decision: sel[c.code] }), `${c.code} sonuçlandırıldı.`)}>Kaydet</Button>
          </div>
        </div>
      ))}
      <Feedback a={act} />
    </Panel>
  )
}

function AS5Evaluate({ id }: { id: string }) {
  const q = useLoad(() => api.get(`/samples/${id}/as5-queue`), [id])
  const act = useAction()
  const items = (q.data?.items ?? []).filter((x: any) => !x.my || x.my.coordinator === useMimar.getState().user?.username)
  return (
    <Panel title="Aday bulguların eğitsel değerlendirmesi" aside={<span>{items.length} aday</span>}>
      <Note tone="info">Bulgunun eğitsel olarak anlamlı olup olmadığını ve önerilecek düzenlemenin mevcut koşullarda uygulanabilir olup olmadığını ayrı ayrı belirtin. Bu değerlendirme kurul kabulü değildir.</Note>
      {items.slice(0, 40).map((it: any) => (
        <div key={it.item} style={{ borderTop: '1px solid var(--line-2)', padding: '10px 0' }}>
          <Pill tone="brand">{CAT[it.category]}</Pill> <span>{it.statement}</span>
          <div className="m-row" style={{ marginTop: 6 }}>
            {[['Anlamlı ve uygulanabilir', true, true], ['Anlamlı, uygulanamaz', true, false], ['Anlamlı değil', false, false]].map(([l, m, f]: any) => (
              <Button key={l} kind={it.my?.completed && it.my.meaningful === m && it.my.feasible === f ? 'primary' : 'secondary'}
                onClick={() => act.run(() => api.post(`/samples/${id}/as5-evaluations`, { item: it.item, meaningful: m, feasible: f }))}>{l}</Button>))}
            <Button kind="quiet" onClick={() => act.run(() => api.post(`/samples/${id}/as5-evaluations`, { item: it.item, completed: false }))}>Değerlendiremiyorum</Button>
          </div>
        </div>
      ))}
      <Feedback a={act} />
    </Panel>
  )
}

function EffortForm() {
  const act = useAction()
  const [activity, setActivity] = useState('AS1 review')
  const [hours, setHours] = useState('1')
  return (
    <Panel title="Aktif emek kaydı" aside={<span>takvim süresinden ayrı, kişi-saat</span>}>
      <div className="m-row">
        <Field label="Etkinlik"><input className="m-input" value={activity} onChange={(e) => setActivity(e.target.value)} /></Field>
        <Field label="Saat"><input className="m-input" type="number" step="0.25" value={hours} onChange={(e) => setHours(e.target.value)} /></Field>
        <Button busy={act.busy} onClick={() => act.run(() => api.post('/effort', { activity, hours: +hours }), 'Emek kaydedildi.')}>Kaydet</Button>
      </div>
      <Feedback a={act} />
    </Panel>
  )
}

export default function ReviewSection() {
  const mine = useLoad(() => api.get('/samples/mine'), [])
  const [sel, setSel] = useState<string>('')
  const t = (mine.data ?? []).find((x: any) => `${x.kind}:${x.id}:${x.role}` === sel)
  const label = (x: any) => x.kind === 'pool' ? `Doğrulama havuzu (${x.purpose.toUpperCase()}) · ${x.n} bulgu · ${x.role === 'validator' ? 'doğrulayıcı' : 'üçüncü kişi'}`
    : x.kind === 'as5' ? `AS5 adayları · ${x.n}` : `AS1 ${x.part === 'test' ? 'kilitli test' : 'geliştirme'} · ${x.n} çift · ${x.role === 'reviewer' ? 'değerlendirici' : 'üçüncü kişi'}`
  return (
    <Page title="İnceleme görevlerim" lead="Size atanan kör inceleme, doğrulama ve değerlendirme görevleri. Bir sonucu hazırlayan veya uygulayan kişi aynı sonucu bağımsız olarak doğrulayamaz; sistem bu kuralı uygular.">
      <Panel title="Görevler">
        {mine.data?.length ? <Select value={sel} onChange={setSel} options={mine.data.map((x: any) => ({ value: `${x.kind}:${x.id}:${x.role}`, label: label(x) }))} placeholder="Görev seçin" />
          : <p className="m-empty">Size atanmış görev yok.</p>}
      </Panel>
      {t?.kind === 'as1' && <AS1Review id={t.id} adjudicate={t.role === 'adjudicator'} />}
      {t?.kind === 'pool' && (t.role === 'validator' ? <PoolValidate id={t.id} /> : <PoolAdjudicate id={t.id} />)}
      {t?.kind === 'as5' && <AS5Evaluate id={t.id} />}
      <EffortForm />
    </Page>
  )
}

import { useEffect, useState } from 'react'
import { getToken, setToken } from './api'
import { Bar, Button, Field, Note, Pill } from './ui'
import './mimar.css'

const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? '') + '/api/v1/pathway/expert'
async function call(method: string, path: string, body?: unknown) {
  const r = await fetch(BASE + path, { method, headers: { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) })
  const t = await r.text()
  if (!r.ok) { let m = t; try { m = JSON.parse(t).detail } catch { /* text */ } throw new Error(`${r.status}: ${m}`) }
  return JSON.parse(t)
}
const TYPE: Record<string, string> = { tekrar: 'Tekrar', temel: 'Temel → ileri düzey', 'ilişkili': 'İlişkili ön bilgi' }
const WRONG: [string, string][] = [['ilgisiz', 'İki konu ilişkili değil'], ['aslinda_yeni', 'Tekrar değil; sonraki konu yeni ve gerekli'],
  ['aslinda_temel', 'Tekrar değil; temel → ileri düzey'], ['aslinda_tekrar', 'Aslında aynı düzeyde tekrar']]
const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `%${Math.round(v * 100)}`)

function Links({ onChange }: { onChange: () => void }) {
  const [items, setItems] = useState<any[]>([])
  const [i, setI] = useState(0)
  const [wrong, setWrong] = useState(''); const [note, setNote] = useState('')
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { call('GET', '/links').then((l) => { setItems(l); const f = l.findIndex((x: any) => !x.mine); setI(f < 0 ? 0 : f) }).catch((e) => setErr(e.message)) }, [])
  const it = items[i]
  useEffect(() => { setWrong(it?.mine?.wrong_kind ?? ''); setNote(it?.mine?.note ?? '') }, [it?.id])
  if (err) return <Note tone="error">{err}</Note>
  if (!it) return <p className="m-empty">Değerlendirilecek bağlantı yok.</p>
  const done = items.filter((x) => x.mine).length
  const decide = async (decision: string) => {
    try {
      const rec = await call('POST', `/links/${encodeURIComponent(it.id)}`, { decision, wrong_kind: decision === 'uygun_degil' ? wrong : '', note })
      setItems((xs) => xs.map((x) => (x.id === it.id ? { ...x, mine: rec } : x))); setErr(null); onChange()
      if (i < items.length - 1) setI(i + 1)
    } catch (e: any) { setErr(e.message) }
  }
  return (
    <section className="m-panel">
      <header className="m-panel-head"><h3>Konu bağlantısı {i + 1} / {items.length}</h3>
        <div className="m-panel-aside"><Pill tone="brand">{TYPE[it.type]}</Pill>
          {it.reports ? <Pill tone="bad">{it.reports} öğrenci bildirimi</Pill> : null}
          {it.origin_tr && it.origin !== 'geri bildirim' && <Pill tone="plain">{it.origin_tr}</Pill>}
          {it.mine && <Pill tone="ok">değerlendirildi</Pill>}</div></header>
      <div className="m-progress"><span style={{ width: `${(100 * done) / items.length}%` }} /></div>
      <span className="m-muted m-text-sm">{done} / {items.length} bağlantı değerlendirildi</span>
      <div className="m-pair">
        <div className="m-pair-side"><small>Önce gelen · {it.early.block} · {it.early.year}. sınıf</small>{it.early.topic}<Objs o={it.early.objectives} /></div>
        <div className="m-pair-side"><small>Sonra gelen · {it.late.block} · {it.late.year}. sınıf</small>{it.late.topic}<Objs o={it.late.objectives} /></div>
      </div>
      <p className="ex-claim"><b>Sistemin önerisi:</b> {it.claim}</p>
      {it.report_notes?.length > 0 && <p className="m-text-sm ex-report"><b>Öğrenci notu:</b> {it.report_notes.join(' · ')}</p>}
      <div className="m-choice">
        <button className={it.mine?.decision === 'uygun' ? 'is-on' : ''} onClick={() => decide('uygun')}>Uygun</button>
        <button className={it.mine?.decision === 'uygun_degil' ? 'is-on' : ''} disabled={!wrong} onClick={() => decide('uygun_degil')}
          title={!wrong ? 'Önce aşağıdan doğrusunu seçin' : undefined}>Uygun değil</button>
        <button className={it.mine?.decision === 'emin_degilim' ? 'is-on' : ''} onClick={() => decide('emin_degilim')}>Emin değilim</button>
      </div>
      <div className="m-grid m-grid-2" style={{ marginTop: 10 }}>
        <Field label="Uygun değilse doğrusu"><select className="m-input" value={wrong} onChange={(e) => setWrong(e.target.value)}>
          <option value="">Seçin…</option>{WRONG.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
        <Field label="Gerekçe (isteğe bağlı)"><input className="m-input" value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      </div>
      <div className="m-row" style={{ marginTop: 10 }}>
        <Button onClick={() => setI(Math.max(0, i - 1))} disabled={i === 0}>Önceki</Button>
        <Button onClick={() => setI(Math.min(items.length - 1, i + 1))} disabled={i === items.length - 1}>Sonraki</Button>
      </div>
    </section>
  )
}

function Paths({ onChange }: { onChange: () => void }) {
  const [items, setItems] = useState<any[]>([])
  const [sel, setSel] = useState(0)
  const [note, setNote] = useState('')
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { call('GET', '/paths').then(setItems).catch((e) => setErr(e.message)) }, [])
  const p = items[sel]
  useEffect(() => setNote(p?.mine?.note ?? ''), [p?.id])
  if (err) return <Note tone="error">{err}</Note>
  if (!p) return null
  const decide = async (decision: string) => {
    try { const rec = await call('POST', `/paths/${p.id}`, { decision, note }); setItems((xs) => xs.map((x) => (x.id === p.id ? { ...x, mine: rec } : x))); setErr(null); onChange() }
    catch (e: any) { setErr(e.message) }
  }
  const groups: [string, string][] = [['once_tazele', 'Önce tazele'], ['gerekli', 'Gerekli'], ['tekrar', 'Tekrar — hızlı gözden geçir']]
  return (
    <div className="adv-grid">
      <aside className="m-panel adv-list">
        {items.map((x, k) => (
          <button key={x.id} className={`adv-item ${k === sel ? 'is-on' : ''}`} onClick={() => setSel(k)}>
            <span><b>{x.pathway.title}</b></span>
            <span className="m-muted m-text-sm">“{x.goal}”</span>
            {x.mine && <span><Pill tone={x.mine.decision === 'uygun_degil' ? 'bad' : 'ok'}>{({ uygun: 'uygun', kucuk_duzeltme: 'küçük düzeltmeyle uygun', uygun_degil: 'uygun değil' } as any)[x.mine.decision]}</Pill></span>}
          </button>))}
      </aside>
      <section className="m-panel">
        <header className="m-panel-head"><h3>{p.pathway.title}</h3><div className="m-panel-aside">Öğrenci isteği: “{p.goal}”</div></header>
        {groups.map(([k, t]) => {
          const steps = p.pathway.steps.filter((s: any) => s.label === k)
          if (!steps.length) return null
          return <div key={k} className="adv-group"><h4>{t} <span className="m-muted">{steps.length}</span></h4>
            <ol className="adv-steps">{steps.slice(0, 30).map((s: any) => <li key={s.order} className="adv-step adv-step-ro"><div><b>{s.topic}</b> <span className="m-muted">· {s.block_id} · {s.year}. sınıf</span><div className="m-text-sm">{s.reason}</div></div></li>)}
              {steps.length > 30 && <li className="m-muted">… ve {steps.length - 30} konu daha</li>}</ol></div>
        })}
        <div className="adv-decision">
          <Field label="Gerekçe (uygun değilse zorunlu)"><input className="m-input" value={note} onChange={(e) => setNote(e.target.value)} /></Field>
          <div className="m-row">
            <Button kind="primary" onClick={() => decide('uygun')}>Uygun</Button>
            <Button onClick={() => decide('kucuk_duzeltme')}>Küçük düzeltmeyle uygun</Button>
            <Button kind="danger" disabled={!note.trim()} onClick={() => decide('uygun_degil')}>Uygun değil</Button>
          </div>
          {err && <Note tone="error">{err}</Note>}
        </div>
      </section>
    </div>
  )
}

function Status({ s }: { s: any }) {
  if (!s) return null
  const th = s.thresholds
  const C = ({ ok, children }: { ok: boolean; children: any }) => <div className={`ex-cond ${ok ? 'is-ok' : ''}`}><span>{ok ? '✓' : '○'}</span><div>{children}</div></div>
  return (
    <section className="m-panel">
      <header className="m-panel-head"><h3>Yayına geçiş durumu</h3>
        <div className="m-panel-aside">{s.released ? <Pill tone="lock">öğrencilere açılabilir</Pill> : <Pill tone="warn">uzman değerlendirmesi sürüyor</Pill>}</div></header>
      <p className="m-text-sm">{s.progress.links_reviewed} / {s.progress.links_total} bağlantı değerlendirildi · {s.progress.confirmed} onaylandı · {s.progress.rejected} reddedildi (öğrenci yollarından çıkarıldı){s.progress.disagreements ? ` · ${s.progress.disagreements} uyuşmazlık` : ''}</p>
      {s.origins && <p className="m-text-sm m-muted">Kuyruktaki bağlantılar: {Object.values(s.origins).filter((o: any) => o.total).map((o: any) => `${o.label}: ${o.decided}/${o.total}`).join(' · ')}{s.reports ? ` · öğrenci bildirimi: ${s.reports}` : ''}. Oranlar yalnız “tümü inceleniyor” ve “rastgele örnek” bağlantılarından hesaplanır; diğerleri tek tek düzeltilir.</p>}
      <C ok={s.conditions.links}>
        <b>Konu bağlantıları:</b> her türde uygun oranı ≥ {pct(th.link_ok_min)}; tekrar bağlantılarının tümü, diğer türlerde en az {th.min_links_per_type} rastgele bağlantı (%95 GA alt sınırı ≥ {pct(th.link_ci_lower_min)})
        <table className="m-table m-table-dense" style={{ marginTop: 6 }}><thead><tr><th>Tür</th><th className="num">Karara bağlanan</th><th className="num">Uygun oranı</th><th>%95 GA</th><th>Durum</th></tr></thead>
          <tbody>{Object.entries(s.per_type).map(([t, v]: any) => <tr key={t}><td>{TYPE[t]}</td><td className="num">{v.decided} / {v.sampled}</td>
            <td className="num">{pct(v.rate)}<Bar value={v.rate} tone={v.met ? 'ok' : 'brand'} /></td><td>{v.ci95[0] === null ? '—' : `${pct(v.ci95[0])} – ${pct(v.ci95[1])}`}</td><td>{v.status}</td></tr>)}</tbody></table>
      </C>
      <C ok={s.conditions.critical}><b>Kritik hata:</b> “tekrar” denip aslında yeni ve gerekli bulunan oranı ≤ {pct(th.critical_max)} — şu an {pct(s.critical.rate)} ({s.critical.count}/{s.critical.of})</C>
      <C ok={s.conditions.paths}><b>Örnek yollar:</b> uygun ya da küçük düzeltmeyle uygun oranı ≥ {pct(th.path_ok_min)} — şu an {pct(s.paths.ok_rate)} ({s.paths.reviewed}/{s.paths.sampled} yol)</C>
      <C ok={s.conditions.agreement}><b>Uzmanlar arası uyum:</b> Gwet AC1 ≥ {th.ac1_min} — şu an {s.agreement.ac1 ?? '—'} {s.agreement.n ? `(${s.agreement.n} ortak bağlantı)` : '(en az iki uzman gerekli)'}</C>
    </section>
  )
}

const Objs = ({ o }: { o?: string[] }) => (o && o.length ? (
  <ul className="ex-objs">{o.map((x, i) => <li key={i}>{x}</li>)}</ul>
) : null)

export default function ReviewPanel() {
  const [ok, setOk] = useState(!!getToken())
  const [tok, setTok] = useState('')
  const [tab, setTab] = useState<'links' | 'paths' | 'status'>('links')
  const [sum, setSum] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)
  const load = () => call('GET', '/summary').then((s) => { setSum(s); setErr(null) }).catch((e) => { setErr(e.message); if (e.message.startsWith('401')) setOk(false) })
  useEffect(() => { if (ok) load() }, [ok])
  if (!ok) return (
    <div className="mimar ms-root"><div className="m-login"><div className="m-login-card">
      <h1>Uzman değerlendirmesi</h1>
      <p>CURATOR’ın öğrenme yolu önerileri geliştirme aşamasında uzmanlarca değerlendiriliyor. Erişim anahtarınızla giriş yapın.</p>
      <form onSubmit={(e) => { e.preventDefault(); setToken(tok); setOk(true) }} className="m-grid">
        <Field label="Erişim anahtarı"><input className="m-input" type="password" value={tok} onChange={(e) => setTok(e.target.value)} autoFocus /></Field>
        <div><Button type="submit" kind="primary" disabled={!tok}>Giriş yap</Button></div>
      </form>
      {err && <Note tone="error">{err}</Note>}
    </div></div></div>)
  return (
    <div className="mimar ms-root"><main className="m-main"><div className="m-page ms-page">
      <div className="ex-tabs" role="tablist">
        {([['links', 'Konu bağlantıları'], ['paths', 'Örnek yollar'], ['status', 'Yayına geçiş durumu']] as const).map(([k, l]) =>
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'is-on' : ''} onClick={() => setTab(k)}>{l}</button>)}
        {sum && <span className="ex-tabs-aside">{sum.released ? <Pill tone="lock">öğrencilere açılabilir</Pill> : <Pill tone="warn">uzman değerlendirmesi sürüyor</Pill>}</span>}
      </div>
      {err && <Note tone="error">{err}</Note>}
      {tab === 'links' && <Links onChange={load} />}
      {tab === 'paths' && <Paths onChange={load} />}
      {tab === 'status' && <Status s={sum} />}
    </div></main></div>
  )
}

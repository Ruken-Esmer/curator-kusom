import { useEffect, useState } from 'react'
import { getToken, setToken } from './api'

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
const pct = (v: number | null | undefined) => (v === null || v === undefined ? 'henüz yok' : `%${Math.round(v * 100)}`)

const ACCENT = '#7A1F2B'
const Err = ({ children }: { children: any }) => <p role="alert" className="text-sm text-red-800 border-l-4 border-red-700 bg-red-50 px-3 py-2">{children}</p>
const Btn = ({ kind = 'plain', className = '', ...p }: any) => (
  <button {...p} className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors disabled:opacity-40 ${kind === 'primary'
    ? 'text-white hover:opacity-90' : kind === 'on' ? 'border border-[#7A1F2B] text-white bg-[#7A1F2B]'
    : 'border border-zinc-300 hover:bg-zinc-50 text-zinc-700'} ${className}`}
    style={kind === 'primary' ? { background: ACCENT } : undefined} />
)
const Card = ({ children, className = '' }: any) => <div className={`rounded-md border border-zinc-300 bg-white p-5 ${className}`}>{children}</div>

function Links({ onChange }: { onChange: () => void }) {
  const [items, setItems] = useState<any[]>([])
  const [i, setI] = useState(0)
  const [rejecting, setRejecting] = useState(false)
  const [wrong, setWrong] = useState(''); const [note, setNote] = useState('')
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { call('GET', '/links').then((l) => { setItems(l); const f = l.findIndex((x: any) => !x.mine); setI(f < 0 ? 0 : f) }).catch((e) => setErr(e.message)) }, [])
  const it = items[i]
  useEffect(() => { setWrong(it?.mine?.wrong_kind ?? ''); setNote(it?.mine?.note ?? ''); setRejecting(it?.mine?.decision === 'uygun_degil') }, [it?.id])
  if (err && !it) return <Err>{err}</Err>
  if (!it) return <p className="text-sm text-zinc-500 text-center py-10">Değerlendirilecek bağlantı yok.</p>
  const done = items.filter((x) => x.mine).length
  const decide = async (decision: string) => {
    try {
      const rec = await call('POST', `/links/${encodeURIComponent(it.id)}`, { decision, wrong_kind: decision === 'uygun_degil' ? wrong : '', note })
      setItems((xs) => xs.map((x) => (x.id === it.id ? { ...x, mine: rec } : x))); setErr(null); onChange()
      if (i < items.length - 1) setI(i + 1)
    } catch (e: any) { setErr(e.message) }
  }
  const Side = ({ t, s }: { t: string; s: any }) => (
    <div className="flex-1 border border-zinc-200 bg-zinc-50 p-3">
      <p className="text-xs text-zinc-500 mb-1">{t}: {s.year}. sınıf, {s.block}</p>
      <p className="font-medium">{s.topic}</p>
      {s.objectives?.length > 0 && <ul className="mt-2 list-disc pl-4 text-xs text-zinc-600">{s.objectives.map((x: string, k: number) => <li key={k}>{x}</li>)}</ul>}
    </div>
  )
  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="flex justify-between text-xs text-zinc-500 mb-1.5">
          <span>{done} / {items.length} değerlendirildi</span>
          <span>{TYPE[it.type]}{it.origin_tr ? `, ${it.origin_tr}` : ''}{it.mine ? ' (kararınız kayıtlı)' : ''}</span>
        </div>
        <div className="h-1 bg-zinc-200 overflow-hidden"><div className="h-full" style={{ width: `${(100 * done) / items.length}%`, background: ACCENT }} /></div>
      </div>

      <Card>
        <p className="text-xs text-zinc-500 mb-3">{i + 1}. bağlantı</p>
        <div className="flex gap-3 items-stretch">
          <Side t="Önce" s={it.early} />
          <div className="self-center text-zinc-400">→</div>
          <Side t="Sonra" s={it.late} />
        </div>
        <p className="mt-4 text-[15px]"><span className="font-semibold">Önerilen ilişki: </span>{it.claim}</p>

        <p className="mt-5 mb-2 text-sm font-semibold">Değerlendirmeniz</p>
        <div className="flex gap-2 flex-wrap">
          <Btn kind={it.mine?.decision === 'uygun' ? 'on' : 'plain'} onClick={() => decide('uygun')}>Uygun</Btn>
          <Btn kind={rejecting ? 'on' : 'plain'} onClick={() => setRejecting(true)}>Uygun değil</Btn>
          <Btn kind={it.mine?.decision === 'emin_degilim' ? 'on' : 'plain'} onClick={() => decide('emin_degilim')}>Emin değilim</Btn>
        </div>

        {rejecting && (
          <div className="mt-4 border-t border-zinc-200 pt-4 flex flex-col gap-3">
            <label className="text-sm">Doğru ilişki
              <select className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm" value={wrong} onChange={(e) => setWrong(e.target.value)}>
                <option value="">Seçin…</option>{WRONG.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className="text-sm">Gerekçe <span className="text-zinc-400">(isteğe bağlı)</span>
              <input className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm" value={note} onChange={(e) => setNote(e.target.value)} />
            </label>
            <div><Btn kind="primary" disabled={!wrong} onClick={() => decide('uygun_degil')}>Kaydet</Btn></div>
          </div>
        )}
        {err && <div className="mt-3"><Err>{err}</Err></div>}
      </Card>

      <div className="flex justify-between text-sm">
        <button className="text-zinc-500 hover:text-zinc-900 disabled:opacity-30" disabled={i === 0} onClick={() => setI(i - 1)}>← Önceki</button>
        <button className="text-zinc-500 hover:text-zinc-900 disabled:opacity-30" disabled={i === items.length - 1} onClick={() => setI(i + 1)}>Sonraki →</button>
      </div>
    </div>
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
  if (err && !p) return <Err>{err}</Err>
  if (!p) return null
  const decide = async (decision: string) => {
    try { const rec = await call('POST', `/paths/${p.id}`, { decision, note }); setItems((xs) => xs.map((x) => (x.id === p.id ? { ...x, mine: rec } : x))); setErr(null); onChange() }
    catch (e: any) { setErr(e.message) }
  }
  const groups: [string, string][] = [['once_tazele', 'Önce tazele'], ['gerekli', 'Gerekli'], ['tekrar', 'Tekrar (hızlı gözden geçirme)']]
  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2 flex-wrap">
        {items.map((x, k) => (
          <button key={x.id} onClick={() => setSel(k)}
            className={`px-2.5 py-1 rounded-sm text-sm border ${k === sel ? 'border-[#7A1F2B] text-[#7A1F2B] font-semibold' : 'border-zinc-300 text-zinc-600 hover:bg-zinc-50'}`}>
            {x.pathway.title}{x.mine ? ' (değerlendirildi)' : ''}
          </button>))}
      </div>
      <Card>
        <p className="text-sm mb-4"><span className="font-semibold">Öğrencinin yazdığı: </span>{p.goal}</p>
        {groups.map(([k, t]) => {
          const steps = p.pathway.steps.filter((s: any) => s.label === k)
          if (!steps.length) return null
          return (
            <details key={k} className="border-t border-zinc-200 py-2" open={k === 'gerekli'}>
              <summary className="cursor-pointer text-sm font-medium py-1">{t} <span className="text-zinc-400">({steps.length})</span></summary>
              <ol className="mt-2 mb-1 flex flex-col gap-2 text-sm">
                {steps.slice(0, 30).map((s: any) => <li key={s.order}><span className="font-medium">{s.topic}</span> <span className="text-zinc-400">· {s.block_id} · {s.year}. sınıf</span><div className="text-xs text-zinc-500">{s.reason}</div></li>)}
                {steps.length > 30 && <li className="text-zinc-400">… ve {steps.length - 30} konu daha</li>}
              </ol>
            </details>
          )
        })}
        <p className="mt-5 mb-2 text-sm font-semibold">Değerlendirmeniz</p>
        <div className="flex gap-2 flex-wrap">
          <Btn kind={p.mine?.decision === 'uygun' ? 'on' : 'plain'} onClick={() => decide('uygun')}>Uygun</Btn>
          <Btn kind={p.mine?.decision === 'kucuk_duzeltme' ? 'on' : 'plain'} onClick={() => decide('kucuk_duzeltme')}>Küçük düzeltmeyle uygun</Btn>
          <Btn kind={p.mine?.decision === 'uygun_degil' ? 'on' : 'plain'} disabled={!note.trim()} onClick={() => decide('uygun_degil')}
            title={!note.trim() ? 'Önce gerekçe yazın' : undefined}>Uygun değil</Btn>
        </div>
        <label className="block mt-3 text-sm">Gerekçe <span className="text-zinc-400">(“uygun değil” için gerekli)</span>
          <input className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm" value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        {err && <div className="mt-3"><Err>{err}</Err></div>}
      </Card>
    </div>
  )
}

function Status({ s }: { s: any }) {
  if (!s) return null
  const th = s.thresholds
  const rows: [boolean, string, string][] = [
    [s.conditions.links, 'Konu bağlantıları', `Her türde en az ${pct(th.link_ok_min)} uygun bulunmalı`],
    [s.conditions.critical, 'Kritik hata', `Tekrar sayılıp aslında yeni olan konular en fazla ${pct(th.critical_max)}; şu an ${pct(s.critical.rate)}`],
    [s.conditions.paths, 'Örnek yollar', `En az ${pct(th.path_ok_min)} uygun; şu an ${pct(s.paths.ok_rate)}, ${s.paths.reviewed}/${s.paths.sampled} yol incelendi`],
    [s.conditions.agreement, 'Uzmanlar arası uyum', `Gwet AC1 en az ${th.ac1_min}; şu an ${s.agreement.ac1 ?? 'hesaplanmadı'}`],
  ]
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <p className="text-[15px] font-semibold">{s.released ? 'Öğrenme yolu önerileri öğrencilere açılabilir.' : 'Öğrenme yolu önerileri henüz öğrencilere açılmadı.'}</p>
        <p className="text-sm text-zinc-500 mt-1">
          {s.progress.links_reviewed} / {s.progress.links_total} bağlantı değerlendirildi, {s.progress.confirmed} onaylandı, {s.progress.rejected} reddedildi
          {s.progress.disagreements ? `, ${s.progress.disagreements} uyuşmazlık var` : ''}. Bir bağlantının değişmesi için iki uzmanın aynı kararı vermesi gerekir.
        </p>
        <table className="w-full text-sm mt-4 border-t border-zinc-200">
          <tbody>{rows.map(([ok, t, d]) => (
            <tr key={t} className="border-b border-zinc-200">
              <td className="py-2 pr-3 font-medium">{t}</td>
              <td className="py-2 pr-3 text-zinc-500">{d}</td>
              <td className={`py-2 text-right whitespace-nowrap ${ok ? 'text-emerald-700' : 'text-zinc-500'}`}>{ok ? 'sağlandı' : 'sağlanmadı'}</td>
            </tr>))}</tbody>
        </table>
      </Card>
      <details className="rounded-md border border-zinc-300 bg-white px-5 py-3">
        <summary className="cursor-pointer text-sm">Türlere göre oranlar</summary>
        <table className="w-full text-sm mt-3">
          <thead><tr className="text-left text-xs text-zinc-500"><th className="py-1">Tür</th><th>Karara bağlanan</th><th>Uygun oranı</th><th>%95 GA</th></tr></thead>
          <tbody>{Object.entries(s.per_type).map(([t, v]: any) => (
            <tr key={t} className="border-t border-zinc-100"><td className="py-1.5">{TYPE[t]}</td><td>{v.decided} / {v.sampled}</td><td>{pct(v.rate)}</td>
              <td>{v.ci95[0] === null ? '' : `${pct(v.ci95[0])} – ${pct(v.ci95[1])}`}</td></tr>))}</tbody>
        </table>
        {s.origins && <p className="text-xs text-zinc-500 mt-3">Uzmanlar önce bütün tekrar önerilerini görür; diğer türlerden rastgele örnek alınır. Oranlar yalnız bu iki gruptan hesaplanır; örnek yol bağlantıları tek tek düzeltilir.
          ({Object.values(s.origins).filter((o: any) => o.total).map((o: any) => `${o.label}: ${o.decided}/${o.total}`).join(' · ')})</p>}
      </details>
    </div>
  )
}

export default function ReviewPanel() {
  const [ok, setOk] = useState(!!getToken())
  const [tok, setTok] = useState('')
  const [tab, setTab] = useState<'links' | 'paths' | 'status'>('links')
  const [sum, setSum] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)
  const load = () => call('GET', '/summary').then((s) => { setSum(s); setErr(null) }).catch((e) => {
    if (e.message.startsWith('401')) { setOk(false); setErr('Erişim anahtarı geçersiz. Lütfen kontrol edip yeniden deneyin.') }
    else if (e.message.startsWith('403')) { setOk(false); setErr('Bu anahtar uzman incelemesine yetkili değil.') }
    else setErr(e.message)
  })
  useEffect(() => { if (ok) load() }, [ok])

  if (!ok) return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-md mx-auto px-6 pt-16">
        <h1 className="text-2xl font-semibold mb-2">Uzman incelemesi</h1>
        <p className="text-[15px] text-zinc-600 mb-6">Bu bölüm öğrenme yolu önerilerini değerlendiren öğretim üyeleri içindir. Size iletilen erişim anahtarıyla giriş yapın.</p>
        <form onSubmit={(e) => { e.preventDefault(); setToken(tok); setOk(true) }} className="flex flex-col gap-3">
          <input type="password" aria-label="Erişim anahtarı" placeholder="Erişim anahtarı" value={tok} onChange={(e) => setTok(e.target.value)} autoFocus
            className="rounded-md border border-zinc-300 px-3 py-2 focus:outline-none focus:border-[#7A1F2B] focus:ring-1 focus:ring-[#7A1F2B]" />
          <Btn type="submit" kind="primary" disabled={!tok} className="self-start">Giriş yap</Btn>
        </form>
        {err && <div className="mt-3"><Err>{err}</Err></div>}
      </div>
    </div>
  )

  const TABS = [['links', 'Konu bağlantıları'], ['paths', 'Örnek yollar'], ['status', 'Durum']] as const
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-semibold">Uzman incelemesi</h1>
        <p className="text-[15px] text-zinc-600 mb-5">Her bağlantı için iki konu arasında önerilen ilişkinin doğru olup olmadığını işaretleyin. Kaydettiğinizde sıradaki bağlantıya geçilir.</p>
        <div className="flex gap-6 mb-6 border-b border-zinc-300" role="tablist">
          {TABS.map(([k, l]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
              className={`pb-2 -mb-px text-sm border-b-2 ${tab === k ? 'border-[#7A1F2B] font-semibold text-zinc-900' : 'border-transparent text-zinc-500 hover:text-zinc-800'}`}>{l}</button>))}
        </div>
        {err && <div className="mb-4"><Err>{err}</Err></div>}
        {tab === 'links' && <Links onChange={load} />}
        {tab === 'paths' && <Paths onChange={load} />}
        {tab === 'status' && <Status s={sum} />}
      </div>
    </div>
  )
}

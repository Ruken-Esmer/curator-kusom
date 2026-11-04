import { useEffect, useState } from 'react'
import { api, getToken, setToken } from './api'
import { hasRole, Section, useMimar } from './state'
import { Button, Field, Note, useLoad } from './ui'
import './mimar.css'
import Overview from './sections/Overview'
import DataSection from './sections/Data'
import AnalysisSection from './sections/Analysis'
import PlanSection from './sections/Plan'
import ReviewSection from './sections/Review'
import FindingsSection from './sections/Findings'
import ValidationSection from './sections/Validation'
import AS5Section from './sections/AS5'
import ImpactSection from './sections/Impact'
import StatsSection from './sections/Stats'
import AuditSection from './sections/Audit'
import PeopleSection from './sections/People'
import Playground from './sections/Playground'

type Item = { id: Section; label: string; step?: string; doneKey?: (o: any) => boolean; lockKey?: (o: any) => string | null }

const STUDY: Item[] = [
  { id: 'data', label: 'Veri ve kalite kontrolü', step: '1', doneKey: (o) => o?.frozen_datasets > 0, lockKey: (o) => o?.frozen_datasets ? `${o.frozen_datasets} sürüm donduruldu` : null },
  { id: 'analysis', label: 'AS1 · Örtüşme analizi', step: '2', doneKey: (o) => o?.analyses > 0 },
  { id: 'plan', label: 'AS1 · Ön kayıt ve örneklem', step: '3', doneKey: (o) => o?.plans_locked > 0, lockKey: (o) => o?.plans_locked ? 'plan kilitli' : null },
  { id: 'findings', label: 'AS2 · Raporlar', step: '4', doneKey: (o) => o?.reports > 0 },
  { id: 'validation', label: 'AS2 · Kör doğrulama', step: '5', doneKey: (o) => o?.pools > 0 },
  { id: 'as5', label: 'AS5 · Koordinatör değerlendirmesi', step: '6' },
  { id: 'impact', label: 'AS6 · Değişiklik etkisi', step: '7', doneKey: (o) => o?.changesets > 0 },
]
const WORK: Item[] = [
  { id: 'playground', label: 'Deneme alanı' },
  { id: 'review', label: 'İnceleme görevlerim' },
  { id: 'stats', label: 'Güç ve uyum hesapları' },
  { id: 'audit', label: 'Denetim günlüğü' },
  { id: 'people', label: 'Kişiler ve roller' },
]

function Login() {
  const setUser = useMimar((s) => s.setUser)
  const [tok, setTok] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [demo, setDemo] = useState<Record<string, string> | null>(null)
  const [busy, setBusy] = useState(false)

  const login = async (t: string) => {
    setErr(null); setToken(t)
    try { setUser(await api.get('/me')) } catch (e: any) { setToken(''); setErr(e.message) }
  }
  const runDemo = async () => {
    setBusy(true); setErr(null); setToken(tok)
    try {
      const s = await api.post('/demo/run?quick=true')
      setDemo(s.users)
      await login(tok)
    } catch (e: any) { setErr(e.message); setToken('') } finally { setBusy(false) }
  }
  return (
    <div className="m-login">
      <div className="m-login-card">
        <h1>MİMAR</h1>
        <p>Müfredat ilişkilerinin uzman denetimli analizi. Ekip üyesi olarak size verilen erişim anahtarıyla giriş yapın; gördüğünüz ekranlar rolünüze göre değişir.</p>
        <form onSubmit={(e) => { e.preventDefault(); login(tok) }} className="m-grid">
          <Field label="Erişim anahtarı" hint="Geliştirme ortamında yönetici anahtarı: dev-admin-token">
            <input className="m-input" type="password" value={tok} onChange={(e) => setTok(e.target.value)} autoFocus />
          </Field>
          <div className="m-row">
            <Button type="submit" kind="primary" disabled={!tok}>Giriş yap</Button>
            <Button onClick={runDemo} busy={busy} disabled={!tok}
              title="Yönetici anahtarı gerekir; sentetik veriyle tüm aşamaları simüle eder">Sentetik demoyu kur</Button>
          </div>
        </form>
        {err && <Note tone="error">{err}</Note>}
        {demo && (
          <Note tone="info">
            Demo kuruldu. Bir role geçmek için seçin:
            <div className="m-demo-users">
              {Object.entries(demo).filter(([u]) => !u.startsWith('coord') || u === 'coord01').map(([u, t]) =>
                <Button key={u} kind="secondary" onClick={() => login(t)}>{u}</Button>)}
            </div>
          </Note>
        )}
      </div>
    </div>
  )
}

export default function MimarApp() {
  const { user, setUser, section, go } = useMimar()
  const [checked, setChecked] = useState(false)
  useEffect(() => {
    if (getToken() && !user) api.get('/me').then(setUser).catch(() => setToken('')).finally(() => setChecked(true))
    else setChecked(true)
  }, [user, setUser])
  const ov = useLoad(() => (user ? api.get('/overview') : Promise.resolve(null)), [user?.username])

  if (!checked) return <div className="mimar" />
  if (!user) return <div className="mimar"><Login /></div>

  const isStaff = hasRole(user, 'admin', 'technical', 'observer')
  const o = ov.data
  const rail = (items: Item[]) => items.map((it) => (
    <button key={it.id} className={`m-rail-item ${section === it.id ? 'is-active' : ''}`} onClick={() => go(it.id)}
      aria-current={section === it.id ? 'page' : undefined}>
      <span className={`m-rail-step ${it.step ? (it.doneKey?.(o) ? 'is-done' : '') : 'is-plain'}`}>{it.step ?? '·'}</span>
      <span>{it.label}</span>
      <span className="m-rail-lock">{it.lockKey?.(o) ? '🔒' : ''}</span>
    </button>
  ))

  const view = {
    overview: <Overview overview={o} />, data: <DataSection />, analysis: <AnalysisSection />, plan: <PlanSection />,
    review: <ReviewSection />, findings: <FindingsSection />, validation: <ValidationSection />, as5: <AS5Section />,
    impact: <ImpactSection />, playground: <Playground />, stats: <StatsSection />, audit: <AuditSection />, people: <PeopleSection />,
  }[section]

  return (
    <div className="mimar">
      <aside className="m-rail">
        <div className="m-rail-brand">
          <h1>MİMAR</h1>
          <p>KUSOM · uzman denetimli müfredat analizi (araştırma prototipi)</p>
        </div>
        <nav aria-label="MİMAR bölümleri">
          <button className={`m-rail-item ${section === 'overview' ? 'is-active' : ''}`} onClick={() => go('overview')}>
            <span className="m-rail-step is-plain">◎</span><span>Genel durum</span><span />
          </button>
          {isStaff && <div className="m-rail-group">Araştırma akışı</div>}
          {isStaff ? rail(STUDY) : null}
          <div className="m-rail-group">Çalışma alanı</div>
          {rail(isStaff ? WORK : WORK.filter((w) => ['playground', 'review', 'stats'].includes(w.id)).concat(
            hasRole(user, 'expert') ? [{ id: 'findings', label: 'Uzman raporu' }] :
            hasRole(user, 'standardizer', 'validator', 'adjudicator') ? [{ id: 'validation', label: 'Kör doğrulama' }] :
            hasRole(user, 'impact_evaluator') ? [{ id: 'impact', label: 'Beklenen etkiler' }] : []))}
        </nav>
        <div className="m-rail-user">
          <strong>{user.display_name}</strong>
          {user.roles.join(', ')}
          <div><button onClick={() => { setToken(''); setUser(null) }}>Çıkış</button></div>
        </div>
      </aside>
      <main className="m-main">{view}</main>
    </div>
  )
}

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
import { ProjectHome, WorkPackagePage } from './sections/WorkPackages'
import MimarAnalyze from './MimarAnalyze'
import OsteoScenario from './sections/OsteoScenario'
import { WORK_PACKAGES, type WorkPackage } from './workPackages'

type Item = { id: Section; label: string; step?: string; doneKey?: (o: any) => boolean; lockKey?: (o: any) => string | null }

// the study is organised by the six work packages of the application; each lists the screens it uses
const PACKAGES: { wp: WorkPackage['id']; items: Item[] }[] = [
  { wp: 'wp1', items: [
    { id: 'data', label: 'Veri ve kalite kontrolü', lockKey: (o) => o?.frozen_datasets ? 'donduruldu' : null },
    { id: 'analysis', label: 'Örtüşme analizi' },
    { id: 'plan', label: 'Ön kayıt ve kilitli örneklem', lockKey: (o) => o?.plans_locked ? 'kilitli' : null },
  ] },
  { wp: 'wp2', items: [{ id: 'findings', label: 'Raporlar' }, { id: 'validation', label: 'Kör doğrulama' }] },
  { wp: 'wp3', items: [] },
  { wp: 'wp4', items: [{ id: 'scan', label: 'Müfredat taraması' }, { id: 'as5', label: 'Koordinatör değerlendirmesi' }] },
  { wp: 'wp5', items: [{ id: 'impact', label: 'Değişiklik etkisi' }] },
  { wp: 'wp6', items: [] },
]
const WORK: Item[] = [
  { id: 'overview', label: 'Sonuçlar ve denetim zinciri' },
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
  const runDemo = async (path = '/demo/run?quick=true') => {
    setBusy(true); setErr(null); setToken(tok)
    try {
      const s = await api.post(path)
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
            <Button onClick={() => runDemo('/demo/osteoartrit')} busy={busy} disabled={!tok}
              title="Yönetici anahtarı gerekir; gerçek KUSOM MSKL oturumlarıyla tüm aşamaları örnek kişilerle çalıştırır">Osteoartrit örneğini kur</Button>
            <Button onClick={() => runDemo()} busy={busy} disabled={!tok}
              title="Yönetici anahtarı gerekir; sentetik veriyle tüm aşamaları simüle eder">Sentetik demoyu kur</Button>
          </div>
        </form>
        {err && <Note tone="error">{err}</Note>}
        {demo && (
          <Note tone="info">
            Demo kuruldu. Bir role geçmek için seçin:
            <div className="m-demo-users">
              {Object.entries(demo).filter(([u]) => !/^(coord|koordinator)/.test(u) || u === 'coord01' || u === 'koordinator01').map(([u, t]) =>
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
    home: <ProjectHome overview={o} />, senaryo: <OsteoScenario />, scan: <MimarAnalyze />,
    wp1: <WorkPackagePage id="wp1" overview={o} />, wp2: <WorkPackagePage id="wp2" overview={o} />, wp3: <WorkPackagePage id="wp3" overview={o} />,
    wp4: <WorkPackagePage id="wp4" overview={o} />, wp5: <WorkPackagePage id="wp5" overview={o} />, wp6: <WorkPackagePage id="wp6" overview={o} />,
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
          <button className={`m-rail-item ${section === 'home' ? 'is-active' : ''}`} onClick={() => go('home')}>
            <span className="m-rail-step is-plain">◎</span><span>Proje özeti</span><span />
          </button>
          <button className={`m-rail-item ${section === 'senaryo' ? 'is-active' : ''}`} onClick={() => { useMimar.getState().setStep(0); go('senaryo') }}>
            <span className="m-rail-step is-plain">→</span><span>Örnek: osteoartrit</span><span />
          </button>
          {isStaff && <div className="m-rail-group">İş paketleri</div>}
          {isStaff && PACKAGES.map(({ wp, items }) => {
            const w = WORK_PACKAGES.find((x) => x.id === wp)!
            const open = section === wp || items.some((i) => i.id === section)
            return (
              <div key={wp}>
                <button className={`m-rail-item ${section === wp ? 'is-active' : ''}`} onClick={() => go(wp)} aria-current={section === wp ? 'page' : undefined}>
                  <span className="m-rail-step">{w.no}</span>
                  <span>{w.short}<span className="m-rail-months">{w.months[0]}–{w.months[1]}. ay</span></span>
                  <span />
                </button>
                {open && items.map((it) => (
                  <button key={it.id} className={`m-rail-item m-rail-sub ${section === it.id ? 'is-active' : ''}`} onClick={() => go(it.id)}
                    aria-current={section === it.id ? 'page' : undefined}>
                    <span /><span>{it.label}</span><span className="m-rail-lock">{it.lockKey?.(o) ? '🔒' : ''}</span>
                  </button>
                ))}
              </div>
            )
          })}
          <div className="m-rail-group">Araçlar</div>
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

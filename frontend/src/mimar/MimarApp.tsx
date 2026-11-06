import { useEffect, useState } from 'react'
import { api, getToken, setToken } from './api'
import { useMimar } from './state'
import { Button, Field, Note } from './ui'
import './mimar.css'
import Prototype, { SCREENS, type ScreenId } from './Prototype'

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
  const { user, setUser } = useMimar()
  const [screen, setScreen] = useState<ScreenId>('veriler')
  const [checked, setChecked] = useState(false)
  useEffect(() => {
    if (getToken() && !user) api.get('/me').then(setUser).catch(() => setToken('')).finally(() => setChecked(true))
    else setChecked(true)
  }, [user, setUser])

  if (!checked) return <div className="mimar" />
  if (!user) return <div className="mimar"><Login /></div>

  return (
    <div className="mimar">
      <aside className="m-rail">
        <div className="m-rail-brand">
          <h1>MİMAR</h1>
          <p>Müfredat ilişkileri · KUSOM (araştırma prototipi)</p>
        </div>
        <nav aria-label="Bölümler">
          {SCREENS.map((x, i) => (
            <button key={x.id} className={`m-rail-item ${screen === x.id ? 'is-active' : ''}`} onClick={() => setScreen(x.id)}
              aria-current={screen === x.id ? 'page' : undefined}>
              <span className="m-rail-step">{i + 1}</span><span>{x.label}</span><span />
            </button>
          ))}
        </nav>
        <div className="m-rail-user">
          <strong>{user.display_name}</strong>
          {user.roles.join(', ')}
          <div><button onClick={() => { setToken(''); setUser(null) }}>Çıkış</button></div>
        </div>
      </aside>
      <main className="m-main"><Prototype screen={screen} /></main>
    </div>
  )
}

import { useState } from 'react'
import { api } from '../api'
import { Button, Feedback, Field, Note, Page, Panel, Pill, Table, useAction, useLoad } from '../ui'

const ROLES: Record<string, string> = {
  admin: 'Yönetici', technical: 'Teknik ekip', reviewer: 'AS1 değerlendirici', adjudicator: 'Üçüncü kişi',
  expert: 'Uzman (Uzman–Çekirdek)', standardizer: 'Standardizasyon', validator: 'Doğrulama kurulu',
  coordinator: 'Koordinatör', impact_evaluator: 'Etki değerlendiricisi', observer: 'Gözlemci',
}

export default function PeopleSection() {
  const users = useLoad(() => api.get('/users'), [])
  const act = useAction()
  const [f, setF] = useState({ username: '', display_name: '', roles: [] as string[] })
  const [token, setToken] = useState<string | null>(null)
  return (
    <Page title="Kişiler ve roller" lead="Veri hazırlama, teknik geliştirme, rapor hazırlama, standardizasyon, bağımsız doğrulama ve uygulama ayrı rollerle yürütülür. Yönetici rolü inceleme veya doğrulama yetkisi vermez.">
      <Panel title="Yeni kişi">
        <div className="m-row">
          <Field label="Kullanıcı adı"><input className="m-input" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} /></Field>
          <Field label="Görünen ad"><input className="m-input" value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} /></Field>
        </div>
        <div className="m-row" style={{ margin: '10px 0' }}>
          {Object.entries(ROLES).map(([r, l]) => (
            <label key={r} className="m-text-sm" style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <input type="checkbox" checked={f.roles.includes(r)} onChange={(e) => setF({ ...f, roles: e.target.checked ? [...f.roles, r] : f.roles.filter((x) => x !== r) })} />{l}</label>))}
        </div>
        <Button kind="primary" busy={act.busy} disabled={!f.username || !f.roles.length}
          onClick={async () => { const r: any = await act.run(() => api.post('/users', f), 'Kişi eklendi.'); if (r) setToken(r.token) }}>Ekle</Button>
        {token && <Note tone="warn">Erişim anahtarı yalnız bir kez gösterilir: <code>{token}</code></Note>}
        <Feedback a={act} />
      </Panel>
      <Panel title="Ekip">
        <Table dense cols={[{ key: 'username', label: 'Kullanıcı' }, { key: 'display_name', label: 'Ad' },
          { key: 'roles', label: 'Roller', render: (u) => <span className="m-row" style={{ gap: 4 }}>{u.roles.map((r: string) => <Pill key={r}>{ROLES[r] ?? r}</Pill>)}</span> }]}
          rows={users.data ?? []} />
      </Panel>
    </Page>
  )
}

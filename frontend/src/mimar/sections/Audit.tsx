import { api } from '../api'
import { Hash, Note, Page, Panel, Table, useLoad } from '../ui'

export default function AuditSection() {
  const v = useLoad(() => api.get('/audit/verify'), [])
  const log = useLoad(() => api.get('/audit?limit=300'), [])
  return (
    <Page title="Denetim günlüğü" lead="Her erişim ve değişiklik, bir öncekinin hash’ine bağlı olarak eklenir. Geriye dönük bir değişiklik zinciri bozar ve burada görünür.">
      {v.data && (v.data.valid ? <Note tone="ok">Zincir geçerli · {v.data.entries} kayıt · baş <Hash value={v.data.head} n={16} /></Note>
        : <Note tone="error">Zincir {v.data.broken_at} numaralı kayıtta bozuk.</Note>)}
      {log.error && <Note tone="error">{log.error}</Note>}
      <Panel title="Son kayıtlar">
        <Table dense cols={[{ key: 'seq', label: '#', num: true }, { key: 'ts', label: 'Zaman' }, { key: 'actor', label: 'Kişi' },
          { key: 'action', label: 'İşlem' }, { key: 'entity', label: 'Varlık' },
          { key: 'details', label: 'Ayrıntı', render: (r) => <span className="m-text-sm m-muted">{JSON.stringify(r.details).slice(0, 120)}</span> },
          { key: 'hash', label: 'Hash', render: (r) => <Hash value={r.hash} /> }]} rows={log.data ?? []} />
      </Panel>
    </Page>
  )
}

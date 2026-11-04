import { useState } from 'react'
import { api } from '../api'
import { Button, Feedback, Field, Hash, Note, Page, Panel, Pill, Table, useAction, useLoad } from '../ui'

function Upload({ dsId, kind, label }: { dsId: string; kind: 'los' | 'ucep' | 'materials'; label: string }) {
  const act = useAction()
  const [file, setFile] = useState<File | null>(null)
  return (
    <div className="m-row">
      <Field label={label}><input className="m-input" type="file" accept=".csv,.tsv,.xlsx,.json" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
      <Button disabled={!file} busy={act.busy}
        onClick={() => act.run(() => api.upload(`/datasets/${dsId}/${kind}/upload`, file!), 'İçe aktarıldı.')}>İçe aktar</Button>
      <div style={{ flexBasis: '100%' }}><Feedback a={act} /></div>
    </div>
  )
}

function DatasetDetail({ id }: { id: string }) {
  const d = useLoad(() => api.get(`/datasets/${id}`), [id])
  const [q, setQ] = useState('')
  const los = useLoad(() => api.get(`/datasets/${id}/los?q=${encodeURIComponent(q)}&limit=200`), [id, q])
  const act = useAction()
  const [label, setLabel] = useState('T1')
  const ds = d.data
  if (!ds) return null
  const qc = ds.qc_report
  return (
    <>
      <Panel title={`${ds.name} · ${ds.version_label}`} aside={ds.status === 'frozen'
        ? <><Pill tone="lock">donduruldu</Pill><Hash value={ds.content_hash} /></> : <Pill tone="warn">taslak</Pill>}>
        {ds.synthetic && <Note tone="warn">Sentetik demo verisi — KUSOM verisi değildir.</Note>}
        {ds.status === 'draft' ? (
          <div className="m-grid">
            <Upload dsId={id} kind="los" label="Öğrenme hedefleri (CSV/XLSX/JSON)" />
            <Upload dsId={id} kind="ucep" label="UÇEP referans ögeleri" />
            <Upload dsId={id} kind="materials" label="KuLearn materyalleri (izin kayıtlı)" />
            <div className="m-row">
              <Button kind="primary" busy={act.busy} disabled={!ds.counts?.los}
                onClick={() => act.run(() => api.post(`/datasets/${id}/freeze`), 'Sürüm donduruldu; içerik hash’i kaydedildi.')}>
                Sürümü dondur</Button>
              <span className="m-muted m-text-sm">Analizler yalnız dondurulmuş sürümlerde çalışır. Dondurulan sürüm değiştirilemez.</span>
            </div>
          </div>
        ) : (
          <div className="m-row">
            <Field label="Yeni sürüm etiketi"><input className="m-input" value={label} onChange={(e) => setLabel(e.target.value)} /></Field>
            <Button busy={act.busy} onClick={() => act.run(() => api.post(`/datasets/${id}/versions`, { version_label: label }), 'Yeni taslak sürüm oluşturuldu.')}>
              Bu sürümden yeni taslak oluştur</Button>
          </div>
        )}
        <Feedback a={act} />
      </Panel>
      {qc && (
        <Panel title="Veri hazırlık raporu" aside={<span>{qc.rows_received} satır alındı</span>}>
          <div className="m-grid m-grid-2">
            <dl className="m-kv">
              <dt>Dahil edilen</dt><dd>{qc.included}</dd>
              <dt>Dışlanan</dt><dd>{qc.excluded}</dd>
              <dt>Eğitim etkinliği</dt><dd>{qc.activities}</dd>
              <dt>Sınıflara göre</dt><dd>{Object.entries(qc.by_year).map(([y, n]) => `${y}. sınıf: ${n}`).join(' · ')}</dd>
              <dt>Doğrulanmamış MeSH (alınmadı)</dt><dd>{qc.unverified_mesh_terms_dropped}</dd>
              <dt>Farklı etkinlikte aynı metin (korundu)</dt><dd>{qc.identical_text_across_activities_kept}</dd>
            </dl>
            <Table dense cols={[{ key: 'k', label: 'Dışlama gerekçesi' }, { key: 'v', label: 'Kayıt', num: true }]}
              rows={Object.entries(qc.exclusion_reasons).map(([k, v]) => ({ k, v }))} empty="Dışlanan kayıt yok." />
          </div>
          {ds.qc_exclusions?.length > 0 && (
            <details className="m-details" style={{ marginTop: 10 }}><summary>Dışlanan kayıtları göster</summary>
              <Table dense cols={[{ key: 'row', label: 'Satır', num: true }, { key: 'uid', label: 'Kimlik' }, { key: 'reason', label: 'Gerekçe' }, { key: 'text', label: 'Metin' }]} rows={ds.qc_exclusions} />
            </details>)}
        </Panel>
      )}
      <Panel title="Öğrenme hedefleri" aside={<span>{ds.counts?.los} hedef · {ds.counts?.ucep} UÇEP · {ds.counts?.materials} materyal</span>}>
        <Field label="Ara"><input className="m-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Metin, kimlik veya ders" /></Field>
        <Table dense cols={[{ key: 'uid', label: 'Kimlik', width: '170px' }, { key: 'year', label: 'Sınıf', num: true },
          { key: 'course', label: 'Ders' }, { key: 'text', label: 'Hedef metni' }]} rows={los.data ?? []} />
      </Panel>
    </>
  )
}

export default function DataSection() {
  const list = useLoad(() => api.get('/datasets'), [])
  const [sel, setSel] = useState<string>('')
  const act = useAction()
  const [name, setName] = useState('MSKL')
  return (
    <Page title="Veri ve kalite kontrolü" lead="Her hedef özgün metni, kalıcı kimliği, kaynağı, eğitim etkinliği ve dönemiyle tutulur. Boş, yinelenen, kaynaksız veya incelemeye elvermeyen kayıtlar gerekçeleriyle dışlanır; farklı derslerdeki benzer hedefler yalnız benzer oldukları için silinmez.">
      <Panel title="Veri sürümleri">
        <Table cols={[
          { key: 'name', label: 'Ad', render: (r) => <Button kind="quiet" onClick={() => setSel(r.id)}>{r.name}</Button> },
          { key: 'version_label', label: 'Sürüm' }, { key: 'scope', label: 'Kapsam' },
          { key: 'los', label: 'Hedef', num: true, render: (r) => r.counts?.los },
          { key: 'status', label: 'Durum', render: (r) => r.status === 'frozen' ? <Pill tone="lock">donduruldu</Pill> : <Pill tone="warn">taslak</Pill> },
          { key: 'content_hash', label: 'İçerik hash’i', render: (r) => <Hash value={r.content_hash} /> },
        ]} rows={list.data ?? []} empty="Henüz veri sürümü yok. Aşağıdan oluşturun." />
        <div className="m-row" style={{ marginTop: 12 }}>
          <Field label="Yeni veri seti adı"><input className="m-input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Button busy={act.busy} onClick={async () => { const r: any = await act.run(() => api.post('/datasets', { name, scope: 'MSKL', version_label: 'T0' }), 'Taslak oluşturuldu.'); if (r) setSel(r.id) }}>Taslak oluştur</Button>
        </div>
        <Feedback a={act} />
      </Panel>
      {sel && <DatasetDetail id={sel} />}
    </Page>
  )
}

import { useState } from 'react'
import { api } from '../api'
import { hasRole, useMimar } from '../state'
import { Button, Feedback, Field, Hash, Note, Page, Panel, Pill, Select, Table, useAction, useLoad } from '../ui'

export const CAT: Record<string, string> = { redundancy: 'Gereksiz tekrar', gap_ucep: 'Eksiklik / UÇEP', integration: 'Entegrasyon' }
const SRC: Record<string, string> = { mimar_core: 'MİMAR–Çekirdek', mimar_extended: 'MİMAR–Genişletilmiş', expert_core: 'Uzman–Çekirdek' }
const UCEP_STATUS: Record<string, [string, any]> = {
  explicit_link: ['kayıtlı bağlantı', 'ok'], candidate_correspondence: ['aday karşılık', 'ok'],
  weak_correspondence: ['zayıf karşılık', 'warn'], no_clear_correspondence: ['açık karşılık yok', 'bad'],
}

function ReportView({ id }: { id: string }) {
  const r = useLoad(() => api.get(`/reports/${id}`), [id])
  const act = useAction()
  const [cat, setCat] = useState('')
  if (r.error) return <Note tone="error">{r.error}</Note>
  const rep = r.data?.report
  if (!rep) return null
  const fs = (r.data.findings ?? []).filter((f: any) => !cat || f.category === cat)
  return (
    <>
      <Panel title={SRC[rep.source] ?? rep.source} aside={rep.locked ? <><Pill tone="lock">kilitli</Pill><Hash value={rep.lock_hash} /></> : <Pill tone="warn">taslak</Pill>}>
        <div className="m-row">
          {Object.entries(rep.counts ?? {}).map(([c, n]: any) => <Pill key={c} tone="brand">{CAT[c]}: {n}</Pill>)}
          {rep.spiral_progressions ? <Pill>Olası spiral ilerleme (rapora alınmadı): {rep.spiral_progressions}</Pill> : null}
          {rep.depth && <span className="m-muted m-text-sm">liste derinliği {rep.depth}</span>}
        </div>
        <div className="m-row" style={{ marginTop: 10 }}>
          {!rep.locked && <Button kind="primary" busy={act.busy} onClick={() => act.run(() => api.post(`/reports/${id}/lock`), 'Rapor kilitlendi.')}>Raporu kilitle</Button>}
          <Button kind="quiet" onClick={() => api.download(`/reports/${id}/export.csv`, `rapor_${id}.csv`)}>CSV indir</Button>
          <Select value={cat} onChange={setCat} placeholder="Tüm kategoriler" options={Object.entries(CAT).map(([v, l]) => ({ value: v, label: l }))} />
        </div>
        <Feedback a={act} />
      </Panel>
      <Panel title="Aday bulgular" aside={<span>{fs.length}</span>}>
        <Table cols={[
          { key: 'category', label: 'Kategori', render: (f) => <Pill tone="brand">{CAT[f.category]}</Pill>, width: '130px' },
          { key: 'statement', label: 'Bulgu ve kanıt', render: (f) => <>
            <div>{f.statement}</div>
            <details className="m-details"><summary>Çekirdek veri desteği ({f.support.length})</summary>
              <ul className="m-text-sm">{f.support.map((s: any, k: number) => <li key={k}>{s.lo ? <><b>{s.lo}</b> · {s.year}. sınıf · {s.course}: {s.text}{s.material && <div className="m-muted">KuLearn: {s.material}</div>}</> : <><b>{s.ucep}</b> {s.text_tr}</>}</li>)}</ul>
              <p className="m-muted m-text-sm">{f.rationale}</p>
            </details></> },
        ]} rows={fs} />
      </Panel>
      {r.data.ucep_map && (
        <Panel title="UÇEP karşılık haritası" aside={<span>yalnız MSKL kapsamındaki ögeler</span>}>
          <Note tone="info">“Açık karşılık yok”, konunun öğretilmediği anlamına gelmez; incelenen kayıtlarda açık karşılık gösterilemediğini belirtir.</Note>
          <Table dense cols={[
            { key: 'code', label: 'Kod', width: '120px' },
            { key: 'text_tr', label: 'Öge', render: (u) => <>{u.text_tr}<div className="m-muted m-text-sm">{u.text_en}</div></> },
            { key: 'status', label: 'Durum', render: (u) => <Pill tone={UCEP_STATUS[u.status]?.[1]}>{UCEP_STATUS[u.status]?.[0]}</Pill> },
            { key: 'best', label: 'En yakın hedef', render: (u) => u.candidates?.[0] ? `${u.candidates[0].lo} · kos ${u.candidates[0].cosine} · kapsama ${u.candidates[0].coverage}` : '—' },
          ]} rows={r.data.ucep_map} />
        </Panel>
      )}
    </>
  )
}

function ExpertImport() {
  const ds = useLoad(() => api.get('/datasets'), [])
  const act = useAction()
  const [dsId, setDsId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [authors, setAuthors] = useState('')
  return (
    <Panel title="Uzman–Çekirdek raporunu yükle">
      <p className="m-muted m-text-sm">Aynı şablon: category (redundancy | gap_ucep | integration), los (noktalı virgülle), ucep, statement, rationale. Rapor hazırlığında üretken yapay zekâ, web araması veya dış belge kullanılmaz.</p>
      <div className="m-row">
        <Field label="Veri sürümü"><Select value={dsId} onChange={setDsId} options={(ds.data ?? []).map((d: any) => ({ value: d.id, label: `${d.name} · ${d.version_label}` }))} /></Field>
        <Field label="Diğer yazarlar (virgülle)"><input className="m-input" value={authors} onChange={(e) => setAuthors(e.target.value)} /></Field>
        <Field label="Dosya"><input className="m-input" type="file" accept=".csv,.xlsx,.json" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
        <Button kind="primary" busy={act.busy} disabled={!dsId || !file}
          onClick={() => act.run(() => api.upload(`/datasets/${dsId}/expert-reports/upload`, file!, { authors }), 'Uzman raporu yüklendi.')}>Yükle</Button>
      </div>
      <Feedback a={act} />
    </Panel>
  )
}

export default function FindingsSection() {
  const user = useMimar((s) => s.user)
  const runs = useLoad(() => api.get('/analyses'), [])
  const reps = useLoad(() => api.get('/reports'), [])
  const act = useAction()
  const [run, setRun] = useState('')
  const [sel, setSel] = useState('')
  const isTech = hasRole(user, 'admin', 'technical')
  return (
    <Page title="AS2 · Raporlar" lead="MİMAR–Çekirdek ve Uzman–Çekirdek raporları aynı çekirdek veri ve aynı şablonla hazırlanır. Raporlar kilitlendikten sonra standardizasyon ve kör doğrulamaya gider. Genişletilmiş rapor yalnız izinli KuLearn içeriğini ayrı bir kanal olarak ekler.">
      {isTech && (
        <Panel title="MİMAR raporu üret">
          <div className="m-row">
            <Field label="Analiz çalıştırması"><Select value={run} onChange={setRun} options={(runs.data ?? []).map((r: any) => ({ value: r.id, label: r.label }))} /></Field>
            <Button kind="primary" busy={act.busy} disabled={!run}
              onClick={() => { const r = (runs.data ?? []).find((x: any) => x.id === run); act.run(() => api.post(`/analyses/${run}/reports`, { kind: r?.with_materials ? 'extended' : 'core' }), 'Rapor üretildi.') }}>Rapor üret</Button>
          </div>
          <Feedback a={act} />
        </Panel>
      )}
      {hasRole(user, 'expert') && <ExpertImport />}
      <Panel title="Raporlar">
        <Table cols={[
          { key: 'source', label: 'Kaynak', render: (r) => <Button kind="quiet" onClick={() => setSel(r.id)}>{SRC[r.source] ?? r.source}</Button> },
          { key: 'n_findings', label: 'Aday', num: true },
          { key: 'authors', label: 'Yazarlar', render: (r) => (r.authors ?? []).join(', ') },
          { key: 'locked', label: 'Durum', render: (r) => r.locked ? <Pill tone="lock">kilitli</Pill> : <Pill tone="warn">taslak</Pill> },
          { key: 'created_at', label: 'Zaman' },
        ]} rows={reps.data ?? []} empty="Henüz rapor yok." />
      </Panel>
      {sel && <ReportView id={sel} />}
    </Page>
  )
}

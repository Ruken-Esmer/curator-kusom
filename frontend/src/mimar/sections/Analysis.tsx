import { useState } from 'react'
import { api } from '../api'
import { useMimar } from '../state'
import { Button, Feedback, Field, Hash, Note, Page, Panel, Pill, Select, Table, useAction, useLoad } from '../ui'

const METHOD_LABEL: Record<string, string> = { bm25: 'BM25', embedding: 'Gömme', graph: 'Kavram grafiği', material: 'Materyal' }

function Ranks({ r }: { r: Record<string, number> }) {
  return <span style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
    {['bm25', 'embedding', 'graph', 'material'].filter((m) => m in r || m !== 'material').map((m) =>
      <Pill key={m} tone={r[m] ? (r[m] <= 10 ? 'brand' : 'plain') : 'plain'}>{METHOD_LABEL[m]} {r[m] ?? '—'}</Pill>)}
  </span>
}

function AnalysisDetail({ id }: { id: string }) {
  const [split, setSplit] = useState('')
  const d = useLoad(() => api.get(`/analyses/${id}?top=60${split ? `&split=${split}` : ''}`), [id, split])
  const concepts = useLoad(() => api.get(`/analyses/${id}/concepts?limit=60`), [id])
  const act = useAction()
  const a = d.data?.analysis
  if (!a) return d.error ? <Note tone="error">{d.error}</Note> : null
  return (
    <>
      <Panel title={a.label} aside={<><span>veri</span><Hash value={a.dataset_hash} /><span>ayar</span><Hash value={a.config_hash} /></>}>
        <div className="m-grid m-grid-3">
          <dl className="m-kv">
            <dt>Hedef sayısı</dt><dd>{a.n_los}</dd>
            <dt>Gömme modeli</dt><dd>{a.backend.embedding}{a.backend.faiss ? ' · FAISS' : ' · numpy'}</dd>
            <dt>Kavram / ilişki</dt><dd>{a.backend.concepts} / {a.backend.related_edges}</dd>
            <dt>Süre</dt><dd>{a.fit_seconds} sn</dd>
          </dl>
          <dl className="m-kv">
            <dt>İçerik ailesi</dt><dd>{a.split_counts.families}</dd>
            <dt>Geliştirme / test hedefi</dt><dd>{a.split_counts.los.dev ?? 0} / {a.split_counts.los.test ?? 0}</dd>
            <dt>Listelenen çift (gel./test/ara)</dt><dd>{a.split_counts.listed_pairs.dev} / {a.split_counts.listed_pairs.test} / {a.split_counts.listed_pairs.cross}</dd>
            <dt>Ayrım kilidi</dt><dd><Hash value={a.split_lock_hash} /></dd>
          </dl>
          <div>
            {a.stability ? (
              <Note tone={a.stability.meets_criterion ? 'ok' : 'warn'}>
                Kararlılık: {a.stability.runs} çalıştırmada ilk {a.stability.top} listelerinin en düşük ikili örtüşmesi {(a.stability.min_overlap * 100).toFixed(0)}% (ölçüt ≥ %90).
              </Note>
            ) : <p className="m-muted m-text-sm">Aynı veri ve ayarlarla beş çalıştırma yapılarak ilk-20 listelerinin örtüşmesi izlenir.</p>}
            <div className="m-row">
              <Button busy={act.busy} onClick={() => act.run(() => api.post(`/analyses/${id}/stability`), 'Kararlılık kontrolü tamamlandı.')}>Kararlılığı ölç</Button>
              <Button kind="quiet" onClick={() => api.download(`/analyses/${id}/export.csv`, `mimar_adaylar_${id}.csv`)}>CSV indir</Button>
              <Button kind="quiet" onClick={() => api.download(`/analyses/${id}/neo4j.cypher`, `mimar_kavram_grafigi_${id}.cypher`)}>Neo4j betiği</Button>
            </div>
          </div>
        </div>
        <Feedback a={act} />
      </Panel>
      <Panel title="Hibrit sıralama (RRF, k = 60)" aside={
        <Select value={split} onChange={setSplit} placeholder="Tüm çiftler"
          options={[{ value: 'dev', label: 'Yalnız geliştirme' }]} />}>
        <Note tone="info">Kilitli test bölümü burada gösterilmez; yalnız ön kayıt kilitlendikten sonra örneklenir. Teknik örtüşme eğitsel “gereksiz tekrar” kararı değildir.</Note>
        <Table cols={[
          { key: 'rank', label: '#', num: true, width: '40px' },
          { key: 'a', label: 'Hedef A', render: (r) => <><b className="m-text-sm">{r.a.uid}</b> <span className="m-muted m-text-sm">· {r.a.year}. sınıf · {r.a.course}</span><div>{r.a.text}</div></> },
          { key: 'b', label: 'Hedef B', render: (r) => <><b className="m-text-sm">{r.b.uid}</b> <span className="m-muted m-text-sm">· {r.b.year}. sınıf · {r.b.course}</span><div>{r.b.text}</div></> },
          { key: 'm', label: 'Yöntem sıraları', render: (r) => <><Ranks r={r.method_ranks} /><div className="m-muted m-text-sm" style={{ marginTop: 4 }}>kosinüs {r.evidence.cosine} · {r.evidence.shared_concepts.slice(0, 3).join(', ')}</div></>, width: '230px' },
        ]} rows={d.data?.top ?? []} />
      </Panel>
      <Panel title="Kavram grafiği" aside={concepts.data && <span>{concepts.data.totals.concepts} kavram · {concepts.data.totals.related_edges} ilişki</span>}>
        <p className="m-muted m-text-sm">Hedef metinlerinden çıkarılan kavramlar (en çok bağlanan 60). Grafik kanalı BM25/FAISS puanlarını kullanmaz.</p>
        <div className="m-concepts">{concepts.data?.nodes.map((n: any) => <span key={n.id}>{n.id} <span className="m-muted">{n.degree}</span></span>)}</div>
      </Panel>
    </>
  )
}

export default function AnalysisSection() {
  const { analysisId, setAnalysisId } = useMimar()
  const ds = useLoad(() => api.get('/datasets'), [])
  const cfgs = useLoad(() => api.get('/configs'), [])
  const runs = useLoad(() => api.get('/analyses'), [])
  const act = useAction()
  const [dsId, setDsId] = useState('')
  const [cfgId, setCfgId] = useState('')
  const [cfg, setCfg] = useState({ name: 'varsayılan', list_depth: 150, rrf_k: 60, per_query_k: 10, backend: 'tfidf-lsa' })
  const frozen = (ds.data ?? []).filter((d: any) => d.status === 'frozen')
  return (
    <Page title="AS1 · Örtüşme analizi" lead="Birincil analiz yalnız dondurulmuş özgün hedef metinlerini kullanır. Üç bağımsız sıralama — BM25, gömme/FAISS ve kavram grafiği — puanlar yerine sıralar üzerinden RRF ile birleştirilir.">
      <div className="m-grid m-grid-2">
        <Panel title="Ayar sürümü oluştur">
          <div className="m-grid m-grid-2">
            <Field label="Ad"><input className="m-input" value={cfg.name} onChange={(e) => setCfg({ ...cfg, name: e.target.value })} /></Field>
            <Field label="Gömme modeli">
              <select className="m-input" value={cfg.backend} onChange={(e) => setCfg({ ...cfg, backend: e.target.value })}>
                <option value="tfidf-lsa">Yerel TF-IDF + LSA (çevrimdışı)</option>
                <option value="sentence-transformers">sentence-transformers (kuruluysa)</option>
              </select></Field>
            <Field label="Liste derinliği (tüm veri)"><input className="m-input" type="number" value={cfg.list_depth} onChange={(e) => setCfg({ ...cfg, list_depth: +e.target.value })} /></Field>
            <Field label="RRF k"><input className="m-input" type="number" value={cfg.rrf_k} onChange={(e) => setCfg({ ...cfg, rrf_k: +e.target.value })} /></Field>
          </div>
          <div className="m-row" style={{ marginTop: 10 }}>
            <Button busy={act.busy} onClick={() => act.run(() => api.post('/configs', { name: cfg.name, params: { list_depth: cfg.list_depth, rrf_k: cfg.rrf_k, per_query_k: cfg.per_query_k, embedding: { backend: cfg.backend } } }), 'Ayar sürümü kaydedildi.')}>Kaydet</Button>
          </div>
        </Panel>
        <Panel title="Analizi çalıştır">
          <div className="m-grid">
            <Field label="Dondurulmuş veri sürümü"><Select value={dsId} onChange={setDsId} options={frozen.map((d: any) => ({ value: d.id, label: `${d.name} · ${d.version_label}` }))} /></Field>
            <Field label="Ayar sürümü"><Select value={cfgId} onChange={setCfgId} options={(cfgs.data ?? []).map((c: any) => ({ value: c.id, label: `${c.name} · ${c.hash}${c.locked ? ' (kilitli)' : ''}` }))} /></Field>
            <div><Button kind="primary" disabled={!dsId || !cfgId} busy={act.busy}
              onClick={async () => { const r: any = await act.run(() => api.post('/analyses', { dataset_id: dsId, config_id: cfgId }), 'Analiz tamamlandı.'); if (r) setAnalysisId(r.id) }}>Çalıştır</Button></div>
          </div>
        </Panel>
      </div>
      <Feedback a={act} />
      <Panel title="Çalıştırmalar">
        <Table cols={[
          { key: 'label', label: 'Çalıştırma', render: (r) => <Button kind="quiet" onClick={() => setAnalysisId(r.id)}>{r.label}</Button> },
          { key: 'n_los', label: 'Hedef', num: true },
          { key: 'with_materials', label: 'KuLearn', render: (r) => r.with_materials ? <Pill tone="brand">genişletilmiş</Pill> : 'çekirdek' },
          { key: 'plan', label: 'Ön kayıt', render: (r) => r.plan_id ? <Pill>var</Pill> : '—' },
          { key: 'created_at', label: 'Zaman' },
        ]} rows={runs.data ?? []} empty="Henüz analiz yok." />
      </Panel>
      {analysisId && <AnalysisDetail id={analysisId} />}
    </Page>
  )
}

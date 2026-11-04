import { useState } from 'react'
import { api } from '../api'
import { useMimar } from '../state'
import { Bar, Button, ci, Feedback, Field, Hash, Note, Page, Panel, Pill, Select, Table, useAction, useLoad, Verdict } from '../ui'

const M = { hybrid: 'Hibrit (RRF)', bm25: 'BM25', embedding: 'Gömme', graph: 'Kavram grafiği' } as Record<string, string>

export function MetricsTable({ met }: { met: any }) {
  const rows = Object.entries(met.methods).map(([m, v]: any) => ({ m, ...v }))
  rows.sort((a, b) => (a.m === 'hybrid' ? -1 : b.m === 'hybrid' ? 1 : 0))
  return (
    <>
      <Table cols={[
        { key: 'm', label: 'Liste', render: (r) => <b>{M[r.m] ?? r.m}</b> },
        { key: 'depth', label: 'Derinlik', num: true },
        { key: 'sensitivity', label: 'Ağırlıklı duyarlılık', num: true, render: (r) => <>{r.sensitivity ?? '—'}<Bar value={r.sensitivity} /></> },
        { key: 'ppv', label: 'Ağırlıklı PKD', num: true, render: (r) => <>{r.ppv ?? '—'}<Bar value={r.ppv} tone="ok" /></> },
        { key: 'f1', label: 'F1', num: true },
        { key: 'p10', label: 'PKD@10', num: true, render: (r) => r.precision_at_k?.['10']?.ppv ?? '—' },
        { key: 'nnr', label: 'Doğru çift başına inceleme', num: true, render: (r) => r.reviews_per_true_pair ?? '—' },
        { key: 'raw', label: 'Ham DP / incelenen', num: true, render: (r) => `${r.raw.tp} / ${r.raw.listed_reviewed}` },
      ]} rows={rows} />
      <p className="m-muted m-text-sm">İncelenen {met.n_reviewed} çift · kullanılabilir {met.n_usable} · “metin yetersiz” {met.n_insufficient} (ana analiz dışı) · pozitif çift (ham) {met.positives_raw}. Ağırlıklı sonuçlar birincil, ham sonuçlar destekleyicidir.</p>
    </>
  )
}

function SampleBox({ s, plan }: { s: any; plan: any }) {
  const users = useLoad(() => api.get('/users'), [])
  const prog = useLoad(() => api.get(`/samples/${s.id}/progress`), [s.id])
  const act = useAction()
  const [r1, setR1] = useState(''); const [r2, setR2] = useState(''); const [adj, setAdj] = useState('')
  const reviewers = (users.data ?? []).filter((u: any) => u.roles.includes('reviewer')).map((u: any) => ({ value: u.username, label: u.display_name }))
  const adjs = (users.data ?? []).filter((u: any) => u.roles.includes('adjudicator')).map((u: any) => ({ value: u.username, label: u.display_name }))
  const p = prog.data
  const ev = s.evaluation
  return (
    <Panel title={s.part === 'test' ? 'Kilitli test örneklemi' : 'Geliştirme örneklemi'}
      aside={<><span>{s.n} çift · derinlik {s.depth}</span>{s.status === 'evaluated' && <Pill tone="ok">değerlendirildi</Pill>}</>}>
      <details className="m-details"><summary>Tabakalar ve seçilme olasılıkları</summary>
        <Table dense cols={[{ key: 'h', label: 'Tabaka' }, { key: 'N', label: 'Evren', num: true }, { key: 'n', label: 'Seçilen', num: true },
          { key: 'pi', label: 'Olasılık', num: true }]}
          rows={Object.entries(s.design.strata_sizes).map(([h, N]: any) => ({ h, N, n: s.design.allocation[h] ?? 0, pi: N ? (s.design.allocation[h] ?? 0) / N : 0 }))} />
      </details>
      {!s.reviewers?.length ? (
        <div className="m-row" style={{ marginTop: 10 }}>
          <Field label="1. değerlendirici"><Select value={r1} onChange={setR1} options={reviewers} /></Field>
          <Field label="2. değerlendirici"><Select value={r2} onChange={setR2} options={reviewers} /></Field>
          <Field label="Üçüncü kişi"><Select value={adj} onChange={setAdj} options={adjs} /></Field>
          <Button busy={act.busy} disabled={!r1 || !r2} onClick={() => act.run(() => api.post(`/samples/${s.id}/assign`, { reviewers: [r1, r2], adjudicator: adj || null }), 'Görevler atandı; her değerlendirici kendi rastgele sırasını görecek.')}>Ata</Button>
        </div>
      ) : p && (
        <Table dense cols={[{ key: 'r', label: 'Değerlendirici' }, { key: 'd', label: 'Karar', num: true }, { key: 'l', label: 'Durum' }]}
          rows={Object.entries(p.reviewers).map(([r, v]: any) => ({ r, d: `${v.decided} / ${p.total}`, l: v.locked ? <Pill tone="lock">kilitlendi</Pill> : <Pill tone="warn">sürüyor</Pill> }))} />
      )}
      {p && p.conflicts > 0 && <Note tone="info">{p.conflicts} uyuşmazlık · {p.adjudicated} tanesi üçüncü kişi tarafından sonuçlandırıldı. İlk bağımsız kararlar korunur.</Note>}
      <div className="m-row" style={{ marginTop: 10 }}>
        <Button kind="primary" busy={act.busy} disabled={!s.reviewers?.length}
          onClick={() => act.run(() => api.post(`/samples/${s.id}/evaluate`), 'Değerlendirme tamamlandı.')}>Değerlendir</Button>
        <Button kind="quiet" onClick={() => api.download(`/samples/${s.id}/labels.csv`, `as1_etiketler_${s.id}.csv`)}>Etiketleri indir</Button>
      </div>
      <Feedback a={act} />
      {ev && (
        <div style={{ marginTop: 12 }}>
          {ev.recalibration_required && <Note tone="warn">Gwet AC1 {ev.agreement_initial.ac1} &lt; 0,60 — kılavuz gözden geçirilmeli, yeniden kalibrasyon ve ilgili grubun yeniden incelemesi gerekir.</Note>}
          <p className="m-text-sm">Başlangıç uyumu: yüzde {ev.agreement_initial.percent} · Cohen κ {ev.agreement_initial.kappa} · Gwet AC1 <b>{ev.agreement_initial.ac1}</b> (n = {ev.agreement_initial.n})</p>
          {ev.depth_selection ? (
            <>
              <MetricsTable met={ev.metrics_at_selected_depth} />
              <Note tone="ok">Geliştirmede seçilen liste derinliği <b>{ev.depth_selection.selected_depth_dev}</b> (hibrit F1 en yüksek); karşılaştırıcı tekil yöntem <b>{M[ev.comparator_selection.comparator]}</b> (eşit derinlikte en yüksek ağırlıklı PKD, eşitlikte F1).</Note>
              <details className="m-details"><summary>Derinlik ızgarası</summary>
                <Table dense cols={[{ key: 'depth', label: 'Derinlik', num: true },
                  ...['hybrid', 'bm25', 'embedding', 'graph'].map((m) => ({ key: m, label: `${M[m]} F1`, num: true, render: (r: any) => r[m]?.f1 ?? '—' }))]}
                  rows={ev.depth_selection.grid} />
              </details>
            </>
          ) : <MetricsTable met={ev.metrics} />}
          {ev.h1 && (
            <div className="m-grid m-grid-2" style={{ marginTop: 10 }}>
              <Verdict ok={ev.h1.verdict === 'supported' ? true : ev.h1.verdict === 'not_supported' ? false : null}>
                <h4>H1 kararı: {({ supported: 'desteklendi', not_supported: 'desteklenmedi', inconclusive_insufficient_positives: 'kesin yargı yok (pozitif çift yetersiz)' } as any)[ev.h1.verdict]}</h4>
                <p>Duyarlılık ≥ 0,80: {ev.h1.criterion_sensitivity.estimate} → {ev.h1.criterion_sensitivity.met ? 'karşılandı' : 'karşılanmadı'}</p>
                <p>PKD farkı GA alt sınırı &gt; 0: {ev.h1.criterion_ppv_difference.ci95_lower} → {ev.h1.criterion_ppv_difference.met ? 'karşılandı' : 'karşılanmadı'}</p>
                <p>Her ölçüt ayrı yorumlanır; “kısmen desteklendi” kullanılmaz.</p>
              </Verdict>
              <Verdict ok={null}>
                <h4>Hibrit − {M[ev.ppv_difference.b]} PKD farkı</h4>
                <p>{ev.ppv_difference.ppv_a} − {ev.ppv_difference.ppv_b} = {ev.ppv_difference.difference}</p>
                <p>%95 GA {ci(ev.ppv_difference.ci95)} · içerik ailesi kümelenmiş bootstrap, {ev.ppv_difference.bootstrap.clusters} küme, B = {ev.ppv_difference.bootstrap.B}</p>
                <p>Ön kayıt kilidi <Hash value={ev.plan_lock_hash} /></p>
              </Verdict>
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}

function PlanParams({ P }: { P: any }) {
  const act = useAction()
  const [f, setF] = useState({ dev_n: P.params.dev_n, test_n: P.params.test_n, test_n_if_rare: P.params.test_n_if_rare, min_positives: P.params.min_positives })
  return (
    <div className="m-row" style={{ marginTop: 12 }}>
      <Field label="Geliştirme örneklemi"><input className="m-input" type="number" value={f.dev_n} onChange={(e) => setF({ ...f, dev_n: +e.target.value })} /></Field>
      <Field label="Test örneklemi"><input className="m-input" type="number" value={f.test_n} onChange={(e) => setF({ ...f, test_n: +e.target.value, test_n_if_rare: +e.target.value })} /></Field>
      <Field label="Asgari pozitif çift"><input className="m-input" type="number" value={f.min_positives} onChange={(e) => setF({ ...f, min_positives: +e.target.value })} /></Field>
      <Button busy={act.busy} onClick={() => act.run(() => api.patch(`/plans/${P.id}`, f), 'Plan taslağı güncellendi.')}>Planı güncelle</Button>
      <div style={{ flexBasis: '100%' }}><Feedback a={act} /></div>
    </div>
  )
}

export default function PlanSection() {
  const { analysisId, setAnalysisId } = useMimar()
  const runs = useLoad(() => api.get('/analyses'), [])
  const run = (runs.data ?? []).find((r: any) => r.id === analysisId)
  const plan = useLoad(() => (run?.plan_id ? api.get(`/plans/${run.plan_id}`) : Promise.resolve(null)), [run?.plan_id])
  const samples = useLoad(() => (analysisId ? api.get(`/samples?analysis_id=${analysisId}`) : Promise.resolve([])), [analysisId])
  const act = useAction()
  const P = plan.data
  const dev = (samples.data ?? []).find((s: any) => s.part === 'dev')
  const test = (samples.data ?? []).find((s: any) => s.part === 'test')
  return (
    <Page title="AS1 · Ön kayıt ve örneklem" lead="Geliştirme (%70) ve kilitli test (%30) ayrımı içerik ailesi düzeyinde korunur. Karşılaştırıcı yöntem ve liste derinliği yalnız geliştirme verisinde seçilir; test, analiz planı kilitlenmeden açılamaz.">
      <Panel title="Analiz çalıştırması">
        <Select value={analysisId ?? ''} onChange={(v) => setAnalysisId(v || null)}
          options={(runs.data ?? []).filter((r: any) => !r.with_materials).map((r: any) => ({ value: r.id, label: r.label }))} />
      </Panel>
      {run && !P && (
        <Panel title="Analiz planı">
          <p className="m-muted">Varsayılanlar başvurudaki gibidir: geliştirme 300 çift, test 1.000 (geliştirmede örtüşme %2’nin altındaysa 1.500), duyarlılık eşiği 0,80, AC1 eşiği 0,60.</p>
          <Button kind="primary" busy={act.busy} onClick={() => act.run(() => api.post(`/analyses/${run.id}/plan`, {}), 'Plan taslağı oluşturuldu.')}>Plan taslağı oluştur</Button>
        </Panel>
      )}
      {P && (
        <Panel title="Analiz planı" aside={P.locked ? <><Pill tone="lock">kilitli</Pill><Hash value={P.lock_hash} /></> : <Pill tone="warn">taslak</Pill>}>
          <div className="m-grid m-grid-3">
            <dl className="m-kv">
              <dt>Geliştirme örneklemi</dt><dd>{P.params.dev_n} çift</dd>
              <dt>Test örneklemi</dt><dd>{P.params.test_n} / {P.params.test_n_if_rare} (seyrek örtüşmede)</dd>
              <dt>Listelenmemiş pay</dt><dd>%{P.params.unlisted_fraction * 100}</dd>
            </dl>
            <dl className="m-kv">
              <dt>Derinlik (gel. / test)</dt><dd>{P.params.depth_selected_dev ?? P.params.depth_dev} / {P.params.depth_test}</dd>
              <dt>Karşılaştırıcı</dt><dd>{P.comparator ? M[P.comparator] : 'geliştirmede seçilecek'}</dd>
              <dt>Asgari pozitif çift</dt><dd>{P.params.min_positives}</dd>
            </dl>
            <dl className="m-kv">
              <dt>Duyarlılık eşiği</dt><dd>{P.params.sens_threshold}</dd>
              <dt>AC1 süreç eşiği</dt><dd>{P.params.ac1_threshold}</dd>
              <dt>Bootstrap</dt><dd>B = {P.params.bootstrap_B}</dd>
            </dl>
          </div>
          {!P.locked && !dev && <PlanParams P={P} />}
          {!P.locked && (
            <div className="m-row" style={{ marginTop: 12 }}>
              {!dev && <Button busy={act.busy} onClick={() => act.run(() => api.post(`/analyses/${run.id}/samples`, { part: 'dev' }), 'Geliştirme örneklemi çekildi.')}>Geliştirme örneklemini çek</Button>}
              <Button kind="primary" busy={act.busy} disabled={!P.comparator}
                onClick={() => act.run(() => api.post(`/plans/${P.id}/lock`), 'Plan kilitlendi; test artık açılabilir.')}>Planı kilitle</Button>
              {!P.comparator && <span className="m-muted m-text-sm">Önce geliştirme örneklemini değerlendirin.</span>}
            </div>
          )}
          {P.locked && !test && (
            <div className="m-row" style={{ marginTop: 12 }}>
              <Button kind="primary" busy={act.busy} onClick={() => act.run(() => api.post(`/analyses/${run.id}/samples`, { part: 'test' }), 'Kilitli test örneklemi çekildi.')}>Kilitli testi aç ve örnekle</Button>
            </div>
          )}
          <Feedback a={act} />
        </Panel>
      )}
      {dev && <SampleBox s={dev} plan={P} />}
      {test && <SampleBox s={test} plan={P} />}
      {!run && <Note tone="info">Önce AS1 analizini çalıştırıp burada seçin.</Note>}
    </Page>
  )
}

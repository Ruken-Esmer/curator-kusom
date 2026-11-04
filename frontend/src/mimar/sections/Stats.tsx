import { useState } from 'react'
import { api } from '../api'
import { Bar, Button, Feedback, Field, Page, Panel, Table, useAction } from '../ui'

export default function StatsSection() {
  const act = useAction()
  const [p, setP] = useState({ p_true: 0.6, shared_fraction: 0.2, mean_family_size: 1.5, margin_pp: -10, sims: 1000 })
  const [rows, setRows] = useState<any[]>([])
  const [r1, setR1] = useState('overlap,overlap,no_overlap,no_overlap,overlap')
  const [r2, setR2] = useState('overlap,no_overlap,no_overlap,no_overlap,overlap')
  const [agr, setAgr] = useState<any>(null)
  return (
    <Page title="Güç ve uyum hesapları" lead="AS2a örneklem güncelleme kuralı için bilgisayar benzetimi: iki yaklaşımın gerçek doğrulanma oranları eşitken, H2a karar kuralının (%95 GA alt sınırı > −10 yp) sağlanma olasılığı. Ortak bulgular ve bağlı aileler taklit edilir.">
      <Panel title="H2a güç benzetimi">
        <div className="m-grid m-grid-3">
          <Field label="Gerçek doğrulanma oranı"><input className="m-input" type="number" step="0.05" value={p.p_true} onChange={(e) => setP({ ...p, p_true: +e.target.value })} /></Field>
          <Field label="Ortak bulgu payı"><input className="m-input" type="number" step="0.05" value={p.shared_fraction} onChange={(e) => setP({ ...p, shared_fraction: +e.target.value })} /></Field>
          <Field label="Ortalama aile büyüklüğü"><input className="m-input" type="number" step="0.1" value={p.mean_family_size} onChange={(e) => setP({ ...p, mean_family_size: +e.target.value })} /></Field>
        </div>
        <div className="m-row" style={{ marginTop: 10 }}>
          <Button kind="primary" busy={act.busy} onClick={async () => setRows((await act.run(() => api.post('/stats/power', p))) ?? [])}>Benzetimi çalıştır</Button>
        </div>
        <Feedback a={act} />
        <Table cols={[{ key: 'n_per_source', label: 'Kaynak başına aday', num: true },
          { key: 'power', label: 'Güç', num: true, render: (r) => <>{r.power}<Bar value={r.power} tone={r.power >= 0.8 ? 'ok' : 'brand'} /></> },
          { key: 'ci_coverage', label: 'GA kapsama sıklığı', num: true }]} rows={rows} empty="Henüz benzetim çalıştırılmadı." />
      </Panel>
      <Panel title="Uyum: yüzde, Cohen κ ve Gwet AC1">
        <p className="m-muted m-text-sm">Yaygınlık dengesiz olduğunda κ düşük çıkabilirken AC1 daha kararlıdır; başvuruda ikisi de raporlanır.</p>
        <div className="m-grid m-grid-2">
          <Field label="1. değerlendirici (virgülle)"><input className="m-input" value={r1} onChange={(e) => setR1(e.target.value)} /></Field>
          <Field label="2. değerlendirici (virgülle)"><input className="m-input" value={r2} onChange={(e) => setR2(e.target.value)} /></Field>
        </div>
        <div className="m-row" style={{ marginTop: 8 }}>
          <Button onClick={async () => setAgr(await act.run(() => api.post('/stats/agreement', { rater1: r1.split(',').map((x) => x.trim()), rater2: r2.split(',').map((x) => x.trim()) })))}>Hesapla</Button>
          {agr && <span>n = {agr.n} · yüzde {agr.percent} · κ {agr.kappa} · AC1 <b>{agr.ac1}</b></span>}
        </div>
      </Panel>
    </Page>
  )
}

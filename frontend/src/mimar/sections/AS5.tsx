import { useState } from 'react'
import { api } from '../api'
import { Button, ci, Feedback, Field, Page, Panel, pct, Select, Table, useAction, useLoad, Verdict } from '../ui'

export default function AS5Section() {
  const reps = useLoad(() => api.get('/reports'), [])
  const samples = useLoad(() => api.get('/samples'), [])
  const act = useAction()
  const [rep, setRep] = useState('')
  const [n, setN] = useState(300)
  const as5 = (samples.data ?? []).filter((s: any) => s.kind === 'as5')
  return (
    <Page title="AS5 · Koordinatör değerlendirmesi" lead="Tüm müfredat taramasının benzersiz adaylarından sınıf, bulgu türü ve sıralama düzeyine göre tabakalı rastgele örnek alınır (en çok 300). Aynı aday için eğitsel anlamlılık ve uygulanabilirlik birlikte olumlu olmalıdır; en az 20 farklı koordinatör aranır.">
      <Panel title="Örneklem çek">
        <div className="m-row">
          <Field label="Kilitli MİMAR raporu"><Select value={rep} onChange={setRep} options={(reps.data ?? []).filter((r: any) => r.locked && r.source.startsWith('mimar')).map((r: any) => ({ value: r.id, label: `${r.source} · ${r.n_findings} aday` }))} /></Field>
          <Field label="Üst sınır"><input className="m-input" type="number" value={n} onChange={(e) => setN(+e.target.value)} /></Field>
          <Button kind="primary" disabled={!rep} busy={act.busy} onClick={() => act.run(() => api.post(`/reports/${rep}/as5-sample`, { n_max: n }), 'Örneklem çekildi; koordinatörler görevlerini “İnceleme görevlerim” bölümünde görür.')}>Çek</Button>
        </div>
        <Feedback a={act} />
      </Panel>
      {as5.map((s: any) => {
        const e = s.evaluation
        return (
          <Panel key={s.id} title={`Örneklem ${s.id}`} aside={<span>{s.n} aday</span>}>
            <Table dense cols={[{ key: 'h', label: 'Tabaka' }, { key: 'N', label: 'Havuz', num: true }, { key: 'n', label: 'Seçilen', num: true }]}
              rows={Object.entries(s.design.strata_sizes).map(([h, N]: any) => ({ h, N, n: s.design.allocation[h] ?? 0 }))} />
            <div className="m-row" style={{ marginTop: 8 }}>
              <Button busy={act.busy} onClick={() => act.run(() => api.post(`/samples/${s.id}/as5-results`), 'H5 hesaplandı.')}>H5’i hesapla</Button>
            </div>
            {e && (
              <Verdict ok={e.verdict === 'target_met_point_estimate' ? true : e.verdict === 'target_not_met' ? false : null}>
                <h4>H5: {({ target_met_point_estimate: 'hedef nokta tahmininde karşılandı', target_not_met: 'hedef karşılanmadı', descriptive_only: 'yalnız tanımlayıcı (katılım koşulu sağlanmadı)' } as any)[e.verdict]}</h4>
                <p>Birlikte olumlu ağırlıklı oran {pct(e.joint_rate)} · %95 GA {ci(e.ci95, true)} (koordinatör kümelenmiş) · hedef &gt; %70</p>
                <p>Anlamlı {pct(e.meaningful_rate)} · uygulanabilir {pct(e.feasible_rate)} · tamamlanma {pct(e.completion_rate)} · {e.coordinators} koordinatör</p>
                <p>Eksik incelemeler için uç durum sınırları: {ci(e.extreme_case_bounds, true)} (güven aralığı değildir)</p>
              </Verdict>
            )}
          </Panel>
        )
      })}
    </Page>
  )
}

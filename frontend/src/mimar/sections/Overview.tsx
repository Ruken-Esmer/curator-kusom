import { api } from '../api'
import { hasRole, useMimar } from '../state'
import { Button, ci, Note, Page, Panel, pct, Stat, useAction, useLoad, Verdict } from '../ui'

const STAGES = [
  ['Veri', 'dondurulmuş sürüm', (o: any) => o?.frozen_datasets > 0],
  ['AS1', 'kilitli test değerlendirildi', (o: any) => o?.as1_samples?.test > 0 && o?.as1_samples?.evaluated > 1],
  ['AS2', 'kör doğrulama havuzu', (o: any) => o?.pools > 0],
  ['AS3–AS4', 'kurul kararı ve odak grup (kurum içi süreç)', () => false],
  ['AS5', 'koordinatör değerlendirmesi', () => false],
  ['AS6', 'değişiklik etkisi izlendi', (o: any) => o?.changesets > 0],
] as const

export default function Overview({ overview: o }: { overview: any }) {
  const user = useMimar((s) => s.user)
  const demo = useLoad(() => api.get('/demo/summary').catch(() => null), [])
  const act = useAction()
  const d = demo.data
  return (
    <Page title="Genel durum"
      lead="MİMAR otomatik müfredat kararı vermez; kaynaklı aday bulgular üretir. Kararlar uzmanlar ve Müfredat Geliştirme ve Koordinasyon Kurulu'ndadır."
      actions={hasRole(user, 'admin') && o?.demo_available ? (
        <Button onClick={() => act.run(() => api.post('/demo/run'), 'Sentetik demo yeniden kuruldu.')} busy={act.busy}>
          Sentetik demoyu yeniden çalıştır</Button>) : undefined}>
      {act.error && <Note tone="error">{act.error}</Note>}
      <div className="m-strip" style={{ marginBottom: 16 }}>
        {STAGES.map(([t, s, f]) => <div key={t} className={f(o) ? 'is-done' : ''}><b>{t}</b><span>{s}</span></div>)}
      </div>
      <div className="m-grid m-grid-4" style={{ marginBottom: 16 }}>
        <Panel><Stat label="Veri sürümü (dondurulmuş)" value={`${o?.frozen_datasets ?? 0} / ${o?.datasets ?? 0}`} /></Panel>
        <Panel><Stat label="Analiz çalıştırması" value={o?.analyses} hint={`${o?.plans_locked ?? 0} ön kayıt kilitli`} /></Panel>
        <Panel><Stat label="Rapor / doğrulama havuzu" value={`${o?.reports ?? 0} / ${o?.pools ?? 0}`} /></Panel>
        <Panel><Stat label="Kayıtlı uzman emeği" value={`${o?.effort?.total_person_hours ?? 0} kişi-saat`} /></Panel>
      </div>
      <Panel title="Denetim zinciri" aside={o?.audit?.valid ? <span>{o.audit.entries} kayıt</span> : null}>
        {o?.audit?.valid ? <Note tone="ok">Değişiklik günlüğü bütün; hash zinciri doğrulandı.</Note>
          : <Note tone="error">Hash zinciri bozuk — kayıt {o?.audit?.broken_at}. Yöneticiye bildirin.</Note>}
      </Panel>
      {d && (
        <Panel title="Son sentetik demo sonuçları" aside={<span>Simüle değerlendiriciler · yalnızca örnek amaçlı</span>}>
          <Note tone="warn">Bu sayılar yapay veri ve simüle insan kararlarıyla üretildi. Hipotezler hakkında kanıt değildir; akışın ve kestiricilerin çalıştığını gösterir.</Note>
          <div className="m-grid m-grid-2">
            <Verdict ok={d.as1?.h1?.verdict === 'supported' ? true : d.as1?.h1?.verdict === 'not_supported' ? false : null}>
              <h4>H1 · {({ supported: 'desteklendi', not_supported: 'desteklenmedi', inconclusive_insufficient_positives: 'kesin yargı yok' } as any)[d.as1?.h1?.verdict] ?? '—'}</h4>
              <p>Hibrit ağırlıklı duyarlılık {d.as1?.h1?.criterion_sensitivity?.estimate} (eşik 0,80)</p>
              <p>Hibrit − {d.as1?.comparator} PKD farkı %95 GA: {ci(d.as1?.ppv_difference?.ci95)}</p>
              <p>Başlangıç uyumu: Gwet AC1 {d.as1?.agreement?.ac1}, κ {d.as1?.agreement?.kappa}</p>
            </Verdict>
            <Verdict ok={d.as2a?.h2a?.met}>
              <h4>H2a · ΔMU {d.as2a?.main?.delta_pp} yp</h4>
              <p>%95 GA {ci(d.as2a?.main?.ci95, false, 1)} · kabul sınırı −10 yp</p>
              <p>MİMAR {pct(d.as2a?.main?.rate_M)} · uzman {pct(d.as2a?.main?.rate_U)} · ortak {d.as2a?.shared_findings}</p>
            </Verdict>
            <Verdict ok={d.as2b?.met_point_estimate}>
              <h4>H2b · yeni doğrulanmış pay {pct(d.as2b?.share)}</h4>
              <p>{d.as2b?.new_verified_direct} yeni doğrulanmış / {d.as2b?.total_unique_candidates} benzersiz aday (hedef ≥ %10)</p>
            </Verdict>
            <Verdict ok={d.as5?.verdict === 'target_met_point_estimate' ? true : d.as5?.verdict === 'target_not_met' ? false : null}>
              <h4>H5 · birlikte olumlu {pct(d.as5?.joint_rate)}</h4>
              <p>%95 GA {ci(d.as5?.ci95, true)} · {d.as5?.coordinators} koordinatör · uç durum sınırları {ci(d.as5?.extreme_case_bounds, true)}</p>
            </Verdict>
            {d.as6_controlled && (
              <Verdict ok={d.as6_controlled.met}>
                <h4>H6 · kontrollü {d.as6_controlled.scenarios} senaryo</h4>
                <p>Doğrulanmış uyarı {pct(d.as6_controlled.verified_alert_rate)} (&gt; %70) · kaçırılan {pct(d.as6_controlled.missed_expected_rate)} (&lt; %20)</p>
              </Verdict>
            )}
            <Verdict ok={null}>
              <h4>AS6 · gerçek değişiklik (tanımlayıcı)</h4>
              <p>{d.as6_real?.alerts} uyarı · {d.as6_real?.verified_alerts} doğrulandı · {d.as6_real?.missed_expected}/{d.as6_real?.total_expected} beklenen etki kaçırıldı</p>
            </Verdict>
          </div>
        </Panel>
      )}
    </Page>
  )
}

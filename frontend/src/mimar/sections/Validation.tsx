import { useState } from 'react'
import { api } from '../api'
import { hasRole, useMimar } from '../state'
import { Button, ci, Feedback, Field, Note, Page, Panel, pct, Pill, Select, Table, useAction, useLoad, Verdict } from '../ui'
import { CAT } from './Findings'

function MatchBuilder() {
  const reps = useLoad(() => api.get('/reports'), [])
  const act = useAction()
  const [m, setM] = useState(''); const [u, setU] = useState('')
  const [prop, setProp] = useState<any>(null)
  const [ok, setOk] = useState<Record<string, boolean>>({})
  const locked = (reps.data ?? []).filter((r: any) => r.locked)
  const opt = (src: string) => locked.filter((r: any) => r.source === src).map((r: any) => ({ value: r.id, label: `${r.source} · ${r.n_findings} aday · ${r.id}` }))
  const [c, setC] = useState(''); const [e, setE] = useState('')
  return (
    <Panel title="Standardizasyon ve havuz oluşturma">
      <Note tone="info">Standardizasyon yalnız biçim, terminoloji, kimlik gizleme ve sıralamayı kapsar; kategori, kapsam, kanıt ve eğitsel anlam değiştirilmez. Ortak bulgular kurula bir kez sunulur.</Note>
      <div className="m-row">
        <Field label="MİMAR–Çekirdek"><Select value={m} onChange={setM} options={opt('mimar_core')} /></Field>
        <Field label="Uzman–Çekirdek"><Select value={u} onChange={setU} options={opt('expert_core')} /></Field>
        <Button disabled={!m || !u} busy={act.busy} onClick={async () => { const r: any = await act.run(() => api.post('/pools/matches', { mimar_report: m, expert_report: u })); if (r) { setProp(r); setOk(Object.fromEntries(r.suggestions.map((s: any) => [s.mimar + s.expert, false]))) } }}>Eşleşmeleri öner</Button>
      </div>
      {prop && (
        <>
          <p className="m-text-sm">{prop.matches.length} otomatik eşleşme (aynı kategori ve aynı ögeler). Aşağıdaki {prop.suggestions.length} öneriyi onaylayın veya reddedin:</p>
          <Table dense cols={[{ key: 'ok', label: 'Onay', render: (s) => <input type="checkbox" checked={!!ok[s.mimar + s.expert]} onChange={(x) => setOk({ ...ok, [s.mimar + s.expert]: x.target.checked })} /> },
            { key: 'mimar', label: 'MİMAR anahtarı' }, { key: 'expert', label: 'Uzman anahtarı' }, { key: 'jaccard', label: 'Öge Jaccard', num: true }]} rows={prop.suggestions} empty="Onay bekleyen öneri yok." />
          <Button kind="primary" busy={act.busy} onClick={() => act.run(() => api.post('/pools', { reports: { M: m, U: u }, confirmed_matches: [...prop.matches, ...prop.suggestions.filter((s: any) => ok[s.mimar + s.expert])], purpose: 'as2a' }), 'Kör doğrulama havuzu oluşturuldu.')}>AS2a havuzunu oluştur</Button>
        </>
      )}
      <div className="m-row" style={{ marginTop: 14 }}>
        <Field label="AS2b · Çekirdek"><Select value={c} onChange={setC} options={opt('mimar_core')} /></Field>
        <Field label="AS2b · Genişletilmiş"><Select value={e} onChange={setE} options={opt('mimar_extended')} /></Field>
        <Button disabled={!c || !e} busy={act.busy} onClick={() => act.run(() => api.post('/pools', { reports: { C: c, E: e }, purpose: 'as2b' }), 'AS2b havuzu (yalnız yeni adaylar) oluşturuldu.')}>AS2b havuzunu oluştur</Button>
      </div>
      <Feedback a={act} />
    </Panel>
  )
}

function PoolDetail({ p }: { p: any }) {
  const user = useMimar((s) => s.user)
  const st = useLoad(() => api.get(`/pools/${p.id}/status`), [p.id])
  const users = useLoad(() => api.get('/users').catch(() => []), [])
  const act = useAction()
  const [v1, setV1] = useState(''); const [v2, setV2] = useState(''); const [adj, setAdj] = useState('')
  const opts = (role: string) => (users.data ?? []).filter((x: any) => x.roles.includes(role)).map((x: any) => ({ value: x.username, label: x.display_name }))
  const s = st.data
  const r = p.as2a
  const b = p.as2b
  return (
    <Panel title={`${p.purpose === 'as2a' ? 'AS2a · MİMAR–uzman karşılaştırması' : 'AS2b · KuLearn ek katkısı'}`}
      aside={<>{p.sealed ? <Pill tone="lock">kaynaklar mühürlü</Pill> : <Pill tone="brand">mühür açıldı</Pill>}<span>{p.n_entries} bulgu</span></>}>
      {!p.validators?.length && hasRole(user, 'admin') && (
        <div className="m-row">
          <Field label="Preklinik doğrulayıcı"><Select value={v1} onChange={setV1} options={opts('validator')} /></Field>
          <Field label="Klinik doğrulayıcı"><Select value={v2} onChange={setV2} options={opts('validator')} /></Field>
          <Field label="Üçüncü kişi"><Select value={adj} onChange={setAdj} options={opts('adjudicator')} /></Field>
          <Button disabled={!v1 || !v2} busy={act.busy} onClick={() => act.run(() => api.post(`/pools/${p.id}/assign`, { reviewers: [v1, v2], adjudicator: adj || null }), 'Doğrulayıcılar atandı.')}>Ata</Button>
        </div>
      )}
      {s && (
        <>
          <p className="m-text-sm">Nihai karar: {s.final} / {s.entries} · bekleyen uyuşmazlık: {s.conflicts.length}</p>
          {s.agreement?.final_verification && (
            <Table dense cols={[{ key: 'd', label: 'Boyut' }, { key: 'percent', label: 'Yüzde uyum', num: true }, { key: 'kappa', label: 'Cohen κ', num: true }, { key: 'ac1', label: 'Gwet AC1', num: true }]}
              rows={[['Veri desteği', 'support'], ['Eğitsel anlamlılık', 'meaningful'], ['Kategori', 'category_ok'], ['Nihai doğrulama', 'final_verification']].map(([d, k]) => ({ d, ...s.agreement[k] }))} />)}
          {s.quality_threshold_met === false && <Note tone="warn">Nihai doğrulamada AC1 &lt; 0,60: değerlendirme durdurulmalı, karar tanımları açıklanmalı ve yeniden kalibrasyon yapılmalıdır.</Note>}
        </>
      )}
      {hasRole(user, 'admin') && (
        <div className="m-row" style={{ marginTop: 8 }}>
          <Button kind="primary" busy={act.busy} disabled={!s?.complete} onClick={() => act.run(() => api.post(`/pools/${p.id}/${p.purpose}`), 'Sonuçlar hesaplandı.')}>
            {p.purpose === 'as2a' ? 'Mührü aç ve ΔMU’yu hesapla' : 'H2b’yi hesapla'}</Button>
          {!s?.complete && <span className="m-muted m-text-sm">Mühür yalnız bütün kararlar kesinleşince açılır.</span>}
        </div>
      )}
      <Feedback a={act} />
      {r && (
        <div className="m-grid m-grid-2" style={{ marginTop: 12 }}>
          <Verdict ok={r.h2a.met}>
            <h4>H2a: {r.h2a.met ? 'kabul sınırı içinde' : 'kabul sınırı içinde değil'}</h4>
            <p>ΔMU = {r.main.delta_pp} yp · %95 GA {ci(r.main.ci95, false, 2)} · bağlı aile kümelenmiş bootstrap ({r.main.clusters} aile)</p>
            <p>MİMAR {r.main.V_M}/{r.main.N_M} ({pct(r.main.rate_M)}) · Uzman {r.main.V_U}/{r.main.N_U} ({pct(r.main.rate_U)})</p>
            <p>Sınır duyarlılığı: {Object.entries(r.h2a.margin_sensitivity).map(([k, v]) => `${k} ${v ? '✓' : '✗'}`).join(' · ')}</p>
            <p>Veri yetersiz dışlanınca: {r.sensitivity_insufficient_excluded.delta_pp} yp</p>
          </Verdict>
          <Panel title="Kategoriye göre">
            <Table dense cols={[{ key: 'c', label: 'Kategori' }, { key: 'M_unique', label: 'Yalnız MİMAR', num: true }, { key: 'U_unique', label: 'Yalnız uzman', num: true }, { key: 'shared', label: 'Ortak', num: true }, { key: 'verified', label: 'Doğrulanan', num: true }]}
              rows={Object.entries(r.by_category).map(([c, v]: any) => ({ c: CAT[c], ...v }))} />
            <p className="m-muted m-text-sm">Körleme kontrolü: kaynak tahmini doğruluğu {pct(r.blinding_check.accuracy)} (n = {r.blinding_check.n}, %95 GA {ci(r.blinding_check.ci95, true)}). Sınıflandırması düzeltilen: {r.category_corrected}.</p>
          </Panel>
        </div>
      )}
      {b && (
        <Verdict ok={b.met_point_estimate}>
          <h4>H2b: yeni doğrulanmış pay {pct(b.share)} (hedef ≥ %10, nokta tahmini)</h4>
          <p>{b.new_verified_direct} yeni doğrulanmış / {b.total_unique_candidates} benzersiz genişletilmiş aday · {b.new_candidates} yeni aday incelendi</p>
          <p>Çekirdekte olup genişletilmiş raporda kaybolan: {b.core_candidates_lost_in_extended} (payda/paya eklenmez; rapordan çıkma sorunun giderildiğini göstermez)</p>
        </Verdict>
      )}
    </Panel>
  )
}

export default function ValidationSection() {
  const user = useMimar((s) => s.user)
  const pools = useLoad(() => api.get('/pools'), [])
  return (
    <Page title="AS2 · Kör doğrulama" lead="Raporlar kilitlendikten sonra, hazırlama ve doğrulamada görev almayan kişi kaynak tanımlayıcılarını kaldırır ve sıralamayı rastgeleleştirir. Bağımsız kurul kararlarını kilitledikten sonra mühür açılır.">
      {hasRole(user, 'standardizer') && <MatchBuilder />}
      {(pools.data ?? []).map((p: any) => <PoolDetail key={p.id} p={p} />)}
      {!pools.data?.length && <Note tone="info">Henüz doğrulama havuzu yok.</Note>}
    </Page>
  )
}

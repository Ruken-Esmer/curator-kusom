import { useState } from 'react'
import { api } from '../api'
import { hasRole, useMimar } from '../state'
import { Button, Feedback, Field, Note, Page, Panel, pct, ci, Pill, Select, Table, useAction, useLoad, Verdict } from '../ui'

const TYPE: Record<string, string> = { new_link: 'Yeni bağlantı', removed_link: 'Kalkan bağlantı', changed_link: 'Değişen bağlantı',
  ucep_link_added: 'UÇEP bağlantısı eklendi', ucep_link_removed: 'UÇEP bağlantısı kaldırıldı', coverage_lost: 'UÇEP karşılığı kayboldu', coverage_gained: 'UÇEP karşılığı oluştu' }

function Changeset({ cs }: { cs: any }) {
  const user = useMimar((s) => s.user)
  const d = useLoad(() => api.get(`/changesets/${cs.id}`), [cs.id])
  const act = useAction()
  const [exp, setExp] = useState('[\n  {"type": "removed_link", "entity": "LO-A|LO-B"}\n]')
  const [ev, setEv] = useState<any>(null)
  const rep = d.data?.report
  // session titles for both versions, so alerts read as text rather than ids
  const names = useLoad(async () => {
    const m: Record<string, string> = {}
    for (const id of [cs.t0, cs.t1]) for (const r of await api.get(`/datasets/${id}/los?limit=5000`)) m[r.uid] = `${r.year}. sınıf · ${r.course} · ${r.text}`
    return m
  }, [cs.id])
  const label = (k: string) => k.split('|').map((u) => <div key={u}>{names.data?.[u] ?? u}</div>)
  const canExpect = hasRole(user, 'coordinator', 'impact_evaluator')
  return (
    <Panel title={cs.description || `Değişiklik ${cs.id}`} aside={<><Pill tone={cs.kind === 'real' ? 'brand' : 'plain'}>{cs.kind === 'real' ? 'gerçek değişiklik' : 'kontrollü'}</Pill>{cs.expected_locked ? <Pill tone="lock">beklenen etkiler kilitli ({cs.expected_count})</Pill> : <Pill tone="warn">beklenen etkiler açık</Pill>}</>}>
      {!cs.expected_locked && canExpect && (
        <>
          <Note tone="info">Beklenen etkileri T0–T1 kayıtlarından, MİMAR raporunu görmeden kaydedin. Teknik ekip bu listeyi göremez.</Note>
          <Field label="Beklenen etkiler (JSON)"><textarea className="m-input" rows={5} value={exp} onChange={(e) => setExp(e.target.value)} /></Field>
          <div className="m-row" style={{ marginTop: 8 }}>
            <Button busy={act.busy} onClick={() => act.run(() => api.post(`/changesets/${cs.id}/expected`, { effects: JSON.parse(exp) }), 'Kaydedildi.')}>Kaydet</Button>
            <Button kind="primary" busy={act.busy} onClick={() => act.run(() => api.post(`/changesets/${cs.id}/expected/lock`), 'Beklenen etkiler kilitlendi.')}>Kilitle</Button>
          </div>
        </>
      )}
      {cs.expected_locked && !rep && hasRole(user, 'admin', 'technical') &&
        <Button kind="primary" busy={act.busy} onClick={() => act.run(() => api.post(`/changesets/${cs.id}/run`), 'Etki raporu üretildi.')}>Etki raporunu üret</Button>}
      {rep && (
        <>
          <p className="m-text-sm">Fark: {rep.diff.added.length} eklenen · {rep.diff.removed.length} kaldırılan · {rep.diff.modified.length} metni değişen · {rep.diff.relinked.length} yeniden ilişkilendirilen hedef. Yalnız sıralama kayması nedeniyle değişen {rep.rank_shift_only.length} çift uyarı sayılmadı.</p>
          <Table dense cols={[{ key: 'id', label: 'Uyarı' }, { key: 'type', label: 'Tür', render: (a) => TYPE[a.type] ?? a.type },
            { key: 'entity', label: 'Öge', render: (a) => label(a.entity) }, { key: 'cause', label: 'Kaynak değişiklik', render: (a) => label(a.cause.join('|')) },
            ...(canExpect ? [{ key: 'v', label: 'Kanıtla değerlendir', render: (a: any) => <span className="m-row">
              <Button kind="quiet" onClick={() => act.run(() => api.post(`/changesets/${cs.id}/alerts/${a.id}`, { verified: true }))}>doğru</Button>
              <Button kind="quiet" onClick={() => act.run(() => api.post(`/changesets/${cs.id}/alerts/${a.id}`, { verified: false }))}>gereksiz</Button></span> }] : [])]}
            rows={rep.alerts} empty="Uyarı yok." />
          {canExpect && <Button busy={act.busy} onClick={async () => setEv(await act.run(() => api.post(`/changesets/${cs.id}/evaluate`)))}>Beklenen etkilerle karşılaştır</Button>}
          {!ev && cs.evaluation && <Note tone="info">{cs.evaluation.verified_alerts}/{cs.evaluation.total_alerts} uyarı doğrulandı · {cs.evaluation.missed_expected}/{cs.evaluation.total_expected} beklenen etki sistemce gösterilmedi.</Note>}
          {ev && <Note tone="info">{ev.verified_alerts}/{ev.total_alerts} uyarı doğrulandı · {ev.missed_expected}/{ev.total_expected} beklenen etki kaçırıldı. {ev.note}</Note>}
        </>
      )}
      <Feedback a={act} />
    </Panel>
  )
}

export default function ImpactSection() {
  const user = useMimar((s) => s.user)
  const ds = useLoad(() => api.get('/datasets'), [])
  const cfgs = useLoad(() => api.get('/configs'), [])
  const list = useLoad(() => api.get('/changesets'), [])
  const act = useAction()
  const [t0, setT0] = useState(''); const [t1, setT1] = useState(''); const [cfg, setCfg] = useState(''); const [desc, setDesc] = useState('')
  const [ctl, setCtl] = useState<any>(null)
  const frozen = (ds.data ?? []).filter((d: any) => d.status === 'frozen').map((d: any) => ({ value: d.id, label: `${d.name} · ${d.version_label}` }))
  const cfgOpts = (cfgs.data ?? []).map((c: any) => ({ value: c.id, label: `${c.name} · ${c.hash}` }))
  return (
    <Page title="AS6 · Değişiklik etkisinin izlenmesi" lead="Öncelik, kurulca onaylanmış, uygulanmış ve sürümlü kayıtlara işlenmiş gerçek değişikliklerdir. Etki müfredat kayıtlarıyla sınırlıdır; öğrenci öğrenmesi veya klinik performans etkisi değildir.">
      {hasRole(user, 'admin', 'technical') && (
        <Panel title="Değişiklik kaydı oluştur">
          <div className="m-row">
            <Field label="T0 (önce)"><Select value={t0} onChange={setT0} options={frozen} /></Field>
            <Field label="T1 (sonra)"><Select value={t1} onChange={setT1} options={frozen} /></Field>
            <Field label="Ayar sürümü"><Select value={cfg} onChange={setCfg} options={cfgOpts} /></Field>
            <Field label="Açıklama / karar no"><input className="m-input" value={desc} onChange={(e) => setDesc(e.target.value)} /></Field>
            <Button kind="primary" disabled={!t0 || !t1 || !cfg} busy={act.busy} onClick={() => act.run(() => api.post('/changesets', { t0, t1, config_id: cfg, description: desc }), 'Değişiklik kaydı oluşturuldu.')}>Oluştur</Button>
          </div>
          <div className="m-row" style={{ marginTop: 12 }}>
            <span className="m-muted m-text-sm">Gerçek örneklerle bir değişiklik türü incelenemiyorsa ayrı test kopyasında en az 24 kontrollü senaryo (tür başına ≥ 8) çalıştırılır:</span>
            <Button disabled={!t0 || !cfg} busy={act.busy} onClick={async () => setCtl(await act.run(() => api.post(`/datasets/${t0}/controlled-test`, { config_id: cfg, per_type: 8 })))}>Kontrollü senaryoları çalıştır (T0 kopyası)</Button>
          </div>
          <Feedback a={act} />
        </Panel>
      )}
      {ctl && (
        <Verdict ok={ctl.overall.met}>
          <h4>H6: {ctl.overall.met ? 'iki koşul birlikte karşılandı' : `karşılanmayan: ${ctl.overall.unmet_criteria.join(', ')}`}</h4>
          <p>Doğrulanmış uyarı {pct(ctl.overall.verified_alert_rate)} (%95 GA {ci(ctl.overall.verified_ci95, true)}, hedef &gt; %70) · kaçırılan beklenen etki {pct(ctl.overall.missed_expected_rate)} (%95 GA {ci(ctl.overall.missed_ci95, true)}, hedef &lt; %20)</p>
          <p>{ctl.overall.scenarios} senaryo · {ctl.overall.alerts} uyarı · {ctl.overall.expected_effects} beklenen etki. Tür bazındaki sonuçlar tanımlayıcıdır: {Object.entries(ctl.by_type).map(([t, v]: any) => `${t} ${pct(v?.verified_alert_rate)} / ${pct(v?.missed_expected_rate)}`).join(' · ')}</p>
        </Verdict>
      )}
      {(list.data ?? []).map((cs: any) => <Changeset key={cs.id} cs={cs} />)}
    </Page>
  )
}

import { ReactNode, useState } from 'react'
import { api } from './api'
import { Button, Note, Page, Panel, Pill, Stat, Table, useAction, useLoad } from './ui'

type S = { year: number | null; course: string; text: string; excluded?: boolean }
const sess = (s: S) => <>{s.year ? `${s.year}. sınıf · ` : ''}{s.course ? `${s.course} · ` : ''}{s.text}</>
const pc = (v?: number | null) => (v == null ? '—' : `%${Math.round(v * 100)}`)
const Example = () => <Pill tone="warn">örnek</Pill>
const Missing = ({ children = 'eksik' }: { children?: ReactNode }) => <Pill tone="bad">{children}</Pill>
const Real = () => <Pill tone="ok">gerçek veri</Pill>
const Q = ({ children }: { children: ReactNode }) => <p className="text-[15px] font-semibold mb-3">{children}</p>

export const SCREENS = [
  { id: 'veriler', label: 'Veriler', q: 'Elimizde hangi veriler var, hangileri eksik?' },
  { id: 'karsilastirma', label: 'Karşılaştırma', q: 'Hangi dersler birbirine benziyor?' },
  { id: 'uzman', label: 'Uzman incelemesi', q: 'Uzmanlar ne buldu, sistem ne buldu?' },
  { id: 'kurul', label: 'Kurul kararları', q: 'Kurul neye karar verdi, müfredatta ne değişti?' },
  { id: 'tum', label: 'Tüm müfredat', q: 'Aynı inceleme bütün müfredatta ne gösteriyor?' },
  { id: 'etki', label: 'Değişikliğin etkisi', q: 'Değişiklikten sonra beklenenler oldu mu?' },
  { id: 'fakulteler', label: 'Diğer fakülteler', q: 'Başka bir fakülte bu incelemeyi yapabilir mi?' },
] as const
export type ScreenId = typeof SCREENS[number]['id']

function Records({ kind, rows, fields, empty }: { kind: string; rows: any[]; fields: { key: string; label: string }[]; empty: string }) {
  const act = useAction()
  const [f, setF] = useState<Record<string, string>>({})
  return <>
    <Table dense rows={rows} empty={empty} cols={[
      ...fields.map((x) => ({ key: x.key, label: x.label })),
      { key: 'by_name', label: 'Kaydeden' }, { key: 'e', label: '', render: (r: any) => (r.example ? <Example /> : null) }]} />
    <div className="flex flex-wrap gap-2 mt-3 items-end">
      {fields.map((x) => (
        <label key={x.key} className="flex flex-col text-[12px] text-zinc-600 gap-1" style={{ flex: x.key === 'text' || x.key === 'note' ? 3 : 1 }}>
          {x.label}
          <input className="m-input" value={f[x.key] ?? ''} onChange={(e) => setF({ ...f, [x.key]: e.target.value })} />
        </label>
      ))}
      <Button busy={act.busy} disabled={!Object.values(f).some(Boolean)}
        onClick={() => act.run(() => api.post('/prototype/records', { kind, ...f }), 'Kaydedildi.').then(() => setF({}))}>Kaydet</Button>
    </div>
    {act.error && <Note tone="error">{act.error}</Note>}
  </>
}

function Check({ kind, k, check }: { kind: string; k: string; check?: any }) {
  const act = useAction()
  if (check) return <span className="whitespace-nowrap">{check.ok ? 'onaylandı' : 'düzeltilmeli'} {check.example && <Example />}</span>
  return <span className="flex gap-1">
    <Button kind="quiet" busy={act.busy} onClick={() => act.run(() => api.post('/prototype/records', { kind, key: k, ok: true }))}>Doğru</Button>
    <Button kind="quiet" busy={act.busy} onClick={() => act.run(() => api.post('/prototype/records', { kind, key: k, ok: false }))}>Düzeltilmeli</Button>
  </span>
}

function Veriler({ d }: { d: any }) {
  const [q, setQ] = useState('')
  return <>
    <Panel title="Yüklenen veriler" aside={<Real />}>
      <Table dense rows={d.versions} cols={[
        { key: 'label', label: 'Sürüm', render: (v) => (v.label === 'T0' ? 'İlk sürüm' : 'Kurul kararından sonra') },
        { key: 'description', label: 'İçerik' }, { key: 'count', label: 'İncelenen başlık', num: true },
        { key: 'frozen', label: 'Durum', render: (v) => (v.frozen ? 'değiştirilemez' : 'taslak') }]} />
    </Panel>
    <Panel title="Ders programından ne alındı?" aside={<Real />} className="mt-4">
      <div className="flex flex-wrap gap-3 mb-3">
        <Stat label="ders programındaki oturum" value={d.received} />
        <Stat label="incelemeye alındı" value={d.included} />
        <Stat label="dışarıda kaldı" value={d.excluded} />
      </div>
      {d.reasons.map((r: any) => <p key={r.reason} className="text-[14px]">{r.n} oturum dışarıda kaldı: {r.reason}. Örnekler: <i>{d.excluded_examples.slice(0, 6).join(' · ')}</i></p>)}
      <Note tone="warn">Eksik: {d.missing.join('; ')}. Şimdilik yalnız oturum başlıklarıyla çalışılıyor.</Note>
    </Panel>
    <Panel title="Osteoartrit hangi oturumlarda?" aside={<Real />} className="mt-4">
      <Table dense rows={d.oa_rows} cols={[{ key: 's', label: 'Oturum', render: (r) => sess(r) },
        { key: 'x', label: '', render: (r) => (r.excluded ? <Missing>başlık çok kısa, dışarıda kaldı</Missing> : 'incelemede') }]} />
    </Panel>
    <Panel title="UÇEP maddelerinin İngilizce karşılıkları doğru mu?" className="mt-4">
      <input className="m-input mb-2" placeholder="Madde ara" value={q} onChange={(e) => setQ(e.target.value)} />
      <Table dense rows={d.ucep.filter((u: any) => !q || (u.tr + u.en).toLowerCase().includes(q.toLowerCase()))} cols={[
        { key: 'tr', label: 'UÇEP (Türkçe)' }, { key: 'en', label: 'Kullanılan İngilizce karşılık' },
        { key: 'c', label: 'Uzman kontrolü', render: (u) => <Check kind="ucep_check" k={u.code} check={u.check} /> }]} />
    </Panel>
    <Panel title="Konu terimleri doğru mu?" className="mt-4">
      <p className="text-[13px] text-zinc-600 mb-2">Oturumlar için önerilen konu terimi. Kaynak: UÇEP-2020 madde 237'nin İngilizce adı. Uzman onaylayana kadar kullanılmaz.</p>
      <Table dense rows={d.terms} cols={[{ key: 's', label: 'Oturum', render: (r) => sess(r) }, { key: 'suggested', label: 'Önerilen terim' },
        { key: 'c', label: 'Uzman kontrolü', render: (r) => <Check kind="term_check" k={r.uid} check={r.check} /> }]} />
    </Panel>
  </>
}

function Karsilastirma({ d }: { d: any }) {
  const M = (m: any) => <span className="text-[12px] text-zinc-600 whitespace-nowrap">kelime {m.bm25 ?? '—'}. · anlam {m.embedding ?? '—'}. · kavram {m.graph ?? '—'}.</span>
  const card = d.card
  const word = (v: string) => (v === 'overlap' ? 'aynı şeyi anlatıyor' : v === 'no_overlap' ? 'farklı' : 'karar veremedi')
  return <>
    <Panel title="En çok benzeyen oturum çiftleri" aside={<Real />}>
      <p className="text-[13px] text-zinc-600 mb-2">{d.titles} başlık üç ayrı yolla karşılaştırıldı: ortak kelimeler, anlam yakınlığı ve kavram bağlantıları. Sıra, üçünün birleşimidir.</p>
      <Table dense rows={d.top} cols={[{ key: 'rank', label: 'Sıra', num: true }, { key: 'a', label: 'Oturum', render: (r) => sess(r.a) },
        { key: 'b', label: 'Benzediği oturum', render: (r) => sess(r.b) }, { key: 'm', label: 'Her yoldaki sırası', render: (r) => M(r.methods) }]} />
    </Panel>
    <Panel title="Osteoartrit oturumları listede nerede?" aside={<Real />} className="mt-4">
      <p className="text-[14px] mb-2">Osteoartritle ilgili bir oturumun geçtiği ilk çift {d.oa_first_rank}. sırada. Başlıklar kısa ve az ortak kelime içerdiği için osteoartrit oturumları birbirine benzer görünmüyor.</p>
      <Table dense rows={d.oa_pairs} cols={[{ key: 'rank', label: 'Sıra', num: true }, { key: 'a', label: 'Oturum', render: (r) => sess(r.a) },
        { key: 'b', label: 'Benzediği oturum', render: (r) => sess(r.b) }]} />
    </Panel>
    <div className="grid gap-4 mt-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))' }}>
      <Panel title="Hakemlerin gördüğü kart" aside={<Example />}>
        {card && <div className="rounded border border-zinc-300 bg-zinc-50 p-3 text-[14px]">
          <p className="text-zinc-500 mb-2">Bu iki oturum aynı şeyi mi anlatıyor?</p>
          <p>A · {sess(card.a)}</p><p>B · {sess(card.b)}</p>
          <p className="mt-2 text-[13px]">{Object.entries(card.decisions).map(([k, v]) => `${k.replace('hakem', 'Hakem ')}: ${word(v as string)}`).join(' · ')}</p>
        </div>}
        <p className="text-[13px] text-zinc-600 mt-2">Hakemler çifti hangi yolun bulduğunu görmez. İki hakem anlaşamazsa üçüncü hakem karar verir.</p>
      </Panel>
      <Panel title="Sistem ne kadar doğru buldu?" aside={<Example />}>
        {d.dev && <p className="text-[14px]">Deneme turunda {d.dev.n} çift incelendi; hakemler {pc(d.dev.agreement)} oranında anlaştı, {d.dev.conflicts} çifte üçüncü hakem baktı. Hakemlerin “aynı” dediği {d.dev.positives} çiftin {pc(d.dev.sensitivity)}’ini sistem listesinin üst kısmında gösterdi.</p>}
        {d.test && <p className="text-[14px] mt-2">Sonuç turunda {d.test.n} çiftten yalnız {d.test.positives} tanesi “aynı” bulundu. Bu sayı karar vermek için az; sonuç “belirsiz”.</p>}
        <p className="text-[13px] text-zinc-600 mt-2">Kurallar sonuç turundan önce kilitlendi ve sonradan değiştirilemez.</p>
      </Panel>
    </div>
  </>
}

function Uzman({ d }: { d: any }) {
  const V = (v: boolean | null | undefined) => (v == null ? '—' : v ? 'doğrulandı' : 'doğrulanmadı')
  return <>
    <Panel title="Uzmanların bulguları" aside={<Example />}>
      <Table dense rows={d.expert} cols={[{ key: 'category', label: 'Tür' }, { key: 'statement', label: 'Bulgu' },
        { key: 's', label: 'Oturumlar', render: (f) => f.sessions.length ? f.sessions.map((s: S, i: number) => <div key={i}>{sess(s)}</div>) : f.ucep.join(', ') },
        { key: 'verified', label: 'Doğrulama', render: (f) => V(f.verified) }]} />
    </Panel>
    <Panel title="Sistemin bulguları" aside={<Real />} className="mt-4">
      <p className="text-[14px] mb-2">Sistem {d.system_count} bulgu çıkardı; {d.system_oa.length === 0 ? 'hiçbiri osteoartritle ilgili değil' : `${d.system_oa.length} tanesi osteoartritle ilgili`}. Uzmanlarla ortak bulgu: {d.shared}. İlk beşi:</p>
      <Table dense rows={d.system_examples} cols={[{ key: 'category', label: 'Tür' },
        { key: 's', label: 'Oturumlar', render: (f) => f.sessions.slice(0, 3).map((s: S, i: number) => <div key={i}>{sess(s)}</div>) },
        { key: 'verified', label: 'Doğrulama', render: (f) => V(f.verified) }]} />
    </Panel>
    <div className="grid gap-4 mt-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(330px, 1fr))' }}>
      <Panel title="Kaynağı bilmeden doğrulama" aside={<Example />}>
        <p className="text-[14px]">İki doğrulayıcı bütün bulguları kimin bulduğunu bilmeden inceledi ve {pc(d.agreement)} oranında anlaştı.</p>
        <p className="text-[14px] mt-2">Doğrulanan: sistemden {d.validated.system[0]}/{d.validated.system[1]}, uzmanlardan {d.validated.expert[0]}/{d.validated.expert[1]}.</p>
        <p className="text-[12px] text-zinc-500 mt-2">Kararlar örnek olduğu için bu oranlar bir şey ölçmüyor; ekranın nasıl çalıştığını gösteriyor.</p>
      </Panel>
      <Panel title="Ders içerikleri eklenince" aside={<Example />}>
        <p className="text-[14px]">{d.kulearn.rows} içerik dosyasından {d.kulearn.usable} tanesi kullanıldı{d.kulearn.unusable_reasons.map((r: any) => `; ${r.n} tanesi kullanılamadı (${r.reason})`).join('')}.</p>
        <p className="text-[14px] mt-2">İçeriklerle {d.kulearn.new_findings} yeni bulgu çıktı.</p>
        <p className="text-[12px] text-zinc-500 mt-2">İçerik metinleri örnektir; gerçek ders içerikleri henüz alınmadı.</p>
      </Panel>
      <Panel title="Harcanan zaman" aside={<Example />}>
        {Object.entries(d.hours).map(([k, v]) => <p key={k} className="text-[14px]">{k}: {String(v)} saat</p>)}
        <p className="text-[14px] mt-1 font-semibold">Toplam: {d.hours_total} kişi-saat</p>
      </Panel>
    </div>
  </>
}

function Kurul({ d }: { d: any }) {
  return <>
    <Panel title="Kurul kararları" aside={<Example />}>
      <Records kind="decision" rows={d.decisions} empty="Henüz karar kaydı yok."
        fields={[{ key: 'key', label: 'Karar no' }, { key: 'text', label: 'Karar' }, { key: 'status', label: 'Durum' }]} />
    </Panel>
    <Panel title="Müfredatta ne değişti?" aside={<Example />} className="mt-4">
      <p className="text-[13px] text-zinc-600 mb-2">Onaylanan kararlar ders programına yeni sürüm olarak işlendi. İlk sürüm aynen saklanır.</p>
      <Table dense rows={d.changes} cols={[{ key: 'ref', label: 'Karar no' }, { key: 'op', label: 'Değişiklik' },
        { key: 'b', label: 'Önce', render: (c) => (c.before ? sess(c.before) : '—') }, { key: 'a', label: 'Sonra', render: (c) => (c.after ? sess(c.after) : '—') }]} />
    </Panel>
    <div className="grid gap-4 mt-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))' }}>
      <Panel title="Osteoartrit: önce">
        {d.t0.map((s: S, i: number) => <p key={i} className="text-[14px]">{sess(s)}</p>)}
        <p className="text-[14px] mt-2 font-semibold">Uzun süreli izlem: {d.t0_followup ? 'var' : 'hiçbir oturumda yok'}</p>
      </Panel>
      <Panel title="Osteoartrit: sonra" aside={<Example />}>
        {d.t1.map((s: S, i: number) => <p key={i} className="text-[14px]">{sess(s)}</p>)}
        <p className="text-[14px] mt-2 font-semibold">Uzun süreli izlem: {d.t1_followup ? 'MSKL 503’te bir hedef olarak var' : 'yok'}</p>
      </Panel>
    </div>
    <Panel title="Öğrenci ve öğretim üyesi görüşleri" className="mt-4" aside={d.focus_groups.length ? null : <Missing>henüz yapılmadı</Missing>}>
      <p className="text-[13px] text-zinc-600 mb-2">Odak grupları sistem dışında yapılır; burada yalnız kısa özetleri tutulur. Değişiklikten önce ve sonra ayrı ayrı yapılır.</p>
      <Records kind="focus_group" rows={d.focus_groups} empty="Odak grubu özeti yok."
        fields={[{ key: 'key', label: 'Önce / sonra' }, { key: 'note', label: 'Özet' }]} />
    </Panel>
    <Panel title="Sayılar ve görüşler yan yana" className="mt-4">
      <Table dense rows={[
        { a: 'Tekrar', n: 'Uzman: eklem ağrısı ve ayırıcı tanı dersleri olası tekrar (örnek)', g: d.focus_groups.length ? 'özetlere bakın' : 'eksik' },
        { a: 'UÇEP izlem', n: d.t1_followup ? 'Sonraki sürümde izlem hedefi var (örnek karar)' : 'izlem yok', g: d.focus_groups.length ? 'özetlere bakın' : 'eksik' },
      ]} cols={[{ key: 'a', label: 'Konu' }, { key: 'n', label: 'Kayıtlardan' }, { key: 'g', label: 'Odak gruplarından' }]} />
    </Panel>
  </>
}

function Tum({ d }: { d: any }) {
  const c = d.coordinators
  return <>
    <Panel title="Hangi sınıfların verisi var?" aside={<Real />}>
      <div className="flex gap-2 flex-wrap">
        {d.years.map((y: any) => <div key={y.year} className={`rounded border px-4 py-2 text-[14px] ${y.present ? 'border-zinc-300' : 'border-red-300 bg-red-50'}`}>
          {y.year}. sınıf · {y.present ? 'ders programı var' : 'eksik'}</div>)}
      </div>
      <p className="text-[13px] text-zinc-600 mt-2">Yazılı öğrenim hedefi belgesi yalnız üç blok için var.</p>
    </Panel>
    <Panel title="Bütün müfredatın taraması" aside={<Real />} className="mt-4">
      <div className="flex flex-wrap gap-3">
        <Stat label="oturum başlığı" value={d.titles} /><Stat label="olası gereksiz tekrar" value={d.redundancy} />
        <Stat label="bağlanabilecek ders" value={d.integration} /><Stat label="öncelikli" value={d.high} />
      </div>
      <p className="text-[14px] mt-3">UÇEP hastalıklarından {d.diseases_with_sessions} tanesi derslerde geçiyor; yalnız {d.diseases_with_profile} tanesi (osteoartrit) ayrıntılı incelendi.</p>
    </Panel>
    <Panel title="Blok koordinatörleri ne dedi?" aside={<Example />} className="mt-4">
      <p className="text-[14px]">{c.items} bulgu {c.people} koordinatöre soruldu, {c.done} tanesi cevaplandı.</p>
      <Table dense rows={[{ k: 'Anlamlı', v: pc(c.meaningful) }, { k: 'Uygulanabilir', v: pc(c.feasible) }, { k: 'İkisi birden', v: pc(c.both) }, { k: 'Hedef', v: `%${Math.round(c.target * 100)}’den fazla` }]}
        cols={[{ key: 'k', label: '' }, { key: 'v', label: 'Bulgu oranı' }]} />
      <p className="text-[12px] text-zinc-500 mt-2">Koordinatör kararları örnektir; oranlar bir şey ölçmüyor.</p>
    </Panel>
  </>
}

function Etki({ d }: { d: any }) {
  const items = (x: any) => x.items.map((s: S, i: number) => <div key={i}>{sess(s)}</div>)
  return <>
    <Panel title={d.description} aside={<Example />}>
      <p className="text-[14px] mb-2 font-semibold">Değişiklikten önce yazılan beklentiler</p>
      <Table dense rows={d.expected} cols={[{ key: 'type', label: 'Beklenen' }, { key: 'i', label: 'Oturumlar', render: items },
        { key: 'shown', label: 'Sistem gösterdi mi?', render: (x) => (x.shown ? 'evet' : <Missing>hayır</Missing>) }]} />
      <p className="text-[14px] mt-4 mb-2 font-semibold">Sistemin uyarıları</p>
      <Table dense rows={d.alerts} cols={[{ key: 'type', label: 'Uyarı' }, { key: 'i', label: 'Oturumlar', render: items },
        { key: 'verified', label: 'Doğru mu?', render: (x) => (x.verified ? 'doğru' : 'gereksiz') }]} />
    </Panel>
    <Note tone="warn">{d.total_expected} beklentiden {d.missed} tanesini sistem göstermedi. Yeni izlem hedefi UÇEP maddesine bağlandı, ama osteoartrit dersleriyle ilişkilendirilmedi. Hedef belgeleri gelince bu ölçüm tekrarlanacak.</Note>
  </>
}

function Fakulteler({ d }: { d: any }) {
  const tone = (v: string) => (v === 'var' ? <Pill tone="ok">var</Pill> : v === 'kısmen' ? <Pill tone="warn">kısmen</Pill> : <Missing />)
  return <>
    <Panel title="Bir fakültenin hazırlaması gerekenler" aside={<Real />}>
      <Table dense rows={d.checklist} cols={[{ key: 'item', label: 'Gereken' }, { key: 'k', label: 'KUSOM’da', render: (r) => tone(r.kusom) }, { key: 'note', label: 'Not' }]} />
    </Panel>
    <Panel title="Fakülte ziyaretleri" className="mt-4" aside={d.visits.length ? null : <Missing>henüz yapılmadı</Missing>}>
      <Records kind="visit" rows={d.visits} empty="Ziyaret kaydı yok." fields={[{ key: 'key', label: 'Fakülte' }, { key: 'note', label: 'Özet' }]} />
    </Panel>
    <Panel title="Çalıştay" className="mt-4" aside={d.workshops.length ? null : <Missing>henüz yapılmadı</Missing>}>
      <Records kind="workshop" rows={d.workshops} empty="Çalıştay kaydı yok." fields={[{ key: 'key', label: 'Tarih' }, { key: 'note', label: 'Geri bildirim özeti' }]} />
    </Panel>
  </>
}

export default function Prototype({ screen }: { screen: ScreenId }) {
  const v = useLoad(() => api.get('/prototype'), [])
  const s = SCREENS.find((x) => x.id === screen)!
  const d = v.data
  return (
    <Page title={s.label} lead="Örnek konu: osteoartrit. Veri KUSOM 2025–26 ders programından; “örnek” işaretli kararlar henüz gerçek kişilerce verilmedi.">
      <Q>{s.q}</Q>
      {v.error && <Note tone="error">{v.error.includes('kurulmadı') ? 'Örnek henüz kurulmadı. Giriş ekranındaki “Osteoartrit örneğini kur” düğmesini kullanın.' : v.error}</Note>}
      {!d && !v.error && <Note tone="info">Yükleniyor…</Note>}
      {d && {
        veriler: <Veriler d={d.data} />, karsilastirma: <Karsilastirma d={d.compare} />, uzman: <Uzman d={d.expert} />,
        kurul: <Kurul d={d.committee} />, tum: <Tum d={d.whole} />, etki: <Etki d={d.impact} />, fakulteler: <Fakulteler d={d.faculties} />,
      }[screen]}
    </Page>
  )
}

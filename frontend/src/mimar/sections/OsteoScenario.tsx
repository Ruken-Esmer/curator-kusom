import { ReactNode, useEffect, useState } from 'react'
import { useMimar } from '../state'
import { Note, Page, Panel, Pill } from '../ui'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

type Kind = 'real' | 'example'
const KIND: Record<Kind, { tone: 'ok' | 'warn'; text: string }> = {
  real: { tone: 'ok', text: 'gerçek veri' },
  example: { tone: 'warn', text: 'örnek · henüz yaşanmadı' },
}

const QUESTIONS: [string, string][] = [
  ['where', 'Nerede işleniyor?'],
  ['objectives', 'Yazılı hedefleri var mı?'],
  ['repetitions', 'Gereksiz tekrar var mı?'],
  ['ucep', 'UÇEP beklentisini karşılıyor mu?'],
]

function Block({ title, kind, children }: { title: string; kind?: Kind; children: ReactNode }) {
  return (
    <div className="border-t border-zinc-200 pt-3 mt-3 first:border-0 first:mt-0 first:pt-0">
      <div className="flex items-baseline justify-between gap-3 mb-1.5">
        <h3 className="text-[14px] font-semibold">{title}</h3>
        {kind && <Pill tone={KIND[kind].tone}>{KIND[kind].text}</Pill>}
      </div>
      <div className="text-[14px] leading-relaxed text-zinc-800 flex flex-col gap-2">{children}</div>
    </div>
  )
}

const Num = ({ v, label }: { v: ReactNode; label: string }) => (
  <div className="rounded border border-zinc-200 px-3 py-2 min-w-[120px]">
    <div className="text-[20px] font-semibold leading-tight">{v}</div>
    <div className="text-[12px] text-zinc-600 leading-snug">{label}</div>
  </div>
)

function Steps(d: any): { no: number; wp: string; name: string; does: string; body: ReactNode }[] {
  const { t0, wp1, wp4 } = d
  const p = t0.plain
  const related = t0.where.related?.length ?? 0
  const direct = t0.where.direct ?? []
  const [pa, pb] = wp1.expert_pair
  const top = wp1.oa_pairs[0]
  return [
    {
      no: 1, wp: 'wp1', name: 'Veri hazırlığı ve ilk analiz',
      does: 'Ders programları ve hedef belgeleri toplanır, kontrol edilir ve üç ayrı yöntemle karşılaştırılır.',
      body: <>
        <Block title="Osteoartrit hangi verilerde var?" kind="real">
          <p>Ders programlarında başlığında osteoartrit geçen {direct.length} oturum var:</p>
          <ul className="list-disc pl-5">
            {direct.map((s: any) => <li key={s.title + s.date}>{s.year}. sınıf · {s.block} · {s.title} ({s.kind})</li>)}
          </ul>
          <p>Bunlara ek olarak konuyla ilgili {related} oturum daha var (anatomi, histoloji, patoloji, radyoloji, ayırıcı tanı gibi).</p>
        </Block>
        <Block title="Eksik veri" kind="real">
          <p>MSKL 303 ve MSKL 503 bloklarının yazılı öğrenim hedefi belgeleri elimizde yok. Bu, Veri Hazırlık Raporu'na “eksik belge” olarak yazılır.
            Şimdilik yalnızca oturum başlıklarıyla çalışılabiliyor.</p>
          <p>Hastalığın adı UÇEP-2020 listesinde {t0.topic.no}. madde ({t0.topic.name}) ve İngilizce karşılığı ({t0.topic.name_en}) ile eşleştirildi.</p>
        </Block>
        <Block title="Üç yöntemle karşılaştırma" kind="real">
          <div className="flex flex-wrap gap-2">
            <Num v={wp1.titles} label={`oturum başlığı (${wp1.blocks.join(', ')})`} />
            <Num v={wp1.hybrid_pairs} label="karşılaştırılan başlık çifti" />
            <Num v={wp1.findings} label="bulgu" />
          </div>
          <p>
            Osteoartritle ilgili en üst sıradaki çift {top ? <>{top.rank}. sırada: <i>{top.a}</i> ↔ <i>{top.b}</i></> : 'bulunamadı'}.
            {' '}{wp1.oa_in_findings ? 'Osteoartrit bulgular arasında yer alıyor.' : 'Bulguların hiçbiri osteoartritle ilgili değil.'}
          </p>
          <p>
            Konu incelemesinde “bakılmalı” denen çift (<i>{pa}</i> ↔ <i>{pb}</i>)
            {wp1.expert_pair_rank ? ` ${wp1.expert_pair_rank}. sırada.` : ' otomatik yöntemlerin listesinde hiç yok.'}
            {' '}Başlıklar kısa olduğu ve az ortak kelime içerdiği için yöntemler bu çifti yakalayamıyor. Hedef belgeleri gelince
            karşılaştırma başlıklar yerine hedef cümleleri üzerinden yapılacak.
          </p>
        </Block>
      </>,
    },
    {
      no: 2, wp: 'wp2', name: 'Uzman doğrulaması',
      does: 'Bulunan olası tekrarlar, hangi yöntemin bulduğu gizlenerek uzmanlara gösterilir; uzman “gerçek tekrar mı?” sorusunu cevaplar.',
      body: <>
        <Block title="Hangi çift uzmana gider?" kind="real">
          <p>
            <i>{pa}</i> (3. sınıf, MSKL 303) ile <i>{pb}</i> (4. sınıf, IMED 410). Bu çifti otomatik yöntemler bulmadı; Konu incelemesi
            sayfasındaki elle hazırlanmış eşleştirmeden geliyor. Projede bu durum “yalnız uzman” grubu olarak kaydedilir: yöntemlerin
            kaçırdığı ama uzmanın önemli bulduğu ilişkiler.
          </p>
        </Block>
        <Block title="Uzmanın göreceği kart" kind="example">
          <div className="rounded border border-zinc-300 bg-zinc-50 p-3 text-[13px]">
            <p className="text-zinc-500 mb-1">Bu iki oturum aynı içeriği gereksiz yere tekrar ediyor mu?</p>
            <p>A · 3. sınıf · {pa}</p>
            <p>B · 4. sınıf · {pb}</p>
            <p className="mt-2 text-zinc-500">Evet, gereksiz tekrar · Hayır, bilerek ilerletilmiş · Karar veremiyorum</p>
          </div>
          <p>Kartta çifti hangi yöntemin bulduğu yazmaz. Uzman kararı burada örnektir; gerçek karar uzman panelinde verilecek.</p>
        </Block>
        <Block title="Eksik veri" kind="real">
          <p>İki dersin içeriği (slaytlar, KuLearn materyali) olmadan uzman yalnızca başlıklara bakabilir. İçerik gelince karşılaştırma içerik üzerinden yapılır.</p>
        </Block>
      </>,
    },
    {
      no: 3, wp: 'wp3', name: 'Kurul kararı',
      does: 'Doğrulanan bulgular odak gruplarında ve müfredat kurulunda görüşülür; kurul değişiklik kararı verir.',
      body: <>
        <Block title="Başlangıç durumu (T0)" kind="real">
          <table className="m-table">
            <thead><tr><th>Soru</th><th>Bugünkü cevap</th></tr></thead>
            <tbody>{QUESTIONS.map(([k, q]) => <tr key={k}><td className="whitespace-nowrap">{q}</td><td>{p[k].text}</td></tr>)}</tbody>
          </table>
        </Block>
        <Block title="Kurula gidebilecek öneriler" kind="example">
          <ol className="list-decimal pl-5 flex flex-col gap-1">
            <li>4. sınıftaki artritlerde ayırıcı tanı dersi, 3. sınıftakini tekrarlamak yerine vaka üzerinden ve daha ileri düzeyde işlensin.</li>
            <li>5. sınıf MSKL 503 stajına osteoartritli hastanın birinci basamakta uzun süreli izlemi için bir öğrenme hedefi eklensin.</li>
          </ol>
        </Block>
        <Block title="Kararlar uygulanırsa beklenen durum (T1)" kind="example">
          <table className="m-table">
            <thead><tr><th>Soru</th><th>Bugün</th><th>Sonra</th></tr></thead>
            <tbody>
              <tr><td>Gereksiz tekrar</td><td>{p.repetitions.flag || '—'}</td><td>yok; 4. sınıf dersi bir üst basamak</td></tr>
              <tr><td>UÇEP beklentisi</td><td>{p.ucep.flag || '—'}</td><td>izlem hedefi eklendi</td></tr>
              <tr><td>Yazılı hedef</td><td>{p.objectives.flag || '—'}</td><td>blok hedef belgeleri istendi</td></tr>
            </tbody>
          </table>
        </Block>
      </>,
    },
    {
      no: 4, wp: 'wp4', name: 'Tüm müfredata yayma',
      does: 'Osteoartrit için yapılan inceleme bütün bloklara ve bütün hastalıklara uygulanır; blok koordinatörleri sonuçları değerlendirir.',
      body: <>
        <Block title="Aynı tarama bütün müfredatta" kind="real">
          <div className="flex flex-wrap gap-2">
            <Num v={wp4.titles} label={`oturum başlığı (${wp4.years[0]}–${wp4.years[wp4.years.length - 1]}. sınıf)`} />
            <Num v={wp4.redundancy} label="olası gereksiz tekrar" />
            <Num v={wp4.integration} label="bütünleştirme fırsatı" />
            <Num v={wp4.high} label="öncelikli bulgu" />
          </div>
          <p>Tarama {wp4.seconds} saniye sürdü.</p>
          <p>UÇEP hastalıklarından {wp4.diseases_with_sessions} tanesi ders programlarında geçiyor. Bunlardan yalnızca {wp4.diseases_with_profile} tanesi
            (osteoartrit) için ayrıntılı inceleme hazır; diğerleri için tekrar ve UÇEP değerlendirmesi henüz yapılmadı.</p>
        </Block>
        <Block title="Koordinatörün göreceği soru" kind="example">
          <p>Osteoartrit örnekleme girerse MSKL koordinatörüne iki soru sorulur: bu bulgu anlamlı mı, ve önerilen değişiklik bloğunuzda uygulanabilir mi?</p>
        </Block>
      </>,
    },
    {
      no: 5, wp: 'wp5', name: 'Değişikliğin etkisi',
      does: 'Yapılan değişikliğin beklenen etkileri önceden yazılır; değişiklikten sonra gerçekleşip gerçekleşmediğine bakılır.',
      body: <>
        <Block title="Önceden kaydedilen beklentiler" kind="example">
          <ul className="list-disc pl-5">
            <li>Yeni izlem hedefi, 3. sınıftaki osteoartrit dersiyle ve 5. sınıftaki egzersiz dersiyle ilişkilendirilmeli.</li>
            <li>UÇEP osteoartrit maddesindeki “izlem” beklentisi artık bir hedefle karşılanmalı.</li>
          </ul>
        </Block>
        <Block title="Prototipin bugünkü davranışı" kind="real">
          <p>Örnek izlem hedefi (<i>Plan the long-term follow-up of a patient with osteoarthritis in primary care</i>) MSKL 503'e eklenip analiz
            çalıştırıldığında sistem bu hedef için hiçbir ilişki önermedi. İP5'in ölçtüğü şey tam olarak bu: değişiklik yapılınca sistem beklenen
            ilişkileri gösterebiliyor mu?</p>
        </Block>
      </>,
    },
    {
      no: 6, wp: 'wp6', name: 'Diğer fakültelere aktarım',
      does: 'Yöntem ve araç diğer tıp fakültelerine tanıtılır ve uygulanabilirliği denenir.',
      body: <>
        <Block title="Ziyaretlerde gösterilecek örnek" kind="example">
          <p>Osteoartrit incelemesi baştan sona (nerede işleniyor, hedefler, tekrarlar, UÇEP) diğer fakültelere örnek olarak gösterilir.</p>
        </Block>
        <Block title="Başka bir fakültenin hazırlaması gerekenler" kind="real">
          <ul className="list-disc pl-5">
            <li>Her oturum için başlık, sınıf, blok veya staj adı ve tarih</li>
            <li>Her blok için yazılı öğrenim hedefi belgesi</li>
            <li>Mümkünse ders içerikleri (slayt, ders notu)</li>
          </ul>
          <p>KUSOM'da bu üçünden yalnızca ilki tam; bu durum diğer fakülteler için de beklenen en sık eksik.</p>
        </Block>
      </>,
    },
  ]
}

export default function OsteoScenario() {
  const { go, step: i, setStep: setI } = useMimar()
  const [d, setD] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    fetch(`${BASE}/api/v1/audit/scenario/osteoartrit`)
      .then(async (r) => { if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? r.statusText); return r.json() })
      .then(setD).catch((e) => setErr(e.message))
  }, [])

  return (
    <Page title="Örnek: osteoartrit altı iş paketinde"
      lead="Bir hastalığın, projenin her aşamasında neyle karşılaştığını adım adım gösterir. Yeşil etiketli kısımlar KUSOM verisinden hesaplandı; sarı etiketli kısımlar henüz yaşanmamış adımların örneğidir.">
      {err && <Note tone="error">{err}</Note>}
      {!d && !err && <Note tone="info">Veriler hazırlanıyor. İlk açılışta yaklaşık 15 saniye sürer.</Note>}
      {d && (() => {
        const steps = Steps(d)
        const s = steps[i]
        return <>
          <div className="flex flex-wrap gap-1.5 mb-4" role="tablist">
            {steps.map((x, k) => (
              <button key={x.no} role="tab" aria-selected={k === i} onClick={() => setI(k)}
                className={`px-3 py-2 rounded border text-[13px] text-left ${k === i ? 'border-[var(--brand)] bg-[var(--brand)] text-white' : 'border-zinc-300 bg-white hover:border-[var(--brand)]'}`}>
                <span className="font-semibold">İP{x.no}</span> <span className={k === i ? '' : 'text-zinc-600'}>{x.name}</span>
              </button>
            ))}
          </div>
          <Panel title={`İP${s.no} · ${s.name}`}>
            <p className="text-[14px] text-zinc-600 mb-4">{s.does}</p>
            {s.body}
          </Panel>
          <div className="flex justify-between mt-4 text-[14px]">
            <button disabled={i === 0} onClick={() => setI(i - 1)} className="text-[var(--brand)] disabled:text-zinc-300">← Önceki</button>
            <button onClick={() => go(s.wp as any)} className="text-zinc-600 underline underline-offset-2">İP{s.no} görevlerine git</button>
            <button disabled={i === steps.length - 1} onClick={() => setI(i + 1)} className="text-[var(--brand)] disabled:text-zinc-300">Sonraki →</button>
          </div>
        </>
      })()}
    </Page>
  )
}

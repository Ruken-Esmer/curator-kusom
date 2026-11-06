// Work packages of the MİMAR TÜBİTAK 1001 application (form of 13.09.2026, section 3.1).
// Months are relative project months (1–36). Texts are plain-language summaries of the form; the
// full wording stays in the application.
import type { Section } from './state'

export type Task = {
  no: string
  months: [number, number]
  title: string
  who: string
  screen?: Section          // where the task is done in the system
  outside?: string          // task done outside the system, and how it is recorded
  note?: string             // current state worth knowing
  status?: (o: any) => boolean | null   // true = there is a record in the system
}

export type WorkPackage = {
  id: 'wp1' | 'wp2' | 'wp3' | 'wp4' | 'wp5' | 'wp6'
  no: number
  short: string
  name: string
  rq: string
  months: [number, number]
  weight: number
  goal: string
  tasks: Task[]
  success: string[]
  outputs: string[]
}

export const WORK_PACKAGES: WorkPackage[] = [
  {
    id: 'wp1', no: 1, short: 'Veri hazırlığı ve teknik doğrulama', rq: 'AS1 / H1', months: [1, 12], weight: 24,
    name: 'MSKL veri hazırlığı ve hibrit sistemin teknik doğrulanması',
    goal: 'Kas-iskelet sistemi (MSKL) verisini izlenebilir biçimde hazırlamak; üç arama yöntemini (BM25, FAISS, Neo4j) geliştirip RRF ile birleştirmek ve birleşik sistemi kilitli bir testte en iyi tekil yöntemle karşılaştırmak.',
    tasks: [
      { no: '1.1', months: [1, 3], title: 'T0 MSKL çekirdek veri seti ve Veri Hazırlık Raporu', who: 'Gören, bursiyer; eğitsel kontrol: Mutlu, Gürsoy, Gönenli', screen: 'data', status: (o) => o?.frozen_datasets > 0 },
      { no: '1.2', months: [1, 3], title: 'UÇEP maddelerinin İngilizce karşılıklarının uzman kontrolü', who: 'Mutlu, Gürsoy, Gönenli', screen: 'data' },
      { no: '1.3', months: [2, 5], title: 'MeSH terimlerinin doğrulanması', who: 'Mutlu, Gürsoy, Gönenli; etkinlik sorumluları', outside: 'Veri modelinde etkinlik başına MeSH alanı var; doğrulama için ayrı bir ekran henüz yok.' },
      { no: '1.4', months: [2, 8], title: 'BM25, FAISS, Neo4j ve RRF bileşenlerinin geliştirilmesi ve kararlılık sınaması', who: 'Gören, bursiyer', screen: 'analysis', status: (o) => o?.analyses > 0 },
      { no: '1.5', months: [9, 11], title: 'AS1 örnekleminin çekilmesi ve kör bağımsız değerlendirme', who: 'Bağımsız teknik değerlendiriciler; örnekleme: Gören, bursiyer', screen: 'plan', status: (o) => o?.plans_locked > 0 },
      { no: '1.6', months: [11, 12], title: 'Duyarlılık, pozitif kestirim değeri ve ikincil analizler', who: 'Gören, bursiyer; eğitsel yorum: Mutlu, Gürsoy, Gönenli', screen: 'plan', status: (o) => o?.as1_samples?.evaluated > 0 },
    ],
    success: [
      'Veri hazırlığı, bağımsız referans ve kilitli test karşılaştırması tamamlanır.',
      'En iyi tekil yöntem geliştirme verisinde seçilip kilitlenir.',
      'Birleşik sistem üstün çıkmasa da planlanan karşılaştırmanın tamamlanması paketin yürütüldüğünü gösterir.',
    ],
    outputs: ['Çekirdek veri seti, veri sözlüğü ve Veri Hazırlık Raporu', 'Doğrulanmış UÇEP İngilizce ve MeSH kayıtları',
      'Sürümlenmiş BM25, FAISS, Neo4j ve RRF bileşenleri', 'Kilitli test, bağımsız referans ve AS1 raporu'],
  },
  {
    id: 'wp2', no: 2, short: 'Eğitsel doğrulama ve KuLearn katkısı', rq: 'AS2a / H2a, AS2b / H2b', months: [9, 18], weight: 23,
    name: 'Aynı çekirdek veride eğitsel doğrulama ve KuLearn ek katkısı',
    goal: 'MİMAR’ın bulduklarını aynı veriyle çalışan uzmanların bulduklarıyla karşılaştırmak ve sisteme yalnızca KuLearn ders içeriği eklendiğinde ne kadar yeni bulgu geldiğini ölçmek.',
    tasks: [
      { no: '2.1', months: [9, 13], title: 'MİMAR–Çekirdek ve Uzman–Çekirdek raporlarının hazırlanması', who: 'Gören, bursiyer; bağımsız MSKL ve tıp eğitimi uzmanları', screen: 'findings', status: (o) => o?.reports > 0 },
      { no: '2.2', months: [13, 15], title: 'İç pilotla başlayan kör doğrulama (her yaklaşımdan yaklaşık 60 aday)', who: 'Bulgu standardizasyon ekibi, bağımsız değerlendirme kurulu', screen: 'validation', status: (o) => o?.pools > 0 },
      { no: '2.3', months: [13, 16], title: 'Yalnız KuLearn içeriği eklenerek genişletilmiş rapor', who: 'Gören, bursiyer; eğitsel kontrol: Mutlu, Gürsoy, Gönenli', screen: 'findings' },
      { no: '2.4', months: [16, 18], title: 'H2a, H2b, yeni bulgular ve uzman emeği (kişi-saat) analizleri', who: 'Bağımsız kurul; analiz: Gören, bursiyer', screen: 'validation', status: (o) => o?.effort?.entries > 0 },
    ],
    success: [
      'Üç rapor ve bağımsız karar kayıtları tamamlanır.',
      'H2a: MİMAR’ın doğrulanmış bulgu oranı uzmanlarınkinden en fazla 10 puan düşüktür (güven aralığının alt sınırı −10 puanın üzerinde).',
      'H2b: KuLearn ile gelen yeni doğrulanmış bulguların payı en az %10’dur.',
      'Kurul üyeleri arasındaki ilk karar uyumu Gwet AC1 ≥ 0,60 olarak izlenir.',
    ],
    outputs: ['Kilitli raporlar ve veri sürümleri', 'İç pilot ve nihai örnekleme kayıtları', 'Benzetim kodu, varsayımları ve çıktıları',
      'Uzman bulgu ortaklığı ve kurul uyum raporu', 'H2a, H2b ve uzman emeği raporları'],
  },
  {
    id: 'wp3', no: 3, short: 'MSKL düzenlemesi ve etkisi', rq: 'AS3 / H3, AS4', months: [13, 29], weight: 21,
    name: 'MSKL müfredatının yeniden düzenlenmesi ve düzenleme etkisinin değerlendirilmesi',
    goal: 'Doğrulanmış MSKL bulgularını Müfredat Geliştirme ve Koordinasyon Kurulu (CDCC) kararıyla müfredata uygulamak; düzenleme öncesi (T0) ve sonrasını (T1) karşılaştırmak, öğrenci ve öğretim üyelerinin deneyimini almak.',
    tasks: [
      { no: '3.1', months: [13, 15], title: 'T0 öğrenci ve öğretim üyesi odak grupları', who: 'KOLT araştırma ekibi', outside: 'Odak grupları kurum içinde yürütülür; kayıtlar KOLT’ta tutulur.' },
      { no: '3.2', months: [18, 20], title: 'Düzenleme önerileri ve CDCC kararları', who: 'Mutlu, Gürsoy, Gönenli; MSKL koordinatörleri; CDCC', outside: 'Kurul kararı sistem dışındadır; onaylanan değişiklikler “Veri” ekranında yeni sürüm olarak işlenir.' },
      { no: '3.3', months: [20, 24], title: 'Onaylanan değişikliklerin uygulanması ve izlenmesi', who: 'MSKL koordinatörleri ve öğretim üyeleri; CDCC', screen: 'data', status: (o) => o?.datasets > 1 },
      { no: '3.4', months: [24, 27], title: 'T0–T1 MİMAR analizi ve bağımsız sonuç değerlendirmesi', who: 'Gören, bursiyer; bağımsız sonuç değerlendiricileri', screen: 'analysis' },
      { no: '3.5', months: [26, 28], title: 'T1 odak grupları', who: 'KOLT araştırma ekibi', outside: 'Öğrenciler düzenlenmiş eğitimi tamamladıktan sonra yapılır.' },
      { no: '3.6', months: [28, 29], title: 'Nicel ve nitel bulguların bütünleştirilmesi', who: 'Mutlu, Gürsoy, Gönenli', outside: 'Bütünleşik yorum tablosu rapor olarak hazırlanır.' },
    ],
    success: [
      'CDCC kararları ve uygulama kanıtları kaydedilir.',
      'Tam uygulanan değişikliklerin sorunu giderip gidermediği ana değerlendirmeye, kısmen uygulananlar ayrı rapora alınır.',
      'Sekiz başlangıç odak grubu yapılır; gerekirse en fazla dört ek grup (toplam en çok 12).',
      'H3 tanımlayıcı olarak değerlendirilir; AS4’te hipotez sınanmaz.',
    ],
    outputs: ['T0 ve T1 odak grup verileri ve raporları', 'CDCC karar ve değişiklik kayıtları', 'Sürümlenmiş T0 ve T1 veri setleri',
      'Bağımsız AS3 ve bütünleşik AS4 raporları'],
  },
  {
    id: 'wp4', no: 4, short: 'Tüm KUSOM müfredatı', rq: 'AS5 / H5', months: [18, 31], weight: 13,
    name: 'MİMAR’ın tüm KUSOM müfredatına uygulanması ve bulguların eğitsel değerlendirilmesi',
    goal: 'MİMAR’ı tüm KUSOM müfredatına uygulamak ve çıkan aday bulguların eğitim açısından anlamlı ve uygulanabilir olup olmadığını blok ve yıl koordinatörlerine değerlendirtmek.',
    tasks: [
      { no: '4.1', months: [18, 26], title: 'Tüm müfredat verisinin aktarımı ve kalite kontrolü', who: 'Gören, bursiyer; eğitsel kontrol: Mutlu, Gürsoy, Gönenli', screen: 'scan',
        note: '2.–5. sınıf ders programları sisteme alındı. 1. ve 6. sınıf programları ile çoğu bloğun hedef belgeleri henüz yok.' },
      { no: '4.2', months: [25, 29], title: 'Sabitlenmiş tüm veride nihai tarama ve aday raporu', who: 'Gören, bursiyer; eğitsel değerlendirme: Mutlu, Gürsoy, Gönenli', screen: 'scan' },
      { no: '4.3', months: [28, 31], title: 'En fazla 300 adaylık H5 örnekleminin koordinatör değerlendirmesi ve uygun bulguların CDCC’ye sunulması', who: 'Blok ve yıl koordinatörleri, alan uzmanları; analiz: Gören, bursiyer; CDCC', screen: 'as5' },
    ],
    success: [
      'Sabitlenmiş veri ve nihai tarama tamamlanır; en fazla 300 adaylık örneklemin seçim ve tamamlanma kayıtları tutulur.',
      'H5: En az 20 farklı koordinatörün değerlendirmesinde bulguların %70’inden fazlası anlamlı ve uygulanabilir bulunur.',
      'Tamamlanmayan incelemeler olumsuz sayılmaz; katılım düşükse tüm havuz için H5 kararı verilmez.',
    ],
    outputs: ['Tüm müfredatın sabitlenmiş veri sürümü', 'Nihai aday raporu', 'H5 örneklem, değerlendirme ve analiz kayıtları', 'CDCC’ye sunulan bulgular'],
  },
  {
    id: 'wp5', no: 5, short: 'Değişiklik etkisinin izlenmesi', rq: 'AS6 / H6', months: [29, 34], weight: 13,
    name: 'Onaylanan müfredat değişikliklerinin dinamik etkisinin izlenmesi',
    goal: 'Onaylanan bir müfredat değişikliğinin başka ders ve hedeflerle bağlantılarını nasıl etkilediğini sistemin doğru uyarıp uyarmadığını değerlendirmek.',
    tasks: [
      { no: '5.1', months: [29, 32], title: 'Onaylanan ve uygulanan değişikliklerin sürümlü kaydı', who: 'Mutlu, Gürsoy, Gönenli; koordinatörler; Gören, bursiyer', screen: 'impact', status: (o) => o?.changesets > 0 },
      { no: '5.2', months: [30, 34], title: 'Beklenen etkilerin önceden kaydı, MİMAR analizi ve bağımsız karşılaştırma; gerekirse en az 24 kontrollü senaryo', who: 'Gören, bursiyer; koordinatörler ve bağımsız müfredat uzmanları', screen: 'impact' },
    ],
    success: [
      'Gerçek değişiklikler için önceden kaydedilmiş beklenti, sistem raporu ve bağımsız karar tamamlanır.',
      'Kontrollü test gerekirse: en az 24 senaryoda doğrulanmış uyarı oranı %70’in üzerinde, kaçırma oranı %20’nin altında olur.',
    ],
    outputs: ['Sürümlenmiş değişiklik ve izleme veri seti', 'Etki ve bağımsız değerlendirme raporu', 'Gerekirse kontrollü test raporu'],
  },
  {
    id: 'wp6', no: 6, short: 'Dış uygulanabilirlik', rq: '—', months: [33, 36], weight: 6,
    name: 'Yapılandırılmış dış uygulanabilirlik ve kurumsal uyarlanabilirlik değerlendirmesi',
    goal: 'Dört tıp fakültesi ziyareti ve 20 kişilik bir çalıştayla MİMAR’ın başka kurumlarda hangi koşullarda kullanılabileceğini belirlemek; yol haritası ve ileride yapılacak çok merkezli doğrulama için protokol taslağı hazırlamak.',
    tasks: [
      { no: '6.1', months: [33, 34], title: 'İstanbul’da dört tıp fakültesine ziyaret ve aynı formla değerlendirme', who: 'Mutlu, Gürsoy, Gönenli', outside: 'Ziyaretler sistem dışında yürütülür; form ve özetler proje arşivinde tutulur.' },
      { no: '6.2', months: [34, 35], title: 'Bulguların karar matrisiyle ürün revizyonu, uyarlama kriterleri ve yol haritasına bağlanması', who: 'Mutlu, Gürsoy, Gönenli; Gören, bursiyer', outside: 'Karar matrisi ve yol haritası belge olarak hazırlanır.' },
      { no: '6.3', months: [35, 36], title: '20 kişilik çalıştayda revize ürünlerin değerlendirilmesi ve sonuçların paylaşılması', who: 'Mutlu, Gürsoy, Gönenli; Gören, bursiyer', outside: 'Çalıştay sistem dışında yapılır.' },
    ],
    success: [
      'Dört ziyaret aynı formla tamamlanıp karar tablosuna aktarılır.',
      'Çalıştayda KUSOM dahil farklı fakültelerden 20 katılımcı hedeflenir.',
      'Katılımcıların en az %60’ından doldurulmuş geri bildirim formu alınır.',
    ],
    outputs: ['Ziyaret veri ve analiz özeti', 'Uyarlama kriterleri ve yol haritası', 'Dış uygulanabilirlik raporu', 'Çalıştay materyalleri',
      'Çok merkezli teknik doğrulama protokol taslağı'],
  },
]

export const SCREEN_LABEL: Partial<Record<Section, string>> = {
  data: 'Veri ve kalite kontrolü', analysis: 'Örtüşme analizi', plan: 'Ön kayıt ve kilitli örneklem', review: 'Kör değerlendirme',
  findings: 'Raporlar', validation: 'Kör doğrulama', scan: 'Müfredat taraması', as5: 'Koordinatör değerlendirmesi', impact: 'Değişiklik etkisi',
}

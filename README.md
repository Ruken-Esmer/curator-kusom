# CURATOR

Koç Üniversitesi Tıp Fakültesi (KUSOM) müfredatı için sorgu ve analiz aracı. KU-PSRF 2025 projesi kapsamında geliştiriliyor; MİMAR (TÜBİTAK 1001 başvurusu) çalışmasının yazılım tarafı da bu depoda.

Ekip: Dr. Gökhan Gönenli, Prof. Dr. Ümit Dilber Mutlu, Prof. Dr. Tuğba Gürsoy, Prof. Dr. Demir, Ruken Esmer

## Ne yapıyor

Uygulamanın üç bölümü var:

- **Sorgu.** Bir konunun hangi sınıf ve bloklarda işlendiği, öğrenim hedefleri, tekrarları ve UÇEP-2020 ile uyumu sorulabiliyor. Öğrenciler için bir blok, staj ya da sınav öncesinde ne çalışılacağını gösteren öğrenme yolu da buradan çıkıyor.
- **Uzman incelemesi.** Öğrenme yolunun dayandığı konu bağlantılarını öğretim üyeleri tek tek değerlendiriyor. Tekrar bağlantılarının hepsi, diğer türlerden 30'ar rastgele bağlantı ve örnek yollardaki bağlantılar inceleniyor. Bir bağlantının değişmesi için iki uzmanın aynı kararı vermesi gerekiyor.
- **Müfredat analizi.** Seçilen blokların öğrenim hedeflerini birbiriyle ve UÇEP-2020 çekirdek hastalık listesiyle karşılaştırıp olası gereksiz tekrarları ve eksikleri listeliyor. Karar müfredat komitesinde.

## Veri

Varsayılan kaynak KUSOM 2025–2026 ders programları (2.–5. sınıf). Ham dosyalar depoya konmuyor; `backend/data/kusom_raw/` altına kopyalanıp şu komutla işleniyor:

```bash
cd backend
python -m app.data.kusom.parse_timetables data/kusom_raw
```

Çıktı `app/data/kusom/kusom_2025_2026.json` dosyasına yazılıyor. Öğrenci listesi içeren sayfalar okunmuyor.

Bilinen eksikler:

- 1. ve 6. sınıf programları henüz yok.
- Yazılı öğrenim hedefi belgesi yalnızca CIRC 204, ERUS 206 ve NUTI 205 için var. Diğer bloklarda oturum başlıkları kullanılıyor.
- Blok adları veride yalnızca kod olarak geçiyor. `app/data/kusom/curriculum.py` içindeki adlar açıklama amaçlı; resmi adlarla değiştirilmeli.
- UÇEP'ten yalnızca çekirdek hastalıklar listesi (342 madde) var. Semptomlar ve temel hekimlik uygulamaları eklenmedi.

Gösterim için eski örnek müfredata `CURRICULUM_SOURCE=placeholder` ile geçilebilir.

## Kurulum

Python 3.11 ve Node 18 gerekiyor.

```bash
cp .env.example .env

cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev          # http://localhost:5173
```

Dil modeli anahtarı yoksa `ACTIVE_LLM=offline` ile çalışıyor. Sorgu cevapları da bu durumda doğrudan veriden üretiliyor.

Uzman hesabı açmak için geliştirme ortamındaki yönetici anahtarı `dev-admin-token`:

```bash
curl -X POST localhost:8000/api/v1/mimar/users -H "Authorization: Bearer dev-admin-token" \
     -H "Content-Type: application/json" -d '{"username":"uzman1","roles":["expert"]}'
curl -X POST localhost:8000/api/v1/mimar/users/uzman1/token -H "Authorization: Bearer dev-admin-token"
```

## Testler

```bash
cd backend
python -m pytest -q
```

## Klasörler

- `backend/app/audit/`: akreditasyon soruları (konu nerede, hedefler, tekrarlar, UÇEP uyumu)
- `backend/app/pathway/`: öğrenme yolu ve uzman incelemesi
- `backend/app/mimar/`: müfredat analizi ve MİMAR çalışma akışı (AS1–AS6)
- `backend/app/data/`: KUSOM ve UÇEP verileri, içe aktarma betikleri
- `frontend/src/`: arayüz

MİMAR'ın ayrıntıları `docs/mimar-notes.md` dosyasında.

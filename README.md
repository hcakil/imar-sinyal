# İmarSinyal Ankara

ABB meclis kararlarını ve imar askılarını otomatik izleyen; kaynak belgeli,
filtrelenebilir planlama değişikliği akışı.

Bu repository üç parçadan oluşur:

- `apps/web`: Next.js 15.5.21, TypeScript, SSR web ürünü ve HTTP API'leri
- `services/pipeline`: Python scraper, belge analizi, ilişkilendirme ve bülten
- `infra`: Firebase, Firestore, Cloud Run, Scheduler ve izleme yapılandırması

İlk sürümde hesap, ödeme, kişisel takip listesi ve harita yoktur. Yerelde
korunan 11 doğrulanmış fixture ile ürün hemen açılır; bulutta veri Firestore'dan
okunur.

## Çalışan ürün

Sayfalar:

- `/`: ürün anlatımı, öne çıkan olaylar ve bülten formu
- `/degisiklikler`: ilçe, aşama, kategori, metin ve etki filtresi
- `/degisiklik/[slug]`: eski/yeni alanlar, süreç, kanıt ve resmî belgeler
- `/bulten`: açık rıza ve en fazla üç ilçe tercihi
- `/gizlilik`, `/kullanim-kosullari`

API:

- `GET /api/events`
- `GET /api/events/{slug}`
- `POST /api/subscribers`
- `GET|POST /api/unsubscribe`
- `GET /api/healthz` (canlı Cloud Run/Firebase sağlık kontrolü)
- `GET /healthz` (yerel uygulama rotası; Google Frontend bu yolu rezerve eder)
- `GET /healthz.json` (Firebase edge sağlık kontrolü)

Tarayıcı Firestore'a doğrudan erişmez. Okuma ve yazma Next.js sunucusu
üzerindendir; Firestore güvenlik kuralları istemci erişimini kapatır.

## Veri hattı

```text
ABB ArcGIS askı katmanları ─┐
                            ├─ snapshot/hash ─ normalize ─ planning_events
ABB meclis kararları/DOCX ──┘                       │
                                                   ├─ kanıt
Gemini belge analizi ───────────────────────────────┤
                                                   └─ ilişkilendirme
```

- UIP, NIP, NIP25 ve CDP bağımsız çekilir; bir kaynağın hatası diğerlerini
  durdurmaz.
- Geometri WGS84 olarak alınır; bbox ve centroid saklanır.
- Yeni, değişmiş, aynı kalan ve kaynaktan düşen snapshot'lar ayrılır.
- Meclis kararları 1 Ocak 2026'ya kadar geriye doldurulabilir.
- DOCX metni, tabloları ve üstü çizili run'ları deterministik okunur.
- PDF'nin tüm sayfaları ucuz metin/çizim taramasından geçer; en ilgili en fazla
  12 sayfa Vision'a gider.
- Varsayılan model `gemini-3.5-flash-lite`, belirsizlik/hata durumunda
  `gemini-3.6-flash` kullanılır. `temperature` gönderilmez.
- Emsal, TAKS, Yençok ve kişi/ha yoğunluğu ayrı alanlardır.
- Kaynaktaki kanıta bağlanamayan eski/yeni değer temizlenir ve yayımlanmaz.
- Meclis ve askı olayları ilçe, parsel, ölçek ve tarih yakınlığıyla bağlanır.
  Düşük güvenli adaylar birleştirilmez.
- Kaynak PDF'lerin tamamı Storage'a kopyalanmaz; URL, hash ve küçük WebP kanıt
  önizlemeleri saklanır.

## Yerel kurulum

Gereksinimler: Node.js 22+, pnpm ve Python 3.11+.

```bash
pnpm install
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/pipeline/requirements.txt
```

Web:

```bash
pnpm dev
```

`http://localhost:3000` adresi Firestore değişkeni yokken 11 fixture olayıyla
açılır.

Pipeline:

```bash
cp services/pipeline/.env.example services/pipeline/.env
PYTHONPATH=services/pipeline python -m imarsinyal.cli nightly
```

Yerel varsayılan veri deposu `data/imarsinyal-local.db` SQLite dosyasıdır.
Gemini anahtarı boşsa kaynak kayıtları yine işlenir fakat eski/yeni alanları
`source_only` olarak boş bırakılır.

Testler:

```bash
pnpm test
pnpm lint
pnpm build
PYTHONPATH=services/pipeline python -m unittest discover -s services/pipeline/tests -v
bash -n infra/bootstrap-cloud.sh infra/configure-schedulers.sh infra/configure-alerts.sh
```

Regresyon paketi özellikle şunları kilitler:

- Yuva `121–250 kişi/ha` emsal değildir.
- Korkutreis `TAKS 0.60` emsal değildir.
- Beytepe UIP/NIP ayrı kayıt kalır ve ilişkilenir.
- Tek ArcGIS katman hatası diğer katmanları durdurmaz.
- Aynı snapshot ikinci çalışmada yeni yazım üretmez.

25 Temmuz 2026 canlı salt-okunur doğrulamasında UIP 1, NIP 5, NIP25 0 aktif
kayıt döndürdü; CDP servis hatası izole edildi. Aynı snapshot'ın ikinci
çalışmasında `changed_snapshots=0`, `unchanged_snapshots=6` elde edildi.
2026 meclis backfill parser'ı 232 benzersiz aday karar buldu.

## Firebase ve Google Cloud kurulumu

Bu adımlar proje sahibi tarafından bir kez yapılır.

1. Yeni ve boş bir Firebase projesi oluşturun.
2. Blaze planını ve faturalandırma hesabını bağlayın.
3. Firestore'u geri değiştirilemeyen bölge olarak `europe-west1` seçerek
   oluşturun.
4. Cloud Billing'de 100 TL, 250 TL ve 500 TL bütçe uyarıları kurun. Uyarılar
   harcamayı otomatik durdurmaz.
5. Yerelde oturum açın:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project FIREBASE_PROJECT_ID
```

6. Repository'deki `.firebaserc` dosyası `imar-sinyal` projesine bağlıdır.
7. API, Artifact Registry, bucket, service account ve Secret Manager
   kaynaklarını hazırlayın:

```bash
./infra/bootstrap-cloud.sh FIREBASE_PROJECT_ID
```

8. Secret değerlerini terminal geçmişine yazmadan ekleyin. Her komut girdiyi
   bekler; değeri yapıştırıp `Ctrl-D` ile tamamlayın:

```bash
gcloud secrets versions add gemini-api-key --data-file=-
gcloud secrets versions add resend-api-key --data-file=-
gcloud secrets versions add unsubscribe-secret --data-file=-
```

`unsubscribe-secret` için en az 32 rastgele byte kullanın. Anahtarları Git'e,
issue'ya veya mesaja koymayın.

Resend'de `İmarSinyal Bülteni` adlı bir Audience oluşturup kimliğini not edin.
Bu kimlik gizli anahtar değildir; web build'indeki `_RESEND_AUDIENCE_ID`
değeridir.

9. Web image'ını oluşturup Cloud Run'a dağıtın. Resend API anahtarı henüz
   eklenmemişse site ve abonelik kaydı yine çalışır; Resend kişi eşitlemesi
   anahtar etkinleştirildikten sonra başlar:

```bash
gcloud builds submit \
  --config cloudbuild.web.yaml \
  --substitutions=_CONTACT_EMAIL=GERCEK_ILETISIM_EPOSTASI,_DATA_CONTROLLER_NAME=VERI_SORUMLUSU_ADI,_TEST_RECIPIENT=RESEND_HESAP_EPOSTASI,_RESEND_AUDIENCE_ID=RESEND_AUDIENCE_ID
```

10. Gece pipeline job'ını dağıtın:

```bash
gcloud builds submit --config cloudbuild.pipeline.yaml
```

11. Gece zamanlayıcısını kurun:

```bash
./infra/configure-schedulers.sh FIREBASE_PROJECT_ID
```

- Gece taraması: her gün `03:15 Europe/Istanbul`

12. Firestore kuralları, indexler ve Hosting yönlendirmesini dağıtın:

```bash
pnpm dlx firebase-tools deploy --only firestore,hosting
```

13. İlk backfill'i bir kez çalıştırın:

```bash
gcloud run jobs execute imarsinyal-nightly \
  --region=europe-west1 \
  --args=backfill,--from-date,2026-01-01 \
  --wait
```

Cloud Run web servisi `min-instances=0`, `max-instances=2` olarak; gece job'ı
tek task, 2 vCPU, 2 GiB, 60 dakika ve bir retry ile yapılandırılmıştır.

## Bülten güvenlik anahtarı

Resend API anahtarı Secret Manager'a eklendikten sonra web servisinde kişi
eşitlemesini açın:

```bash
gcloud run services update imarsinyal-web \
  --region=europe-west1 \
  --update-secrets=RESEND_API_KEY=resend-api-key:latest
```

Ardından test bülteni job'ını ve haftalık scheduler'ı dağıtın:

```bash
gcloud builds submit \
  --config cloudbuild.newsletter.yaml \
  --substitutions=_SITE_URL=https://FIREBASE_PROJECT_ID.web.app,_TEST_RECIPIENT=RESEND_HESAP_EPOSTASI

./infra/configure-schedulers.sh FIREBASE_PROJECT_ID true
```

Varsayılan dağıtımda `NEWSLETTER_PUBLIC_SENDS=false` kalır. Kayıt olan gerçek
kişiye e-posta gönderilmez; yalnızca `_TEST_RECIPIENT` olarak verilen Resend
hesap e-postasına test gönderilir.

Alan adı Resend'de doğrulandıktan ve gizlilik/iletişim bilgileri
tamamlandıktan sonra iki Cloud Run ortamında:

```text
NEWSLETTER_PUBLIC_SENDS=true
NEWSLETTER_FROM=İmarSinyal Ankara <bulten@alanadiniz.com>
```

değerleri açılır.

## İzleme

Pipeline üç ardışık boş askı sonucu gördüğünde
`THREE_CONSECUTIVE_EMPTY_SCRAPES` logunu üretir. Bootstrap script'i bunun için
`imarsinyal_empty_scrape_streak` log metriğini oluşturur.

Google Cloud Console'da Monitoring → Alerting altında iki e-posta politikası
oluşturun veya e-posta notification channel kimliğini kopyalayıp çalıştırın:

```bash
./infra/configure-alerts.sh FIREBASE_PROJECT_ID NOTIFICATION_CHANNEL_ID
```

Oluşturulan iki politika:

1. Cloud Run Job `imarsinyal-nightly` execution failure sayısı `> 0`
2. `logging.googleapis.com/user/imarsinyal_empty_scrape_streak` metriği `> 0`

Bildirim e-postası repository'ye yazılmaz; proje sahibinin Monitoring
notification channel'ı olarak eklenir.

## Henüz yapılmayacaklar

- Alan adı ve reklam satın alma
- Kullanıcı hesabı, ödeme ve Pro paket
- Harita ve kişisel alarm
- WhatsApp/SMS
- Tüm Türkiye'ye açılma

Önce en az 20 gerçek olay sayfası, ilk bülten ve davranış sinyalleri
tamamlanmalıdır.

## Veri ve sorumluluk

Veri ABB'nin kamuya açık sistemlerinden gelir. İmarSinyal bağımsız bir veri
ürünüdür; belediye hizmeti, resmî imar belgesi veya yatırım tavsiyesi değildir.

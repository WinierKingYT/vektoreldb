# 5. Embedding sağlayıcı sözleşmesi

## Amaç

Uygulama, local model ile OpenAI gibi harici bir servisi değiştirebilmeli; ingest ve search katmanları sağlayıcı ayrıntılarını bilmemelidir.

Local provider varsayılandır. `openai` adapter'ı artık opt-in runtime yoludur; yalnızca `VDB_EMBEDDING_PROVIDER=openai` ve `OPENAI_API_KEY` birlikte sağlandığında oluşturulur. Varsayılan local akış harici ağ çağrısı yapmaz.

```text
EmbeddingProvider
├── manifest
├── embed_documents(texts)
└── embed_query(text)
```

## Sağlayıcı çıktısı

Provider'ın `manifest` alanı şu bilgileri taşır:

- sağlayıcı adı
- model adı ve sürümü
- embedding boyutu
- sorgu/doküman encoding yöntemi
- normalizasyon durumu
- mesafe metriği
- external provider için runtime batch boyutu (embedding manifest'inin semantik
  vector contract'ına dahil değildir)
- oluşturulma zamanı
- hata ve retry bilgisi runtime telemetrisiyle ayrıca raporlanır; manifest'in
  değişmez vector contract'ına yazılmaz.

Embedding üretimi başarısız olan kayıt index'e yüklenmez; hata kuyruğuna alınır.

## Local embedding

Local seçenek, hassas verinin dışarı çıkmasını engeller ve tekrar eden işler için maliyeti azaltabilir; karşılığında disk, RAM/GPU ve model indirme/versiyon yönetimi gerekir. Türkçe ve asimetrik retrieval performansı gerçek sorgu setiyle ölçülmelidir.

`VDB_EMBEDDING_OFFLINE=true` local provider'ı cache-only moda alır; eksik pinned
modelde ağ indirmesi beklemek yerine hızlı ve açık hata verir. Varsayılan `false`
olduğu için ilk kurulumda model indirme davranışı korunur.
Offline parametresi yalnızca bu mod açıkken model loader'a geçirilir; mevcut
provider/test-double sözleşmesi varsayılan akışta değişmez.

## Harici embedding

`VDB_EMBEDDING_PROVIDER=openai` seçildiğinde başarılı provider oluşturma sırasında
privacy-safe `external_embedding_provider_selected` audit olayı üretilir. Olay
yalnızca provider türü, model, endpoint scheme/host ve dimension metadata'sını
taşır; API key, endpoint path, sorgu/belge metni ve embedding yazılmaz. Provider
oluşturulamazsa başarılı seçim olayı üretilmez ve hata fail-closed kalır.

Harici OpenAI-compatible endpoint gerekiyorsa `VDB_EMBEDDING_BASE_URL`,
`VDB_EMBEDDING_TIMEOUT_SECONDS`, `VDB_EMBEDDING_MAX_RETRIES` ve
`VDB_EMBEDDING_BATCH_SIZE` ve `VDB_EMBEDDING_CACHE_SIZE` ayarlanabilir. Batch
boyutu 1–256, in-memory cache kapasitesi 0–4096 ile sınırlıdır; varsayılanlar
sırasıyla 32 ve 256'dır ve bu ayarlar yalnızca harici provider'da uygulanır.
Retry sayısı 0–5 ile sınırlıdır; local provider bu ayarlara bakmaz. API anahtarı
yalnızca `OPENAI_API_KEY` ortam değişkeninden alınır ve loglanmaz.
Boyut, retry, batch ve cache ayarları kesin tam sayı olmalı (boolean/kesirli
değerler kabul edilmez); timeout sonlu ve pozitif, backoff sonlu ve negatif
olmayan sayısal değer olmalıdır. Yanıt
vektörlerinin koordinatları sonlu olmasının yanında toplam normu da pozitif ve
sonlu olmalıdır; aşırı büyüklükte koordinatların norm taşması manifest uyumsuzluğu
olarak fail-closed reddedilir. Daha önce geçerli biçimde kullanılan konfigürasyon
değişmez; hatalı tipler artık kullanım sırasında değil kurulum anında reddedilir.
Endpoint provider oluşturulurken HTTPS URL olarak doğrulanır; yalnızca
`localhost`, `127.0.0.1` veya `::1` loopback endpoint'lerinde HTTP test amacıyla
izin verilir. Hatalı ya da uzak HTTP endpoint ile ağ çağrısı başlatılmaz.
Embedding HTTP istemcisi yönlendirmeleri izlemez: endpoint'in 3xx cevabı
credential veya metnin başka bir URL'ye yönelmesini önlemek için istek hatası
olarak kapatılır. Özel OpenAI-compatible endpoint `/embeddings` isteğini doğrudan
yanıtlamalı; yönlendirme gerekiyorsa `base_url` nihai adrese göre ayarlanmalıdır.

Harici servis seçeneğinde API anahtarı kodda tutulmaz; veri paylaşımı, saklama ve bölge politikası kontrol edilir. Timeout, rate limit ve exponential backoff ile sınırlandırılmış yeniden deneme uygulanır. Ancak istemci cevap alamadan servis isteği işlemiş olabilir; adapter idempotency anahtarı garantisi vermez ve belirsiz ağ hatasında aynı batch tekrar gönderilebilir. Sağlayıcıya göre yinelenen işleme veya ücret oluşabileceği için retry sayısı sınırlıdır ve gerçek maliyet final ölçümünde kontrol edilir. Ham hassas içerik gönderilecekse açık bir gizlilik kararı gerekir.

Adapter metinleri yapılandırılmış batch boyutlarında OpenAI Embeddings endpoint'ine
gönderir, batch'ler arasında input sırasını korur, dönen `data.index` alanına göre
sıralar ve boyut/sonlu sayı/sıfır-norm kontrolleri yapar. Her batch kendi sınırlı
retry döngüsüne sahiptir; kısmi sonuç başarı kabul edilmez. API anahtarı
ve ham metin loglanmaz; herhangi bir input için vektör üretilemezse provider
sonuç listesini sessizce kısaltmak yerine fail-closed hata döndürür. Aynı çağrı
içindeki duplicate input'lar tek external
input'a indirilir ve sonuçlar özgün sıraya geri açılır. Tekrarlanan input'lar için
yalnızca SHA-256 anahtarı ve
vektör tutulur; ham input cache'e yazılmaz. Cache state erişimi eşzamanlı
provider kullanımı için kilitlidir; ağ çağrıları bu kilidi tutmaz. Ağ retry/backoff
ve provider maliyet
ölçümü bu ilk
adapter diliminde sınırlı (en fazla 5) retry/backoff ile ele alınır; provider maliyet
ölçümü final kapasite çalışmasına bırakılmıştır. İstek hatası fail-closed
olarak embedding işini durdurur.

Yanıt sözleşmesinde her `data` kaydı nesne olmalı; `index` JSON tam sayısı olmalı
(boolean veya sayısal metin kabul edilmez) ve batch içindeki beklenen indeks
dizisini tam olarak `0..N-1` karşılamalıdır. `embedding` JSON dizisi içindeki her
koordinat JSON sayı olmalı; boolean ve metin değerleri sayıya dönüştürülerek
kabul edilmez. Bu tür/indeks kontrolleri boyut ve sonluluk doğrulamasından önce
yapılır; uyumsuz cevap fail-closed reddedilir.

HTTP yanıt gövdesi en fazla 64 MB olacak şekilde sınırlı okunur; limit aşılırsa
JSON parse veya vektör oluşturma yapılmadan istek reddedilir. Bu üst sınır bozuk
veya uyumsuz endpoint yanıtlarının belleği sınırsız tüketmesini önleyen yerel
korumadır; provider'ın fiyat, token ve kullanım limitlerinin yerine geçmez.

Provider ayrıca ham input içermeyen `cache_stats` görünümü sunar: `hits`, `misses`,
`entries` ve `capacity`. Bu sayaçlar cache davranışını ölçmeye yarar; tek başına
provider maliyeti, kalite kazanımı veya genel kapasite kanıtı değildir. Cache
kapasitesi `0` seçildiğinde cache devre dışıdır; her input lookup'ı privacy-safe
`misses` sayacına yansır.

## Koleksiyon uyumluluğu

Şu dört değer değişirse yeni koleksiyon gerekir:

1. model veya model sürümü
2. embedding boyutu
3. vektör uzayı/normalizasyon
4. chunking veya parser çıktısını anlamlı biçimde değiştiren sürüm

Query ve document embedding aynı uyumlu model uzayından üretilmelidir. Koleksiyon adı veya manifest'i bu değerleri taşımalıdır.

## Sağlayıcı karşılaştırma testi

Her aday için aynı benchmark üzerinde ölç:

- Recall@k ve MRR
- Türkçe sorgu performansı
- p95 embedding latency
- toplam kaynak/maliyet
- veri gizliliği ve operasyon kolaylığı
- hata sonrası yeniden çalıştırma davranışı

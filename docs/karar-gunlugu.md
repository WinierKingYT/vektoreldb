# Karar günlüğü

## 2026-09-22 — Query relevance etiketleme protokolü

- V1.7 query-label sözleşmesi ikili chunk relevance'ı olarak kalacak;
  `relevant_chunk_ids`, sorguyu cevaplamakta doğrudan kullanılabilir kanıt
  taşıyan chunk'ları gösterir. Dereceli qrels schema değişikliği bu goal'a
  eklenmeyecek; ölçülmüş ihtiyaç çıkarsa ayrı migration/metric kararı açılacak.
- Exact/lexical ve dense (varsa opt-in retrieval varyantı) adaylarının havuzu
  incelenecek; havuz tamlık kanıtı sayılmayacak. İncelenmemiş chunk otomatik
  “non-relevant” değildir. Negative etiketi, corpus ve parse kapsamı kontrol
  edilmeden verilmeyecek.
- Tek annotator için ikinci annotator zorunlu değil; test split'inden ayrı,
  skor/rank bilgisi gizli küçük tekrar incelemesindeki değişiklikler kaydedilecek.
  Bu sonuç annotator'lar arası anlaşma diye sunulmayacak.
- Kaynaklar: [NIST TREC relevance judgments](https://trec.nist.gov/data/reljudge_eng.html),
  [BEIR paper](https://arxiv.org/abs/2104.08663). BEIR'in task/domain çeşitliliği,
  kişisel fixture'da tek tip sorgularla 300 sayısına ulaşmama kararını destekler;
  bu bir tasarım çıkarımıdır, BEIR protokolünün zorunlu kuralı değildir.
- Etki/rollback: kod, label schema, mevcut veri ve runtime davranışı değişmez.
  Yönerge yetersiz kalırsa doküman güncellenebilir; qrels schema değişirse eski
  binary kayıtlar sessizce dönüştürülmeden ayrı sürüm açılır.

## 2026-09-22 — Parser izolasyonu belgesinin uygulamayla hizalanması

- Parser rehberinin izolasyon bölümünde timeout, bellek sınırı ve geçici alan
  mevcutmuş gibi yazılmıştı; gerçek kod senkron in-process parser ve dosya/içerik
  boyut limitleri kullanıyor, fakat process deadline/peak-RAM sandbox'ı kurmuyor.
- Yanlış güvence kaldırıldı. PDF sayfa metni limit kontrolünden önce çıkarıldığı
  için boyut kontrollerinin peak-memory garantisi olmadığı da açıkça belirtildi.
  Format başına gerçek runtime/RAM profili final ölçümüne eklendi; daha karmaşık
  worker izolasyonu ancak bu ölçüm ihtiyacı kanıtlarsa açılacak.

## 2026-09-22 — Harici embedding numeric sınır doğrulaması

- Provider constructor'ı aralık içinde olsa da boolean/kesirli integer ayarlarını
  kabul edebiliyor, NaN/sonsuz timeout ve backoff değerlerini geçirebiliyordu;
  hatalar geç aşamada oluşabilir veya sınırsız bekleme yaratabilirdi. Ayarların
  numeric türü ve sonluluğu kullanım başlamadan doğrulanır.
- Dış vektörün her koordinatı sonlu olsa bile kareler toplamı taşarak sonsuz
  olabilir. Normun pozitif ve sonlu olması manifest boyutuyla beraber zorunlu
  tutulur. Bu, geçerli config ve olağan vektörleri değiştirmez; yalnızca yanlış
  tür ve bozuk/taşan yanıtları erkenden fail-closed reddeder.

## 2026-09-22 — Harici embedding yönlendirmelerini kapatma

- Python 3.12.13'ün aktif `urllib.request.HTTPRedirectHandler` uygulaması
  POST→GET yönlendirmesinde Authorization dahil request header'larını yeni
  request'e kopyalıyordu. Kaynak başvuru olarak [CPython urllib.request
  uygulaması](https://github.com/python/cpython/blob/main/Lib/urllib/request.py)
  ve [Python urllib.request belgeleri](https://docs.python.org/3/library/urllib.request.html)
  incelendi; çalışma ortamındaki sürümün gerçek metodu da doğrulandı.
- Embedding endpoint'i redirect verirse, API credential'ı veya metnin farklı
  hedefe gitme riskini önlemek için istek artık fail-closed durur. Tüketici
  endpoint'in son adresini `base_url` olarak vermelidir. Şema/index değişmez;
  rollback yalnızca transport opener değişikliğini geri almaktır.
- Aynı incelemede provider dokümanındaki “idempotent batch retry” iddiası
  düzeltildi: client tarafında idempotency key yoktur; response kaybı sonrası
  yeniden gönderim sağlayıcıda tekrarlı işleme/ücrete yol açabilir. Bounded retry
  korunur, gerçek maliyet final ölçümüne bırakılır.

## 2026-09-21 — RAG context metadata attribute escaping

- RAG context kaynak metnini XML text olarak escape ediyordu; ancak title,
  document/chunk id ve heading path değerlerini double-quoted XML attribute'larına
  yalnızca text escaping uygulayarak yazıyordu. Tırnak içeren metadata
  attribute yapısını genişletebildiğinden `quoteattr` ile encode edildi.
- XML parser regresyon testi saldırgan tırnak örneklerinin attribute ekleyemediğini
  ve değerlerin kayıpsız kaldığını denetler. Bu, prompt injection'a karşı tek başına
  güvenlik garantisi değildir; context hâlâ güvenilmeyen kanıttır.

## 2026-09-21 — Abstention eşiği ve reranking skor sözleşmesi

- `min_score` yalnızca dense cosine retrieval'a uygulanır ve varsa reranking
  öncesinde aday kabulünü belirler. Reranker sadece bu adayları sıralar; [Sentence
  Transformers kullanım rehberi](https://www.sbert.net/docs/cross_encoder/usage/usage.html)
  bazı CrossEncoder modellerinin ham logit döndürdüğünü ve sigmoidin yalnızca
  ölçeği dönüştürdüğünü belirtir.
- Hybrid RRF ve late-interaction MaxSim skorları cosine değildir. Kalibrasyonsuz
  eşik yanlış abstention üretebileceğinden bu iki modda eşik talebi servis/model
  çalıştırılmadan reddedilir; eşiksiz arama korunur. [Qdrant RRF](https://qdrant.tech/documentation/search/hybrid-queries/)
  sıraları, [MaxSim](https://qdrant.tech/documentation/manage-data/vectors/)
  token düzeyi benzerlik maksimumlarını birleştirir. İleride açılmaları için ayrı
  skor sözleşmesi ve validation kalibrasyonu gerekir. Reranker-confidence eşiği
  bu sürümün kapsamı dışındadır. Reranking açıkken validation ve test aynı
  retrieval/reranker bileşimini kullanmalıdır.
- Eşik seçici helper, evaluator ile aynı biçimde boolean/sayısal olmayan score ve
  kalite tabanı girdilerini reddeder. API/servis `min_score` da boolean veya
  sayısal olmayan değeri kabul etmez.

## 2026-09-21 — Private-local corpus artifact'lerini izlenen benchmark'tan ayırma

- Önceki karar inventory/manifest varsayılanlarını ignore edilen dizinlere aldı,
  ancak eski `data/benchmarks/corpus-inventory.json`, `corpus-manifest.json` ve
  bunlara bağlanan `representative-personal-*.json` fixture/label/coverage
  kayıtlarının Git'te izlenmeye devam etmesini gözden kaçırdı. Bu dosyalar
  `private-local` sınıfı taşıyor; ham metin içermemeleri paylaşım için yeterli
  güvence değil, çünkü yollar/hash'ler/ID'ler ve içerikten türetilmiş sorular
  açığa çıkabilir.
- Bu artifact aileleri `.gitignore` kapsamına alınıyor; yerel dosyalar korunur ve
  testler kişisel corpus snapshot'ı yerine geçici, açıkça sentetik manifestler
  kullanacak. `data/benchmarks/queries.json` gibi genel contract fixture'ları
  ayrı ve paylaşılabilir sözleşme girdileri olmaya devam eder.
- Compatibility: CLI şeması, corpus checksum/provenance ve kullanıcı tarafından
  verilen output yolları değişmez; temiz clone artık kişisel corpus snapshot'ı
  varsaymaz. Geri alma yalnızca ignore kuralı/test yardımcıları/docs değişikliğini
  geri almak ve bilinçli şekilde sentetik public fixture koymaktır; kişisel
  artifact'leri yeniden Git'e eklemek varsayılan rollback değildir.
- GitHub'da önceden yayımlanmış commit geçmişi bu yerel düzeltmeyle silinmez;
  public geçmişi gizleme/yeniden yazma ayrı kullanıcı onayı gerektirir.

## 2026-09-21 — Kişisel corpus artifact'lerini Git dışına alma

- `corpus-inventory` varsayılanı Git'te izlenen `data/benchmarks/` içine
  yazıyordu. Inventory ham metin taşımasa da göreli kaynak yolu, içerik hash'i,
  document/chunk kimlikleri ve boyut metadata'sı içerdiğinden gerçek kişisel
  corpus için public paylaşım riski oluşturuyordu; ayrıca sentetik benchmark
  artifact'lerinin üzerine yazabilirdi.
- Kişisel kullanım için inventory/manifest varsayılanları zaten ignore edilen
  `data/derived/` ve `data/manifests/` klasörlerine taşındı. `data/benchmarks/`
  mevcut izli sentetik fixture paketi olarak kalır. Açık `--output`/`--manifest`
  seçenekleri geriye uyumludur; dosya formatı ve fixture provenance sözleşmesi
  değişmez. Geri alma yolu eski CLI varsayılanlarına dönüştür; kullanıcı bu
  sırada kendi özel yollarını açıkça verebilir.
- Defaultsız `vdb corpus-inventory` komutu 14 yerel kaynağı 47 chunk/19.961
  karakter olarak işledi; JSON çıktıları yalnızca `data/derived/` ve
  `data/manifests/` altına yazıldı ve ikisi `git check-ignore` ile doğrulandı.
  Embedding/Qdrant başlatılmadı; komut izlenen benchmark dosyalarını değiştirmedi.

## 2026-09-21 — HTML gizli blok yığın doğrulaması

- Mevcut HTML filtresi atlanan etiketleri tek bir sayısal derinlikle izliyordu;
  eşleşmeyen `</aside>` gibi kapanışlar açık `<nav>`/`<script>` filtresini erken
  bitirebilir, bozuk iç içe etiketler de sonraki görünür metni gereksiz yere
  bastırabilirdi.
- Filtreleme sözleşmesi tag-aware stack olarak güncellendi. HTML kanonik
  çıktısındaki olası farklar `html-v4` parser sürümüne bağlandı; HTML belgeleri,
  corpus manifesti ve parser provenance taşıyan fixture/coverage artifact'leri
  yeniden üretilip doğrulanmalıdır. Geri alma yolu önceki parser sürümüne dönüş
  ve etkilenen HTML belgelerini önceki manifestle yeniden indekslemektir.
- Uygulama sonrası `corpus-inventory`: 14 kaynak, 47 chunk, 19.961 karakter,
  sıfır parse hatası; dosya bazlı corpus checksum'ı değişmedi. Fixture
  `parser_versions_binding_status=valid` ve `corpus_binding_status=valid`;
  final kapısı mevcut 36 review-required etiket ve eksik large bucket nedeniyle
  beklenen biçimde açık. HTML hedefli regresyon `3 passed`; tam paket final
  turuna bırakıldı.

## 2026-09-21 — Metinsiz PDF için OCR teşhisi

- pypdf resmi metin çıkarım rehberi, kütüphanenin OCR yapmadığını; görsel/tarama
  içeriğinden metin çıkaramayacağını, sıralamanın PDF içerik akışına bağlı olarak
  beklenenden farklı olabileceğini ve sıkıştırılmış page content stream'lerinin
  yüksek bellek kullanabileceğini belirtiyor.
- Tamamen metinsiz PDF'ler artık genel `empty parsed document` hatası yerine
  taranmış/görsel içerik olasılığını ve olası OCR ihtiyacını belirten dosya-seviyesi
  hata veriyor; bu durum tek başına dosyanın tarama olduğunu kanıtlamaz.
  Kısmen metinsiz sayfalara fallback/OCR eklenmedi; pypdf `layout` modu varsayılan
  olmadı. Başarılı sayfalardaki metin, parser sürümü ve provenance değişmiyor.
- Geri alma yolu yeni özel hata dalını kaldırmaktır. Bu davranış source text ya
  da Qdrant payload sözleşmesini değiştirmez. Hızlı parser testi pypdf çağrısını
  taklit ederek metinsiz PDF teşhisini doğrular; gerçek çeşitlendirilmiş PDF
  kalite raporu ve süreç/bellek izolasyonu final ölçüm kapısında kalır.

## 2026-09-12 — İlk taslak

- Sağlayıcıdan bağımsız veri modeli; varsayılan uygulama Qdrant.
- Qdrant: payload filtreleme ve filtre indeksleri kişisel RAG için pratik.
- FAISS: kütüphane düzeyi, sabit/RAM ağırlıklı prototip seçeneği.
- pgvector: PostgreSQL ekosistemi ve ilişkisel sorgular baskınsa alternatif.
- HNSW parametreleri benchmark olmadan optimize edilmeyecek.
- Embedding modeli, boyut ve mesafe metriği koleksiyon sözleşmesinin parçası.

## 2026-09-12 — Aşama 1 kapsamı

- İlk veri türleri: Markdown/TXT, PDF, DOCX, HTML, JSON ve CSV.
- XLSX, görsel, OCR ağırlıklı PDF, ses/video ve özel kod araması sonraki aşamalara bırakıldı.
- Uygulama local-first olacak; local ve harici embedding sağlayıcıları ortak adapter sözleşmesiyle değiştirilebilecek.
- Parser çıktısı, chunk çıktısı ve embedding manifest'i ayrı sürümlenecek.
- Aşama 2 araştırması: dense-only yaklaşım, kendi benchmark'ımız yetersiz kalırsa sparse/hybrid ve reranking ile genişletilecek.
- Model seçiminde local ve harici seçenekler aynı Türkçe benchmark üzerinde karşılaştırılacak.
- Kritik şema kararı: Qdrant point ID UUIDv5 olacak; `document_id` ve `chunk_id` payload'da tutulacak.
- V1 dense-only olacak; sparse/hybrid named-vector yapısı v2 migration'ı olarak ele alınacak.
- Yetki modeli V1'de yalnızca `owner_id = me`; `tenant_id` kullanılmayacak.
- İleri seviye özellikler V1'e dahil edilmeyecek; hybrid, multi-vector, quantization, sharding, multimodal ve Graph-RAG ölçüm sonucu ile ayrı sürümlerde değerlendirilecek.
- Temel dokümantasyon kapanışında JSON Schema, OpenAPI, yapılandırma, geliştirici kurulum, benchmark fixture ve release politikası eklendi.
- İlk karar dönemi: [V1 geçiş kabul listesi](15-kodlama-oncesi-kabul-listesi.md) tamamlanmadan uygulama kodu yazılmayacak.
- İlk dikey dilim Markdown/TXT ile başlayacak; PDF, DOCX, HTML, JSON ve CSV parser'ları temel akış doğrulandıktan sonra eklenecek.
- Vektörel veritabanı ileride kişisel RAG sisteminin retrieval katmanı olacak; LLM/generation katmanı ayrı tutulacak ve sonuçlarda provenance taşınacak.
- Kodlama öncesi V1 kapsamı [V1 kapsam tanımı](v1-kapsam-tanimi.md) ile sabitlendi; ilk dikey dilim Markdown/TXT ve dense-only exact/HNSW retrieval'dır.
- Kodlama öncesi başlangıç varsayılanı: CPython 3.12, uv, pytest/ruff, local multilingual-e5-base, 768-dim cosine normalized vector ve önce CLI. Bu seçim benchmark sonrası değiştirilebilir.
- Local embedding provider iskeleti eklendi: Sentence Transformers lazy-load, E5 query/passage önekleri, normalize edilmiş vector ve manifest boyut kontrolü. Gerçek model seçimi 30 sorguluk benchmark sonrası kesinleşecek.

## 2026-09-13 — V1.1 ilk dikey dilim

- Filtre sözleşmesi `document_id`, `source_uri`, `source_type` ve `title` alanlarıyla sınırlı tutuldu; alanlar arası AND, aynı alan içi OR uygulanır.
- `owner_id=me` ve `document_status=active` koşulları istemciden bağımsız server-side zorunlu kalır.
- Retrieval audit olayına aday/filtrelenen/sonuç sayısı, filtre alanları ve latency eklendi; ham sorgu ve belge metni loglanmaz.
- V1.1 filtreleri ve gözlemlenebilirliği için 98 test geçti. Hybrid, reranking ve query planner sonraki sürümlere bırakıldı.

## 2026-09-13 — V1.2 baseline hazırlığı

- PromtGen README corpus'u için 100 sorguluk deney fixture'ı hazırlandı: 89 pozitif ve 11 negatif sorgu.
- Dense baseline sonucu: Recall@k `1.0000`, MRR `0.9157`, nDCG `0.9378`, negative success `0.0000`, p95 `28.970 ms`, error rate `0.0000`.
- Hybrid kararını küçük corpus'tan çıkarmama kararı alındı; dense+sparse RRF ayrı koleksiyon/manifest ve rollback ile denenecek.
- V1.2 RRF prototipi aynı fixture'da Recall `1.0000`, MRR `0.9101`, nDCG `0.9337`, p95 `35.555 ms` verdi. Dense baseline'a göre kalite artmadığı ve p95 yükseldiği için dense varsayılan korundu; hybrid yalnızca opt-in deney yolu olarak bırakıldı.
- V1.3 lexical-overlap kontrol reranker'ı aynı fixture'da Recall `1.0000`, MRR `0.9157`, nDCG `0.9378`, p95 `36.264 ms` verdi. Kalite artışı olmadığı için reranking varsayılan açılmadı; fallback ve sözleşme prototipi korunuyor.
- V1.4 selectivity-aware planner eklendi. İlk eşikler strict `0.05`, medium `0.50`; katı filtre exact fallback, orta filtre geniş ANN seçer. Planner varsayılan kapalı ve eşikler gerçek filtreli workload ile yeniden ölçülecek.
- V1.4 filtreli 100 sorgu benchmark'ında planner kapalı/açık Recall `1.0000`, MRR `0.9000`, nDCG `0.9262` kaldı; p95 `26.617 → 28.363 ms` yükseldi. Planner varsayılan açılmadı.
- V1.5 deterministic hashed token multi-vector ve Qdrant `MAX_SIM` late-interaction yolu eklendi. Late vector HNSW'siz rescoring için ayrıldı; kalite ve kapasite benchmark'ı tamamlanana kadar varsayılan dense/hybrid değişmeyecek.
- V1.5 ilk 100 sorgu sonucu MRR `0.9494`, nDCG `0.9627`, p95 `30.922 ms` oldu. Dense baseline'a göre kalite arttı fakat iki-chunk corpus ve p95 maliyeti nedeniyle late varsayılan yapılmadı; hard-negative/uzun corpus doğrulaması açık kaldı.
- V1.6 scalar INT8 quantized adapter eklendi. Docker Qdrant server üzerinde quantization config ve arama smoke testi `3 passed`; local Qdrant client ayarı uygulamadığı için quantized mod localde fail-closed. Ayrı koleksiyon ve rollback planı kullanılıyor.
- V1.6 Docker server benchmark'ında 100 sorguda Recall `1.0000`, MRR `0.9157`, nDCG `0.9378`, p95 `49.729 ms` oldu. Küçük corpus'ta kalite ve kapasite kazanımı kanıtlanmadığı için quantized mod varsayılan yapılmadı.
- V1.7 benchmark çıktısına query-type metrikleri eklendi; embedding/retrieval latency ve güvenli maliyet sinyalleri audit'e taşındı. Prompt injection tespiti `needs_review` karantinasına bağlandı. 100 sorguluk dense run Recall `1.0000`, MRR `0.9157`, nDCG `0.9378`, p95 `25.304 ms`, negative success `0.0000` verdi.
- İlk ingest omurgası eklendi: parser → chunk → embedding → Qdrant `PointStruct`; point ID UUIDv5 ile deterministik, provenance ve embedding manifest payload'da korunuyor. Qdrant bağlantısına karşı entegrasyon testi henüz ayrı bir runtime adımıdır.
- Retrieval katmanı eklendi: provider-agnostic `RetrievalService`, limit/min-score doğrulaması ve RAG-safe provenance response'u. Exact cosine baseline test ediliyor; HNSW gerçek Qdrant smoke test'i Docker daemon bekliyor.
- Ingest yaşam döngüsüne `delete_document` ve delete-önce-upsert `reindex_file` eklendi; Qdrant araması yalnızca `owner_id=me` ve `document_status=active` kayıtlarını döndürüyor. Local runtime için Qdrant `v1.19.0` compose tanımı eklendi.
- CLI çekirdeği `doctor`, `ingest` ve `search` komutlarıyla çalışır hale getirildi. `doctor` Qdrant erişimini kontrol eder; ingest/search gerçek Qdrant bağlantısı gerektirir.
- CLI yaşam döngüsü `delete` ve `reindex` komutlarıyla tamamlandı; tüm komutlar aynı servis/adaptör sınırlarını kullanıyor.
- Qdrant adapter'ına snapshot oluşturma/restore çağrıları ve embedding/collection sözleşmesini taşıyan backup manifest yazımı eklendi. Gerçek snapshot restore doğrulaması Docker runtime smoke testine bırakıldı.
- Source-root, uzantı ve dosya boyutu doğrulaması ingest'e bağlandı; Recall@k ve elapsed-time ölçen temel benchmark primitives eklendi. Benchmark sonuçları gerçek kişisel sorgu setiyle üretilecek.
- FastAPI retrieval yüzeyi OpenAPI ile hizalandı: `/v1/health` ve `/v1/search`; generation katmanı API'ye eklenmedi, provenance response'ta korunuyor.
- Benchmark fixture `data/benchmarks/queries.json` 30 etiketli sorgu ve loader ile eklendi; sonuçlar gerçek corpus ile doldurulmadan model/indeks seçimi kesinleştirilmeyecek.
- Production composition root `personal_vector_db.server:app` eklendi; API Qdrant erişimini health endpoint üzerinden raporlar ve RAG istemcisi için kalıcı servis giriş noktası sağlar.
- API kullanıcı hatalarını kontrollü doğruluyor; `/v1/search` boş sorgu ve geçersiz değerleri 4xx olarak ele alıyor. Test toplamı 24'e ulaştı.
- Qdrant adapter'ı `:memory:` modunu destekleyecek şekilde doğrulandı; gerçek Qdrant motoruyla collection, upsert, `owner_id`/status filtreleme, retrieval ve delete round-trip testi geçti. Payload index etkisi yalnızca server Qdrant'ta geçerlidir.
- Qdrant in-memory üzerinde gerçek parser → chunk → embedding → upsert → retrieval round-trip testi de geçti; test toplamı 26 oldu. Docker server smoke testinde payload index ve snapshot davranışı ayrıca doğrulanacak.
- Qdrant collection/index tekrar açılış davranışı ve snapshot adapter çağrıları test edildi; statik OpenAPI `/v1/health` ve provenance alanlarıyla güncellendi. Test toplamı 27 oldu.
- Snapshot yaşam döngüsü CLI'ye `backup` ve `restore` komutlarıyla bağlandı; backup manifest'i collection ve embedding sözleşmesini birlikte kaydediyor.
- HTTP yaşam döngüsü ingest/delete/reindex endpoint'leriyle genişletildi; V1 API yalnızca source-root içindeki `file_ref` kabul ediyor. OpenAPI bu gerçek sözleşmeyle hizalandı.
- HTTP reindex yaşam döngüsü test edildi; belge içeriği değiştiğinde eski point'ler temizlenip aynı document kimliği altında yeni chunk'lar yazılıyor. Test toplamı 29 oldu.
- Server Qdrant runtime smoke test prosedürü ve `data/sources` kullanım rehberi eklendi; Docker daemon hazır olmadığından prosedür henüz çalıştırılmadı.
- Server Qdrant snapshot yanıtındaki checksum ve local tar arşivinin SHA-256 değeri backup manifest'e taşınıyor; restore doğrulaması aynı checksum sözleşmesini kullanıyor.
- Backup manifest için JSON Schema eklendi; manifest artık dosyaya yazılmadan önce runtime schema doğrulamasından geçiyor.
- Exact baseline upsert işlemi Qdrant ile aynı stable point ID idempotency davranışına getirildi; aynı point tekrar yazıldığında duplicate oluşmuyor.
- Kodlama başlangıç formundaki dokuz kod öncesi karar maddesi repository kanıtlarıyla doğrulanıp işaretlendi; yalnızca gerçek corpus ölçümü ve Docker server smoke testi son geçiş kapısı olarak kaldı.
- Chunk payload şeması provenance alanlarıyla genişletildi; ingest artık document metadata ve chunk payload'ını upsert öncesi JSON Schema ile runtime doğruluyor.
- Gerçek `multilingual-e5-base` smoke testi geçti: 768 boyut, L2 norm 1.0; gerçek Qdrant in-memory ingest/retrieval ile repository source dosyasında provenance sonucu doğrulandı.
- Kodlama öncesi kabul listesi güncellendi; tamamlanan sözleşme/test maddeleri işaretlendi, yalnızca server Qdrant smoke testi ve gerçek corpus benchmark eşikleri açık bırakıldı.
- Benchmark fixture'ı gerçek retrieval servisine bağlayan `vdb benchmark --fixture ... --limit ...` komutu eklendi; sonuçta sorgu sayısı, Recall@k ve elapsed time raporlanıyor.
- Benchmark komutuna `--output` ile JSON sonuç kaydı eklendi; kalite/latency koşuları artık karşılaştırılabilir artefact olarak saklanabiliyor. Test toplamı 32 oldu.
- JSON Schema runtime validator eklendi; document metadata ve chunk payload sözleşmeleri bilinmeyen alanlara karşı test ediliyor. Test toplamı 31 oldu.
- Qdrant adapter'ına `path:<dir>` local persistence desteği eklendi; kapanıp açılma sonrası collection/point kalıcılığı test edildi. V1 varsayılanı Docker gerektirmeyen `path:qdrant_storage`, server Qdrant ileri runtime doğrulaması için ayrıdır.
- Docker Desktop/WSL ortamındaki stale socket sorunu nedeniyle server Qdrant smoke testi ertelendi. Docker V1 local geliştirmesini bloklamaz; payload-index ve server snapshot/restore doğrulaması Docker ortamı düzeldikten sonra ayrı entegrasyon geçişi olarak çalıştırılacaktır.
- Gerçek `multilingual-e5-base` ile disk persistence uçtan uca doğrulandı: ingest, Qdrant local path kapanıp açma ve semantic retrieval başarıyla tamamlandı; örnek hit score'u 0.874032 oldu. Bu tek smoke örneğidir, benchmark eşiği değildir.
- Qdrant collection yeniden açılışında dimension, named-vector ve cosine sözleşmesi kontrolü eklendi; isteğe bağlı `VDB_HNSW_EF` ile HNSW arama bütçesi provider/store sınırında yapılandırılabilir hale getirildi. Varsayılan davranış Qdrant'ın mevcut HNSW ayarlarını korur.
- CLI composition root da `VDB_HNSW_EF` ayarını aynı Qdrant adapter'ına geçiriyor; API ve CLI retrieval davranışları bu nedenle aynı collection/search sözleşmesini kullanıyor.
- Benchmark sonucu artık Recall@k yanında sorgu bazlı p50/p95/p99 latency ve error rate taşıyor; hata veren sorgular ölçüm döngüsünü bozmadan başarısız olarak raporlanıyor.
- Local-first varsayılanın Qdrant local client'ında native snapshot desteklemediği doğrulandı; bu nedenle adapter'a storage klasörünü arşivleyen tar snapshot ve path-traversal kontrollü restore eklendi. Server modunda native Qdrant snapshot API'si kullanılmaya devam ediyor.
- Local tar snapshot restore'unda opsiyonel SHA-256 checksum doğrulaması eklendi; uyuşmayan arşiv açılmadan reddediliyor.
- Benchmark altyapısı Recall@k yanında MRR@k ve nDCG@k rank metriklerini de raporluyor; latency/error ölçümleriyle aynı sorgu döngüsünde hesaplanıyor.
- Kabul listesi, mevcut geliştirme durumuyla tutarlı olacak şekilde “kod yazımını engelleyen” ifadeden “V1 üretim geçişini engelleyen” ifadeye güncellendi; local snapshot/restore koşulu tamamlandı olarak işaretlendi.
- FastAPI hata yanıtları güvenli ortak envelope'a alındı: `code`, `message`, `retryable`, `request_id` ve `details`; validation mesajı ham input/path yansıtmıyor.
- OpenAPI sözleşmesi gerçek V1 API ile yeniden hizalandı: uygulanmayan ileri alanlar ve GET/idempotency iddiaları kaldırıldı; validation/error response'ları ve provenance alanları eklendi. YAML parse doğrulaması geçti.
- README’ye local-first V1 çalıştırma akışı eklendi: kurulum, ingest, search, benchmark, backup ve restore komutları gerçek CLI sözleşmesiyle örneklendirildi.
- Exact baseline da Qdrant ile aynı `owner_id=me` ve `document_status=active` filtresini uyguluyor; böylece ground-truth kalite ölçümü erişim izolasyonunu atlamıyor.
- Local Qdrant'ta etkisiz olan payload-index çağrıları atlanıyor; server Qdrant'ta `document_id`, `owner_id` ve `document_status` index'leri oluşturulmaya devam ediyor.
- `:memory:` Qdrant da local mode olarak işaretlendi; etkisiz payload index ve HNSW search parameter çağrıları artık memory testlerinde de yapılmıyor. Server modunda HNSW bütçesi uygulanıyor.
- `uv build` ile source distribution ve wheel üretimi doğrulandı; `dist/` ve `*.egg-info/` artefact'leri ignore listesine alındı.
- CLI'nin aynı local Qdrant storage'a iki ayrı client açması `AlreadyLocked` hatasına yol açıyordu; client oluşturma yalnızca ilgili `doctor`/`delete` komutlarına taşındı ve regresyon testi eklendi. Tam test/lint sonucu: 43 test geçti, Ruff temiz.
- Qdrant adapter'ına açık `close()` yaşam döngüsü eklendi; CLI tüm command path'lerinde local storage lock'ını serbest bırakıyor. Bu, Windows'ta ardışık CLI çağrılarının stale lock yüzünden başarısız olmasını önlemek içindir.
- Gerçek CLI embedding smoke testi, `multilingual-e5-base` cache'inin eksik ve Hugging Face dış ağ erişiminin kapalı olduğunu gösterdi. Model indirme/cache hazırlığı runtime kurulum koşuludur; test doubles kullanan birim testleri bundan bağımsız kalır.
- Embedding config sözleşmesi tamamlandı: `VDB_EMBEDDING_REVISION` manifest'e taşınıyor ve V1 dışı provider değerleri sessizce local provider'a düşmek yerine açıkça reddediliyor. Böylece yanlış/unspecified provider ile collection'a yazma riski azaltıldı. Test toplamı 44 oldu, Ruff temiz.
- `reindex` artık `--document-id` verilmediğinde dosyanın deterministik document ID'sini parse ederek eski chunk'ları siler; parse başarısızsa mevcut veri korunur. Değişen dosyanın stale chunk bırakmaması için regresyon testi eklendi. Test toplamı 45 oldu.
- CLI ve FastAPI composition root aynı runtime ayar doğrulamasını kullanıyor; V1 dışı embedding provider veya cosine dışı mesafe metriği fail-closed reddediliyor. Sunucu embedding revision'ı da manifest'e aktarıyor. Test toplamı 46 oldu, Ruff temiz.
- Kabul listesinde metrik/regresyon maddesi `docs/25-kapasite-slo-hedefleri.md` içindeki Search p95/p99, Recall@5 ve hata oranı eşikleriyle kapatıldı; gerçek kişisel corpus sonucu ayrı geçiş koşulu olmaya devam ediyor.
- Son runtime sözleşme değişikliklerinden sonra `uv build` ile source distribution ve wheel yeniden üretildi; iki artefact da başarılı.
- API'ye beklenmeyen storage/provider exception'ları için güvenli 500 error envelope'u eklendi; ham backend ayrıntıları istemciye dönmüyor ve regresyon testiyle doğrulandı. Test toplamı 47 oldu, Ruff temiz.
- Content-safe structured audit event helper eklendi; ingest/delete/retrieval olayları JSON olarak loglanıyor, sorgu metni yalnızca SHA-256 fingerprint ile temsil ediliyor. Test toplamı 48 oldu.
- Benchmark'a baseline/aday Recall regresyonunu yüzde puan olarak hesaplayan ve 2 puanlık bütçeyi aşınca hata veren doğrulama eklendi; benchmark testleri aynı sorgu sayısı sözleşmesini de denetliyor.
- Benchmark regresyon doğrulaması kayan nokta toleranslı test ile doğrulandı; toplam test sayısı 49, Ruff temiz.
- Kodlama başlama onay formu repository kanıtlarıyla yeniden hizalandı; benchmark fixture'ına altı sorgu sınıfı metadata'sı eklendi. Açık kalanlar Docker server smoke testi ve gerçek kişisel corpus ölçümüdür.
- `uv lock --check` ve `uv build` tekrar başarılı; benchmark metadata değişiklikleri kilitli bağımlılık ve dağıtılabilir wheel/sdist ile uyumlu.
- Docker hazır olduğunda otomatik çalışacak, server Qdrant payload index ve upsert/search/delete yaşam döngüsünü doğrulayan integration testi eklendi; server URL yoksa test güvenli biçimde skip edilir. Doğrulama sonucu: 49 geçti, 1 skip.
- Local embedding model yükleme hataları artık library traceback'i yerine cache/indirme hazırlığını belirten güvenli bir runtime hatası olarak yüzeye çıkıyor; ingest başarısızlığında mevcut indeks yazılmıyor.
- Embedding modelinin `encode` aşamasında oluşan ağ/cache hataları da aynı güvenli hata sözleşmesine alındı; test sonucu 50 geçti, 1 Docker integration testi skip, Ruff temiz.
- API ingest/reindex filesystem hataları ham exception metni yerine güvenli özet döndürüyor; path sızıntısı için regresyon testi eklendi.
- Güvenlik regresyonları sonrası doğrulama sonucu: 51 test geçti, 1 Docker integration testi skip edildi; Ruff temiz.
- Son tam kalite geçişi: 51 test geçti, 1 Docker integration testi skip edildi, Ruff ve `uv lock --check` başarılı, wheel/sdist build başarılı.
- Gerçek `multilingual-e5-base` model cache'i hazırlandı; revision `d128750597153bb5987e10b1c3493a34e5a4502a` pinlendi ve Hugging Face offline modunda gerçek local CLI `ingest → search` smoke testi başarıyla çalıştı.
- Gerçek local CLI smoke testi aynı README dosyası iki kez ingest edilerek tekrarlandı; aynı deterministic document ID döndü, arama sonucu geldi ve collection point count `1` kaldı. Idempotency canlı local storage üzerinde doğrulandı.
- Local embedding çıktıları artık dimension yanında sonlu değer ve sıfır olmayan norm açısından da doğrulanıyor; geçersiz vektörler Qdrant'a yazılmadan reddediliyor.
- Vektör doğrulama regresyon testiyle tamamlandı; sonuç 52 test geçti, 1 Docker integration testi skip, Ruff temiz.
- Benchmark negative sorguları artık pozitif Recall/MRR/nDCG hesaplarını bozmayıp ayrı `negative_success_rate` olarak raporlanıyor; CLI çıktısı ve fixture sözleşmesi güncellendi.
- Negative benchmark davranışı boş sonuç bekleyen regresyon testiyle doğrulandı; son doğrulama 53 test geçti, 1 Docker integration testi skip, Ruff temiz.
- Gerçek fixture benchmark smoke testi 30 sorguda çalıştı; ilk model yüklemesinin p99'u şişirdiği görüldü. `run_benchmark` varsayılan warm-up ile steady-state latency ölçüyor; gerçek corpus kalite sonucu üretilmedi.
- Warm-up sonrası aynı teknik fixture benchmark'ı 30 sorguda hatasız tamamlandı; steady-state p95 `27.139 ms`, p99 `27.429 ms`. Recall sonucu kişisel corpus olmadığı için kalite kabulü sayılmadı.
- Gerçek local collection üzerinde geçici hedefe backup alındı; manifest collection/model/dimension/metric sözleşmesini ve SHA-256 snapshot checksum'ını içeriyor. Mevcut storage değiştirilmedi.
- Backup snapshot ayrı geçici local storage'a checksum ile restore edildi ve yeniden açılışta point count `1` doğrulandı; local snapshot/restore round-trip gerçek runtime'da geçti.
- Docker daemon erişimi tekrar kontrol edildi; Windows Docker engine pipe'ı mevcut olmadığı için server Qdrant smoke testi çalıştırılamadı. Docker V1 local persistence için gerekli değil; server entegrasyon doğrulaması sonraki aşamaya ertelendi. İzole temp klasörüyle son kalite doğrulaması `53 passed, 1 skipped` verdi; Docker testi skip olarak kaldı.
- Local Qdrant storage ile Docker server volume'ünün eşzamanlı kullanılmaması gerektiği README ve runtime smoke prosedürüne eklendi; iki mod arasında dosya kilidi ve veri bütünlüğü riski önlendi.
- Docker Compose ve manuel server örneği, local `qdrant_storage` yerine ayrı `qdrant_server_storage` kullanacak şekilde güncellendi. `docker compose config --quiet`, Ruff ve `uv lock --check` başarılı.
- Server entegrasyon testine gerçek Qdrant snapshot/restore round-trip senaryosu eklendi: collection oluşturma, point upsert, snapshot alma, silme, checksum ile restore ve arama doğrulaması. Docker daemon yokken iki entegrasyon testi beklenen şekilde skip; local suite `53 passed, 2 skipped`.
- Kodlama öncesi kabul listesine gereksinim→kanıt matrisi eklendi; local V1 kanıtları ile Docker/kişisel corpus bekleyen iki geçiş koşulu birbirinden ayrıştırıldı.
- Ayrı Docker server storage klasörü (`qdrant_server_storage/`) `.gitignore` kapsamına alındı; local/server Qdrant verisinin yanlışlıkla sürümlenmesi engellendi.
- Kabul listesi, kodlama öncesi belge olmaktan çıkarılıp mevcut V1 uygulaması için geçiş kapısı olarak yeniden adlandırıldı; açık Docker ve kişisel corpus koşulları korunuyor.
- README ve roadmap içindeki kabul listesi bağlantı başlıkları güncel adla eşitlendi; eski karar kaydı yalnızca tarihsel bağlam olarak bırakıldı.
- API sözleşmesi uygulamayla yeniden eşitlendi: V1 ingest yalnızca `file_ref` alıyor, retrieval alanı `embedding_manifest_id`; desteklenmeyen filtre/hybrid/rerank örnekleri gelecek roadmap olarak işaretlendi.
- API sözleşmesindeki uygulanmayan `PUT`/`GET` örnekleri kaldırıldı; mevcut `reindex` ve `delete` endpoint'leriyle eşitlendi.
- Pipeline/OpenAPI planlarında gelecek filtre, rerank, idempotency ve async iş davranışları roadmap olarak ayrıştırıldı; V1 dense-only ve mevcut alanlarla çelişen örnekler düzeltildi.
- V1 request modelleri unknown field'ları reddedecek şekilde strict yapıldı; desteklenmeyen `rerank` gibi alanların sessizce yok sayılması engellendi ve API regresyon testi eklendi.
- Strict request davranışı kök `openapi.yaml` sözleşmesine `additionalProperties: false` olarak işlendi; kod ve istemci sözleşmesi eşitlendi.
- API hata sözleşmesi uygulamadaki gerçek V1 davranışıyla eşitlendi; beklenmeyen provider/storage ayrıntıları güvenli `internal_error` zarfında tutuluyor, ayrıntılı dependency kodları gelecek iyileştirme olarak bırakıldı.
- Qdrant local ve server entegrasyon testleri collection HNSW yapılandırmasının mevcut olduğunu da doğrulayacak şekilde güçlendirildi; V1 retrieval'ın ANN yolu yalnızca dokümantasyon iddiası olarak bırakılmadı.
- Mimari dokümandaki uzun vadeli veri türleri ile V1 kapsamı ayrıştırıldı; Markdown/TXT dışındaki parser'ların henüz uygulanmadığı açıkça belirtildi.
- Ingest sınırında embedding boyutu, sonlu değer ve sıfır olmayan norm doğrulaması eklendi; hatalı provider çıktısının Qdrant'a yazılması regresyon testleriyle engellendi.
- V1 release gate yeniden çalıştırıldı: `57 passed, 2 skipped`; Ruff, `uv lock --check` ve source/wheel build başarılı. Skip edilen iki test yalnızca Docker server smoke koşuludur.
- Release sonrası Docker'sız local runtime `vdb doctor` ile yeniden kontrol edildi ve `ok` döndü; local storage/collection sözleşmesi sağlam kaldı.
- Son gerçek local smoke'ta offline pinned model cache ile `vdb doctor` `ok` ve `vdb search "local persistence" --limit 1` provenance'lı hit (`score=0.7470`) verdi; embedding/storage/API zinciri çalışır durumda.
- Reindex güvenliği düzeltildi: verilen `document_id` kaynak dosyanın deterministic kimliğiyle eşleşmiyorsa silme yapılmadan istek reddediliyor; veri kaybı regresyon testi eklendi.
- Reindex ön hazırlık aşamasına taşındı: parse/chunk/embedding başarısızsa eski point'ler silinmiyor; embedding hatasında eski belgenin korunduğu regresyon testiyle doğrulandı.
- Reindex kimlik doğrulaması ile hazırlama aşaması aynı parse sonucunu paylaşacak şekilde düzenlendi; kaynak dosyanın iki parse arasında değişmesiyle oluşabilecek kimlik/içerik ayrışması azaltıldı.
- Qdrant ve exact baseline için `replace_document` eklendi; yeni point'ler önce upsert edilip eski content hash'li chunk'lar sonra temizleniyor. Böylece reindex sırasında boş arama penceresi ve normal upsert hatasında gereksiz veri kaybı riski azaltıldı.
- Belge yaşam döngüsü ve operasyon runbook'u `replace_document` sırasını açıkça belgeledi; reindex güvenlik varsayımı kod ve işletim talimatlarında eşitlendi.
- `VectorStore` protokolüne `replace_document` eklendi ve Qdrant koleksiyon şemasında güvenli replacement sırası tanımlandı; yeni backend'lerin aynı reindex sözleşmesini izlemesi zorunlu.
- Delete/reindex document kimliği doğrulaması `doc_` prefix kontrolünden kanonik regex kontrolüne sıkılaştırıldı; path-benzeri geçersiz ID'ler reddediliyor.
- `replace_document` point payload'larının verilen `document_id` ile eşleşmesi zorunlu kılındı; backend replacement sözleşmesi yanlış belge yazımına karşı regresyon testiyle güçlendirildi.
- Exact baseline'a da dimension, finite değer ve non-zero norm invariant'ları eklendi; Qdrant ile kalite karşılaştırmasında farklı boyutlu vektörlerin sessizce kısaltılması engellendi.
- Strict API regresyon kapsamı ingest isteklerine genişletildi; V1 dışı `content` gibi alanların da sessizce yok sayılmadığı doğrulandı.
- Strict ingest alanı testi çalışan fake dependency ile doğrulandı; API testleri `10 passed`, Ruff temiz.
- Exact baseline'da geçersiz ilk upsert'in dimension state'ini zehirlemesi engellendi; state yalnızca vector invariant'ları geçtikten sonra kaydediliyor ve regresyon testi eklendi.
- Exact baseline non-numeric vector elemanlarını da kontrollü `ValueError` ile reddediyor; tip hatasının backend'e sızması için regresyon testi eklendi.
- Search limit sözleşmesi Qdrant ve exact backend'lere taşındı; servis/HTTP dışından yapılan aramalarda da `1–100` sınırı korunuyor.
- Backend limit kontrolü sonrası tam suite `67 passed, 2 skipped` verdi; Ruff ve `uv lock --check` başarılı.
- CLI search'e API ile aynı `--min-score` eşiği eklendi; düşük skorlu/negative sorgu sonuçlarını komut satırından filtrelemek mümkün oldu ve parser regresyonu güncellendi.
- Benchmark fixture yükleyicisi duplicate kimlikleri, boş/yanlış türde alanları ve ilgili chunk taşıyan negative sorguları reddedecek şekilde sıkılaştırıldı; kalite ölçümünün bozuk fixture ile sessizce sapması engellendi.
- Benchmark doğrulama kapısı güncel sonuçla tekrarlandı: `68 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı. Bekleyen iki skip, Docker server smoke testleridir.
- Cosine retrieval sözleşmesinde `min_score` değeri API, servis ve OpenAPI katmanlarında sonlu `[-1, 1]` aralığına alındı; NaN/sonsuz ve aralık dışı eşikler regresyon testleriyle reddediliyor.
- `min_score` sınırı sonrasında tam kalite kapısı tekrarlandı: `73 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- API kullanım rehberleri de `min_score` aralığıyla eşitlendi; uygulama, OpenAPI ve kullanıcı dokümanları aynı cosine sınırını belirtiyor.
- Exact baseline sorgu vektörü doğrulaması ingest ile eşitlendi; non-numeric, non-finite ve zero-norm sorgular kontrollü `ValueError` ile reddediliyor ve baseline hata davranışı backend ayrıntısına bağlı kalmıyor.
- Sorgu vektörü doğrulaması sonrası tam kalite kapısı tekrarlandı: `75 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- CLI `doctor` girişinde runtime provider/metric doğrulaması zorunlu hale getirildi; sağlık kontrolünün geçersiz yapılandırmayı başarılı göstermesi regresyon testiyle kapatıldı.
- Güncel kaynak dağıtımı doğrulandı: `uv build` source distribution ve wheel üretti; `compileall` import/bytecode derlemesi hatasız tamamlandı.
- Yapılandırma referansındaki embedding revision `unresolved` kalıntısı sabit V1 model commit'iyle eşitlendi; model sözleşmesinin değişmesi re-index gerektirir.
- Güncel yerel runtime smoke testi Docker olmadan tekrarlandı: `vdb doctor` başarılı; varsayılan `path:qdrant_storage`, `personal_documents_v1`, 768 boyut ve cosine sözleşmesi doğrulandı.
- Geliştirici kurulum rehberi ve parser sınırları mevcut V1 ile eşitlendi: local persistence varsayılan, Docker server opsiyonel; Markdown/TXT kaynak limiti 10 MB ve uygulanmayan parser timeout varsayımı kaldırıldı.
- OpenAPI kabul maddesi gerçek contract testiyle güçlendirildi: YAML parse ediliyor, V1 path'leri ve strict `SearchRequest` sözleşmesi doğrulanıyor; PyYAML yalnızca geliştirme bağımlılığı olarak pinlendi.
- OpenAPI contract testi ve PyYAML lock güncellemesi sonrası tam kalite kapısı tekrarlandı: `76 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- CLI `doctor` fail-closed düzeltmesi sonrası tam kalite kapısı tekrarlandı: `77 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Local embedding provider, manifest'teki model revision'ını `SentenceTransformer` yükleyicisine gerçekten aktarıyor; runtime'ın pinlenmemiş güncel model çekmesi engellendi ve loader argümanı regresyon testiyle doğrulandı.
- Model revision pinlemesi sonrası tam kalite kapısı tekrarlandı: `80 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Qdrant collection uyumluluk kontrolü embedding manifest'ine genişletildi; ingest, CLI composition root ve production API aynı manifest dışındaki mevcut point'leri reddediyor, böylece aynı boyutlu farklı model uzaylarının karışması engelleniyor.
- Manifest uyumluluk regresyonu sonrası tam kalite kapısı tekrarlandı: `82 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Manifest uyumluluk değişikliği sonrası kaynak dağıtımı ve wheel yeniden üretildi; `uv build` ve `compileall` başarılı.
- Embedding provider belgeleri V1 sınırıyla eşitlendi: harici provider adapter sözleşmesi mimari hazırlık, runtime'da yalnızca pinned local Sentence Transformers provider uygulanıyor.
- FastAPI uygulamasına lifespan cleanup eklendi; uygulama kapanışında storage adapter'ı varsa `close()` çağrılıyor ve local Qdrant dosya kilidinin gömülü kullanımda bırakılması test ediliyor.
- Lifespan cleanup değişikliği sonrası tam kalite kapısı tekrarlandı: `83 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Backup manifest'ine V1 parser ve chunking sürümleri eklendi; snapshot'ın yalnızca embedding değil, metin dönüşüm sözleşmesiyle de eşleştirilebilmesi sağlandı.
- Backup manifest sürüm alanları sonrası tam kalite kapısı tekrarlandı: `83 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- `vdb restore --manifest` eklendi; restore öncesinde collection, embedding manifest'i ve checksum uyumluluğu doğrulanıyor, manifestsiz mevcut restore kullanımı korunuyor.
- Restore manifest doğrulaması dimension ve metric alanlarını da açıkça karşılaştırıyor; yalnızca ID eşleşmesine güvenilmiyor.
- Restore manifest kullanıldığında snapshot adı da restore konumuyla eşleştiriliyor; farklı bir snapshot'ın aynı sözleşme manifest'iyle yüklenmesi engellendi ve regresyon testi eklendi.
- Snapshot adı doğrulama testi sonrası tam kalite kapısı tekrarlandı: `87 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Restore vector contract kontrolü sonrası tam kalite kapısı tekrarlandı: `84 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- JSON Schema dosyaları package data olarak `personal_vector_db/schemas` altına alındı; kurulu wheel repository kökü dışında çalışırken de document/chunk/backup doğrulaması yapabilecek.
- Package schema taşıması sonrası wheel içeriği üç schema dosyasıyla doğrulandı ve tam kalite kapısı `85 passed, 2 skipped` verdi; Ruff ve `uv lock --check` başarılı.
- README restore örneği manifest doğrulamasını kullanacak şekilde güncellendi; önerilen kullanıcı akışı collection/provider/checksum kontrolünü görünür biçimde çalıştırıyor.
- Repository canonical schema ile package schema kopyalarının eşitliği için drift regresyon testi eklendi; dağıtım ve kaynak sözleşmesinin ayrışması engellendi.
- Schema drift testi düzeltmesi sonrası tam kalite kapısı tekrarlandı: `86 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Restore manifest uyumsuzluk yoluna CLI regresyon testi eklendi; collection uyuşmazlığında restore çağrısı başlatılmıyor.
- Restore hata yolu testi sonrası tam kalite kapısı tekrarlandı: `85 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Restore manifest doğrulaması sonrası tam kalite kapısı tekrarlandı: `84 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Restore manifest API'si sonrası source distribution, wheel ve `compileall` yeniden doğrulandı; tüm release artefact kontrolleri başarılı.
- Güncel final yerel kalite kapısı tekrarlandı: `83 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı. Açık kalan iki skip yalnızca gerçek Docker server entegrasyon testleridir.
- Qdrant şema dokümanı da gerçek manifest uygulamasıyla eşitlendi: dimension/metric collection config'ten, embedding manifest'i point payload'larından doğrulanıyor; ayrı collection metadata manifest'i varsayılmıyor.
- `vdb doctor` artık `_services` üzerinden collection sözleşmesini ve pinned local embedding modelini gerçek bir health-query ile doğruluyor; yalnızca Qdrant bağlantısının sağlıklı görünmesi engellendi.
- Offline local smoke gerçek pinned model cache'i ve izole Qdrant storage ile geçti: model yükleme, health-query embedding'i, collection oluşturma ve `vdb doctor` `ok` sonucu doğrulandı. Varsayılan storage başka bir süreç tarafından kilitli olduğu için değiştirilmedi.
- Retrieval sorgu uzunluğu 4.000, ingest dosya referansı 4.096 karakterle sınırlandı; API/Pydantic/OpenAPI ve servis katmanları eşitlendi, embedding kötüye kullanım riski için regresyon testleri eklendi.
- İstek sınırı regresyonları sonrası tam kalite kapısı tekrarlandı: `79 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Exact baseline değişikliği sonrası tam suite yeniden doğrulandı: `66 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Replacement sözleşmesi sonrası tam regresyon kapısı yeniden çalıştırıldı: `62 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Qdrant koleksiyon dokümanı gerçek V1 indeks davranışıyla eşitlendi: yalnızca `document_id`, `owner_id` ve `document_status` indeksleri garanti ediliyor; sunulmayan metadata filtreleri roadmap'e bırakıldı.
- Kurulum rehberindeki eski metadata indeks listesi de gerçek V1 alanlarıyla eşitlendi; uygulanmayan `language`, `tags` ve `source_type` filtreleri kaldırıldı.

## Kaynaklar

- [Qdrant Guides](https://qdrant.tech/documentation/guides/)
- [Qdrant Indexing](https://qdrant.tech/documentation/manage-data/indexing/)
- [FAISS Documentation](https://faiss.ai/)
- [OpenAI Embeddings FAQ](https://help.openai.com/en/articles/6824809-embeddings-faq-2)
- Release politikası gereği repository köküne `CHANGELOG.md` eklendi; mevcut V1 kapsamı, doğrulanan yetenekler ve Docker/gerçek corpus bekleyen açık geçiş koşulları kaydedildi. Test çıktısı veya üretim davranışı değiştirilmedi.
- Qdrant memory HNSW yolu ile exact baseline aynı üç vektörlü fixture üzerinde karşılaştırıldı; sonuç sırası eşleşti. Tam kalite kapısı `88 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı. Docker server ve gerçek kişisel corpus koşulları açık kaldı.
- `min_score` filtresi top-k kırpmasından önce uygulanacak şekilde düzeltildi; böylece eşik altındaki ilk aday geçerli sonraki adayı gizleyemiyor. Regresyon testi ve tam kalite kapısı `89 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Silme ve reindex temizliği `owner_id = me` koşuluyla sınırlandırıldı; aynı `document_id` taşıyan başka sahipli noktalar etkilenmiyor. Qdrant memory regresyon testi eklendi; tam kalite kapısı `90 passed, 2 skipped`, Ruff ve `uv lock --check` başarılı.
- Local snapshot restore için tar arşivi path-traversal regresyon testi eklendi; güvenli olmayan üyeler çıkarılmadan reddediliyor. Tam kalite kapısı `91 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Tekrarlanan ingest artık Qdrant'ın replacement akışını kullanıyor; değişen belgenin eski chunk'ları geride kalmıyor. Uçtan uca regresyon testi eklendi; tam kalite kapısı `92 passed, 2 skipped`, Ruff ve `uv lock --check` başarılı.
- Exact baseline replacement akışı da owner kapsamına alındı; replacement noktaları yalnızca `owner_id = me` olabilir ve aynı kimlikteki başka sahipli noktalar korunur. Tam kalite kapısı `93 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- Document ID doğrulaması ortak yardımcıya taşındı ve CLI `delete` akışına bağlandı; geçersiz kimliklerde Qdrant bağlantısı açılmıyor. Tam kalite kapısı `94 passed, 2 skipped`; Ruff ve `uv lock --check` başarılı.
- İzole local Qdrant path ve mevcut offline model cache'iyle gerçek `vdb doctor` yeniden çalıştırıldı ve `ok` döndü. Docker server smoke testi ve gerçek kişisel corpus benchmark'ı bu doğrulamanın kapsamı dışında tutuldu.
- `HF_HUB_OFFLINE=1` ile gerçek local runtime smoke tekrarlandı; pinned embedding model cache'ten ağ erişimi olmadan yüklendi ve `vdb doctor` `ok` döndü. Local-first başlangıç davranışı güçlendirildi; Docker server doğrulaması hâlâ ertelenmiştir.
- Release paket doğrulaması tekrarlandı: `uv build` wheel ve sdist üretti; üç kanonik JSON Schema wheel içinde mevcut bulundu. Geçici `dist` ve build cache temizlendi.

- Geniş corpus goal'unun ilk parser dikey dilimi eklendi: Markdown/TXT akışı korunarak PDF, DOCX, HTML, JSON ve CSV için suffix-tabanlı dispatch ve kanonik belge üretimi sağlandı. PDF için `pypdf`, DOCX için zip/XML, HTML için görünür metin, JSON/CSV için deterministik kayıt/satır dönüşümü kullanılıyor. OCR, karmaşık tablo/sütun yerleşimi ve tam DOCX tablo fidelity'si bilinçli olarak sonraki kalite çalışmasına bırakıldı; bilinmeyen formatlar açıkça reddediliyor. Kapsamlı format testleri ve uzun süreli ölçümler goal'un final aşamasında yapılacak.
- Parser allowlist'i güvenlik doğrulamasıyla tek sözleşmede birleştirildi; böylece dispatch'in desteklediği PDF/DOCX/HTML/JSON/CSV kaynakları ingest güvenlik katmanında yanlışlıkla reddedilmiyor.
- 300+ sorgu hedefi için fixture sözleşmesi ve contract-only manifest eklendi. Mevcut 100 sorguluk smoke fixture'ı kopyalanmayacak; gerçek kişisel corpus, split, label provenance ve checksum final benchmark öncesi doldurulacak.
- Benchmark loader, `split`, `size_bucket` ve `filter_selectivity` metadata'sını geriye dönük uyumlu şekilde kabul edecek biçimde genişletildi. `validate_fixture_requirements` yalnızca `status=ready` manifestini kabul ediyor; mevcut 100 sorgu fixture'ı doğru biçimde final 300+ kapısından geçemiyor.
- `vdb fixture-validate` komutu eklendi; embedding modeli/Qdrant başlatmadan fixture ve manifest kabul kapısını çalıştırıyor. Contract-only manifestin reddedilmesi bilinçli davranış olarak korundu.
- `vdb corpus-inventory` eklendi; desteklenen yerel dosyaları recursive tarayıp metin taşımadan checksum, byte boyutu, size bucket, parser/section/chunk sayısı ve hata türü üretir. Gerçek query label'ları bu envanterden sonra hazırlanacak.
- `vdb ingest-dir` eklendi; desteklenen kaynakları relative path sırasıyla işler, dosya hatalarını izole eder ve başarısız dosyanın önceki indeks sürümünü korur. Bu toplu akış kişisel corpus büyütme için kullanılır; bütün klasör işlemi atomik değildir ve bu durum dokümante edildi.
- Bozuk PDF smoke akışı `pypdf.errors.PdfStreamError` exception'ının önceki dar catch listesine sığmadığını gösterdi; toplu ingest normal parser/provider exception'larını genel dosya-seviyesi failure kaydıyla izole edecek şekilde düzeltildi. `BaseException` yakalanmıyor.
- Corpus inventory artık aynı çalışmada deterministik, metinsiz corpus manifesti de üretiyor. Corpus checksum'ı kaynak dosya kimlikleri/hash durumu ile fixture etiketlerinin bağlanacağı provenance köprüsüdür.
- Corpus manifesti için repository ve package schema kopyaları eklendi; manifest yazılmadan önce runtime JSON Schema doğrulaması yapılıyor.
- Aktif gelişim goal'u için kabul matrisi eklendi. Kodlanmış özelliklerle final ölçüm kanıtları ayrıştırıldı; mevcut iki kaynak/üç chunk corpus nedeniyle goal'un tamamlanmadığı açıkça kaydedildi.
- Fixture kabul kapısı sıkılaştırıldı: `ready` manifestlerde split oranları doğrulanıyor, `unspecified` sorgular reddediliyor ve corpus/parser/chunking/embedding provenance alanları zorunlu tutuluyor.
- Final doğrulama başlangıcında tam test paketi `117 passed, 3 skipped` verdi. Mevcut 100 sorguluk smoke benchmark pinned local modelin Hugging Face indirme/cache aşamasında ilerlemediği için çıktı üretmeden durduruldu; bu durum ölçüm ortamı hazır değil olarak kaydedildi, kalite başarısızlığı olarak yorumlanmadı.
- Pinned local model cache'inin eksik olduğu görüldü; benchmarkın uzun indirme beklemesini önlemek için `VDB_EMBEDDING_OFFLINE=true` cache-only modu eklendi. Varsayılan local indirme davranışı değişmedi; offline mod eksik modelde fail-fast sağlar.
- Offline loader parametresi yalnızca `VDB_EMBEDDING_OFFLINE=true` iken gönderilecek şekilde geriye dönük uyumluluk düzeltildi; mevcut SentenceTransformer test double'ları ve default loader çağrısı gereksiz yeni keyword almaz.
- Bounded concurrency probe eklendi: privacy-safe toplam istek, hata, throughput ve p50/p95/p99 latency özeti üretiyor. 1–64 worker ve 1–100 tekrar sınırlarıyla yalnızca geliştirme/ön kontrol aracı; uzun süreli yük ve kapasite kararı final ölçüm kapısına bırakıldı.
- `vdb concurrency-probe` bounded primitive'ini fixture, worker, tekrar ve output seçenekleriyle CLI üzerinden kullanılabilir yaptı; command gerçek Qdrant/provider ölçümü için hazır, ancak bu turda uzun süreli koşu çalıştırılmadı.
- Negative sorgular için `VDB_RETRIEVAL_MIN_SCORE` ile opt-in varsayılan abstention eşiği eklendi. Eşik kalibre edilmeden boş bırakılır; istek üzerindeki `min_score` yapılandırılmış varsayılanı geçersiz kılar. Böylece dense varsayılanı korunurken üretim kullanıcısı güvenli boş-sonuç politikasını açıkça etkinleştirebilir.
- Harici embedding için OpenAI-compatible adapter ve provider factory eklendi. Local varsayılan değişmedi; harici yol yalnızca açık provider seçimi ve `OPENAI_API_KEY` ile etkinleşiyor, anahtar/metin loglanmıyor, response boyut/sonlu sayı/norm doğrulanıyor, geçici 408/429/5xx ve ağ hataları en fazla 5 deneme ile ele alınıyor, diğer hatalar fail-closed dönüyor. Maliyet ölçümü final kapasite turuna bırakıldı.
- RAG entegrasyonu retrieval/generation sınırında tutuldu: vector DB yalnızca sıralı, provenance'lı ve güvenilmeyen kanıt üretir; context builder/generator ayrı katmandır. Citation coverage, context kalitesi ve abstention doğruluğu 300+ sorgu fixture'ı sonrasında ayrı ölçülecek.
- RAG context builder eklendi: retrieval sonuçlarını karakter bütçeli, XML ile escape edilmiş untrusted evidence bloklarına dönüştürüyor ve citation metadata'sını ayrı taşıyor. Generation veya kaynak talimatı yürütme yok; bütçeye sığmayan bütün bloklar atlanıyor.
- RAG cevap citation bütünlüğü kontrolü eklendi; yalnızca context'te bulunan `E` marker'larını geçerli sayıyor ve bunun factuality/faithfulness ölçümü olmadığı açıkça ayrıştırıldı.
- Güncel release kapısı tekrarlandı: `94 passed, 2 skipped`, Ruff ve `uv lock --check` başarılı; wheel/sdist üretildi ve paketlenmiş üç schema doğrulandı. Geçici build çıktıları temizlendi.
- Belge yaşam döngüsü dokümanındaki chunk ID tanımı gerçek uygulamayla hizalandı: document ID, index, chunking version ve metin hash'i birlikte kullanılıyor. Kod davranışı değiştirilmedi.
- Docker server smoke testi tamamlandı: Docker Desktop `29.7.2` üzerinde Qdrant `v1.19.0` named volume'larla çalıştırıldı; payload index/lifecycle ve snapshot restore round-trip `2 passed` oldu. Server adapter'ına uzun süren snapshot işlemleri için opsiyonel timeout eklendi; restore testi Qdrant'ın gerektirdiği collection-absent ve `file:///qdrant/snapshots/...` akışını kullanıyor. Eski Windows bind-mounted test verileri silinmeden `.stale-smoke-test` yedeklerine taşındı.
- Benchmark örnek şeması V1 strict loader ile hizalandı: `text`, `relevant_chunk_ids` ve `query_type` kanonik alanlar; `relevance_grade`, `language` ve document-level etiketler ileri değerlendirme kapsamına bırakıldı. `tests/test_benchmark.py` `8 passed`.
- Kullanıcının sağladığı PromtGen README'si izole local Qdrant path'inde gerçek test corpus'u olarak ingest edildi. 30 etiketli sorgu ile eşiksiz benchmark `Recall@2=1.0000`, `error_rate=0` verdi; `--min-score 0.8` ile negative başarı `1.0000` olurken Recall@2 `0.5000`'a düştü. Bu sonuç retrieval smoke kanıtıdır, kişisel corpus kabul eşiği değildir; skor eşiği varsayılan yapılmadı.
# İleri sürüm geçiş kararı — V2.0 kapısı

- Tarih: 2026-09-13
- Karar: V2.0 adayları (multimodal, Graph-RAG, çoklu kullanıcı, sharding ve HA)
  ihtiyaç ve kapasite kanıtı oluşmadan varsayılan kapsam olmayacak.
- Gerekçe: V1.7 benchmark'ı küçük bir corpus üzerinde tamamlandı; V2 adaylarını
  seçmek için henüz temsilî 300 sorguluk corpus ve kapasite sınırı ölçümü yok.
- Sonraki kapı: V1.7 dense baseline'ını en az 300 etiketli sorgu ve üç tekrar ile
  çalıştır; veri boyutu, concurrency, RAM/disk, tazelik ve restore ölçümlerini
  kaydet; ardından yalnızca kanıtlanan ilk darboğaz için deney kartı aç.
- Rollback: V1 dense varsayılanı ve mevcut opt-in modlar korunur; V2 adayı
  feature flag kapatılarak devre dışı bırakılır.

## 2026-09-13 — V1.7 kapasite ölçüm kartı

- V2 adayını seçmeden önce kalite, tail latency, kaynak, tazelik, concurrency ve
  restore ölçümleri aynı corpus sözleşmesiyle tekrarlanacak.
- Üç tekrar ve en az 300 etiketli sorgu zorunlu tutuldu; mevcut 100 sorguluk
  PromtGen sonucu V2 kapasite kanıtı sayılmayacak.
- Araçta bulunmayan RSS/disk/tazelik alanları tahmin edilmeyecek; eksik alanlar
  açıkça `null` raporlanıp karar günlüğünde işaretlenecek.
- Gerçek PromtGen corpus'unda üç tekrarlı dense baseline çalıştırıldı ve ham
  kayıt `.test-tmp/promtgen-readme-v17-repeat3.json` olarak üretildi. Üç koşulda
  Recall `1.0000`, MRR `0.9157`, nDCG `0.9378`, error rate `0.0000` sabit kaldı;
  p95 değerleri sırasıyla `33.644`, `27.603` ve `27.482 ms`, p99 değerleri
  `69.597`, `41.207` ve `37.951 ms` oldu. İlk koşudaki tail artışı cold/warm
  etkisinin ayrı raporlanması gerektiğini gösterdi; bu sonuç V2 açılış kanıtı
  sayılmadı çünkü corpus 100 sorgu ve kaynak ölçümü eksik.
- Docker Qdrant `v1.19.0` çalışma durumu da gözlendi: container sağlıklı,
  `personal_documents_v1` koleksiyonu green ve server storage volume'u
  `1.27GB`, snapshot volume'u `6.708MB`, container RSS'i yaklaşık `111.4MiB`.
  Bu ölçümde server koleksiyonunda yalnızca 2 point bulunduğu için değerler
  kapasite benchmark'ı değil, runtime smoke gözlemidir; V2 ölçek kararı için
  kullanılmayacak.
- Docker Qdrant server entegrasyon kapısı tekrarlandı: `RUN_QDRANT_INTEGRATION=1`
  ile lifecycle, payload filtreleme ve snapshot restore testleri `3 passed`
  verdi. Bu, V1 server sözleşmesini doğrular; büyük corpus kapasite kanıtı
  yerine geçmez.
- İzole Docker server collection'ında PromtGen README iki chunk olarak ingest
  edilip dense benchmark üç kez çalıştırıldı; Recall `1.0000`, MRR `0.9157`,
  nDCG `0.9378`, error rate `0.0000` sabit kaldı. p50 değerleri `38.138`,
  `30.785`, `36.678 ms`; p95 `48.874`, `54.459`, `49.712 ms`; p99 `50.465`,
  `108.566`, `56.628 ms` oldu. Container RSS gözlemi yaklaşık `124MiB` idi.
  Collection test sonunda silindi; iki chunk'lık bu koşul kapasite veya V2
  geçiş kanıtı sayılmadı.
- API uyum denetiminde kök OpenAPI sözleşmesinin filtre, rerank ve ileri
  `retrieval_stage` değerlerini eksik belgelediği görüldü; YAML ve API rehberleri
  V1.7 uygulama davranışıyla eşitlendi. İstemciye açık retrieval mode hâlâ yok,
  seçim sunucu yapılandırmasındadır.
- OpenAPI contract testi filtre alanlarını, `rerank` seçeneğini ve retrieval stage
  enum'unu doğrulayacak şekilde güçlendirildi; uygulama ve kanonik YAML yeniden
  ayrışırsa test kapısı bunu yakalayacak.
- V1.7 release paketleme kapısı tekrarlandı: source distribution ve wheel
  üretildi, `compileall` başarılı, `uv lock --check`, Ruff ve `git diff --check`
  başarılı. Dağıtılabilir artefakt üretimi V2.0 geçişini açmıyor; yalnızca mevcut
  sürümün paketlenebilirliğini doğruluyor.
- İleri arama mimarisi dokümanı V1.2 sonrası gerçek davranışla eşitlendi:
  dense varsayılan, hybrid/rerank/late/quantized yollar ölçüm amaçlı opt-in.
- README ileri seviye doküman indeksine V2.0 geçiş kapısı ve kapasite deney
  kartı eklendi; tekrarlı benchmark CLI örneği de başlangıç akışında gösterildi.
- Tekrarlı benchmark CLI çıktısı tüm koşuları `repeat=N` etiketiyle gösterecek
  şekilde düzeltildi; tek koşuluk mevcut çıktı biçimi korunuyor.
- Resmî Qdrant dokümantasyonu 13 Eylül 2026'da yeniden kontrol edildi: v1.19
  memory tiers ve Turbo4/multivector seçenekleri mevcut görünüyor. Uygulamanın
  v1.19.0 image'ı bu yeni seçenekleri varsayılan kullanmıyor; Turbo4 yalnızca
  ayrı kapasite deneyi adayı olarak kaydedildi.
- README ve `docs/` altındaki yerel Markdown bağlantıları otomatik tarandı:
  239 bağlantı kontrol edildi, kırık bağlantı bulunmadı.
- Benchmark sonucu artık process CPU süresini `cpu_seconds` alanında ölçüyor;
  RSS ve disk alanları hâlâ host/Qdrant dış ölçümü gerektirdiği için otomatik
  tahmin edilmiyor.
- `vdb benchmark` terminal özeti `cpu_seconds` alanını da gösteriyor; wall-clock
  ve CPU sürelerinin karıştırılması engellendi.
- PromtGen 100 sorguluk local dense baseline tekrarında `cpu_seconds=19.343750`,
  wall-clock `elapsed_seconds=2.4889`, p95 `27.251 ms` ve p99 `35.412 ms`
  ölçüldü; CPU süresinin wall-clock'tan yüksek olması çok iş parçacıklı model
  çalışmasının beklenen sinyalidir. Bu küçük corpus sonucu V2 kapasite kanıtı
  değildir.
- RSS ölçümü Windows `GetProcessMemoryInfo` ile tamamlandı. PromtGen 100 sorgu
  local baseline'ında `elapsed_seconds=2.2823`, `cpu_seconds=18.015625` ve
  gözlenen process RSS `1834.309 MB` oldu; model yükleme belleği dahil olduğu
  için bu değer Qdrant'ın toplam RAM kullanımı veya genel sistem peak'i değildir.
- Kapasite deney kartındaki JSON örneği gerçek benchmark çıktısıyla hizalandı:
  `cpu_seconds` ve `rss_mb` üst düzey alanlar olarak gösteriliyor; disk alanı
  uygulama dışı ölçüm olarak ayrı tutuluyor.
- Kapsam denetiminde veri türleri matrisi gerçek runtime ile hizalandı: mevcut
  parser yalnızca Markdown/TXT, PDF/DOCX/HTML/JSON/CSV parser'ları sonraki
  geliştirme alanı. Kurulum rehberindeki `source_type` filtresi de mevcut API
  allowlist davranışıyla düzeltildi.
- Kapasite kartındaki sonuç formatı “deney zarfı” olarak netleştirildi; model,
  corpus checksum, Qdrant sürümü ve restore alanlarının mevcut `vdb benchmark`
  tarafından otomatik üretilmediği açıkça yazıldı.
- RSS/benchmark değişiklikleri sonrasında Docker Qdrant server entegrasyon testi
  yeniden çalıştırıldı: lifecycle, filtre ve snapshot/restore dahil `3 passed`.
- Roadmap V1.7 durumu process CPU/RSS ölçümünü ve V2 için kalan dış host/server
  ölçümlerini açıkça kapsayacak şekilde güncellendi.
- Benchmark yazım testi `cpu_seconds` ve `rss_mb` alanlarının JSON çıktısında
  korunmasını zorunlu kıldı.
- Uyarı denetimi yapıldı: Starlette/httpx deprecation uyarıları üçüncü taraf
  dependency bakım adayı, local Qdrant `search_params` mesajı beklenen local
  brute-force davranışı olarak sınıflandırıldı; uygulama hatası bulunmadı.
- Genel benchmark/reindex rehberi de `cpu_seconds` ve `rss_mb` alanlarını,
  warm-up ve RSS kapsam notlarıyla birlikte belgeledi.
- 300+ sorgu fixture manifesti için canonical JSON Schema eklendi. `fixture-validate`, kabul kapısındaki sayısal ve provenance kontrollerinden önce manifest biçimini ve `ready`/`contract-only` durum sözleşmesini doğruluyor; bilinmeyen manifest alanları reddediliyor.
- Parser dikey dilimi için kalıcı regresyon testleri eklendi: HTML görünür içerik filtresi, JSON/CSV deterministik kayıtlar, DOCX paragraf/tablo konumları, bilinmeyen format reddi ve `ingest-dir` bozuk dosya izolasyonu artık hızlı testlerle korunuyor. Bu testler uzun süreli corpus/kapasite ölçümünün yerine geçmiyor.
- Corpus inventory, ingest ile aynı kaynak kökü ve 10 MB dosya sınırına bağlandı. Büyük/okunamayan destekli dosyalar artık tüm envanteri kesmek yerine içerik hash'i üretmeden `failed` kaydı oluşturuyor.
- RAG provenance sözleşmesi retrieval sonucuyla hizalandı: retrieval aşaması, parser sürümü, document status ve security flags artık `RetrievalResult`/`ContextCitation` içinde korunuyor. Bunlar yalnızca denetim metadata'sıdır; kaynak metni talimat olarak çalıştırılmaz.
- RAG değerlendirme sınırı genişletildi: `evaluate_rag_citation_coverage`, marker precision ile beklenen chunk citation coverage'ını ayrı ölçüyor. Bu metrikler factuality/faithfulness olarak yorumlanmayacak; cevap kalitesi final insan etiketli ölçümünde ayrıca değerlendirilecek.
- Fixture kabul kapısı split oranlarını da doğrulamaya başladı. Manifestteki `split_tolerance` ile development/validation/test dağılımı önerilen orandan anlamlı biçimde saparsa paket reddediliyor; yalnızca split alanlarının mevcut olması yeterli sayılmıyor.
- Harici embedding adapter'ının endpoint, timeout ve retry ayarları `Settings` üzerinden yapılandırılabilir yapıldı. Bu yalnızca provider `openai` seçildiğinde kullanılır; local varsayılan, secret politikası ve bounded retry sınırı korunur.
- 300+ fixture için ayrı query label sözleşmesi eklendi. Annotator, tarih, karar notu, relevance chunk'ları ve corpus/parser/chunking provenance schema ile doğrulanıyor; `fixture-validate --labels` fixture ile label kimlik ve relevance eşleşmesini zorunlu kılıyor.
- Concurrency probe için başarı/hata izolasyonu ve 1–64 worker sınırlarını doğrulayan hızlı testler eklendi. Bu primitive'in gerçek throughput ve tail-latency kararı vermediği, final uzun süreli ölçüm gerektirdiği korunuyor.
- Harici embedding endpoint'i provider oluşturulurken HTTP(S) URL olarak doğrulanıyor. Hatalı endpoint'lerde ağ çağrısı yapılmadan fail-fast davranış korunuyor.
- Güncel regresyon doğrulamasında tam test paketi `141 passed, 3 skipped` verdi; Ruff ve `uv lock --check` de başarılı. Bu sonuç uzun süreli benchmark veya gerçek corpus kalite kabulü değildir.
- Benchmark ve concurrency komutlarına opsiyonel acceptance preflight eklendi. Fixture manifesti verildiğinde fixture, corpus manifesti ve label provenance'ı provider/Qdrant başlatılmadan doğrulanıyor; `contract-only` paketle yanlışlıkla final ölçüm başlatılamıyor.
- Final fixture kabulünde derived etiketlerin doğrudan geçmesi engellendi. Otomatik türetilen relevance kayıtları geliştirme aşamasında tutulabilir; `ready` manifest için manual/reviewed annotation gerekir.
- RAG context güvenlik regresyonu eklendi: kaynak içindeki XML/HTML karakterleri ve sahte talimat ifadeleri escape edilerek veri olarak kalıyor; davranış `test_rag.py` ile korunuyor.
- Current status doğrulamasında tam test paketi `147 passed, 3 skipped` verdi; RAG/API provenance, context escape ve yapılandırılabilir kaynak boyutu regresyonları da bu pakete dahil.
- Corpus manifesti artık metin taşımadan gerçek `chunk_ids` listesini de içeriyor. Fixture kabulü, etiketlerin corpus checksum/parser sürümünün yanında mevcut chunk kimliklerine de bağlandığını doğruluyor; bilinmeyen relevance kimlikleri erken reddediliyor.
- Corpus manifesti fixture preflight sırasında `total_chunks == len(unique(chunk_ids))` bütünlük kontrolünden geçiriliyor; elle bozulmuş veya eksik manifestler ölçüm başlatılmadan reddediliyor.
- HTML parser çıktısı artık blok/başlık bölümlerini ve `heading_path` bilgisini koruyor; bu kanonik çıktı değişikliği `html-v2` parser sürümüyle provenance ve yeniden indeksleme gereksinimine bağlandı.
- RAG context builder aynı `chunk_id` için tekrarlanan retrieval hit'lerini ilk sıralı kayıtla tekilleştiriyor; citation ve karakter bütçesi yinelenen kanıtla bozulmuyor.
- DOCX parser başlık stillerini `heading_path` metadata’sına taşıyor ve kanonik çıktı sürümünü `docx-v2` olarak yükseltiyor; yapı değişikliğinde provenance kontrollü yeniden indeksleme gerekiyor.
- OpenAI-compatible embedding adapter base URL içindeki kullanıcı bilgisi, query ve fragment alanlarını reddediyor; gizli değerlerin endpoint yapılandırmasından taşınması fail-closed tutuldu.
- Chunking, farklı `heading_path` değerlerini aynı chunk içinde birleştirmiyor; başlık sınırı provenance kaybını önlemek için `paragraph-pack-v2` ile sürümlendi ve yeniden indeksleme gerektiriyor.
- Bu turdaki tam regresyon doğrulaması `148 passed, 3 skipped` verdi; yeni HTML yapı/citation tekilleştirme davranışları da pakete dahil.
- DOCX başlık metadata’sı ve yeni parser regresyonları sonrasında tam paket `149 passed, 3 skipped` verdi; uzun süreli kalite ölçümü hâlâ final kapısında.
- Chunking sürüm yükseltmesi backup sözleşmesiyle doğrulandı; başlık sınırı regresyonu sonrasında tam paket `150 passed, 3 skipped` verdi.
- Sürüm taramasında kalan `paragraph-pack-v1` referanslarının yalnızca tarihsel regresyon testleri olduğu doğrulandı; aktif fixture contract-only olduğu için gerçek etiketleme `paragraph-pack-v2` ile başlayacak.
- Backup manifesti tek parser varsayımına bağlı kalmıyor: geriye dönük `parser_version` alanına ek olarak opsiyonel `parser_versions` listesi taşıyor; karma corpus backup’larında tekil alan `mixed` olarak işaretleniyor.
- Backup parser provenance testi eklendi; karma parser sürümlerinin sıralı ve tekilleştirilmiş biçimde saklandığı doğrulandı. Güncel tam paket `151 passed, 3 skipped`.
- CLI backup akışına `--corpus-manifest` eklendi; doğrulanmış parser sürümleri snapshot öncesinde backup manifestine aktarılabiliyor.
- Corpus manifest okuma/round-trip testi eklendi; backup provenance girdisi yalnızca schema ve chunk bütünlüğü doğrulandıktan sonra kullanılabiliyor. Tam paket `154 passed, 3 skipped`.
- Backup manifestine opsiyonel `corpus_checksum` eklendi; `--corpus-manifest` kullanıldığında snapshot’ın kaynak corpus kimliği de kaydediliyor, eski backup’lar geriye dönük okunuyor.
- Restore akışına `--corpus-manifest` checksum kontrolü eklendi; farklı corpus’a ait snapshot yanlışlıkla geri yüklenemiyor.
- Backup corpus manifesti artık provider/Qdrant başlatılmadan okunup doğrulanıyor; bozuk provenance ile snapshot işlemi başlamıyor.
- Backup hazırlık sırası için tam regresyon paketi `155 passed, 3 skipped` verdi; mevcut 3 skip yalnızca runtime/Docker kapsamındadır.
- Bozuk backup corpus manifestinin servisler açılmadan reddedildiği CLI testi eklendi; tam paket `156 passed, 3 skipped`.
- Farklı corpus restore reddi için CLI regresyonu eklendi; uyumsuz snapshot’ın restore adapter’ına ulaşmadığı doğrulandı.
- Restore corpus checksum regresyonu sonrası tam paket `155 passed, 3 skipped` verdi.
- Corpus inventory, kişisel export/backup kopyalarını ham içerik döndürmeden
  `duplicate_of` ile görünür kılıyor. İlk görülen relative path kanonik tutuluyor;
  otomatik merge veya silme yok, çünkü aynı byte içeriği farklı provenance amacı
  taşıyabilir. Bu sinyal yalnızca corpus hazırlama incelemesinde kullanılır.
- Duplicate kanonik aday seçimi daha deterministik hale getirildi: önce path
  derinliği, eşitlikte alfabetik relative path kullanılıyor. Böylece backup gibi
  alt klasör kopyaları, kökteki asıl kaynağın önüne geçmiyor. Tam paket `157
  passed, 3 skipped` verdi.
- `vdb corpus-inventory` artık kaynak metni göstermeden parsed/failed/duplicate
  kaynak ve toplam chunk özetini stdout'ta raporluyor. Bu, geniş corpus hazırlığında
  ilk kalite kontrolünü kolaylaştırıyor; tam paket `158 passed, 3 skipped` verdi.
- Aynı inventory özeti desteklenen suffix dağılımını ve parser failure type
  dağılımını da metinsiz raporlayacak şekilde genişletildi; format kalite
  raporunun ilk operasyonel özeti artık komuttan alınabiliyor.
- Corpus manifestine `chunking_version` eklendi ve fixture preflight bu sürümü birebir eşleştirmeye başladı; yeniden üretilen manifestte mevcut `paragraph-pack-v2` kaydı doğrulandı.
- Yanlış fixture chunking sürümü için negatif preflight testi eklendi; uyumsuz etiket paketi provider/Qdrant başlamadan reddediliyor.
- Parser ve chunking ile üretilen `heading_path` retrieval sonucu, RAG citation ve OpenAPI sözleşmesine taşındı; eski payload’lar boş liste varsayılanıyla geriye dönük çalışıyor.
- RAG evidence XML bloklarına escape edilmiş `heading_path` attribute’u eklendi; generator bölüm bağlamını görürken kaynak metni talimat olarak çalıştırılmıyor.
- `fixture-validate` ve benchmark preflight hataları traceback yerine kısa stderr mesajı ve çıkış kodu `2` ile raporlanıyor; bozuk fixture kullanıcıya daha temiz gösteriliyor.
- HTML parser `<title>` bilgisini belge başlığına taşıyor; bu kanonik metadata değişikliği sürümü `html-v3` yaptı ve HTML kaynaklarının yeniden indekslenmesini gerektiriyor.
- PDF parser mevcut metadata title’ını belge başlığına taşıyor; fallback dosya adı korunurken parser sürümü `pdf-v2` olarak yükseltildi.
- DOCX core-properties title’ı belge başlığına taşınıyor; fallback dosya adı korunurken parser sürümü `docx-v3` olarak yükseltildi.
- CLI sözleşme hata testi eklendi; tam regresyon paketi `152 passed, 3 skipped` ile temiz tamamlandı.
- Bozuk fixture JSON yükleme hataları da traceback yerine kısa stderr/kod `2` ile raporlanıyor; fixture kabul girişleri tek tip hata davranışına getirildi.
- Fixture yükleme ve doğrulama hata yolları için CLI regresyonları eklendi; güncel tam paket `153 passed, 3 skipped`.
- Model cache eksikliği nedeniyle doctor’ın ağ indirmesine takılmasını önlemek için opt-in `vdb doctor --offline` seçeneği eklendi; cache yoksa fail-fast davranır.
- `doctor --offline` CLI sözdizimi ve cache-kontrol yolu doğrulandı; tam regresyon paketi `154 passed, 3 skipped` olarak kaldı.
- Kaynak dosyası üst sınırı `VDB_SOURCE_MAX_BYTES` ayarıyla yapılandırılabilir hale getirildi. Aynı değer CLI ingest, server ingest ve privacy-safe corpus inventory akışlarında uygulanıyor; varsayılan 10 MB korunuyor.
- `IngestService`, `source_root` verilmeden kullanılan library akışlarında da `max_source_bytes` sınırını uygulayacak şekilde sertleştirildi; güvenlik limiti artık composition biçimine bağlı değil.
- Negative retrieval davranışı için audit olayına privacy-safe abstention nedeni
  eklendi: aday yoksa `no_candidates`, adaylar eşik altında kaldıysa
  `below_min_score`; eşik nedeniyle elenen aday sayısı da kaydediliyor. API
  sonuç sözleşmesi değişmedi, RAG katmanı bu telemetriden cevap vermeme kararını
  destekleyebilir. Kalibrasyon final 300+ fixture ölçümüne bırakıldı.
- Abstention ayrımını koruyan retrieval regresyon testi eklendi; tam paket `159
  passed, 3 skipped` ile tamamlandı. Uzun süreli negative-query kalibrasyonu
  yine final ölçüm aşamasına bırakıldı.
- 300+ fixture hazırlığını kolaylaştırmak için `vdb fixture-coverage` komutu
  eklendi. Final `fixture-validate` kapısını gevşetmeden, query türü, split,
  document size ve filter selectivity kovalarını metinsiz sayar; mevcut 30
  sorguluk fixture'ın neden henüz hazır olmadığını görünür kılar. Tam paket
  `160 passed, 3 skipped` verdi.
- Coverage raporuna `coverage_complete` ve split eksikliği/oran sapması alanları
  eklendi. Bu değer yalnızca sayısal hazırlık durumunu ifade eder; label,
  provenance ve gerçek relevance doğrulaması hâlâ final validator'a aittir.
- `fixture-coverage` komutuna opsiyonel `--labels` eklendi. Etiket sayısını,
  etiketsiz sorgu ve fixture dışı label sayılarını metin içeriğini döndürmeden
  raporlar; final relevance/provenance kontrolü `fixture-validate`'da kalır.
  Tam paket `161 passed, 3 skipped` verdi.
- RAG generation handoff için `assess_rag_generation` eklendi. Boş/eşik-altı
  retrieval veya review/security işaretli kanıt fail-closed reddediliyor; yalnızca
  aktif ve güvenlik işareti olmayan kanıt generation'a uygun kabul ediliyor. Bu
  karar factuality/faithfulness değildir; cevap ölçümü final fixture'a bırakıldı.
- RAG generation handoff için `assess_rag_generation` eklendi. Boş/eşik-altı
  retrieval veya review/security işaretli kanıt fail-closed reddediliyor; yalnızca
  aktif ve güvenlik işareti olmayan kanıt generation'a uygun kabul ediliyor. Bu
  karar factuality/faithfulness değildir; cevap ölçümü final fixture'a bırakıldı.
  Policy için üç regresyon testi eklendi; tam paket `164 passed, 3 skipped` verdi.
- Kişisel corpus kapsamı `.eml` ile genişletildi. Stdlib email parser yalnızca
  düz metin gövdesini ve konu başlığını alıyor; HTML gövdesi ve ekler işlenmiyor.
  `email-v1` provenance sürümü, allowlist ve document/chunk schema enum'larına
  eklendi; parser regresyon testiyle korundu.
- `.eml` parser'ının plain-text gövde ve attachment izolasyonu tam regresyon
  paketiyle doğrulandı; sonuç `165 passed, 3 skipped`. HTML email gövdesi,
  ek dosya ve OCR benzeri içerikler bu sade parser'ın kapsamı dışında tutuldu.
- EML enum değişikliği sonrası repository ve paket chunk schema kopyaları byte
  düzeyinde eşitlendi; parser/schema paketi `11 passed`, tam paket `165 passed,
  3 skipped` ile yeniden doğrulandı.
- EML parser, dosya adı taşıyan `inline` parçaları da attachment kabul edip
  dışarıda bırakacak şekilde sıkılaştırıldı; böylece ek metninin embedding'e
  sızma yolu azaltıldı. Tam parser ve regression paketi yeniden `165 passed,
  3 skipped` verdi.
- Bounded concurrency probe sonuçlarına yalnızca exception sınıfı adlarını sayan
  `error_types` alanı eklendi. Hata mesajları özellikle dışarıda bırakıldı; bu
  alan kapasite ölçümünde hata dağılımını ayırmaya yarar, sorgu/belge metni
  taşımaz. Geriye dönük tek koşu zarfının mevcut alanları korunuyor; rollback
  için alan yok sayılabilir veya önceki sürüme dönülebilir.
- Gerçek fixture etiketlemesini başlatmak için `fixture-label-template` eklendi.
  Mevcut query/chunk kimliklerini taşır, kaynak metnini yazmaz ve `source=derived`
  ile `REVIEW_REQUIRED` işaretini zorunlu kılar. Corpus manifestindeki tek
  parser sürümü güvenle doldurulur; çoklu parser durumunda placeholder korunur.
  Template final label değildir. Yeni iki test ile tam paket `167 passed, 3
  skipped` sonucuna ulaştı.
- Coverage raporu, ID'leri tam olsa bile `source=derived` taslaklarını
  `labels_status=review-required` olarak işaretliyor. Böylece provenance
  placeholder'ı içeren veya insan incelemesi tamamlanmamış taslaklar final
  etiketlerle karıştırılmıyor. Bu güvenlik sınırını koruyan test eklendi; tam
  paket `168 passed, 3 skipped` verdi.
- `fixture-label-template` CLI'ında corpus manifesti zorunlu yapıldı. Böylece
  normal kullanıcı akışı eksik provenance placeholder'lı bir taslak üretmiyor;
  doğrudan Python helper'ındaki düşük seviye placeholder davranışı ise geriye
  dönük ve kontrollü kullanım için korunuyor.
- External embedding adapter'ında tek büyük ağ isteği riskini azaltmak için
  `VDB_EMBEDDING_BATCH_SIZE` eklendi. Sadece opt-in external provider'da 1–256
  arası batch bölme yapılır; input sırası ve manifest/dimension kontrolleri
  korunur, her batch kendi retry döngüsünde kısmi başarı kabul etmez. Local
  varsayılan etkilenmez; rollback için ayar eski varsayılan davranışa alınabilir.
  Batch sırası, factory aktarımı ve sınırları test edildi; tam paket `170
  passed, 3 skipped` verdi.
- External embedding için bounded hash-keyed in-memory cache eklendi. Ham input
  bellekte tutulmuyor; `embed_query` ve `embed_documents` aynı cache'li akışı
  kullanıyor, kapasite `VDB_EMBEDDING_CACHE_SIZE` ile sınırlı ve cache provider
  instance'ına bağlı. İlk testte query yolunun cache'i bypass ettiği yakalandı ve
  düzeltildi; tam paket `171 passed, 3 skipped` ile yeniden doğrulandı.
- Cache'in concurrency altında güvenli erişimini doğrulayan test eklendi;
  external embedding testleri `9 passed`, tam paket `172 passed, 3 skipped`
  verdi. Kilit yalnızca cache state için tutuluyor, ağ çağrısı sırasında değil.
- Aynı `embed_documents` çağrısındaki duplicate input'lar request seviyesinde
  SHA-256 anahtarıyla tekilleştirildi ve sonuçlar özgün sıraya geri açılıyor.
  Böylece cache kapalı olsa bile tekrarlı chunk'ler provider'a gereksiz gönderilmiyor;
  external embedding testleri `10 passed`, tam paket `173 passed, 3 skipped` verdi.
- Cache davranışını final ölçümde gözlemleyebilmek için ham input taşımayan
  `cache_stats` eklendi: hit/miss, entry ve kapasite. Bu yalnızca gözlem yüzeyi;
  gerçek maliyet/kalite/kapasite sonucu değildir. Cache ve stats regresyonlarıyla
  external embedding testleri `10 passed`, tam paket `173 passed, 3 skipped`
  olarak korundu.
- JSONL parser desteği eklendi. Her boş olmayan satır ayrı JSON kaydı olarak
  işleniyor, `location.line` korunuyor ve bozuk satır dosya bazında fail-closed
  oluyor. Suffix/allowlist/schema/`CanonicalDocument` Literal uyumu birlikte
  doğrulandı; parser-corpus testleri `27 passed`, tam paket `175 passed, 3
  skipped` verdi.
- JSONL desteğinin `inventory → corpus-manifest` zinciri için uçtan uca hızlı
  regresyon testi eklendi. Parser sürümü, chunk ID'leri ve manifest toplamı
  korunuyor; test paketi güncel olarak `176 passed, 3 skipped`.
- JSONL ile aynı sözleşmeyi kullanan `.ndjson` suffix alias'ı eklendi; yeni bir
  source type veya provenance modeli açılmadı. Parser/corpus regresyonları `15
  passed`, tam paket `177 passed, 3 skipped` verdi.
- `concurrency-probe` terminal çıktısı Python dict yerine deterministik JSON
  olarak standardize edildi; ölçüm sarmalayıcılarının stdout'u güvenilir biçimde
  tüketebilmesi için CLI regresyon testi eklendi. Tam paket `178 passed, 3
  skipped` verdi.
- Güncel privacy-safe coverage snapshot'ı yenilendi: corpus 2 Markdown kaynak,
  9 chunk; küçük fixture 30, smoke fixture 100 sorgu ve ikisi de `contract-only`
  kabul paketinin altında. Eksik split/boyut/selectivity metadata'sı ve smoke
  fixture'daki `typo=0` açıkça kaydedildi; bu verilere sentetik doldurma yapılmadı.
- Corpus manifesti format dağılımı, parse hata türleri ve advisory duplicate
  sayısını metin içermeden kalıcı özet olarak saklamaya başladı. Alanlar opsiyonel
  bırakıldı; eski manifestler geriye dönük uyumlu. Tam paket `179 passed, 3
  skipped` verdi.
- Parser kalite görünürlüğü genişletildi: inventory kaynak metni saklamadan
  çıkarılan karakter ve boş olmayan section sayılarını, manifest ise corpus
  toplamını saklıyor. Bunlar extraction hacmi karşılaştırmasıdır; semantik
  doğruluk veya relevance sonucu olarak yorumlanmayacak.
- Yeni opsiyonel manifest alanları olmadan üretilmiş eski corpus manifestlerinin
  okunmaya devam ettiği regresyon testi eklendi; başarısız kaynaklarda hata türü
  özeti de doğrulandı. Tam paket `180 passed, 3 skipped` verdi.
- DOCX parser için ZIP üye yolu traversal, şifreleme ve toplam açılmış boyut
  kontrolleri eklendi; güvensiz paketler XML parse edilmeden fail-closed reddediliyor.
  Güvenlik regresyonu ve tam paket `181 passed, 3 skipped` ile doğrulandı.
- `fixture-coverage --corpus-manifest` ile fixture relevance ID bağlama denetimi
  eklendi. Güncel smoke fixture'da 89 pozitif sorgunun chunk ID'si güncel corpus'ta
  bulunmadığı için durum açıkça `mismatch`; bu fixture kalite ölçümüne uygun kabul
  edilmiyor. Tam paket `182 passed, 3 skipped` verdi.
- Coverage bağlama denetimi fixture checksum'ını da karşılaştırıyor; checksum
  verilmemiş eski/contract-only fixture'lar `not-declared`, uyuşmayanlar
  `mismatch`, eşleşenler `valid` olarak ayrılıyor. Tam paket `183 passed, 3
  skipped` verdi.
- `fixture-label-template` artık corpus manifestini schema ve chunk ID bağlamıyla
  doğruluyor; stale relevance ID içeren fixture için taslak üretimi fail-closed.
  Böylece yanlış corpus provenance'ı taşıyan etiket dosyası oluşturulamıyor.
- Template schema/chunk binding regresyonları eklendi; güncel tam paket `184
  passed, 3 skipped` verdi. Docker testleri final runtime doğrulamasına bırakıldı.
- Label dosyasındaki relevance chunk ID'leri de corpus manifestine karşı
  denetleniyor; stale label'lar coverage aşamasında `mismatch` ve sayısal
  unknown-count alanlarıyla görünür oluyor.
- Bu label-binding kontrolü için regresyon testi eklendi; tam paket `187 passed,
  3 skipped` verdi. Uzun süreli benchmark ve gerçek relevance etiketleri hâlâ
  final ölçüm kapısında bekliyor.
- `corpus-inventory` CLI özetine normalize edilmiş extraction hacmi
  (`extracted_chars`) eklendi; gerçek kaynak metni yazdırılmadan parser kalite
  karşılaştırması yapılabilecek. Tam paket `184 passed, 3 skipped` olarak korundu.
- PDF parser şifreli dosyaları ve 50 milyon karakter üstü extraction çıktısını
  parse etmeden reddedecek şekilde güçlendirildi; güvenlik regresyon testi eklendi.
  Tam paket `185 passed, 3 skipped` verdi.
- `parse_source` ve `parse_source_file` doğrudan kullanıldığında da varsayılan
  10 MB boyut sınırını uyguluyor; `max_bytes` yalnızca açıkça artırılabiliyor.
  Böylece ingest dışı parser kullanımı güvenlik politikasını bypass etmiyor.
  Tam paket `186 passed, 3 skipped` verdi.
- RAG context çıktısına aday/eklenen/atlanmış evidence sayıları ve kullanılan
  karakter bütçesi eklendi. Bu ölçümler citation/provenance davranışını değiştirmeden
  context kalite değerlendirmesi için privacy-safe sinyal sağlıyor; tam paket `187
  passed, 3 skipped` verdi.
- Concurrency probe toplam istek bütçesi 100.000 ile sınırlandı; fixture ve tekrar
  sayısı birlikte büyüdüğünde bellek/iş kuyruğu taşması fail-fast oluyor. Tam paket
  `188 passed, 3 skipped` verdi.
- Toplam concurrency bütçesi artık iş listesi oluşturulmadan önce kontrol ediliyor;
  limit aşımında erken liste tahsisi yapılmıyor. Bu sıralama regresyon testiyle
  güvenceye alındı; tam paket `189 passed, 3 skipped` verdi.
- Abstention eşiği için validation skorlarını kullanan `evaluate_abstention_threshold`
  ve `choose_abstention_threshold` eklendi. Positive acceptance/negative success
  tabanları sağlanmıyorsa eşik seçimi fail-closed; runtime varsayılanı otomatik
  değiştirmiyor.
- Threshold değerlendirme ve seçici regresyon testleriyle doğrulandı; tam paket
  `192 passed, 3 skipped` verdi. Final eşik kalibrasyonu gerçek validation/test
  fixture'ı hazırlandıktan sonra yapılacak.
- Fixture coverage duplicate sorgu ve final validation duplicate/cross-split
  leakage kapılarıyla güçlendirildi; 300 sorgu sayısının tekrarlarla şişirilmesi
  engellendi. Tam paket `194 passed, 3 skipped` verdi.
- RAG generation handoff kararına `context_truncated` alanı eklendi; context
  bütçesi nedeniyle kanıt atlandığında üst katman bunu açıkça görebiliyor.
  Mevcut generation izin davranışı korunarak tam paket `195 passed, 3 skipped`
  verdi.
- Export edilen `parse_text_file` de boyut sınırı politikasına bağlandı; doğrudan
  public parser girişlerinin tamamı aynı fail-closed kaynak boyutu kuralını
  uyguluyor. Tam paket `196 passed, 3 skipped` verdi.
- DOCX arşiv güvenliği Windows backslash/drive-letter, absolute path ve NUL
  isimlerini de kapsayacak şekilde sertleştirildi; yeni regresyonla tam paket
  `197 passed, 3 skipped` verdi.
- DOCX ZIP paketi duplicate member ve symbolic-link üyeleri de parse edilmeden
  reddediyor; böylece aynı isimli içerik ve link yönlendirmesi kaynak provenance'ını
  belirsizleştiremiyor. Tam paket `198 passed, 3 skipped` verdi.
- Local Qdrant snapshot restore güvenliği genişletildi: duplicate, symlink,
  hardlink, Windows/POSIX unsafe path ve device/FIFO gibi özel üyeler extraction
  öncesi reddediliyor. Tam paket `201 passed, 3 skipped` verdi.
- Local Qdrant snapshot restore, duplicate/symlink/hardlink ve Windows/POSIX
  unsafe tar üyelerini extraction öncesi reddedecek şekilde sertleştirildi.
  Restore güvenlik testleriyle tam paket `200 passed, 3 skipped` verdi.
- Local restore arşivi geçici alanda doğrulanıp çıkarılmadan mevcut Qdrant client
  kapatılmıyor. Geçersiz snapshot sonrası store healthcheck'i çalışmaya devam
  ediyor; tam paket `201 passed, 3 skipped` olarak korundu.
- Local restore tar üyeleri için canonical path kontrolü sıkılaştırıldı: boş, `.`,
  `..` içeren göreli yollar ve normalize edilmiş çakışmalar extraction öncesi
  reddediliyor. Göreli traversal regresyon testiyle tam paket `202 passed,
  3 skipped` doğrulandı.
- Başarılı local snapshot restore sonrasında Qdrant client yeniden açılıyor;
  aynı store nesnesiyle arama yapılabildiği regresyon testiyle doğrulandı.
- Yapılandırılabilir kaynak boyutu sınırı parser katmanında da tutarlı uygulandı;
  ingest, reindex ve corpus inventory artık sabit 10 MB varsayılanına geri
  dönmüyor.
- Kaynak boyutu sınırının ingest'ten parser'a aktarıldığı regresyon testi eklendi;
  tam paket `203 passed, 3 skipped` verdi.
- Local snapshot üretimi sonrasında da Qdrant client yeniden açılıyor; arşiv
  oluşturma başarısız olsa bile yaşam döngüsü `finally` ile toparlanıyor ve
  snapshot sonrası aynı store nesnesiyle arama yapılabiliyor.
- RAG context duplicate chunk'ları elerken citation marker'larını daima ardışık
  üretiyor; böylece duplicate sıralaması generator tarafında boş marker aralığı
  oluşturmuyor.
- Ardışık citation ID davranışı duplicate sonrası iki kanıtlı regresyon testiyle
  doğrulandı; tam paket `204 passed, 3 skipped` verdi.
- RAG context duplicate aday sayısını `duplicate_candidate_count` olarak açıkça
  raporluyor; duplicate rate artık candidate ve evidence sayılarından dolaylı
  çıkarım gerektirmeden ölçülebilir.
- Local restore için staging ve rollback planı karara bağlandı: mevcut storage
  yeni arşiv tamamen staging'e kopyalanmadan silinmeyecek; son taşıma başarısız
  olursa eski storage otomatik geri getirilecek.
- Staging kopyalama hatası simüle edilerek eski storage ve açık client'ın
  korunduğu doğrulandı; tam paket `205 passed, 3 skipped` verdi.
- Search API yanıtına list uyumlu retrieval diagnostics eklendi: `abstention_reason`,
  `candidate_count` ve `threshold_rejected_count`; boş sonuç nedeni HTTP istemcisine
  de açıkça taşınıyor.
- API sözleşmesi hem `no_candidates` hem `below_min_score` senaryolarında doğrulandı;
  tam paket `206 passed, 3 skipped` verdi.
- API/OpenAPI planında abstention alanlarının anlamı ve `results=[]` yorumlama
  kuralı açıklandı; istemci tarafı yanlış “veri yok” çıkarımı engellendi.
- `SearchResponse.abstention_reason` serbest metin olmaktan çıkarılıp üç değerli
  Literal sözleşmesine bağlandı; kod ve OpenAPI enum'u artık aynı kapıyı kullanıyor.
- Unknown abstention değerinin response model tarafından reddedildiği API regresyonu
  eklendi; tam paket `207 passed, 3 skipped` verdi.
- Harici embedding cache kapatıldığında (`cache_size=0`) miss sayacının doğru
  artması sağlandı; cache istatistiği artık devre dışı modu da açıklıyor.
- HTTP ingest composition'ında `source_root` zorunlu hale getirildi; rootsuz
  servisle makine geneli dosya erişimi açılması fail-closed engelleniyor.
- Kaynak kökü dışına yönlenen symlink için kalıcı güvenlik regresyonu eklendi;
  erişim izni olmayan platformlarda test kontrollü skip davranışı kullanıyor.
- Symlink sınırı bu ortamda çalıştırıldı; tam paket `210 passed, 3 skipped` verdi.
- Harici embedding provider eksik vektör durumunda sessizce kısa liste döndürmek
  yerine fail-closed hata veriyor; provider count invariant'ı güçlendirildi.
- Güncel `fixture-coverage` denetimi 100 sorguluk PromtGen paketinin `contract-only`
  olduğunu, corpus checksum'ı taşımadığını ve 89 relevance chunk ID'sinin mevcut
  corpus'ta bulunmadığını doğruladı; bu paket final kalite ölçümü sayılmadı.
- Corpus inventory parser çağrısı doğrulanmış canonical path'i kullanacak şekilde
  düzeltildi; source-root ve provenance kontrolü aynı path üzerinde birleşti.
- `data/sources/temsilî-kisisel-kayitlar.md` sentetik ve privacy-safe temsilî corpus
  olarak eklendi; inventory artık 3 kaynak, 20 chunk ve 8.696 extracted karakter
  raporluyor. Yeni corpus checksum'ı `sha256:2b5c951c9441a89a68d07ac809a0d524f158a4060ebe84263485cfd3f12600a3`.
- Sentetik corpus'a bağlı 30 sorguluk `representative-personal-queries.json`
  oluşturuldu; tüm relevance chunk ID'leri güncel corpus'a bağlı, split ve
  selectivity alanları dolu. Coverage sonucunda checksum/chunk binding geçerli,
  bilinmeyen chunk ve duplicate query sayısı sıfır.
- Aynı fixture için provenance'lı `representative-personal-query-labels-template.json`
  üretildi. Şablon `source=derived` ve `REVIEW_REQUIRED` olarak bırakıldı; manuel
  onay olmadan final kabul etiketi sayılmayacak.
- Label template coverage tekrarlandı: checksum/chunk binding `valid`, label sayısı
  30, `review-required` label sayısı 30, bilinmeyen label chunk sayısı 0. Fixture
  hâlâ 300 sorgu ve medium/large corpus kovaları olmadığı için final değildir.
- Privacy-safe format corpus genişletildi: HTML, JSON, CSV, EML, ICS ve ORG örnekleri
  eklendi. Inventory sonucu dokuz kaynak, 29 chunk, 10.000 extracted karakter,
  dokuz parse edilmiş kaynak ve sıfır hata; yeni corpus checksum'ı
  `sha256:bf9d884f8be07773f6c7919c9c01e49516ea224157fac52fd3377690e451d90e`.
- Inventory'nin allowlist dışında kalan kişisel dosyaları sessizce gizlememesi için
  privacy-safe `unsupported_files` ve `unsupported_suffixes` özeti eklendi. Bu
  sinyaller corpus checksum'ını değiştirmiyor; desteklenmeyen içerik yine ingest
  edilmiyor.
- Güncel corpus inventory tekrarlandı: `unsupported_files=0`, `unsupported_suffixes=none`;
  tam regresyon paketi `227 passed, 3 skipped, 3 warnings` verdi.
- Medium-size corpus davranışı için sentetik uzun proje günlüğü eklendi. Güncel
  inventory 10 kaynak, 43 chunk ve 18.865 extracted karakter raporluyor; tüm
  kaynaklar parse edildi, unsupported suffix yok. Yeni corpus checksum'ı
  `sha256:dd834e113b20dc77566f7577ad1cb0cd9a4b2e9352b57fb2f79923b77116168f`.
- Uzun günlükteki gerçek chunk kimliklerine bağlı altı aday sorgu fixture'a eklendi.
  Coverage artık 36 sorgu/36 derived label, 6 medium-size sorgu, geçerli corpus
  binding ve sıfır bilinmeyen chunk raporluyor; yalnızca large kovası eksik kaldı.
- Repository corpus smoke testi, Markdown dışındaki altı formatı ve medium-size
  kaynağı privacy-safe biçimde koruyacak şekilde eklendi; 1 MB large bucket
  sınıflandırması da ayrı test edildi. Tam paket `229 passed, 3 skipped, 3 warnings`.
- Parser auditinde mevcut PDF/DOCX/HTML sınırları yeniden doğrulandı: HTML görünmeyen
  script/style/nav bloklarını dışlıyor, PDF şifreli girdiyi reddediyor, DOCX arşivinde
  traversal/symlink/encryption ve uncompressed-size kontrolleri korunuyor. Bu turda
  davranış değişikliği gerekmedi; parser kapsamı ve kalite ölçümü final benchmark'a açık.
- Corpus manifestine privacy-safe `size_bucket_counts` eklendi. Böylece medium veya
  large kaynağın corpus'ta gerçekten bulunup bulunmadığı, fixture sorgu kovalarının
  eksikliğinden ayrı izlenebiliyor; legacy manifestler geriye dönük okunmaya devam ediyor.
- `fixture-coverage` artık fixture `size_bucket_counts` ile corpus manifestindeki
  `corpus_size_bucket_counts` değerlerini ayrı raporluyor; legacy corpus manifesti
  için ikinci alan `null` kalıyor. Bu ayrım için regression testi eklendi.
- Güncel coverage snapshot'ı binding `valid`, corpus boyutları `small=9/medium=1/large=0`,
  fixture boyutları `small=30/medium=6/large=0`, 36 sorgu ve 36 review-required label
  gösteriyor. Tam regresyon paketi `231 passed, 3 skipped, 3 warnings`.
- Chunk→size provenance binding eklendi. Coverage, positive sorgunun `size_bucket`
  etiketini referans chunk'ın gerçek kaynak kovasıyla karşılaştırıyor; uyumsuzluk
  corpus binding'i `mismatch` yapıyor. Güncel fixture'da uyumsuzluk 0.
- Bu kapı için mismatch regression testi eklendi; güncel tam paket
  `233 passed, 3 skipped, 3 warnings` verdi.
- Boş görünür extraction için parser fail-closed davranışı korunarak inventory'ye
  `extraction_status=empty`, manifest'e `empty_extraction_count` eklendi. Script-only
  HTML regression testi ile doğrulandı; mevcut corpus sayacı 0. Güncel paket
  `232 passed, 3 skipped, 3 warnings`.
- 300+ sorguluk paketin tek dosyaya bağımlı kalmaması için `fixture-merge` eklendi.
  Sorgu shard'larında duplicate `query_id` ve normalize sorgu, label shard'larında
  duplicate `query_id` veya corpus/parser/chunking provenance uyumsuzluğu fail-closed
  reddediliyor; merge sonucu yine coverage ve final validation kapılarından geçirilmek
  zorunda.
- Label provenance merge kapısı için regresyon eklendi; hedefli suite `42 passed`,
  tam test paketi `226 passed, 3 skipped, 3 warnings` verdi.
- `fixture-validate` mevcut 100 sorguluk paketi corpus checksum uyuşmazlığında
  benchmark başlatmadan reddetti; final kabul kapısının fail-closed çalıştığı
  doğrulandı.
- Cache kapalı moddaki miss sayacı regresyon testiyle doğrulandı; tam paket
  `208 passed, 3 skipped` verdi.
- HTTP ingest için rootsuz `IngestService` ile app oluşturma reddedildi; bu
  güvenlik regresyonuyla tam paket `209 passed, 3 skipped` verdi.
- Fixture validator, `corpus_checksum: null` durumunu gerçek checksum mismatch'inden
  ayıracak şekilde netleştirildi; mevcut contract-only fixture artık doğru nedenle
  “checksum is required” kapısında duruyor. Benchmark acceptance kapısı gevşetilmedi.
- Tam doğrulama tekrarlandı: `211 passed, 3 skipped, 3 warnings`; fixture coverage
  raporu da mevcut paketin 100 sorgu, 89 bilinmeyen relevance chunk ID'si,
  eksik split/kova dağılımı ve labelsız contract-only durumda kaldığını doğruladı.
- Kişisel corpus kapsamı `.org`, `.rst`, `.log` ve `.tex` uzantılarıyla genişletildi;
  bunlar yeni semantik varsayım eklemeden mevcut UTF-8 plain-text parser sözleşmesini
  kullanıyor. Dört uzantı için parser dispatch regresyonu eklendi.
- Yeni plain-text alias kapsamı tam pakette doğrulandı: `215 passed, 3 skipped,
  3 warnings`; uyarılar bağımlılık deprecation'ları ve local exact-search bilgisidir.
- Corpus inventory davranışı yeniden denetlendi: allowlist dışı dosyalar bilinçli
  olarak inventory ve corpus checksum dışında tutuluyor; böylece indekslenmeyen
  görsel/cache dosyaları benchmark provenance'ını gereksiz yere bozmaz. Envanter
  dokümanındaki gerçekte üretilmeyen `source_uri`/mtime alanları düzeltilip gerçek
  privacy-safe alanlar yazıldı.
- Kişisel corpus kapsamına `.ics` takvim dışa aktarımları eklendi; özel takvim
  semantiği icat edilmeden UTF-8 plain-text parser kullanılıyor ve provenance
  korunuyor. Dispatch regresyonu ile doğrulandı.
- `.ics` kapsamı sonrası tam doğrulama `216 passed, 3 skipped, 3 warnings` verdi;
  mevcut uyarı profili değişmedi.
- API sözleşmesindeki desteklenen suffix listesi gerçek parser allowlist'iyle
  eşitlendi; JSONL/NDJSON daha önce dokümanda eksik kalmıştı.
- Plain-text parser, Windows dışa aktarımlarındaki UTF-8/UTF-16 BOM'larını kontrollü
  biçimde çözümleyecek şekilde güçlendirildi; BOM'suz encoding tahmini ve sessiz
  replacement yapılmıyor. Unicode BOM regresyonları eklendi.
- BOM desteği sonrası tam test paketi `218 passed, 3 skipped, 3 warnings` verdi;
  ingest, retrieval ve RAG katmanlarında regresyon gözlenmedi.
- Yapılandırılmış UTF-8 export'larda BOM normalizasyonu JSON, JSONL/NDJSON, CSV ve
  HTML parser'larına da yayıldı; CSV başlık sızıntısı ve JSON parse hatası önlendi.
- Yapılandırılmış BOM regresyonları sonrası tam paket `219 passed, 3 skipped,
  3 warnings` verdi; mevcut uyarı profili değişmedi.
- Plain-text BOM regresyonu UTF-32 dışa aktarımını da kapsayacak şekilde genişletildi;
  parser'ın mevcut UTF-8/16/32 BOM davranışı artık test sözleşmesinde açık.
- UTF-32 regresyonu sonrası tam test paketi `220 passed, 3 skipped, 3 warnings` verdi.
- Dokümanda vaat edilen varsayılan kaynak exclude politikası kodlandı: inventory ve
  `ingest-dir`, VCS/virtualenv/cache/build/secrets/credentials dizinlerini aynı
  allowlist ile dışlıyor; tekil dosya ingest akışı değişmedi. Hassas ve build
  dizini regresyonları eklendi.
- Exclude politikası sonrası güvenlik/corpus/ingest hedefli testleri `28 passed`,
  tam paketi `222 passed, 3 skipped, 3 warnings` verdi.
- Güncel release öncesi paketleme de doğrulandı: `uv build`, `compileall`,
  `uv pip check` ve `git diff --check` başarılı; wheel ve source distribution
  üretildi. Docker entegrasyon testleri bu kontrolde çalıştırılmadı.
- Inventory CLI özetine dışlanan dosya sayısı eklendi; corpus/CLI/ingest hedefli
  testler `39 passed`, tam regresyon paketi `222 passed, 3 skipped, 3 warnings`
  olarak kaldı.
- Recursive exclude davranışı README'de de görünür hale getirildi; kullanıcı,
  `ingest-dir` ile tekil `ingest` arasındaki kapsam farkını artık başlangıç
  dokümanında görebiliyor.
- `corpus-inventory` özetine privacy-safe `excluded_files` sayacı eklendi; dışlanan
  dosya yolları ve içerikleri raporlanmıyor, corpus checksum davranışı değişmiyor.
- Karma formatlı corpus'un beş parser sürümü fixture provenance'ında tekil
  `plain-text-v1` değeriyle temsil edilmemelidir. Sözleşme `mixed` özetini ve
  sıralı `parser_versions` listesini fixture manifesti ile label kayıtlarına
  taşıyacak şekilde güncellendi; legacy tek parser kayıtları korunuyor.
- Mixed parser provenance regression testi eklendi; fixture label template artık
  `parser_version: mixed` ve ayrıntılı sürüm listesini üretip doğruluyor. Tam
  regresyon paketi `234 passed, 3 skipped, 3 warnings` ile tamamlandı; üç skip
  Docker/runtime kapsamındadır.
- Fixture coverage raporuna label provenance kontrolü eklendi. Fixture manifesti
  ayrıntılı `parser_versions` yayımlıyorsa label kayıtları da aynı parser setini
  taşımalı; uyuşmazlık privacy-safe biçimde `label_provenance_status=mismatch`
  ve corpus binding `mismatch` olarak raporlanıyor. Eski tek parser manifestleri
  korunuyor. Yeni regression sonrası tam paket `235 passed, 3 skipped, 3 warnings`.
- Uzun süreli benchmark hazırlığı için `write_benchmark_results` artık ham
  tekrarları koruyan `runs` alanına ek olarak ortalama/minimum/maksimum metrik
  özeti yazıyor. `--repeat 1` geriye dönük uyumlu kaldı; mixed query-count
  özeti reddeden regression ile tam paket `236 passed, 3 skipped, 3 warnings`
  olarak doğrulandı.
- Concurrency kapasite ölçümünün farklı worker seviyelerini tekrarlanabilir
  biçimde saklaması için bounded `run_concurrency_matrix` helper'ı eklendi.
  Seviyeler tekil ve sıralı; her probe kendi istek bütçesiyle sınırlandırılıyor.
  İki hızlı regression sonrası tam paket `238 passed, 3 skipped, 3 warnings`;
  uzun süreli yük testi hâlâ final kapısında.
- Matrix helper CLI'a opt-in `--concurrency-levels` ile bağlandı. Matrix çıktısı
  `runs` zarfında makine-okunur worker sonuçları taşıyor; eski tek probe JSON'u
  değişmedi. CLI regression ile tam paket `239 passed, 3 skipped, 3 warnings`
  olarak doğrulandı.
- Matrix çıktı yazımı ortak `write_concurrency_matrix_results` helper'ına
  taşındı; duplicate seviye ve boş sonuç kapıları ile sorgu metni sızıntısı
  regression'ı eklendi. Tam paket `240 passed, 3 skipped, 3 warnings` ile
  temiz; Docker/runtime skip'leri korunuyor.
- İleri seviye final audit belgesi eklendi. Sekiz alanın altyapı kanıtı ile
  gerçek 300+ label, uzun süreli ölçüm ve ertelenmiş runtime kanıtlarını aynı
  tabloda ayırıyor; mevcut 36 sorguluk aday veri final sonuç olarak kabul
  edilmiyor.
- Fixture coverage kanıtının kaybolmaması için `--output` seçeneği eklendi.
  Yazılan JSON yalnızca privacy-safe sayısal/provenance alanlarını içeriyor;
  sorgu metni sızıntısı regression'ı ile doğrulandı. Tam paket `241 passed,
  3 skipped, 3 warnings`.
- Güncel temsilî fixture coverage artifact'i üretildi:
  `query_count=36`, `minimum_query_count=300`, `corpus_binding_status=valid`,
  `label_provenance_status=valid`, `labels_status=review-required` ve
  `coverage_complete=false`. Artifact sorgu/belge metni içermez.
- Coverage raporuna `corpus_parser_versions` ve `fixture_parser_versions`
  alanları eklendi; beş parser sürümünün eşleştiği yeni artifact ile doğrulandı.
  Tam paket `242 passed, 3 skipped, 3 warnings`.
- Coverage raporuna `corpus_checksum` ve `fixture_corpus_checksum` alanları
  eklendi. Temsilî artifact yeniden üretildi ve iki hash'in eşleştiği doğrulandı;
  tam paket `243 passed, 3 skipped, 3 warnings`.
- Fixture dosyası için `fixture_checksum=sha256:082d140b...` fingerprint'i
  coverage artifact'ine eklendi ve artifact yeniden üretildi. Bu değer yalnızca
  veri paketini bağlar, sorgu metni içermez; tam paket `244 passed, 3 skipped,
  3 warnings`.
- Coverage artifact'i için ayrı schema ve ortak writer eklendi. Eksik rapor
  gövdesi regression ile reddediliyor; mevcut temsilî artifact schema doğrulamalı
  writer üzerinden yeniden üretildi. Tam paket `245 passed, 3 skipped,
  3 warnings`.
- Coverage schema'nın repository/paket kopyaları strict alan sözleşmesiyle
  hizalandı; labelsız hazırlık coverage'ında sıfır label sayaçlarının da
  yazılması sağlandı. JSON parse, Ruff ve tam test paketi temiz kaldı.
- Gelişim goal kabul matrisi güncel coverage kanıtıyla hizalandı: aday fixture
  36 sorgu, corpus binding/provenance geçerli, fakat `contract-only`,
  `review-required` ve 300+ kapısı açık. Eski PromtGen 100 sorguluk kayıtlar
  yalnızca tarihsel smoke kanıtı olarak tutuluyor.
- Temsilî kişisel corpus'a JSONL örneği eklendi. Inventory 11 kaynak, 44 chunk,
  19.268 extracted karakter ve altı parser sürümü raporluyor; fixture manifesti,
  label şablonu ve coverage artifact'i yeni corpus checksum'ına bağlandı.
- Örnek veri paketi ve roadmap, mevcut parser gerçekliğiyle hizalandı: JSONL/NDJSON
  ve EML örnekleri açıkça listeleniyor; final fixture hedefi smoke 30 yerine 300+
  sorgu ve query type başına en az 30 olarak tanımlı.
- Label shard merge sırasında `parser_versions` provenance alanı sıralanarak
  karşılaştırılıyor. Böylece aynı parser kümesini farklı JSON sırasıyla taşıyan
  shard'lar uyumsuz sayılmıyor; corpus checksum/parser/chunking farkları yine
  fail-closed reddediliyor. Hedefli merge testleri ve Ruff temiz.
- Fixture coverage, corpus manifestinde bulunan `chunk_size_buckets` mapping'inin
  tüm `chunk_ids` değerlerini kapsamasını artık zorunlu tutuyor. Kısmi mapping,
  ilgili fixture chunk'ı eşlenmiş olsa bile mismatch olarak raporlanıyor; yeni
  regresyon testi bu provenance açığını koruyor.
- XML desteği standart kütüphane leaf-node parser'ı olarak eklendi. DTD/entity
  declaration içeren girdiler fail-closed reddediliyor; domain ve iki payload
  schema kopyası güncellendi. Temsilî inventory 12 kaynak, 45 chunk ve 7 parser
  sürümü raporluyor; fixture provenance yeni checksum'a bağlandı.
- XML entegrasyonu sonrası sabit checksum/parser testleri güncellendi; tam regresyon
  `249 passed, 3 skipped, 3 warnings`, Ruff ve diff kontrolü temiz.
- XML desteği eklendikten sonra mimari, V1 kapsamı, başlangıç onay formu ve örnek
  veri belgelerindeki eski format listeleri güncellendi; tarihsel karar kayıtları
  değiştirilmeden güncel dokümanlar tek kapsamla hizalandı.
- Package corpus-manifest şemasında bulunan extraction/size/chunk bucket alanlarının
  repository kopyasında eksik olduğu tespit edildi ve eşitlendi. Validation testi
  artık yedi şema kopyasının tamamını semantik olarak karşılaştırıyor; tam paket
  `249 passed, 3 skipped, 3 warnings` ile temiz kaldı.
- XML parser davranışı ortak parser/normalizasyon rehberine işlendi: yalnızca yerel
  leaf-node metni ve node path korunuyor, DTD/entity declaration'ları reddediliyor;
  attribute, yorum ve karmaşık şema semantiği kapsam dışı.
- Fixture coverage, corpus ve fixture `parser_versions` kümelerinin eşitliğini
  `parser_versions_binding_status` ile raporlayacak şekilde güçlendirildi.
  Farklı kümeler `corpus_binding_status=mismatch` üretiyor; strict schema kopyaları,
  gerçek coverage artifact'i ve tam regresyon (`251 passed`) doğrulandı.
- Parser sürüm kümesi binding kabul koşulu final audit ve roadmap'e işlendi;
  `valid` olmadan corpus provenance'ı final ölçüm için geçerli sayılmayacak.
- Corpus manifesti ile coverage çalışırken checksum/parser declaration eksikliği
  bulunan bir fixture'ın `coverage_complete=true` üretmesi engellendi. Yeni
  fail-closed regression ile tam paket `252 passed, 3 skipped, 3 warnings` verdi.
- Fixture sözleşmesindeki coverage açıklaması yeni koşullu kapıyla hizalandı:
  corpus manifesti verildiğinde checksum ve parser binding geçerli olmadan
  `coverage_complete` true olamaz; reviewed relevance hâlâ ayrı final kapısıdır.
- XML source type için document JSON Schema kabul testi eklendi; tam regresyon
  `250 passed, 3 skipped, 3 warnings`, Ruff ve diff kontrolü temiz.
- RAG generation handoff fail-open açığı kapatıldı: context bütçesi nedeniyle
  kanıt atlandıysa `assess_rag_generation` artık `context_truncated` nedeniyle
  generation'a izin vermiyor. Eksik kanıtla cevap üretimi için regresyon testi
  güncellendi; cevap kalite sınırı dokümanı bu kararla hizalandı.
- Citation marker parser'ı token sınırlarıyla sıkılaştırıldı; `E1abc` veya
  `_E1_` gibi identifier parçaları artık gerçek citation olarak ölçülmüyor.
- RAG marker regresyonu sonrasında hedefli paket `11 passed`, tam regresyon
  `253 passed, 3 skipped, 3 warnings`; Ruff ve diff kontrolü temiz.
- Harici embedding adapter'ında uzak HTTP endpoint'lere hassas metin gönderme
  riski kapatıldı: HTTPS zorunlu, yalnızca loopback HTTP test endpoint'leri
  kabul ediliyor. Endpoint regresyonu genişletildi; local-first ve opt-in
  provider sınırı korunuyor.
- Güncel fixture kapısı komutla yeniden doğrulandı: coverage çıktısı
  `corpus_binding_status=valid`, `parser_versions_binding_status=valid` ve
  `coverage_complete=false`; 36 sorgu, `review-required` etiketler, eksik
  large bucket ve sorgu türü başına 30 sınırı nedeniyle `fixture-validate`
  beklenen exit code `2` ile durdu. Bu durum veri hazırlığı açığıdır, kod
  regresyonu değildir.
- `CitationCheck.valid` alanı eklendi; citation içermeyen veya bilinmeyen marker
  kullanan cevaplar tek bir açık durum alanıyla başarısız işaretlenebiliyor.
  Bu alan factuality/faithfulness değerlendirmesi değildir.
- Citation geçerlilik değişikliğinin ardından güncel tam regresyon
  `254 passed, 3 skipped, 3 warnings`; RAG hedefli paket `12 passed` olarak
  doğrulandı.
- Embedding provider dokümanında gerçekte bulunmayan `describe` ve
  `health_check` yöntemleri kaldırıldı; sözleşme `manifest`, `embed_documents`
  ve `embed_query` Protocol alanlarıyla hizalandı. Yeni runtime health katmanı
  eklenmedi.
- Dokümantasyon yerel bağlantıları değişken-gölgeleme hatası düzeltilmiş tarama
  ile yeniden kontrol edildi; `docs` altındaki tüm yerel Markdown bağlantıları
  geçerli, `broken_count=0`.
- `.env.example` ve yapılandırma referansında harici embedding'in HTTPS/
  loopback kuralı ile batch/cache sınırları görünür hale getirildi; kullanım
  sözleşmesi ve runtime doğrulaması artık aynı ayarları listeliyor.
- Concurrency matrix'in toplam istek bütçesi tekil probe limitleriyle çarpılarak
  beklenmedik kaynak tüketimi oluşturamıyor; 100.000 toplam sınırı iş
  genişletilmeden önce kontrol ediliyor ve regression testi eklendi.
- Matrix bütçesi değişikliği concurrency hedefli `8 passed`, tam regresyon
  `255 passed, 3 skipped, 3 warnings` ile doğrulandı.
- Concurrency matrix `k` ve `repetitions` sınırlarını da iş başlatmadan doğruluyor;
  yeni regression testleriyle concurrency paketi `10 passed`, tam regresyon
  `257 passed, 3 skipped, 3 warnings` verdi.
- Model registry ve kodlama öncesi karar belgesindeki tarihsel “yalnızca local”
  ve “kod başlamadı” ifadeleri güncellendi; local varsayılan, opt-in harici
  provider ve final benchmark kapıları artık mevcut durumla tutarlı.
- Final audit'e V2 adayları için ölçülebilir ihtiyaç sinyalleri eklendi; 300+
  sorgu ve kapasite ölçümü tamamlanmadan multimodal, Graph-RAG veya çoklu
  kullanıcı kapsamı açılmayacak.
- Roadmap, concurrency matrix toplam bütçesi ile HTTPS/loopback embedding
  endpoint kuralını mevcut implementasyon ve kabul belgeleriyle hizalayacak
  şekilde güncellendi.
- Coverage artifact'i yeniden üretildiğinde temsilî label template'inin de
  `--labels` ile verilmesi gerektiği doğrulandı. Labelsız üretim bilinçli olarak
  `label_provenance_status=not-provided` raporlar; güncel artifact template ile
  `label_provenance_status=valid`, `labels_status=review-required`, 36 sorgu,
  `coverage_complete=false` ve corpus/parser binding durumları `valid` olarak
  tutuluyor.
- Kişisel yapılandırma/export dosyalarının daha geniş kapsanması için YAML/YML
  parser'ı eklendi. `yaml.safe_load`, deterministic JSON serialization,
  `yaml-v1` provenance ve Python-object tag'leri için fail-closed davranış
  güvenlik allowlist'i, domain/JSON schema ve parser kalite dokümanlarıyla
  birlikte güncellendi; hedef corpus'a yeni sentetik YAML kaynağı da eklendi.
  YAML regresyonları dahil hedefli parser/schema paketi `30 passed` verdi.
  Değişiklik geriye dönük uyumludur: mevcut suffix ve parser sürümleri
  değişmedi; sorun görülürse YAML suffix dispatch'i ve ilgili schema enum değeri
  geri alınarak eski corpus checksum'ları korunabilir.
- Sentetik YAML export örneği `temsilî-formatlar` corpus'una eklendi. Inventory
  yeniden üretimi 13 kaynak, 46 chunk, 19.815 karakter ve `yaml-v1` provenance
  verdi; fixture manifesti/template'i yeni corpus checksum'ına bağlandı ve
  coverage tekrar `corpus_binding_status=valid`,
  `parser_versions_binding_status=valid`, `labels_status=review-required`,
  36 sorgu ve `coverage_complete=false` raporladı.
- Benchmark result artefact'lerine privacy-safe `fixture_checksum`,
  `corpus_checksum` ve `embedding_manifest_id` alanları eklendi; CLI benchmark
  akışı bunları otomatik dolduruyor. Böylece final kalite ölçümü aynı görünen
  ama farklı corpus/model ile karıştırılamıyor. Eski doğrudan Python çağrıları
  için alanlar opsiyonel bırakıldı; benchmark metric sözleşmesi geriye dönük
  korunuyor. Benchmark/CLI hedefli paketi `79 passed` verdi.
- YAML corpus ve benchmark provenance değişiklikleri sonrasında tam regresyon
  `260 passed, 3 skipped, 3 warnings` verdi; üç skip Docker/runtime koşullarına
  ait ve bilerek final runtime turuna bırakıldı.
- Concurrency result artefact'lerine de fixture/corpus/model provenance alanları
  eklendi; gerçek provider kimliği korunurken eski/mock provider'lar için alan
  opsiyonel kaldı. CLI hedefli paket `80 passed`; tam regresyon güncel olarak
  `261 passed, 3 skipped, 3 warnings` verdi.
- Benchmark ve concurrency sonuç writer'ları için canonical JSON Schema'lar
  eklendi. Writer, provenance alanları dahil tüm artefact'i diske yazmadan önce
  fail-closed doğruluyor; schema parity paket kopyalarıyla korunuyor. Mevcut
  metric alanları ve doğrudan Python API'si geriye dönük tutuldu.
- Writer şemalarının fail-closed davranışı için bozuk metric/negative değerlerin
  dosyaya yazılmadığı regresyonlar eklendi. Hedefli paket `87 passed`; tam
  regresyon güncel olarak `263 passed, 3 skipped, 3 warnings` verdi.
- Tekrarlı benchmark ve concurrency matrix aggregate'lerinde koşular arası
  fixture/corpus/embedding provenance tutarlılığı zorunlu hale getirildi;
  farklı contract'ları birleştiren sonuçlar reddediliyor. Yeni regresyonlarla
  hedefli paket `89 passed`, tam regresyon `265 passed, 3 skipped, 3 warnings`.
- Aktif temsilî fixture için `fixture-validate --labels` yeniden denetlendi;
  manifest `contract-only` olduğu için beklenen exit code 2 ile reddedildi.
  Bu, final veri/etiket hazırlığının henüz tamamlanmadığını doğrulayan kanıttır;
  kod veya parser regresyonu değildir.
- Kişisel arşiv kapsamını gereksiz ağır bağımlılık eklemeden genişletmek için
  temel RTF parser'ı eklendi. `rtf-v1` yalnızca metin, paragraf/satır sonu,
  sekme ve Unicode/cp1252 kaçışlarını çıkarır; gömülü nesne, makro ve stil
  fidelity'si bilinçli olarak kapsam dışıdır. Parser/güvenlik hedefli paket
  `31 passed`, Ruff temizdir; gerçek RTF extraction kalitesi final corpus
  incelemesinde değerlendirilecektir.
- RTF değişikliğinden sonra tam regresyon `267 passed, 3 skipped, 3 warnings`
  verdi; üç skip Docker/Qdrant dış runtime testleridir ve kullanıcı kararıyla
  final runtime turuna bırakılmıştır.
- RTF metadata/object gruplarını atlayan tarayıcı eklendi; hex dönüşümünün
  temizlenmiş metin yerine ham RTF üzerinde çalışmasına neden olan regresyon
  düzeltildi. Dengesiz grup yapısı artık fail-closed reddediliyor. Hedefli paket
  `29 passed`, tam regresyon `269 passed, 3 skipped, 3 warnings` verdi.
- Gerçek kişisel veri içermeyen sentetik RTF örneği corpus'a bağlandı. Inventory
  artık 14 kaynak, 47 chunk, 19.961 extracted karakter ve `rtf-v1` dahil dokuz
  parser sürümü raporluyor; corpus checksum'ı
  `sha256:80170ea3cd3b1adb2b4ecc71918a9460a87050a6cfbcf22fa639611e8dded919`.
  Fixture manifesti, label template'i ve coverage artifact'i yeni corpus
  provenance'ına yeniden üretildi; coverage binding valid, final durum yine
  `contract-only`/`review-required`.
- Abstention threshold evaluator'ı non-numeric ve boolean threshold/score
  değerlerini açık `ValueError` ile reddedecek şekilde sıkılaştırıldı; böylece
  dış provider kaynaklı tip hataları sessizce kabul edilmiyor. Benchmark hedefli
  paket `68 passed`, tam regresyon `270 passed, 3 skipped, 3 warnings` verdi.
- RAG generation handoff'u boş context, citation/evidence count uyuşmazlığı
  veya `used_chars` tutarsızlığında `invalid_context` ile fail-closed reddedecek
  şekilde güçlendirildi. Bu kontrol factuality sonucu üretmez; yalnızca bozuk
  context'in generation katmanına geçmesini engeller.
- RAG context invariant regresyonu immutable context sözleşmesine uygun test ile
  doğrulandı. RAG hedefli paket `13 passed`; tam regresyon `271 passed, 3 skipped,
  3 warnings` verdi.
- Harici embedding HTTP yanıtı 64 MB üst sınırıyla okunuyor; limit+1 byte
  sentinel'i aşımda fail-closed hata üretiyor ve JSON/vektör parse edilmiyor.
  Adapter hedefli paket `12 passed`, tam regresyon `272 passed, 3 skipped,
  3 warnings`; gerçek provider çağrısı yapılmadı.
- Harici embedding yanıtındaki indeks ve koordinat alanları JSON türüyle
  doğrulanıyor; boolean ve sayısal metin coercion'ı reddediliyor. Provider
  sözleşmesi güncellendi, hedefli paket `16 passed`, tam regresyon `276 passed,
  3 skipped, 3 warnings`; gerçek API çağrısı yapılmadı.
- Kullanıcının verdiği `data/sources/temsilî-kisisel-kayitlar.md` sentetik
  corpus girdisi olarak doğrulandı. DOCX incelemesinde run'lar arasındaki
  `w:tab`, `w:br` ve `w:cr` işaretlerinin metin birleştirilirken kaybolduğu
  görüldü; `docx-v4` ile paragraf/tablo hücresinde sekme-satır sonu korunuyor,
  iç tablo içeriği üst hücrede yinelenmiyor. Sonraki güvenlik incelemesinde DOCX
  içindeki `word/document.xml` ve `docProps/core.xml` için DTD/entity
  declaration'ları parse öncesi reddedildi. DOCX yeniden indeksleme ihtiyacı
  dokümante edildi. Ayrıca gerçek `pypdf` ile oluşturulmuş minimal PDF smoke
  testi eklendi; mevcut kaynak klasöründe PDF olmadığı için bu test gerçek
  kişisel corpus kalite kanıtı sayılmıyor. Parser hedefli regresyon paketi
  `38 passed`, Ruff ve diff kontrolleri temiz; kapsamlı regresyon ve uzun
  ölçümler final turuna bırakıldı.
- Aday retrieval sorguları iki kaynak belgede yoğunlaştığı için sentetik
  `temsilî-formatlar/` corpus'undan 20 sorgu eklenerek paket 56'ya çıkarıldı;
  hedef belge kapsamı 2'den 12'ye genişledi. `fixture-label-template` ve
  privacy-safe `fixture-coverage` başarıyla üretildi: corpus/parser/chunk ve
  label provenance binding valid, bilinmeyen chunk/duplicate/cross-split
  duplicate sıfır. Tür dağılımı `17/11/7/7/7/7`, split `32/13/11`; 56 label'ın
  tamamı derived/review-required, large bucket yok ve 300+ kabul kapısı açık.
  Uzun benchmark ve relevance doğrulaması yapılmadı.
- Medium günlüğün 14 chunk'ından yalnızca 5'inin mevcut fixture'da hedeflendiği
  görüldü; diğer dokuz chunk için içerikten türetilmiş 9 aday sorgu eklendi.
  Fixture 65 sorguya çıktı ve medium günlük kapsamı `14/14` oldu. Label template
  ve coverage tekrar üretildi: corpus/parser/chunk/label binding valid, unknown
  chunk, duplicate query ve cross-split duplicate sıfır; split oran sorunu yok.
  65 label'ın tamamı review-required, her sorgu türü 30'un altında, large bucket
  eksik; bu nedenle `coverage_complete=false` ve manifest `contract-only` kalıyor.
  Fixture checksum `sha256:2ad89b0de12832da3e9df2a7213e4db1fdea401866034ec9bcdedc2c07d4f05e`.
- 2026-09-21 devamında temsilî kişisel kayıt kaynağının giriş chunk'ı da aday
  sorguyla kapsandı; fixture 66 sorguya çıktı ve bu kaynak `11/11`, medium günlük
  `14/14` chunk kapsamasına ulaştı. Yeniden üretilen coverage'ta corpus/label/parser
  binding geçerli, unknown chunk, duplicate query ve cross-split duplicate sıfır;
  split oranları tolerans içinde. Tür dağılımı semantic=23, exact_identifier=14,
  typo=7, morphology=7, long_context=8, negative=7; split development=38,
  validation=14, test=14. Tüm 66 etiket `review-required`; 300+ sorgu ve large
  bucket kapıları açık, dolayısıyla `coverage_complete=false`.
  Fixture checksum: `sha256:27432801ce5813f20247b9e156481c38c2b21b1ee0d093ef9621c6d6d1952771`.

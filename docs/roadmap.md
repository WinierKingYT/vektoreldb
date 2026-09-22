# Geliştirme Roadmap'i

Bu roadmap, kişisel kullanım için yerel çalışabilen ve gerektiğinde harici embedding sağlayıcısına geçebilen vektörel veritabanı/RAG sisteminin kontrollü biçimde geliştirilmesi içindir. Amaç, kodu küçük ve değiştirilebilir tutmak; kalite, veri güvenliği ve ölçülebilirlik oluşmadan ileri özelliklere geçmemektir.

## 1. Yol haritası ilkeleri

- İlk sürüm kişisel ve tek kullanıcı odaklıdır.
- Qdrant ilk backend adayıdır; repository kodu backend ayrıntılarını tek bir adaptör arkasında tutar.
- Embedding sağlayıcısı bir sözleşme ile soyutlanır; yerel ve harici sağlayıcı aynı arayüzü uygular.
- Her arama optimizasyonundan önce exact baseline ve ölçülebilir test seti bulunur.
- Ham kaynak, normalize metin, chunk, embedding ve indeks metadata'sı birbirinden ayrılır.
- Güvenlik ve yedekleme sonradan eklenen özellikler değil, ilk çalışan sürümün parçasıdır.
- Dağıtık deployment, multimodal, Graph-RAG ve gelişmiş quantization ancak ölçüm bunları gerektirirse açılır.

## 2. Fazlar ve teslimatlar

### Faz 0 — Başlangıç sözleşmesi ve çalışma alanı

**Amaç:** Kodlamaya başlamadan teknik sınırları sabitlemek.

**Teslimatlar:**

- Python sürümü, paket yöneticisi ve çalışma komutları
- Yerel Qdrant çalışma şekli
- Yapılandırma/secrets politikası
- Kanonik belge ve chunk şemalarının doğrulama kuralları
- İlk dikey dilim Markdown ve düz metinle başlatıldı; sonraki ingest adımında
  PDF, DOCX, HTML, EML, JSON, JSONL/NDJSON, CSV ve XML desteği de eklendi. OCR,
  karmaşık ofis düzenleri ve multimodal kaynaklar ayrı kalite/araştırma alanıdır.
- Örnek veri seti ve en az 20–30 etiketli sorgudan oluşan ilk değerlendirme seti
- Karar günlüğünde provider, metric, dimension ve ID kararları

**Geçiş kapısı:** `docs/15-kodlama-oncesi-kabul-listesi.md` maddeleri karşılanır; belirsiz kararlar varsayım olarak değil karar günlüğünde kayıtlıdır.

### Faz 1 — Proje iskeleti ve sözleşme testleri

**Amaç:** Uygulama katmanlarını birbirine kilitlemeden temel repository yapısını kurmak.

**Teslimatlar:**

- `config`, `domain`, `parsers`, `chunking`, `embeddings`, `storage`, `retrieval`, `api` sınırları
- JSON Schema ve OpenAPI doğrulama testleri
- Provider, parser, vector store ve ID üretimi için protokol/interface tanımları
- Structured logging ve hata sınıfları
- Birim testleri ve yerel geliştirici çalıştırma komutu

**Geçiş kapısı:** Uygulama gerçek veri olmadan smoke test ile başlar; katmanlar doğrudan birbirinin özel API'sine bağımlı değildir.

### Faz 2 — Ingest: kaynak alma, parse ve normalize

**Amaç:** Kaynak dosyayı kayıpsız ve tekrar üretilebilir biçimde kanonik belgeye dönüştürmek.

**Teslimatlar:**

- Dosya kimliği, checksum, kaynak yolu, zaman ve sürüm metadata'sı
- Markdown/TXT/HTML/PDF parser'ları
- Unicode, whitespace, başlık ve link normalizasyonu
- Parser hata/uyarı raporu ve desteklenmeyen içerik politikası
- Aynı girdide deterministik çıktı testi

**Geçiş kapısı:** Örnek veri paketindeki her dosya parse edilir; kayıp veya belirsiz bölüm raporlanmadan sessizce atılmaz.

### Faz 3 — Chunking ve embedding hattı

**Amaç:** Aranabilir, izlenebilir ve provider değişimine dayanıklı vektör üretmek.

**Teslimatlar:**

- Yapısal/semantik chunking ve overlap politikası
- Chunk ID, document ID, section path ve karakter/token sınırları
- Yerel embedding provider
- Harici provider için aynı sözleşmeyi kullanan ikinci implementasyon
- Model registry: model adı, revision, dimension, metric, normalization ve oluşturma zamanı
- Embedding cache ve retry/rate-limit davranışı

**Geçiş kapısı:** Aynı model ve aynı girdide deterministik metadata üretilir; provider hatası veri kaybına yol açmaz; model değişimi re-index gerektirir.

### Faz 4 — Depolama ve ilk indeksleme

**Amaç:** Güvenli ve tekrar çalıştırılabilir ilk veri yükleme akışını tamamlamak.

**Teslimatlar:**

- Qdrant collection oluşturma ve named vector sözleşmesi
- Payload alanlarının indekslenmesi
- Upsert, idempotency, delete ve belge yeniden indeksleme
- Manifest ile collection/model uyumluluk kontrolü
- WAL/snapshot kullanım prosedürü
- CLI veya tek komutluk ingest/reindex akışı

**Geçiş kapısı:** Aynı corpus iki kez yüklendiğinde duplicate oluşmaz; silinen veya değişen belge eski chunk'ları geride bırakmaz; snapshot'tan geri dönüş smoke test'i geçer.

### Faz 5 — Retrieval API ve exact baseline

**Amaç:** Önce doğru ve ölçülebilir temel aramayı sunmak.

**Teslimatlar:**

- Query normalize etme ve embedding üretme
- Exact arama baseline'ı
- HNSW araması
- Payload filtreleri ve erişim sınırı
- Sonuçlarda score, kaynak, chunk ve provenance bilgisi
- API/OpenAPI endpoint'leri
- Recall@k, MRR/nDCG, p50/p95/p99 ve hata oranı ölçümü

**Geçiş kapısı:** HNSW sonucu exact baseline ile karşılaştırılır; kabul edilebilir recall ve latency eşikleri yazılı olarak karşılanır.

### Faz 6 — Kalite, güvenlik ve işletim sertleştirmesi

**Amaç:** Kişisel kullanımda güvenilir, geri alınabilir ve gözlemlenebilir sistem oluşturmak.

**Teslimatlar:**

- API anahtarı/secrets yönetimi
- Path traversal, zararlı dosya, prompt injection ve metadata sızıntısı kontrolleri
- Structured audit log
- Snapshot/restore ve backup retention
- Sağlık kontrolü, hata alarmı ve temel metrikler
- Parser, ingest, retrieval, recovery ve güvenlik testleri
- Dependency pinleme ve release checklist

**Geçiş kapısı:** Güvenlik tehdit modelindeki kritik senaryolar test edilir; restore işlemi belgelenmiş süre içinde başarıyla tamamlanır.

### Faz 7 — Ölçüme dayalı gelişmiş retrieval

**Amaç:** Gerçek sorgu dağılımı ihtiyaç gösteriyorsa kaliteyi artırmak.

**Sıra:**

1. Dense + sparse hybrid ve RRF
2. Candidate generation + reranking
3. Multi-vector/late interaction
4. Scalar veya product quantization
5. Query planner ve filtre seçiciliğine göre fallback
6. Gerekirse on-disk/memory tier optimizasyonu

Her özellik ayrı deney kartı, baseline, kalite farkı, p95/p99 etkisi ve kaynak maliyetiyle eklenir.

**Geçiş kapısı:** Özellik yalnızca kişisel sorgu setinde anlamlı kazanım sağlıyor ve kabul edilen maliyet/latency sınırını koruyorsa varsayılan yapılır.

### V1.1 geçiş durumu

V1.1'in ilk dikey dilimi tamamlandı: allowlist metadata filtreleri (`document_id`,
`source_uri`, `source_type`, `title`) ve hassas içerik taşımayan retrieval audit
metrikleri eklendi. Hybrid, reranking ve otomatik query planning sonraki sürümlere
bırakıldı. Ayrıntılı sözleşme için [V1.1 filtreleme ve gözlemlenebilirlik](v1.1-filtreleme-gozlemlenebilirlik.md)
dosyasına bakılır.

V1.2 için kodlama öncesi deney kartı hazırlandı. Hybrid implementasyonu, en az
100 etiketli sorgu ve dense baseline karşılaştırması tamamlanmadan başlatılmaz.

V1.2 deney prototipi de tamamlandı. Named dense/sparse Qdrant koleksiyonu ve RRF
çalışıyor; ancak ilk 100 sorguluk küçük corpus'ta kalite kazanımı ve latency
kapısı geçilmediği için varsayılan dense retrieval korunuyor. Hybrid davranış
yalnızca `VDB_RETRIEVAL_MODE=hybrid` ile opt-in'dir.

V1.3 için candidate reranking deney kartı hazırlandı. Aday bütçesi, fallback,
latency ve güvenlik kapıları geçilmeden reranker varsayılan açılmayacaktır.

V1.3 lexical kontrol reranker prototipi çalıştırıldı; kalite kazanımı olmadığı ve
tail latency yükseldiği için yalnızca opt-in deney yolu olarak bırakıldı.

V1.4 selectivity-aware query planner prototipi eklendi. Katı filtrelerde exact
fallback, orta seçicilikte geniş ANN aday bütçesi ve diğer durumlarda normal ANN
planı seçilebilir; planner varsayılan kapalıdır.

İlk 100 filtreli sorgu benchmark'ında kalite değişmedi ve p95 yaklaşık 1.746 ms
arttı; planner varsayılan açılmadı. Orta-selectivity kararı için daha geniş
corpus gereklidir.

V1.5 multi-vector/late-interaction prototipi eklendi. Dense+sparse adayları
Qdrant `MAX_SIM` multi-vector ile yeniden sıralanabilir; late koleksiyonu ve
modu opt-in tutuluyor.

İlk 100 sorguda MRR/nDCG artışı gözlendi ancak corpus yalnızca iki chunk içerdiği
ve p95 yükseldiği için late interaction varsayılan yapılmadı.

V1.6 scalar INT8 quantization prototipi eklendi. Quantized koleksiyon server
Qdrant için opt-in'dir; local client ayarı yok saydığı için local mod fail-closed
davranır. Rescore ve oversampling ölçümü yapılmadan varsayılan değişmez.

V1.7 gelişmiş query-type benchmark metrikleri, embedding/retrieval telemetrisi,
process CPU/RSS ölçümü ve prompt-injection karantina/red-team kontrolleriyle
tamamlandı. Qdrant toplam RAM'i, disk kullanımı, concurrency, tazelik ve restore
süreleri V2 geçiş kartı için hâlâ ayrı host/server ölçümü gerektiriyor.

### Faz 8 — Ölçek ve ileri araştırma seçenekleri

**Amaç:** Kişisel sürümün sınırları ölçüldükten sonra mimariyi büyütmek.

**Adaylar:**

- Çoklu kullanıcı, tenant izolasyonu ve shard planı
- Replica, consistency ve failover
- DiskANN/FAISS/ScaNN backend deneyleri
- Multimodal embedding
- Graph-RAG ve entity ilişki katmanı
- Gelişmiş cache, compaction ve maliyet optimizasyonu

Bu faz varsayılan roadmap sırası değildir; kapasite raporu ve benchmark sonucuyla tetiklenir.

## 3. Bağımlılık sırası

```text
kararlar ve şemalar
        ↓
proje iskeleti → parser/normalize → chunk/embedding
                                      ↓
                              storage/indexing
                                      ↓
                         exact baseline → HNSW API
                                      ↓
                        test/güvenlik/operasyon
                                      ↓
                         ölçüme dayalı ileri arama
                                      ↓
                              ölçek seçenekleri
```

## 4. Her faz için çalışma döngüsü

1. Faz hedefi ve değişmeyecek sözleşmeler yazılır.
2. En küçük çalışan dikey dilim uygulanır.
3. Birim, entegrasyon ve veri kalitesi testleri çalıştırılır.
4. Benchmark ve hata kayıtları alınır.
5. Karar günlüğü güncellenir.
6. Geçiş kapısı karşılanmadan sonraki faza geçilmez.

## 5. İlk geliştirme sırası

İlk kodlama turunda yalnızca Faz 0 ve Faz 1 ele alınmalıdır. İlk dikey dilim şu kadar küçük tutulmalıdır:

```text
Markdown/TXT → normalize → deterministic chunk → tek embedding provider
→ Qdrant upsert → exact/HNSW search → kaynaklı sonuç
```

PDF, HTML, harici provider, hybrid search ve reranking bu dikey dilim doğrulanmadan sisteme bağlanmamalıdır. Böylece bir hatanın parser'dan mı, chunking'den mi, embedding'den mi yoksa indeksten mi kaynaklandığı ayrıştırılabilir.

## 6. Başarı ölçütleri

İlk sürümün başarılı sayılması için:

- Veri kaynağından sonuca kadar provenance korunmalı.
- Aynı girdi tekrar işlendiğinde deterministik ve idempotent sonuç alınmalı.
- Exact baseline ile ANN kalitesi karşılaştırılmalı.
- Model/provider değişimi kontrollü re-index olmadan kabul edilmemeli.
- Snapshot ve restore doğrulanmalı.
- Hatalar sessiz veri kaybına dönüşmemeli.
- Ölçülmemiş bir optimizasyon varsayılan davranış yapılmamalı.

## 7. İlgili karar ve teknik dokümanlar

- [V1 geçiş kabul listesi](15-kodlama-oncesi-kabul-listesi.md)
- [Kodlamaya başlama onay formu](kodlama-baslama-onay-formu.md)
- [Kodlama öncesi mimari kararları](27-kodlama-oncesi-mimari-kararlari.md)
- [Kanonik veri şeması](16-kanonik-veri-semasi.md)
- [Embedding model registry](21-embedding-model-registry.md)
- [Test stratejisi](23-test-stratejisi.md)
- [Kapasite ve SLO hedefleri](25-kapasite-slo-hedefleri.md)
- [Araştırma kapanış ve deney planı](advanced/10-arastirma-kapanis-ve-deney-plani.md)
- [V2.0 geçiş kapısı ve aday deney matrisi](advanced/12-v2-gecis-kapisi.md)
- [V1.7 kapasite ve tekrarlanabilir ölçüm deney kartı](advanced/13-kapasite-ve-tekrarlanabilir-olcum.md)
- [Gelişim goal'u kabul matrisi](advanced/16-gelisim-goal-kabul-matrisi.md)
- [V1.7 ileri seviye final audit](advanced/17-v1.7-final-audit.md)
- [V1.7 final ölçüm runbook'u](advanced/18-v1.7-final-olcum-runbook.md)

## 8. Aktif gelişim goal'u — sade ileri seviye yükseltme

Kapsamlı test ve benchmark çalışması bu listenin sonunda yapılacaktır. Geliştirme sırası:

1. Geniş kişisel corpus ve parser dispatch: parser (Markdown/plain-text, PDF, DOCX, HTML, JSON/JSONL, YAML/YML, RTF, CSV, EML ve XML), metinsiz corpus inventory/manifest, deterministik toplu ingest ve ham-byte duplicate inceleme sinyali uygulandı; PDF için gerçek `pypdf` minimal sentetik smoke testi ve extraction metni olmayan PDF için OCR olasılığını belirten hata eklendi. HTML gizli-blok eşleşmesi `html-v4`, DOCX sekme/satır sonu fidelity'si, nested-table yinelenme önlemi ve DTD/entity reddi extraction davranışıdır; ayrıca DOCX arşivleri 50 MB açılmış içerik ve 4.096 ZIP üyesi sınırlarıyla fail-closed kabul edilir. Kişisel inventory/manifest varsayılanları Git-ignore altındadır; `corpus-quality-report-v2` format/hata/hacim yanında privacy-safe parse elapsed sinyali üretir. Gerçek corpus extraction kalitesi ve format başına runtime/peak-RAM ölçümü final kapısında. Parser'lar henüz process timeout/RAM izolasyonuna sahip değildir; mevcut boyut sınırları bunu garanti etmez. Klasör ingest için varsayılan 5.000 desteklenen dosya ve 1 GB toplam kaynak admission cap'i eklendi; limit ön kontrolü geçmeden ilk embedding/store write yapılmaz. Bu değerler kapasite SLO'su değildir.
2. En az 300 etiketli sorgu için fixture/veri sözleşmesi, metadata destekli loader, Qdrant gerektirmeyen `fixture-coverage`, opsiyonel label kapsama raporu, shard merge akışı ve split/provenance kontrolü yapan final kabul kapısı hazırlandı; corpus/fixture parser sürüm kümesi ve chunk-size binding'i de fail-closed doğrulanıyor. V5 corpus-türetilmiş fixture 300 sorgu, altı türde 50'şer kayıt, 180/60/60 split ve small/medium/large kapsamı sağlıyor; duplicate yok, label'ların 300'ü reviewed, negative'lerin 50'si full-corpus doğrulamalı ve `fixture-validate`/`final-readiness` ready. 300 sorgu tek sahipli self-review ile tamamlanabilir; çoklu insan annotator şartı yoktur. Relevance yargılama protokolü binary chunk kanıtını, aday pooling'i ve gerçek-negative doğrulamasını açıklar. Uzun süreli embedding/Qdrant benchmark ölçümü ayrı final ölçüm kapısıdır.
3. Concurrency ve kapasite test primitive'i, bounded worker matrix yardımcı fonksiyonu ve CLI probe'u eklendi; tek probe ve tüm matrix toplamı 100.000 istekle sınırlı, `k`/repetitions sınırları iş başlamadan doğrulanıyor. Uzun süreli gerçek yük matrisi final ölçümünde çalıştırılacak. İlk benchmark denemesi model cache/indirme hazırlığına takıldı.
4. Negative sorgular için abstention ve skor eşiği davranışı: opt-in eşik yalnızca dense cosine aday skoruna rerank öncesi uygulanır; kalibre edilmemiş hybrid/late modları eşik talebini fail-closed reddeder. Reranker yalnızca sıralama yapar, girdiler strict doğrulanır. `no_candidates`/`below_min_score` telemetrisi ve validation split'e bağlı `abstention-scores-v1`/`abstention-calibrate` akışı hazır; dense threshold final kalibrasyonu açık, hybrid/late eşik desteği ayrı skor sözleşmesi ve kalibrasyon gerektirir.
5. RAG cevap kalitesi değerlendirme sınırı: retrieval/generation ayrımı, context/provenance sözleşmesi, fail-closed generation handoff policy, kaynak text escape ve metadata attribute quoting uygulandı; privacy-safe insan değerlendirme artifact'i ve offline özeti hazır, cevap ölçümü 300+ fixture sonrasına bırakıldı. Benchmark sonuçları fixture/corpus/model provenance kimliklerini de taşır.
6. Harici embedding provider adapter'ı ve kontrollü kullanım yolu: OpenAI adapter'ı opt-in, uzak endpoint'lerde HTTPS (yalnızca loopback HTTP test istisnası), redirect izlememe, strict config/sonlu norm doğrulama, sınırlı retry/backoff, yapılandırılabilir batch bölme, ham metin saklamayan bounded cache ve privacy-safe cache sayaçları ile fail-closed olarak eklendi; hit oranı, retry maliyeti ve kalite etkisi final çalışmasında ölçülecek.
7. Ölçülmüş ihtiyaç olursa multimodal, Graph-RAG veya çoklu kullanıcı genişlemeleri.

Her dilimde sözleşme, provenance/RAG sınırı, güvenlik etkisi ve rollback notu güncellenecek; sekizinci alan ihtiyaç kanıtı olmadan varsayılan kapsam olmayacaktır.

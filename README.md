# Kişisel Vektörel Veritabanı

Bu klasör, kişisel dokümanlardan güvenilir semantik arama ve RAG sistemi kurmak için yaşayan dokümantasyondur.

## V1'i çalıştırma

```powershell
uv sync --dev
if (!(Test-Path .env)) { Copy-Item .env.example .env }
New-Item -ItemType Directory -Force data\sources
uv run vdb doctor
uv run vdb ingest data\sources\notlar.md
uv run vdb ingest-dir data\sources
uv run vdb search "aranan konu"
uv run vdb search "aranan konu" --min-score 0.70
uv run vdb benchmark --fixture data\benchmarks\queries.json --output data\benchmarks\results\latest.json
uv run vdb benchmark --fixture data\benchmarks\queries.json --repeat 3 --output data\benchmarks\results\repeat3.json
uv run vdb concurrency-probe --fixture data\benchmarks\queries.json --concurrency 4 --warmup-repetitions 1 --repetitions 2
uv run vdb concurrency-probe --fixture data\benchmarks\queries.json --concurrency-levels 1 2 4 8 16 --warmup-repetitions 1 --repetitions 2 --output data\benchmarks\results\concurrency-matrix.json
uv run vdb corpus-inventory `
  --root data\sources `
  --output data\derived\corpus-inventory.json `
  --manifest data\manifests\corpus-manifest.json
# Preparation report; it does not start Qdrant or embeddings:
# uv run vdb fixture-coverage --fixture data\benchmarks\queries-v1.json --manifest data\benchmarks\query-fixture-manifest.json --labels data\benchmarks\labels-v1.json
# uv run vdb fixture-coverage --fixture data\benchmarks\queries-v1.json --manifest data\benchmarks\query-fixture-manifest.json --output data\benchmarks\results\fixture-coverage.json
# uv run vdb fixture-label-template --fixture data\benchmarks\queries-v1.json --corpus-manifest data\benchmarks\corpus-manifest.json --output data\benchmarks\labels-v1-template.json
# Shard'ları collision kontrolüyle birleştirme:
# uv run vdb fixture-merge queries --input data\benchmarks\shards\a.json data\benchmarks\shards\b.json --output data\benchmarks\queries-v1.json
# uv run vdb fixture-merge labels --input data\benchmarks\labels\a.json data\benchmarks\labels\b.json --output data\benchmarks\labels-v1.json
# Final gate after the real personal fixture and labels are prepared:
# uv run vdb fixture-validate --fixture data\benchmarks\queries-v1.json --manifest data\benchmarks\query-fixture-manifest.json --corpus-manifest data\benchmarks\corpus-manifest.json --labels data\benchmarks\labels-v1.json
uv run vdb backup --corpus-manifest data\manifests\corpus-manifest.json
uv run vdb restore data\snapshots\latest.tar.gz --manifest data\snapshots\latest.json
```

`corpus-inventory` çıktısı kaynak metni içermez; ancak göreli dosya yolları,
content hash'leri ve chunk kimlikleri içerir. Kişisel corpus çıktıları için
izlenmeyen `data/derived/` ve `data/manifests/` klasörlerini kullan; bu dosyaları
yayımlamadan veya benchmark fixture'ına bağlamadan önce metadata'yı ayrıca gözden geçir.
`corpus-inventory` çıktısında aynı ham byte içeriğine sahip
kopyalarda `duplicate_of` alanı daha sığ kanonik adayı gösterir; bu alan yalnızca
inceleme içindir, otomatik silme veya birleştirme yapmaz. Komut çıktısındaki
`formats` ve `failure_types` alanları format dağılımını ve parser hata özetini
metin taşımadan gösterir. `fixture-coverage` komutuna `--corpus-manifest`
verilirse relevance chunk ID'lerinin ve fixture corpus checksum'ının güncel
corpus'a bağlanıp bağlanmadığı kontrol edilir.
Çıktıdaki `coverage_complete` alanı yalnızca dağılım hazırlığının tamamlanıp
tamamlanmadığını belirtir; final etiket/provenance kapısı yine `fixture-validate`
komutudur.

HTTP `/v1/search` yanıtı `results` alanına ek olarak `abstention_reason`,
`candidate_count` ve `threshold_rejected_count` döndürür. Boş sonuçta bu alanlar
`no_candidates` ile `below_min_score` ayrımını gösterir; ayrıntılı sözleşme
[API/OpenAPI planında](docs/20-api-openapi-plani.md) bulunur.

Varsayılan `path:qdrant_storage` local persistence kullanır ve Docker gerektirmez. Server Qdrant smoke testi için `.env` içinde `VDB_QDRANT_URL=http://localhost:6333` ayarla; ayrıntılı prosedür [runtime smoke testi](docs/runtime-smoke-testi.md) dosyasındadır. `data/sources/` altında Markdown/TXT, Org/RST/LOG/TEX/ICS, PDF, DOCX, HTML, EML, JSON, JSONL/NDJSON, YAML/YML, TOML, RTF, CSV ve XML kaynakları kullanılabilir. Plain-text parser UTF-8/UTF-16/UTF-32 BOM'lu export'ları; yapılandırılmış parser'lar UTF-8 BOM'lu export'ları destekler. JSONL/NDJSON'de her boş olmayan satır ayrı kayıt olarak işlenir ve satır provenance'ı korunur. EML parser yalnızca düz metin gövdesini ve konu başlığını alır; HTML gövdesi ve ek dosyalar işlenmez. PDF metin çıkarımı yapar; OCR ve karmaşık tablo/sütun düzeni bu ilk parser diliminin kapsamı dışındadır. DOCX paragraf, temel tablo satırı ve Heading1–Heading6 stillerini çıkarır. XML parser yalnızca leaf-node metnini ve node yolunu alır; DTD/entity declaration içeren girdileri reddeder. YAML parser yalnızca `safe_load` ile veri okur; Python nesnesi tag'lerini çalıştırmaz. TOML parser `tomllib` ile veri okur ve tek deterministik JSON bölümü üretir. RTF parser temel metin, paragraf/satır sonu, sekme, Unicode ve cp1252 hex kaçışlarını çıkarır; gömülü resim/nesne, makro ve karmaşık biçimlendirme anlamlandırılmaz.

Recursive `ingest-dir` ve `corpus-inventory` akışları `.git`, virtualenv,
`node_modules`, cache/temp, build/dist, secrets/credentials ve benzeri varsayılan
dışlama dizinlerini işlemez. Tekil `ingest` çağrısı yalnızca açıkça verilen ve
source root doğrulamasından geçen dosyayı işler. `corpus-inventory` özeti,
exclude edilen dosya sayısını da içerir; dosya yolları ve içerikleri raporlanmaz.
Gerçek corpus'tan üretilen inventory, manifest, aday sorgu ve review-gerekli
label/coverage artifact'leri `private-local` kabul edilir; kaynak metni içermeseler
bile yol, hash, kimlik ve içerikten türetilmiş sorgu metadata'sı açığa çıkarabilirler.
Bu yüzden bu tür dosyalar `.gitignore` kapsamındadır ve kişisel corpus'la birlikte
yerelde üretilmelidir; public fixture veya test verisi olarak kullanılmamalıdır.
Bunlar 300+ final benchmark yerine geçmez. `data/sources/temsilî-formatlar/`
altındaki dosyalar yalnızca parser/inventory smoke kapsamını genişleten sentetik
örneklerdir; gerçek kişisel kayıt olarak değerlendirilmemelidir.

Compose server deployment'ı `qdrant_server_storage` ve `qdrant_server_snapshots` named volume'larını kullanır; böylece local `qdrant_storage` ile dosya kilidi çakışması önlenir. Elle volume bağlarken de local Qdrant süreci ile Docker Qdrant server aynı klasörü eşzamanlı kullanmamalıdır.

## Başlangıç yolu

Harici embedding yalnızca açıkça `VDB_EMBEDDING_PROVIDER=openai` seçildiğinde
devreye girer; başarılı provider seçimi ham veri veya API key içermeyen audit
olayı üretir. Ayrıntılı ağ, retry ve gizlilik sınırları [embedding provider
sözleşmesinde](docs/05-embedding-provider-sozlesmesi.md) açıklanır.

Inventory çıktısındaki `unsupported_files` ve `unsupported_suffixes` alanları
allowlist dışındaki dosyaları yol ve içerik göstermeden raporlar. Bu dosyalar
ingest edilmez ve corpus checksum'ına dahil edilmez.

1. Dokümanları kaynak kimliği ve sürümüyle kaydet.
2. Metni anlamlı bölümlere ayır; her parçaya kaynak ve erişim metadatası ekle.
3. Tek bir embedding modeli ve tek bir mesafe metriği kullan.
4. Vektörleri Qdrant koleksiyonunda, payload filtrelerini indeksleyerek sakla.
5. Önce exact/ground-truth arama ile ölç, sonra HNSW parametrelerini optimize et.

RAG cevapları için ham soru/cevap/source metni saklamayan insan değerlendirme
artifact'ini doğrulamak ve özetlemek için:

```powershell
uv run vdb rag-evaluation-summary `
  --input data/benchmarks/rag-evaluations.json `
  --output data/benchmarks/results/rag-evaluation-summary.json
```

Bu komut embedding sağlayıcısı veya Qdrant başlatmaz; yalnızca şema, duplicate
`query_id` ve provenance tutarlılığını kontrol eder.

Inventory oluşturulduktan sonra format bazlı extraction kalite özetini almak için:

```powershell
uv run vdb corpus-quality `
  --inventory data/derived/corpus-inventory.json `
  --output data/derived/corpus-quality-report.json
```

Kalite raporu yalnızca sayım, byte/karakter/chunk toplamı, parser sürümü ve hata
sınıfı taşır; kaynak yolu, hash, chunk kimliği ve metin taşımaz.

Dense validation skorlarından eşik seçimi de Qdrant başlatmadan yapılabilir.
`abstention-scores-v1` artifact'i yalnızca sorgu kimliği ve maksimum cosine
skorlarını taşır; komut seçilen split'in sorgu kimlikleriyle birebir eşleşme
arar ve pozitif kabul/negative abstention tabanlarını sağlayan en yüksek eşiği
üretir:

```powershell
uv run vdb abstention-calibrate `
  --fixture data/benchmarks/queries.json `
  --scores data/benchmarks/abstention-scores.json `
  --split validation `
  --output data/benchmarks/results/abstention-calibration.json
```

Gerçek dense benchmark koşusunda bu artifact'i doğrudan üretmek için benchmark'a
`--scores-output` eklenebilir; varsayılan olarak yalnızca validation split'i
yazılır, başka split için `--scores-split development|test` seçilebilir. Bu
seçenek bilinçli olarak `repeat=1`, eşiksiz ve rerank kapalı dense koşulla
sınırlıdır; böylece calibration girdisi önceden uygulanmış bir eşik veya
reranker skoru olmaz.

## Dokümanlar

- [Geliştirme roadmap'i](docs/roadmap.md)
- [V1.7 ileri seviye final audit](docs/advanced/17-v1.7-final-audit.md)
- [V1 kodlama öncesi kapsam tanımı](docs/v1-kapsam-tanimi.md)
- [Kodlama öncesi teknik karar önerileri](docs/kodlama-oncesi-teknik-karar-onerileri.md)
- [Local runtime smoke testi](docs/runtime-smoke-testi.md)
- [Kodlamaya başlama onay formu](docs/kodlama-baslama-onay-formu.md)
- [Kapsam ve desteklenen veri türleri](docs/00-kapsam-ve-veri-turleri.md)
- [Mimari ve veri modeli](docs/01-mimari.md)
- [Kurulum ve ilk indeksleme](docs/02-kurulum.md)
- [İçe aktarma, chunking ve sorgu sözleşmesi](docs/03-pipeline.md)
- [Değerlendirme, güvenlik ve işletim](docs/04-degerlendirme-isletim.md)
- [Embedding sağlayıcı sözleşmesi](docs/05-embedding-provider-sozlesmesi.md)
- [Parser ve normalizasyon akışı](docs/06-parser-normalizasyon-akisi.md)
- [Embedding modeli seçimi](docs/07-embedding-model-secimi.md)
- [Hybrid search ve reranking](docs/08-hybrid-search-ve-reranking.md)
- [Benchmark ve yeniden indeksleme](docs/09-benchmark-ve-reindex-stratejisi.md)
- [API sözleşmesi](docs/10-api-sozlesmesi.md)
- [Güvenlik ve tehdit modeli](docs/11-guvenlik-tehdit-modeli.md)
- [Operasyon runbook'u](docs/12-operasyon-runbook.md)
- [Maliyet ve kapasite](docs/13-maliyet-kapasite.md)
- [Terimler sözlüğü](docs/14-terimler-sozlugu.md)
- [V1 geçiş kabul listesi](docs/15-kodlama-oncesi-kabul-listesi.md)
- [Kanonik veri şeması](docs/16-kanonik-veri-semasi.md)
- [Qdrant koleksiyon şeması](docs/17-qdrant-koleksiyon-semasi.md)
- [Belge yaşam döngüsü](docs/18-belge-yasam-dongusu.md)
- [Kimlik ve erişim modeli](docs/19-kimlik-ve-erisim-modeli.md)
- [API/OpenAPI ayrıntı planı](docs/20-api-openapi-plani.md)
- [Embedding model registry](docs/21-embedding-model-registry.md)
- [Parser kalite standardı](docs/22-parser-kalite-ve-sinirlari.md)
- [Test stratejisi](docs/23-test-stratejisi.md)
- [Sürüm ve dependency politikası](docs/24-surum-ve-dependency-politikasi.md)
- [Kapasite ve SLO hedefleri](docs/25-kapasite-slo-hedefleri.md)
- [Kaynak envanteri ve sınıflandırma](docs/26-kaynak-envanteri-ve-siniflandirma.md)
- [Kodlama öncesi mimari kararları](docs/27-kodlama-oncesi-mimari-kararlari.md)
- [JSON Schema kullanım rehberi](docs/28-json-schema-rehberi.md)
- [OpenAPI kullanım rehberi](docs/29-openapi-rehberi.md)
- [Yapılandırma referansı](docs/30-yapilandirma-referansi.md)
- [Geliştirici kurulum rehberi](docs/31-gelistirici-kurulum-rehberi.md)
- [Örnek veri ve benchmark paketi](docs/32-ornek-veri-ve-benchmark-paketi.md)
- [Release ve değişiklik politikası](docs/33-release-ve-degisiklik-politikasi.md)
- [Değişiklik günlüğü](CHANGELOG.md)
- [İleri arama mimarisi](docs/34-ileri-arama-mimarisi.md)
- [Multi-vector ve late interaction](docs/35-multivector-ve-late-interaction.md)
- [Quantization ve depolama](docs/36-kuantizasyon-ve-depolama.md)
- [Çoklu kullanıcı ve sharding](docs/37-coklu-kullanici-ve-sharding.md)
- [Dağıtık deployment ve yüksek erişilebilirlik](docs/38-dagitik-ve-yuksek-erisebilirlik.md)
- [Multimodal ve özel veri](docs/39-multimodal-ve-ozel-veri.md)
- [Graph-RAG ve ilişkiler](docs/40-graph-rag-ve-iliskiler.md)
- [Gelişmiş değerlendirme](docs/41-gelismis-degerlendirme.md)
- [300+ etiketli sorgu fixture sözleşmesi](docs/advanced/14-etiketli-query-fixture-sozlesmesi.md)
- [RAG context ve cevap kalite sınırı](docs/advanced/15-rag-context-ve-cevap-kalite-siniri.md)
- [Gelişim goal'u kabul matrisi](docs/advanced/16-gelisim-goal-kabul-matrisi.md)
- [Gelişmiş gözlemlenebilirlik ve maliyet](docs/42-gelismis-gozlemlenebilirlik-ve-maliyet.md)
- [İleri güvenlik ve gizlilik](docs/43-ileri-guvenlik-gizlilik.md)
- [V1.1 filtreleme ve gözlemlenebilirlik](docs/v1.1-filtreleme-gozlemlenebilirlik.md)
- [V1.2 hybrid search deney kartı](docs/v1.2-hybrid-search-deney-karti.md)
- [V1.3 reranking deney kartı](docs/v1.3-reranking-deney-karti.md)
- [V1.4 query planner deney kartı](docs/v1.4-query-planner-deney-karti.md)
- [V1.5 multi-vector/late-interaction deney kartı](docs/v1.5-multivector-late-interaction-deney-karti.md)
- [V1.6 quantization ve depolama deney kartı](docs/v1.6-quantization-depolama-deney-karti.md)
- [V1.7 değerlendirme, telemetri ve red-team](docs/v1.7-degerlendirme-telemetri-redteam.md)
- [İleri seviye araştırma raporu](docs/advanced/00-ileri-seviye-arastirma-raporu.md)
- [ANN indeksleri derinlemesine](docs/advanced/01-ann-indeksleri-derinlemesine.md)
- [Filtreli hybrid ve rerank](docs/advanced/02-filtreli-hybrid-ve-rerank.md)
- [Dağıtık tutarlılık ve kapasite](docs/advanced/03-dagitik-tutarlilik-ve-kapasite.md)
- [İleri değerlendirme ve güvenlik](docs/advanced/04-ileri-degerlendirme-ve-guvenlik.md)
- [İleri araştırma kaynakları ve açık sorular](docs/advanced/05-arastirma-kaynaklari-ve-acik-sorular.md)
- [Araştırma metodolojisi](docs/advanced/06-arastirma-metodolojisi.md)
- [Segment, WAL ve compaction](docs/advanced/07-segment-wal-compaction.md)
- [Query planner ve filtre mimarisi](docs/advanced/08-query-planner-ve-filtre-mimarisi.md)
- [Model–indeks ortak optimizasyonu](docs/advanced/09-model-index-joint-optimization.md)
- [Araştırma kapanış ve deney planı](docs/advanced/10-arastirma-kapanis-ve-deney-plani.md)
- [Backend uyumluluk ve sürüm matrisi](docs/advanced/11-backend-uyumluluk-ve-surum-matrisi.md)
- [V2.0 geçiş kapısı ve aday deney matrisi](docs/advanced/12-v2-gecis-kapisi.md)
- [V1.7 kapasite ve tekrarlanabilir ölçüm deney kartı](docs/advanced/13-kapasite-ve-tekrarlanabilir-olcum.md)
- [Karar günlüğü](docs/karar-gunlugu.md)

## Kapsam dışı

Bu ilk sürüm üretim ölçeğinde dağıtık altyapı, model eğitimi ve otomatik web taraması içermez. Bunlar ölçüm sonuçlarına göre eklenecektir.

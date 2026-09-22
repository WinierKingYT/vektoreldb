# 16. Gelişim goal'u kabul matrisi

Bu belge aktif gelişim goal'unun mevcut durumunu ve tamamlanma kanıtını ayırır.
Bir özellik için kodun bulunması tek başına final kabul anlamına gelmez;
ölçüm gerektiren maddeler ilgili final koşusu tamamlanana kadar açık kalır.

| Alan | Mevcut durum | Final kanıtı |
|---|---|---|
| Geniş corpus | Parser registry, yapılandırılabilir güvenlik sınırlı inventory/manifest, root bağımsız boyut korumalı `ingest-dir`, ingest ve inventory için 5.000 desteklenen dosya/1 GB batch kabul kapısı ve preflight tamamlanmadan embed/store/parse/yazım yapılmaması, PDF/DOCX/HTML/RTF/EML/JSON/JSONL/NDJSON/YAML/YML/TOML/CSV/XML format desteği, format/hata ve unsupported suffix özeti, extraction hacmi metrikleri, privacy-safe parse elapsed sinyalleri ve ham-byte duplicate inceleme sinyali, inventory’den kaynak metni taşımayan format kalite özeti (`corpus-quality`) hazır | Temsilî corpus envanteri ve format kalite raporu; duplicate kararları gözden geçirilmiş olmalı; parse elapsed değerleri peak-RAM/process timeout hedefi sayılmamalı |
| 300+ sorgu | Loader metadata desteği, query-label schema, review-required `fixture-label-template`, derived-label review kapısı, canonical manifest schema, split toleransı, privacy-safe `fixture-coverage`, label kapsama özeti, shard'ları çakışma kontrollü birleştiren `fixture-merge`, fixture preflight, corpus/chunk-size binding ve labelsız/corpus-manifestsiz kabulü reddeden `fixture-validate` hazır | `status=ready`, en az 300 sorgu, tek sahipli manual/reviewed etiket/provenance, gerçek chunk kimliği ve dağılım kapıları; çoklu insan anotasyonu gerekmez |
| PDF/DOCX/HTML | Suffix dispatch; PDF text ve metinsiz PDF için açık, OCR olasılığını belirten hata, DOCX paragraf+temel tablo ve güvenli ZIP paketi doğrulaması (50 MB açılmış içerik, 4.096 üye), HTML görünür metin; hızlı parser/ingest regresyon testleri | Gerçek örnek corpus üzerinde extraction kalite raporu; PDF sırası/boş sayfa, her formatın runtime/peak-RAM profili ve gerekirse worker/timeout kararı |
| Concurrency/kapasite | Bounded probe, CLI, privacy-safe exception sınıfı dağılımı, cold/warm ayrımı için ölçüm dışı warm-up ve hızlı primitive testleri hazır | Local/server, worker, tekrar ve uzun süreli percentile ölçümleri |
| Negative/abstention | Opt-in `VDB_RETRIEVAL_MIN_SCORE` yalnızca dense cosine aday skoruna rerank öncesi uygulanır; kalibre edilmemiş hybrid/late kiplerinde eşik fail-closed reddedilir; strict girdi, privacy-safe telemetri ve validation split'e bağlı `abstention-scores-v1`/`abstention-calibrate` akışı hazır | Dense validation/test threshold, reranking ile birlikte negative success ve yanlış boş sonuç; hybrid/late threshold açılacaksa ayrı skor sözleşmesi ve kalibrasyon |
| RAG kalite sınırı | Context builder, citation integrity/coverage, provenance/security metadata, XML text/attribute escaping, boş/review/truncated durumlarında fail-closed generation handoff policy ve privacy-safe insan cevap evaluation artifact sözleşmesi hazır | Retrieval/context/answer katmanlarının ayrı değerlendirme raporu; 300+ sorguda insan değerlendirmesi |
| Harici embedding | Opt-in OpenAI-compatible adapter, strict numeric config, bounded hash-keyed in-memory cache, privacy-safe `cache_stats`, HTTPS/loopback, redirects disabled, finite-norm/dimension validation ve sınırlı retry hazır | Aynı corpus üzerinde kalite, latency, retry maliyeti ve veri paylaşımı kararı |
| Multimodal/Graph-RAG/çoklu kullanıcı | Bilinçli olarak ertelendi | Ölçülmüş darboğaz veya açık kullanım ihtiyacı |

### Fixture etiketleme güvenilirliği — yeni protokol

`docs/advanced/14-etiketli-query-fixture-sozlesmesi.md` binary chunk relevance'ın
anlamını, aday pooling ile mevcut dense baseline'a önyargıyı azaltmayı, gerçek
corpus-negative sorguyu top-k false negative'den ayırmayı ve tek annotator için
kör tekrar kontrolünü tanımlar. Bu protokol mevcut 66 derived label'ı reviewed
yapmaz; benchmark kanıtı üretmez ve kod/schema değişikliği gerektirmez. NIST'in
judgment kapsamı uyarısıyla uyumlu olarak incelenmemiş chunk “non-relevant”
varsayılmaz.

## Final koşusundan önceki gerçek durum

Mevcut yerel corpus inventory'si 23 kaynak ve 633 chunk içeriyor;
Markdown yanında HTML, JSON, JSONL, YAML, RTF, XML, CSV, EML, ICS ve ORG örnekleri de gerçek dispatch
akışından geçirildi; Kargo Gemisi arşivindeki 9 DOCX dosyası da `docx-v4` ile
başarıyla parse edildi. Sentetik uzun proje günlüğüyle medium-size ve arşiv
belgeleriyle large kaynak davranışı inventory'de temsil ediliyor.
Bu nedenle 300+ query kabul kapısı henüz çalıştırılabilir biçimde hazır olsa da
`ready` değildir. Gerçek kişisel kaynaklar eklendiğinde şu sıra izlenir:

Güncel coverage snapshot'ı genişletilmiş aday fixture'ın corpus'a bağlandığını gösteriyor:
66 sorguluk paket `corpus_binding_status=valid` ve
`label_provenance_status=valid` durumunda; ancak manifest hâlâ `contract-only`,
etiket şablonu `review-required` ve 300 sorgu kapısı henüz karşılanmış değil.
Tüm 66 etiket derived/review-required durumundadır; bu paket geliştirme/smoke
girdisidir, final relevance etiketi ve benchmark kanıtı değildir. Aday sorgular
önce yalnızca iki belgeyi hedeflerken artık 12 corpus belgesini kapsıyor; medium
boyutlu günlükteki 14 ve temsilî kişisel kayıt dosyasındaki 11 chunk'ın
tamamına en az bir aday sorgu bağlanıyor.
Eski PromtGen smoke fixture'ları tarihsel deney kanıtıdır ve güncel
kişisel corpus kabul kapısının yerine geçmez. Sentetik kişisel kayıtlar
corpus'a eklendi; yeni corpus checksum'ı
`sha256:3df6f87547c96a4d1af40f829c0bfc9196dfec52a7227e35ab3fd299ce59098d`.
Bu karma formatlı corpus için fixture provenance'ı `parser_version: mixed`
özetini ve on parser sürümünü içeren `parser_versions` listesini korur.
Yerel aday sorgu/label/coverage dosyaları `data/benchmarks/representative-personal-*.json`
adlarıyla üretilebilir; bu `private-local` artifact'ler `.gitignore` kapsamındadır
ve fresh clone'da bulunmaları beklenmez.
Fixture coverage binding açısından geçerli; 66 sorgu olduğu için 300+ kabul kapısını
henüz geçmez ve label şablonu manuel review gerektirir. On beş sorgu medium-size
günlüğe bağlandı; large corpus kovası mevcut olsa da 66 sorguluk fixture henüz
large belgeyi hedeflemiyor.

1. `vdb corpus-inventory` ile corpus manifesti oluştur.
2. Inventory içindeki `duplicate_of` alanlarını gözden geçir; otomatik merge/silme
   yapılmaz, yalnızca gerçekten aynı kaynağın kopyalarıysa corpus dışına alma kararı ver.
3. Sorgu/etiket paketini development/validation/test split'leriyle doldur.
4. `vdb fixture-validate --labels ... --corpus-manifest ...` ile final kabul kapılarını geçir.
5. Dense baseline, threshold, concurrency ve RAG kalite ölçümlerini aynı
   corpus checksum'ı üzerinde çalıştır.
6. Sonuçları karar günlüğüne yaz; ancak bundan sonra goal kabulünü değerlendir.

Uzun süreli test ve benchmarklar bu belgeyi erken kapatmak için atlanamaz.

## İlk final doğrulama notu

Tam test paketi son doğrulamada `345 passed, 3 skipped, 3 warnings` ile tamamlandı. Önceki
`117 passed, 3 skipped` kaydı tarihsel ilk doğrulama sonucudur. Eski 100 sorguluk
smoke benchmark denemesi pinned local modelin Hugging Face cache/indirme
aşamasında ilerlemediği için sonuç dosyası üretmeden durduruldu; bu kalite
sonucu değildir ve benchmark ortamı hazır değil olarak kaydedilmiştir.
Model hazırlığını teşhis etmek için local provider'a opt-in
`VDB_EMBEDDING_OFFLINE=true` cache-only modu eklendi; eksik cache durumunda
gelecek ölçümler uzun network beklemesi yerine açık failure verecek.

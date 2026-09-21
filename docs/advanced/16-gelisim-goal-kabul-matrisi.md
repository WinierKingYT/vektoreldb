# 16. Gelişim goal'u kabul matrisi

Bu belge aktif gelişim goal'unun mevcut durumunu ve tamamlanma kanıtını ayırır.
Bir özellik için kodun bulunması tek başına final kabul anlamına gelmez;
ölçüm gerektiren maddeler ilgili final koşusu tamamlanana kadar açık kalır.

| Alan | Mevcut durum | Final kanıtı |
|---|---|---|
| Geniş corpus | Parser registry, yapılandırılabilir güvenlik sınırlı inventory/manifest, root bağımsız boyut korumalı `ingest-dir`, PDF/DOCX/HTML/RTF/EML/JSON/JSONL/NDJSON/YAML/YML/CSV/XML format desteği, format/hata ve unsupported suffix özeti, extraction hacmi metrikleri ve ham-byte duplicate inceleme sinyali hazır | Temsilî corpus envanteri ve format kalite raporu; duplicate kararları gözden geçirilmiş olmalı |
| 300+ sorgu | Loader metadata desteği, query-label schema, review-required `fixture-label-template`, derived-label review kapısı, canonical manifest schema, split toleransı, privacy-safe `fixture-coverage`, label kapsama özeti, shard'ları çakışma kontrollü birleştiren `fixture-merge`, fixture preflight, corpus chunk-ID binding ve `fixture-validate` hazır | `status=ready`, en az 300 sorgu, etiket/provenance, gerçek chunk kimliği ve dağılım kapıları |
| PDF/DOCX/HTML | Suffix dispatch; PDF text, DOCX paragraf+temel tablo ve güvenli ZIP paketi doğrulaması, HTML görünür metin; hızlı parser/ingest regresyon testleri | Gerçek örnek corpus üzerinde extraction kalite raporu |
| Concurrency/kapasite | Bounded probe, CLI, privacy-safe exception sınıfı dağılımı ve hızlı primitive testleri hazır | Local/server, worker, tekrar ve uzun süreli percentile ölçümleri |
| Negative/abstention | Opt-in `VDB_RETRIEVAL_MIN_SCORE` ve istek override’ı; privacy-safe `abstention_reason` telemetrisi hazır | Validation threshold, test negative success ve yanlış boş sonuç oranı |
| RAG kalite sınırı | Context builder, citation integrity, citation coverage, provenance/security metadata ve boş/review/truncated durumlarında fail-closed generation handoff policy hazır | Retrieval/context/answer katmanlarının ayrı değerlendirme raporu |
| Harici embedding | Opt-in OpenAI-compatible adapter, yapılandırılabilir batch bölme, bounded hash-keyed in-memory cache ve privacy-safe `cache_stats`, fail-fast HTTPS/loopback endpoint doğrulaması, dimension/index validation ve sınırlı retry hazır | Aynı corpus üzerinde kalite, latency, maliyet ve gizlilik kararı |
| Multimodal/Graph-RAG/çoklu kullanıcı | Bilinçli olarak ertelendi | Ölçülmüş darboğaz veya açık kullanım ihtiyacı |

## Final koşusundan önceki gerçek durum

Mevcut yerel corpus inventory'si on dört kaynak ve 47 chunk içeriyor;
Markdown yanında HTML, JSON, JSONL, YAML, RTF, XML, CSV, EML, ICS ve ORG örnekleri de gerçek dispatch
akışından geçirildi. Sentetik uzun proje günlüğüyle medium-size kaynak davranışı
da inventory'de temsil ediliyor.
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
`sha256:80170ea3cd3b1adb2b4ecc71918a9460a87050a6cfbcf22fa639611e8dded919`.
Bu karma formatlı corpus için fixture provenance'ı `parser_version: mixed`
özetini ve dokuz parser sürümünü içeren `parser_versions` listesini korur.
Bu corpus'a bağlı ilk aday fixture ve label şablonu sırasıyla
`data/benchmarks/representative-personal-queries.json` ve
`data/benchmarks/representative-personal-query-labels-template.json` dosyalarındadır.
Fixture coverage binding açısından geçerli; 66 sorgu olduğu için 300+ kabul kapısını
henüz geçmez ve label şablonu manuel review gerektirir. On beş sorgu medium-size
günlüğe bağlandı; large kovası henüz temsil edilmiyor.

1. `vdb corpus-inventory` ile corpus manifesti oluştur.
2. Inventory içindeki `duplicate_of` alanlarını gözden geçir; otomatik merge/silme
   yapılmaz, yalnızca gerçekten aynı kaynağın kopyalarıysa corpus dışına alma kararı ver.
3. Sorgu/etiket paketini development/validation/test split'leriyle doldur.
4. `vdb fixture-validate` ile dağılım kapılarını geçir.
5. Dense baseline, threshold, concurrency ve RAG kalite ölçümlerini aynı
   corpus checksum'ı üzerinde çalıştır.
6. Sonuçları karar günlüğüne yaz; ancak bundan sonra goal kabulünü değerlendir.

Uzun süreli test ve benchmarklar bu belgeyi erken kapatmak için atlanamaz.

## İlk final doğrulama notu

Tam test paketi son bilinen durumda `276 passed, 3 skipped, 3 warnings` ile tamamlandı. Önceki
`117 passed, 3 skipped` kaydı tarihsel ilk doğrulama sonucudur. Eski 100 sorguluk
smoke benchmark denemesi pinned local modelin Hugging Face cache/indirme
aşamasında ilerlemediği için sonuç dosyası üretmeden durduruldu; bu kalite
sonucu değildir ve benchmark ortamı hazır değil olarak kaydedilmiştir.
Model hazırlığını teşhis etmek için local provider'a opt-in
`VDB_EMBEDDING_OFFLINE=true` cache-only modu eklendi; eksik cache durumunda
gelecek ölçümler uzun network beklemesi yerine açık failure verecek.

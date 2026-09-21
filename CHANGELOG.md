# Changelog

Bu dosya kullanıcıya görünür değişiklikleri ve release kararlarını kısa biçimde kaydeder.

## [Unreleased]

- `min_score` yalnızca dense cosine retrieval'da, varsa reranking öncesinde
  uygulanıyor. Kalibrasyonu olmayan hybrid/late eşik istekleri fail-closed
  reddedilir; eşiksiz arama açıktır. Reranker yalnızca dense eşiğini geçen
  adayları yeniden sıralar. Eşik helper'ları invalid score/floor türlerini reddeder.
- RAG evidence metadata'sı XML attribute bağlamında quote-aware encode ediliyor;
  source-controlled başlık/heading tırnakları yeni attribute oluşturamıyor.
- Harici embedding HTTP istemcisi 3xx yönlendirmelerini reddediyor; API anahtarı ve
  kişisel metin yalnızca yapılandırılmış embedding endpoint'ine gönderiliyor.
- Harici embedding numeric config tipleri/sonluluğu kurulum anında doğrulanıyor;
  response vektör normunun taşması fail-closed reddediliyor.
- Parser kalite rehberi mevcut durumu netleştiriyor: dosya/açılmış içerik sınırları
  var, ancak process timeout veya peak-RAM izolasyonu uygulanmıyor; gerçek corpus
  ölçümünde runtime/RAM gözlenip gereksinim kararı verilecek.
- PDF extraction hiç metin bulamadığında artık taranmış/görsel içerik olasılığını ve
  OCR gerekebileceğini belirten açık hata verir; pypdf metin sırası ve sıkıştırılmış
  içerik akışının bellek sınırları parser kalite dokümantasyonunda netleştirildi.
  Gerçek PDF corpus kalite incelemesi ve süreç izolasyonu hâlâ final kapısında.
- Kişisel corpus inventory/manifest/query/label/coverage artifact'leri `private-local`
  olarak Git ignore kapsamına alındı; corpus'a bağlı testler sentetik metadata ile
  çalışacak. Daha önce public GitHub geçmişine gönderilmiş kayıtlar için geçmiş
  temizliği bu çalışma ağacından otomatik yapılmıyor.
- Corpus'a bağlı temsilî retrieval fixture'ı 36'dan 66 aday sorguya ve iki yerine
  12 hedef belgeye genişletildi; kişisel kayıt örneğinin 11, medium günlüğün 14
  chunk'ı kapsanıyor. Yeniden üretilen label template'i 66 kaydı da
  derived/review-required işaretliyor; coverage binding geçerli, final 300 sorgu
  ve large-bucket kapıları açık kalıyor.
- V1 local-first retrieval çekirdeği tamamlandı: Markdown/TXT ingest, deterministic document/chunk kimlikleri, local embedding, Qdrant persistence, filtreli arama ve provenance/citation alanları.
- Ingest, search, delete, reindex, backup/restore ve benchmark CLI/API akışları eklendi.
- JSON Schema, OpenAPI, güvenlik kontrolleri, exact baseline ve regression ölçümleri için test altyapısı eklendi.
- Snapshot restore akışına backup manifest doğrulaması, checksum ve snapshot adı uyumu kontrolleri eklendi.
- Docker server Qdrant smoke test prosedürü ve iki entegrasyon testi eklendi; Docker daemon/runtime doğrulaması bu çalışma ortamında henüz çalıştırılmadı ve testler skip olarak kalıyor.
- V1.1 dikey dilimi eklendi: allowlist metadata filtreleri ve ham içerik taşımayan retrieval audit metrikleri.
- V1.2 opt-in dense+sparse RRF koleksiyonu ve hashed lexical encoder eklendi; benchmark kazanımı olmadığı için varsayılan retrieval dense kaldı.
- V1.3 opt-in candidate reranking sözleşmesi, offline lexical kontrol reranker'ı ve güvenli fallback ölçümü eklendi.
- V1.4 opt-in selectivity-aware query planner ve filtreli exact fallback yolu eklendi.
- V1.4 filtreli benchmark sonucu kaydedildi; planner kalite kazanımı göstermediği için varsayılan kapalı kaldı.
- V1.5 opt-in multi-vector/late-interaction MaxSim koleksiyonu ve rollback uyumlu retrieval yolu eklendi.
- V1.6 opt-in scalar INT8 quantization, original-vector rescore ve oversampling yolu eklendi; local client desteği yoksa fail-closed davranır.
- V1.6 Docker benchmark sonucu kaydedildi; küçük corpus'ta quantization varsayılanı değiştirilmedi.
- V1.7 query-type benchmark metrikleri, embedding/retrieval telemetrisi ve prompt-injection karantina kontrolleri eklendi.
- Kişisel corpus parser kapsamı `.org`, `.rst`, `.log`, `.tex` ve `.ics` plain-text alias'larıyla genişletildi; UTF-8/UTF-16/UTF-32 BOM'lu plain-text ve UTF-8 BOM'lu JSON, JSONL/NDJSON, CSV ve HTML export'ları normalize ediliyor.
- Recursive `corpus-inventory` ve `ingest-dir` akışlarına ortak VCS, virtualenv, cache, build ve secrets/credentials dizin exclude politikası eklendi; tekil dosya ingest davranışı korunuyor.
- `corpus-inventory` CLI özeti, exclude edilen dosya sayısını (`excluded_files`) ham yol veya içerik göstermeden raporluyor.
- Privacy-safe sentetik format corpus'u HTML, JSON, CSV, EML, ICS ve ORG örnekleriyle genişletildi; inventory akışında 9 kaynak/29 chunk ve sıfır parse hatası doğrulandı.
- `corpus-inventory` allowlist dışı dosyaları `unsupported_files` ve `unsupported_suffixes` ile privacy-safe biçimde görünür kılıyor; bu dosyalar checksum'a dahil edilmiyor.
- Corpus manifesti kaynak boyutu dağılımını `size_bucket_counts` ile taşımaya başladı; alan metin veya yol içermez ve eski manifestler uyumludur.
- `fixture-coverage` fixture ve gerçek corpus boyut kovalarını ayrı raporlamaya başladı (`size_bucket_counts` / `corpus_size_bucket_counts`).
- Boş görünür extraction kaynakları parser hatası olarak fail-closed korunurken inventory/manifest üzerinde `extraction_status` ve `empty_extraction_count` ile ayrıştırılıyor.
- Medium-size sentetik uzun proje günlüğü ile corpus inventory 10 kaynak/40 chunk kapsamına genişletildi; tüm kaynaklarda parser hatası yok.
- Medium günlük için altı provenance-bağlı aday sorgu eklendi; fixture coverage 36 sorgu ve 6 medium-size sorgu gösteriyor, etiketler review-required durumda.
- Benchmark CLI'ına tekrarlanabilir ölçüm için `--repeat` eklendi; tek koşu geriye dönük uyumlu, çoklu koşular ham JSON olarak saklanıyor.
- OpenAPI sözleşmesi mevcut filtre, rerank ve retrieval-stage davranışıyla hizalandı; contract testleri bu alanları koruyacak şekilde genişletildi.
- V2.0 geçiş kapısı, kapasite deney kartı ve ileri seviye doküman indeks bağlantıları tamamlandı.
- Qdrant v1.19 memory-tier ve Turbo4 araştırma notları backend uyumluluk matrisine işlendi; Turbo4 varsayılanlaştırılmadı.
- Benchmark kaynak telemetrisi process CPU süresi ve platform-native gözlenen RSS belleğiyle genişletildi; ölçülemeyen disk/host alanları tahmin edilmiyor.
- Benchmark JSON contract testi CPU ve RSS alanlarının çıktıdan kaybolmasını engelleyecek şekilde güçlendirildi.
- Geniş corpus için PDF, DOCX, HTML, JSON ve CSV parser dispatch'i eklendi; OCR ve karmaşık düzen sınırlamaları dokümante edildi.
- 300+ etiketli sorgu fixture sözleşmesi ve bounded concurrency ölçüm primitive'i eklendi; gerçek veri ve uzun süreli ölçümler final aşamaya bırakıldı.
- Opt-in OpenAI embedding adapter'ı eklendi; local varsayılan ve provider manifest uyumluluğu korunurken anahtar/metin loglama ve sessiz dimension mismatch engellendi. Geçici ağ/408/429/5xx hataları sınırlı exponential backoff ile yeniden deneniyor.
- RAG context/provenance ve cevap kalite sınırı dokümante edildi; generation vector DB içine alınmadı.
- Generation katmanına bağımsız `build_rag_context` helper'ı eklendi; citation/provenance korunuyor, kaynak metni escape edilip untrusted evidence olarak sınırlandırılıyor.
- RAG cevaplarında geçersiz citation marker'larını raporlayan `validate_rag_answer_citations` helper'ı eklendi; otomatik doğruluk iddiası oluşturmaz.
- V2.0 geçiş kapısı eklendi; multimodal, Graph-RAG, çoklu kullanıcı, sharding ve HA yalnızca ölçülmüş ihtiyaçla açılacak.
- Fixture manifesti canonical schema, split toleransı ve corpus manifest binding ile güçlendirildi; ayrı `query-labels` schema/loader ve `fixture-validate --labels` eklendi.
- Benchmark ve concurrency komutlarına provider/Qdrant başlamadan çalışan acceptance preflight seçenekleri eklendi.
- Karma parser'lı kişisel corpus için fixture ve query-label provenance sözleşmesi
  `parser_version: mixed` özeti ile ayrıntılı `parser_versions` listesini taşıyacak
  şekilde genişletildi; tek parser'lı eski kayıtlar geriye dönük uyumlu bırakıldı.
- `fixture-coverage` artık label provenance uyuşmazlıklarını da privacy-safe
  `label_provenance_status` ve `label_provenance_mismatch_count` alanlarıyla
  görünür kılıyor; uyuşmazlık corpus binding sonucuna yansıtılıyor.
- Tekrarlı benchmark çıktısı ham koşulara ek olarak privacy-safe `summary`
  alanında run count ile ortalama/minimum/maksimum kalite, latency, hata, CPU
  ve RSS değerlerini taşıyor; `--repeat 1` davranışı korunuyor.
- Concurrency kapasite hazırlığına bounded worker matrix helper'ı eklendi;
  seviyeler sıralı/tekil tutuluyor, her koşu mevcut istek bütçesinden geçiyor ve
  sorgu içeriği çıktıya taşınmıyor.
- `concurrency-probe` komutuna opt-in `--concurrency-levels` matrix seçeneği
  eklendi; tek seviyeli `--concurrency` çıktısı geriye dönük korundu.
- Concurrency matrix JSON yazımı `write_concurrency_matrix_results` helper'ına
  taşındı; boş veya duplicate worker seviyeleri reddediliyor ve sorgu metni
  çıktıya alınmıyor.
- V1.7 için gereksinim, mevcut kanıt, açık final kapısı ve ölçüm sırasını tek
  yerde ayıran ileri seviye final audit dokümanı eklendi.
- `fixture-coverage` komutuna opsiyonel `--output` eklendi; privacy-safe
  coverage kanıtı sorgu/belge metni taşımadan JSON dosyasına saklanabiliyor.
- Temsilî 36 sorguluk fixture için güncel privacy-safe coverage artifact'i
  üretildi; corpus binding geçerli, label'lar review-required ve 300 eşiği
  bilinçli olarak açık durumda.
- Coverage artifact'ine corpus ve fixture parser sürüm setleri eklendi; karma
  parser provenance'ı kaynak metni taşımadan doğrudan karşılaştırılabiliyor.
- Coverage artifact'ine corpus ve fixture checksum alanları eklendi; raporun
  hangi veri paketine bağlı olduğu hash üzerinden doğrulanabiliyor.
- Coverage artifact'i fixture dosyasının gerçek SHA-256 fingerprint'iyle yeniden
  üretildi; fixture değişikliklerinin eski raporu geçersiz kılması sağlandı.
- Coverage raporu için ayrı JSON Schema ve ortak `write_fixture_coverage_report`
  writer'ı eklendi; eksik raporlar fail-closed reddediliyor.
- Repository ve paket coverage schema kopyaları strict unknown-field kontrolüyle
  hizalandı; label içermeyen hazırlık raporlarında sıfır sayaçları da sözleşmeye
  dahil edildi.
- Corpus inventory ingest ile aynı kaynak kökü ve 10 MB güvenlik sınırını kullanacak, büyük/bozuk dosyaları hash üretmeden izole edecek şekilde sertleştirildi.
- Parser, ingest, RAG citation/provenance ve concurrency primitive'leri için kalıcı regresyon testleri genişletildi; `/v1/search` parser/security metadata'sını koruyacak şekilde güncellendi.
- Harici embedding endpoint, timeout ve retry ayarları yapılandırılabilir hale getirildi; endpoint doğrulaması fail-fast yapıldı.
- RAG context’in kaynak metnini escape ederek untrusted data sınırında tuttuğu davranış kalıcı güvenlik testiyle güvence altına alındı.
- Corpus inventory, aynı ham byte içeriğine sahip kaynakları `duplicate_of` ile
  metinsiz inceleme sinyali olarak raporlamaya başladı; otomatik merge/silme yok.
- `corpus-inventory` format/hata özetleriyle, `fixture-coverage` ise 300+ sorgu
  hazırlığı ve opsiyonel label kapsamasıyla genişletildi; final `fixture-validate`
  kapısı korunuyor.
- Retrieval abstention telemetrisi (`no_candidates`, `below_min_score`) ve
  RAG'ın boş/eşik-altı/review işaretli kanıtta fail-closed generation handoff
  policy'si eklendi. Bunlar factuality/faithfulness ölçümü değildir.
- Kişisel corpus kapsamına ek bağımlılıksız `.eml` parser'ı eklendi; konu ve düz
  metin gövdesi alınırken HTML gövdesi ve ek dosyalar güvenli biçimde dışarıda
  bırakılıyor.
- Bounded concurrency probe, hata mesajlarını taşımadan exception sınıfı
  dağılımını raporlayacak şekilde güçlendirildi; kapasite ölçümünde hata kaynağı
  ayrıştırılabilir hale geldi.
- Gerçek sorgu etiketlemesini kolaylaştırmak için kaynak metni taşımayan,
  `source=derived` ve `REVIEW_REQUIRED` işaretli `fixture-label-template` CLI
  akışı eklendi; taslaklar final acceptance etiketi olarak kabul edilmiyor.
- Fixture coverage, tüm ID'ler mevcut olsa dahi derived etiketleri
  `labels_status=review-required` olarak ayırıyor; taslak etiketler artık
  `complete` gibi yorumlanamıyor.
- `fixture-label-template` CLI'ında gerçek corpus provenance'ı olmadan taslak
  üretimi engellendi; `--corpus-manifest` artık zorunlu.
- Harici embedding adapter'ına 1–256 arası yapılandırılabilir batch bölme eklendi;
  input sırası korunuyor ve retry her batch için fail-closed çalışıyor.
- External batch ayarı `.env.example` içine eklendi; ayarın yalnızca opt-in
  provider yolunda kullanıldığı netleştirildi.
- Harici embedding provider'ına ham metin saklamayan, bounded SHA-256 anahtarlı
  in-memory embedding cache eklendi; tekrar eden input'larda gereksiz provider
  çağrıları azaltılabiliyor ve kapasite `VDB_EMBEDDING_CACHE_SIZE` ile sınırlı.
- External embedding cache state erişimi eşzamanlı kullanımda `RLock` ile
  korunuyor; ağ çağrıları seri hale getirilmiyor.
- Harici embedding tek çağrı içindeki duplicate input'ları request seviyesinde
  tekilleştirip özgün sırayı koruyacak şekilde geri açıyor; cache kapalı olsa da
  gereksiz duplicate provider çağrıları azaltılıyor.
- Harici embedding provider'ı, ham input taşımayan `cache_stats` ile hit/miss,
  entry ve kapasite gözlemini sağlıyor; bu sayaçlar final kalite/maliyet ölçümü
  için gözlem yüzeyi, tek başına performans sonucu değil.
- Kişisel corpus kapsamına JSONL parser'ı eklendi; satır konumu provenance'ta
  korunuyor ve bozuk satırda kaynak dosyası fail-closed oluyor.
- JSONL parser sözleşmesi `.ndjson` suffix alias'ını da kapsıyor; yeni format
  ayrı bir source type oluşturmadan aynı satır provenance'ını kullanıyor.
- Corpus manifesti artık kaynak formatı, hata türü ve advisory duplicate
  özetlerini metin içermeden kalıcılaştırıyor; eski manifestler geriye dönük
  uyumlu biçimde kabul edilmeye devam ediyor.
- Corpus inventory/manifest akışına kaynak metni saklamayan çıkarılan karakter
  ve boş olmayan section hacmi metrikleri eklendi; bunlar extraction kalitesini
  karşılaştırma sinyali olarak kullanılacak, semantik doğruluk iddiası taşımıyor.
- DOCX parser, ZIP içi traversal, şifreli arşiv ve açılmış toplam boyut sınırı
  kontrolleriyle fail-closed hale getirildi.
- DOCX ZIP yol kontrolü Windows backslash/drive-letter, absolute path ve NUL
  karakterlerini de kapsayacak şekilde genişletildi.
- DOCX ZIP parser duplicate member ve symbolic-link üyelerini de reddediyor;
  paket içi içerik seçimi deterministik tutuluyor.
- Local Qdrant snapshot restore, duplicate/symlink/hardlink ve Windows/POSIX
  unsafe tar üyelerini extraction öncesi reddedecek şekilde sertleştirildi.
- Local snapshot restore artık device/FIFO gibi normal dosya/dizin olmayan özel
  tar üyelerini de extraction öncesi reddediyor.
- Local snapshot path doğrulaması relative `..`, boş ve `.` üyeleri de reddediyor;
  canonical path alias'larıyla oluşabilecek restore belirsizliği kapatıldı.
- Local restore geçersiz arşiv doğrulanırken mevcut Qdrant client'ı açık tutuyor;
  client yalnızca başarılı extraction sonrasında storage replacement öncesi kapanıyor.
- `fixture-coverage` komutuna opsiyonel corpus-manifest bağlama denetimi eklendi;
  stale/yanlış chunk ID'leri retrieval başlatmadan ve sorgu metni taşımadan
  raporlanıyor.
- Coverage bağlama denetimi fixture corpus checksum'ı ile güncel corpus checksum'ı
  uyuşmazlığını da privacy-safe biçimde raporlayacak şekilde güçlendirildi.
- Final fixture validator, eksik corpus checksum ile mevcut corpus checksum'ının
  uyuşmaması durumlarını ayrı ve açıklayıcı hatalarla raporlar.
- `fixture-label-template`, corpus manifest schema'sını ve chunk ID bağını
  doğrulayarak stale fixture'lar için hatalı etiket taslağı üretmiyor.
- `fixture-coverage --labels --corpus-manifest`, label relevance ID'lerindeki
  stale bağları da sayısal ve privacy-safe biçimde raporluyor.
- `corpus-inventory` CLI özeti privacy-safe extraction hacmini
  `extracted_chars` alanıyla görünür kılıyor.
- PDF parser şifreli dosyaları ve aşırı büyüyen extraction çıktısını fail-closed
  reddedecek güvenlik sınırlarıyla güçlendirildi.
- Public parser çağrıları da varsayılan kaynak boyutu sınırını uyguluyor; doğrudan
  parser kullanımı ingest dışındaki kontrolsüz büyük dosya yolunu kapatıyor.
- Export edilen `parse_text_file` yardımcı fonksiyonu da aynı boyut politikasına
  bağlandı; tüm public parser girişleri tutarlı fail-closed davranıyor.
- RAG context çıktısına aday, eklenen, bütçe nedeniyle atlanan kanıt ve kullanılan
  karakter sayaçları eklendi; context kalite ölçümü metin sızdırmadan yapılabiliyor.
- RAG generation handoff kararı context'in bütçe nedeniyle kısaltıldığını da
  `context_truncated` alanıyla bildiriyor; mevcut izin davranışı korunuyor.
- Concurrency probe'a toplam 100.000 istek bütçesi eklendi; büyük fixture/repetition
  kombinasyonlarının sınırsız iş kuyruğu oluşturması engelleniyor.
- Concurrency bütçe kontrolü iş listesi genişletilmeden önce çalışacak şekilde
  düzeltildi; limit aşımında erken bellek tahsisi de önleniyor.
- Validation skorlarından privacy-safe abstention metrikleri hesaplayan ve kalite
  tabanlarını sağlayan en yüksek eşiği seçen threshold helper'ları eklendi.
- `fixture-coverage` normalize duplicate sorguları ve split'ler arası leakage
  sinyalini metin taşımadan raporlamaya başladı; cross-split duplicate varsa
  coverage tamamlanmış sayılmıyor.
- Final fixture validation da normalize duplicate sorguları ve cross-split
  leakage'ı fail-closed reddediyor; 300 sorgu eşiği yapay tekrarlarla şişirilemiyor.
- Local Qdrant restore path güvenliği canonical tar üye kontrolüyle genişletildi;
  boş, `.` ve `..` içeren göreli yollar extraction öncesi reddediliyor. Geçersiz
  snapshot doğrulaması sırasında mevcut client yaşam döngüsü de korunuyor.
- Başarılı local snapshot restore sonrasında aynı Qdrant store client'ı yeniden
  açılıyor; restore edilen veri yeniden başlatma gerektirmeden kullanılabiliyor.
- `VDB_SOURCE_MAX_BYTES` ingest, reindex ve corpus inventory akışlarından parser'a
  aktarılıyor; özel boyut sınırı kullanılırken gizli 10 MB çakışması kaldırıldı.
- Local snapshot oluşturma sonrasında Qdrant client yeniden açılıyor; başarılı
  veya hatalı arşiv üretimi mevcut store yaşam döngüsünü kapalı bırakmıyor.
- RAG context citation ID'leri duplicate chunk'lar elendikten sonra ardışık
  üretiliyor; citation/provenance eşlemesi daha sade ve deterministik hale geldi.
- RAG context çıktısına duplicate aday sayısı eklendi; context kalite ölçümünde
  duplicate rate doğrudan raporlanabiliyor.
- Local snapshot restore staging ve rollback akışına taşındı; yeni arşivin
  kopyalanması tamamlanmadan mevcut storage silinmiyor.
- Restore staging hatası için regresyon testi eklendi; eski storage ve client
  kullanılabilirliği korunuyor.
- `/v1/search` yanıtı privacy-safe abstention nedeni, aday sayısı ve threshold
  rejection sayısını taşıyor; eski `query`/`results` alanları korunuyor.
- Harici embedding cache `0` kapasitede kapalıyken miss sayaçları artık doğru
  tutuluyor; cache istatistiği maliyet analizi için daha tutarlı.
- HTTP ingest artık yapılandırılmış `source_root` olmadan uygulama oluşturmayı
  reddediyor; dosya erişim kapsamı composition seviyesinde zorunlu.
- Kaynak kökü dışına yönlenen symlink reddi için güvenlik regresyon testi eklendi.
- Harici embedding adapter eksik vektörleri sessizce düşürmek yerine açık hata
  döndürüyor; input/output count sözleşmesi güçlendirildi.

## [0.1.0]

İlk geliştirme sürümü. Ayrıntılı kararlar için [karar günlüğü](docs/karar-gunlugu.md) ve [release politikası](docs/33-release-ve-degisiklik-politikasi.md) incelenmelidir.
- Fixture authoring akışına `fixture-merge` eklendi; sorgu shard'larında duplicate
  ID/normalize sorgu, label shard'larında duplicate ID veya provenance uyumsuzluğu
  fail-closed reddediliyor.
- Gelişim goal kabul matrisi güncel 36 sorguluk corpus-bağlı aday fixture ile
  hizalandı; eski 100 sorguluk PromtGen kaydı tarihsel smoke kanıtı olarak
  ayrıştırıldı.
- Temsilî kişisel corpus'a JSONL örneği eklendi; inventory 11 kaynak/44 chunk
  olarak yeniden üretildi ve fixture provenance yeni corpus checksum'ına bağlandı.
- Örnek veri paketi ve roadmap format listeleri JSONL/NDJSON ile EML desteğini
  ve aktif 300+ sorgu kabul kapısını yansıtacak şekilde güncellendi.
- Label shard merge provenance karşılaştırması `parser_versions` sırasını
  normalize ediyor; aynı parser kümesinin farklı JSON sırası gereksiz reddedilmiyor.
- Coverage, sağlanan `chunk_size_buckets` mapping'inin corpus'taki tüm chunk ID'lerini
  kapsamasını zorunlu kılıyor; kısmi mapping artık fail-closed mismatch üretiyor.
- XML leaf-node parser'ı domain/schema/allowlist zincirine eklendi; DTD/entity
  declaration'ları reddediliyor ve temsilî corpus XML örneğiyle 12 kaynak/45 chunk'a çıktı.
- XML parser, güvenlik ve inventory regresyonlarıyla birlikte tam testte doğrulandı;
  güncel paket `249 passed, 3 skipped, 3 warnings`.
- Mimari, V1 kapsamı, başlangıç onay formu ve örnek veri belgeleri XML desteğiyle
  hizalandı; mevcut format kapsamı artık tek biçimde listeleniyor.
- Repository ve package corpus-manifest şemaları yeniden hizalandı; tüm JSON
  şema kopyaları için semantik parity testi eklendi.
- Parser/normalizasyon rehberine XML’in leaf-node, node-path ve DTD/entity
  fail-closed sınırları eklendi.
- Fixture coverage, corpus/fixture parser sürüm kümelerini karşılaştıran
  `parser_versions_binding_status` alanını ve fail-closed mismatch kapısını aldı.
- Final audit ve roadmap, parser sürüm kümesi binding’inin kabul koşulunu açıkça
  belgeledi.
- Coverage final kapısı, corpus manifesti verildiğinde checksum veya parser
  provenance’ı bildirilmemiş raporları artık tamamlanmış saymıyor.
- Fixture sözleşmesindeki `coverage_complete` açıklaması, corpus manifesti
  verildiğinde provenance binding’inin de kapıya dahil olduğunu yansıtacak şekilde düzeltildi.
- XML source type için doğrudan document schema regression testi eklendi; tam
  regresyon paketi `250 passed, 3 skipped, 3 warnings`.
- RAG generation handoff, context bütçesi nedeniyle kanıt atlandığında artık
  `context_truncated` nedeniyle fail-closed reddediliyor; eksik kanıtla cevap
  üretimini önleyen regresyon testi ve kalite sınırı dokümanı güncellendi.
- Citation marker doğrulaması identifier sınırlarıyla sıkılaştırıldı; gömülü
  `E1` parçaları citation precision hesabına dahil edilmiyor.
- RAG marker değişikliği hedefli test ve tam regresyon paketiyle doğrulandı:
  `253 passed, 3 skipped, 3 warnings`.
- Harici embedding endpoint doğrulaması sıkılaştırıldı: uzak endpoint'lerde
  HTTPS zorunlu, HTTP yalnızca loopback test adreslerinde kullanılabiliyor.
- `CitationCheck.valid` ile citation yokluğu veya bilinmeyen marker kullanımı
  açıkça geçersiz cevap durumu olarak sunuluyor; factuality kapsamı değişmedi.
- Güncel tam regresyon paketi `254 passed, 3 skipped, 3 warnings` olarak
  doğrulandı; RAG hedefli test paketi `12 passed`.
- Embedding provider sözleşme dokümanı gerçek Protocol ile hizalandı;
  dokümanda vaat edilen ancak implementasyonda olmayan health/describe yöntemleri
  kaldırıldı.
- `.env.example` ve yapılandırma referansı harici embedding için HTTPS/loopback
  kuralı ile batch/cache ayarlarını eksiksiz açıklıyor.
- Concurrency matrix toplam istek bütçesiyle sınırlandı; seviyeler, fixture
  boyutu ve tekrar sayısı birlikte 100.000 isteği aşarsa iş başlamadan reddediliyor.
- Concurrency değişikliği test edildi; güncel tam paket `255 passed, 3 skipped,
  3 warnings`.
- Concurrency matrix'in `k` ve `repetitions` sınırları için fail-fast testleri
  eklendi; güncel tam paket `257 passed, 3 skipped, 3 warnings`.
- Model registry ve mimari karar dokümanlarındaki güncel olmayan başlangıç
  ifadeleri mevcut opt-in provider ve aktif implementasyonla hizalandı.
- Final audit, multimodal/Graph-RAG/çoklu kullanıcı açılışını ölçülebilir ihtiyaç
  sinyallerine bağlayacak şekilde netleştirildi; V1.7 varsayılan kapsamı korunuyor.
- Roadmap, concurrency matrix toplam bütçesi ve embedding endpoint güvenlik
  kuralını açıkça yansıtacak şekilde güncellendi.
- Temsilî coverage artifact'i label template'i ile yeniden üretildi; doğru
  komutta `label_provenance_status=valid`, `labels_status=review-required`,
  36 sorgu ve `coverage_complete=false` korunuyor. Labelsız komutun
  `not-provided` sonucu verdiği davranış dokümante edildi.
- Kişisel yapılandırma/export kapsamı YAML/YML ile genişletildi. Parser güvenli
  `safe_load`, deterministik JSON çıktısı ve `yaml-v1` provenance kullanıyor;
  Python-object tag'leri fail-closed reddediliyor. Şema, allowlist ve parser
  belgeleri güncellendi; hedef corpus checksum'ı yeni sentetik örnek nedeniyle
  kontrollü olarak yenilendi.
  Mevcut format sözleşmeleri değişmedi; YAML desteği sorun çıkarırsa yalnızca
  YAML dispatch/schema ekleri geri alınarak önceki corpus yolu korunabilir.
- Sentetik YAML export örneği corpus'a eklendi; inventory 13 kaynak, 46 chunk,
  19.815 karakter ve `yaml-v1` gösteriyor. Fixture provenance yeni checksum'a
  bağlandı; coverage binding geçerli, final coverage hâlâ 36/300 ve review-required.
- Benchmark sonuçlarına fixture/corpus checksum ve embedding manifest kimliği
  eklendi; CLI bunları otomatik bağlıyor. Alanlar optional bırakılarak eski
  Python çağrıları korunuyor. Benchmark/CLI hedefli doğrulama `79 passed`.
- YAML ve benchmark provenance değişiklikleri sonrası tam regresyon
  `260 passed, 3 skipped, 3 warnings` ile tamamlandı; Docker/runtime skip'leri
  final turuna bırakıldı.
- Concurrency probe/matrix sonuçlarına da fixture/corpus/model provenance
  alanları eklendi; CLI ve eski mock provider uyumluluğu korundu. Tam regresyon
  `261 passed, 3 skipped, 3 warnings` ile doğrulandı.
- Benchmark ve concurrency result writer'larına canonical JSON Schema doğrulaması
  eklendi; bozuk/eksik privacy-safe artefact'ler artık diske yazılmıyor.
- Bozuk metric değerleri için writer fail-closed regresyonları eklendi; tam paket
  `263 passed, 3 skipped, 3 warnings` ile doğrulandı.
- Tekrarlı benchmark ve concurrency matrix aggregate'leri farklı
  fixture/corpus/model provenance'larını birleştirmeyi reddediyor; tam paket
  `265 passed, 3 skipped, 3 warnings` ile doğrulandı.
- Temsilî fixture final validator'ı `status=contract-only` nedeniyle beklenen
  exit code 2 ile reddetti; final 300+ veri/etiket kapısı bilinçli olarak açık.
- Temel RTF parser desteği (`rtf-v1`) allowlist, canonical source schema,
  corpus dokümantasyonu ve regresyon testlerine eklendi; embedded object/macro
  ve stil semantiği kapsam dışı bırakıldı.
- RTF değişikliği sonrası tam regresyon `267 passed, 3 skipped, 3 warnings`;
  Docker/Qdrant dış runtime skip'leri final ölçüm turuna bırakıldı.
- RTF parser metadata/object gruplarını nested biçimde atlayacak ve dengesiz
  grup yapısını fail-closed reddedecek şekilde güçlendirildi; hex dönüşüm yolu
  da temizlenmiş metne bağlandı. Tam regresyon `269 passed, 3 skipped, 3 warnings`.
- Sentetik RTF corpus örneği eklendi; inventory 14 kaynak, 47 chunk ve 19.961
  karaktere çıktı. Corpus manifesti, fixture manifesti, label template'i ve
  coverage artifact'i `rtf-v1` ile yeni checksum'a yeniden bağlandı.
- Abstention threshold değerlendirmesi non-numeric ve boolean score/threshold
  değerlerinde fail-closed davranacak şekilde güçlendirildi; tam regresyon
  `270 passed, 3 skipped, 3 warnings`.
- RAG generation handoff'u context text, used-character ve citation/evidence
  count invariant'larını doğrulayacak şekilde fail-closed güçlendirildi;
  tutarsız context için `invalid_context` kararı ve regresyon testi eklendi.
  Tam regresyon `271 passed, 3 skipped, 3 warnings`.
- Harici embedding endpoint yanıtları için 64 MB sınırlı okuma eklendi;
  oversized body fail-closed reddediliyor. Tam regresyon `272 passed, 3 skipped,
  3 warnings`; gerçek API çağrısı yapılmadı.
- Harici embedding yanıtındaki `index` ve vektör koordinatları artık JSON türü
  bakımından sıkı doğrulanıyor; boolean/sayısal metin coercion'ı reddediliyor.
  Adapter hedefli testler `16 passed`, tam regresyon `276 passed, 3 skipped,
  3 warnings`; gerçek API çağrısı yapılmadı.
- HTML görünür metin filtresi, eşleşmeyen kapanış etiketlerinin filtreyi erken
  kapatmasını ve bozuk iç içe atlanan etiketlerin sonraki metni yutmasını
  engelleyecek tag-aware yığınla `html-v4` olarak sertleştirildi. Corpus ve
  fixture parser provenance'ı yeniden bağlandı; parser hedefli HTML testleri
  `3 passed`. Uzun/tam regresyon final turuna bırakıldı.
- Kişisel corpus inventory/manifest varsayılanları izlenmeyen `data/derived/`
  ve `data/manifests/` konumlarına alındı; böylece kullanıcıya ait yol/hash/chunk
  metadata'sı benchmark fixture'larını veya Git'te izlenen örnekleri yanlışlıkla
  ezmiyor.
- DOCX `docx-v4`, paragraf/tablo hücresi içindeki Word sekme ve açık satır
  sonlarını koruyor ve iç içe tablo içeriğini üst hücrede yinelemiyor;
  ayrıca ana belge ve core-properties XML'inde DTD/entity declaration'larını
  reddediyor. Eski DOCX kayıtları yeni parser provenance'ı için yeniden
  indekslenmelidir.
- PDF parser entegrasyonu, kişisel belge gerektirmeyen gerçek bir sentetik PDF
  ile `pypdf` smoke testinde doğrulanıyor; bu, çeşitlendirilmiş corpus kalite
  incelemesinin yerine geçmiyor.

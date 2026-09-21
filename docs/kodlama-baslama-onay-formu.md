# Kodlamaya Başlama Onay Formu

Bu belge, uygulama koduna geçmeden önce teknik kararların, örnek verinin ve kabul ölçütlerinin tek yerde doğrulanması için kullanılır. Bir madde **Onaylandı** durumuna gelmeden ilgili uygulama kararı kalıcılaştırılmaz.

## A. V1 kapsamı

| Karar | V1 durumu | Not |
|---|---|---|
| Kullanım modeli | Onaylandı | Kişisel, tek kullanıcı, `owner_id = me` |
| Çalışma ortamı | Onaylandı | Local-first, tek makine |
| Vector backend | Önerilen | Qdrant; adapter arkasında |
| İlk dikey dilim | Onaylandı | Markdown/TXT → chunk → embedding → Qdrant → exact/HNSW |
| V1 arama | Onaylandı | Dense-only |
| V1 format kapsamı | Kademeli | Markdown/TXT, PDF, DOCX, HTML, EML, JSON, JSONL/NDJSON, CSV ve XML; OCR/karmaşık düzen kapsam dışı |
| V1 dışı | Onaylandı | Hybrid, multi-vector, reranking, multimodal, Graph-RAG, sharding |

## B. Kod öncesi kararlar

- [x] Python sürümü ve paket yönetimi seçildi (`.python-version`, `pyproject.toml`, `uv.lock`).
- [x] Qdrant'ın local çalışma ve veri klasörü politikası belirlendi (`path:qdrant_storage`, Docker server alternatifi).
- [x] İlk local embedding modeli seçildi ve gerçek model smoke testi yapıldı (`multilingual-e5-base`, 768 dim).
- [x] Harici embedding provider için adapter sözleşmesi ve veri paylaşımı sınırı onaylandı; V1'de local provider varsayılandır.
- [x] Embedding dimension, distance metric ve normalization kararı kaydedildi (`768`, cosine, normalized).
- [x] Document/chunk/point ID üretimi ve checksum politikası testlerle doğrulandı.
- [x] Collection adı, named vector politikası ve payload indeksleri belirlendi.
- [x] Ingest, search, delete ve reindex API'leri gerçek V1 OpenAPI sözleşmesiyle uyumlu.
- [x] Secrets ve loglarda kişisel veri politikası belirlendi; güvenli hata envelope'u ham path/input sızdırmıyor.

## C. Veri ve benchmark hazırlığı

- [x] Güvenli örnek fixture hazır (`data/sources/README.md`, parser/ingest test fixture'ları).
- [x] En az 30 gerçekçi sorgu hazır (`data/benchmarks/queries.json`, 30 kayıt).
- [x] Sorgular `semantic`, `exact_identifier`, `typo`, `morphology`, `long_context` ve `negative` sınıflarına ayrıldı.
- [x] Her sorgu için beklenen chunk kümesi işaretlendi (`relevant_chunk_ids`).
- [x] Exact baseline ölçüm prosedürü yazıldı (`docs/09-benchmark-ve-reindex-stratejisi.md`) ve kod karşılığı mevcut.
- [x] Recall@k, MRR/nDCG, p50/p95/p99 ve hata oranı için ilk eşikler belirlendi (`docs/25-kapasite-slo-hedefleri.md`).
- [x] Aynı girdinin tekrar ingest edilmesi ve belge güncelleme/silme senaryoları testlerle doğrulandı.

## D. İşletim ve güvenlik

- [x] Snapshot, restore ve rollback prosedürü local persistence üzerinde denendi; Docker server snapshot smoke testi Qdrant `v1.19.0` ile geçti.
- [x] Model/chunking/parser değişiminde re-index prosedürü yazıldı.
- [x] Path traversal, zararlı dosya, prompt injection ve metadata sızıntısı kontrolleri tehdit modelinde tanımlı ve ilgili güvenlik kontrolleri testli.
- [x] Structured log, health check ve temel benchmark metrikleri tanımlı.
- [x] Dependency pinleme ve release checklist hazır.

## E. RAG entegrasyon sözleşmesi

Vektörel veritabanı RAG sisteminin **retrieval katmanı** olarak kullanılacaktır. LLM/generation katmanı ayrı tutulur.

```text
RAG query → normalize → embedding → filtered retrieval → optional rerank
→ context packing → LLM generation → answer + citations/provenance
```

Arama sonucu en az `document_id`, `chunk_id`, kaynak URI/path, başlık, chunk metni, score, retrieval aşaması, embedding manifest'i ve erişim metadata'sını döndürmelidir. Böylece aynı retrieval API'si farklı LLM ve citation akışlarıyla kullanılabilir. Retrieval sonucu kanıt olarak taşınır; kaynak metni LLM talimatı olarak güvenilmez.

## F. Son onay

- [x] Tüm V1 kararları karar günlüğüne işlendi.
- [x] Dokümanlar arası çelişki kalmadı. *(Açık kalan sorgu sınıfı maddesi bilinçli olarak ayrıştırılmıştır.)*
- [x] Şemalar ve OpenAPI doğrulandı.
- [x] Benchmark fixture ve sorgu seti hazır.
- [x] İlk dikey dilimin kabul kriterleri ölçülebilir.
- [x] Kodlamaya başlama onayı verildi; üretim geçiş kapıları ayrıca korunuyor.

Bu formdaki son onay verilmeden üretim kodu, kalıcı collection migration'ı veya ileri retrieval özelliği uygulanmaz.

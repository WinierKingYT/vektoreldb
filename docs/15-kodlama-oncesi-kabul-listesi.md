# 15. V1 geçiş kabul listesi

V1 uygulaması ve üretim geçişi için aşağıdaki karar, sözleşme ve doğrulama maddeleri geçerli kabul kapısıdır:

- [x] İlk veri türleri ve desteklenmeyen tür davranışı net.
- [x] Ortak parser çıktısı ve metadata şeması net.
- [x] Embedding provider sözleşmesi ve manifest alanları net.
- [x] Local/harici veri paylaşımı kararı ve gizlilik sınırı net.
- [x] Qdrant koleksiyon, mesafe ve indeks yaklaşımı net.
- [x] Ingest/search/delete API sözleşmeleri net.
- [x] Yetki filtresi sunucu tarafında zorunlu.
- [x] En az 30 gerçekçi benchmark sorgusu hazır.
- [x] Kabul metrikleri ve regression eşiği belirli. (`docs/25-kapasite-slo-hedefleri.md`)
- [x] Backup/restore ve rollback prosedürü yazılı.
- [x] İlk kapasite ve maliyet varsayımları kayıtlı.
- [x] Dokümanlar arası terim ve karar tutarlılığı kontrol edildi.
- [x] JSON Schema ve OpenAPI sözleşmeleri doğrulandı.
- [x] Yapılandırma, geliştirici kurulum ve release politikası hazır.
- [x] Güvenli örnek fixture ve en az 30 benchmark sorgusu hazır.

## Açık geçiş koşulları

- [x] Local-first Qdrant storage için snapshot/restore ve checksum round-trip testi geçti.
- [x] Gerçek Docker server Qdrant üzerinde payload index ve snapshot/restore smoke testi geçti (`2 passed`, Qdrant `v1.19.0`, named volumes).
- [x] Kullanıcının sağladığı gerçek proje corpus'u (PromtGen README) ile 30 sorguluk benchmark çalıştırıldı; Recall/latency ve negative eşik karşılaştırması karar günlüğüne işlendi. Eşik kararı daha geniş corpus için provisional'dır.

İlk gerçek corpus benchmark koşulu tamamlanmıştır. Daha geniş ve domain çeşitliliği yüksek kişisel corpus geldiğinde eşik kararı yeniden ölçülebilir; bu, mevcut V1 geçişini bloke etmez. Docker server smoke koşulu tamamlanmıştır.

## Mevcut kanıt matrisi

Bu tablo V1 geçişinin tarihsel kanıtlarını içerir; ileri seviye yükseltme
goal'unun güncel kabul durumu aşağıdaki ayrı bölümde tutulur.

| Gereksinim | Kanıt |
|---|---|
| Plain-text/Markdown alias parser, normalizasyon ve provenance | `tests/test_plain_text_parser.py`, `tests/test_parsers.py`, `tests/test_ingest.py`, `tests/test_chunking.py` |
| Deterministic ID ve idempotent ingest/reindex | `tests/test_ingest.py`, `tests/test_api.py` |
| Local embedding provider ve model sözleşmesi | `tests/test_local_embeddings.py`, gerçek offline local smoke kaydı |
| Qdrant local persistence, filtreli retrieval ve HNSW yolu | `tests/test_qdrant_memory.py`, `tests/test_retrieval.py`, `src/personal_vector_db/storage/qdrant.py` |
| Exact baseline ve benchmark metrikleri | `tests/test_benchmark.py`, `data/benchmarks/queries.json` |
| Ingest/search/delete/reindex API ve güvenli hata zarfı | `tests/test_api.py`, `tests/test_security.py` |
| Snapshot/restore ve checksum | `tests/test_qdrant_memory.py`, `tests/test_qdrant_backup_adapter.py` |
| Server payload index ve server snapshot/restore | `tests/test_qdrant_server_integration.py` (`2 passed`, Docker Qdrant `v1.19.0`) |
| V1 tarihsel son kalite kapısı | `98 passed, 2 skipped` + Docker entegrasyonunda `2 passed`; Ruff ve `uv lock --check` başarılı |
| Release değişiklik kaydı | `CHANGELOG.md`, `docs/33-release-ve-degisiklik-politikasi.md` |

## İleri seviye goal güncel durumu

- [x] Geniş format parser dispatch'i, privacy-safe corpus inventory ve provenance manifesti.
- [x] 300+ sorguya uygun fixture, label ve corpus-binding sözleşmesi.
- [x] Bounded concurrency/capacity probe altyapısı.
- [x] Negative sorgu abstention ve opt-in skor eşiği telemetrisi.
- [x] RAG context, citation/provenance ve generation handoff sınırı.
- [x] Opt-in harici embedding adapter'ı, retry/backoff ve bounded cache.
- [ ] Gerçek kişisel corpus üzerinde 300+ manuel etiketli sorgu fixture'ı.
- [ ] Uzun süreli benchmark, kapasite matrisi ve eşik kalibrasyonu.
- [ ] Ölçülmüş ihtiyaç olmadan multimodal/Graph-RAG/çoklu kullanıcı kapsamı açılmayacak.

İleri seviye goal'un güncel tam test kanıtı `276 passed, 3 skipped, 3 warnings`;
bu sonuç gerçek kişisel corpus ve uzun süreli ölçüm koşullarının yerine geçmez.

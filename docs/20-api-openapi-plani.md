# 20. API/OpenAPI ayrıntı planı

## Hedef endpoint özeti (roadmap)

| Method | Path | Başarı |
|---|---|---|
| POST | `/v1/documents:ingest` | `202 Accepted` (V1'de işlem çağrı içinde tamamlanır) |
| POST | `/v1/documents/{document_id}:reindex` | `202 Accepted` |
| POST | `/v1/search` | `200 OK` |
| DELETE | `/v1/documents/{document_id}` | `202 Accepted` |

Mevcut V1, ingest/reindex için `file_ref` alır ve idempotent deterministic kimlik kullanır; `Idempotency-Key`, `content` ingest'i ve async iş kuyruğu sonraki sürüm planıdır.
HTTP ingest yalnızca yapılandırılmış bir `source_root` ile uygulamaya bağlanır;
rootsuz library ingest mümkün olsa da HTTP composition'ında fail-closed reddedilir.

## HTTP hata kodları

`400` şema/filtre hatası, `401` kimlik doğrulama, `403` erişim, `404` belge yok, `409` idempotency çakışması, `413` boyut sınırı, `429` kota, `422` parse/validation, `500` beklenmeyen hata, `503` provider/Qdrant erişilemezliği.

## Arama

`top_k` 1–50 aralığındadır. Retrieval mode istemciye açılmaz; sunucu yapılandırması
ile dense, opt-in hybrid, late-interaction veya quantized yol seçilir. Arama
isteği allowlist filtreleri (`document_ids`, `source_uris`, `source_types`,
`titles`) ve yapılandırılmış rerank talebi taşıyabilir. `min_score` varsayılan
sabit değildir; model/metric ve benchmark'tan gelir.

Yanıt `query` ve `results` alanlarına ek olarak privacy-safe abstention tanısı
taşır:

| Alan | Anlam |
|---|---|
| `abstention_reason` | Yalnızca `none`, `no_candidates` veya `below_min_score` |
| `candidate_count` | Eşik uygulanmadan önceki retrieval aday sayısı |
| `threshold_rejected_count` | `min_score` nedeniyle elenen aday sayısı |

`results=[]` tek başına “veri yok” anlamına gelmez; istemci bu alanlarla aday
bulunamadığını ve adayların eşik altında kaldığını ayırmalıdır. Bu alanlar ham
sorgu veya kaynak metni taşımaz.

## Pagination ve partial failure (roadmap)

Arama sayfalaması için opaque `next_cursor` kullanılır. Batch ingest cevabı her belge için ayrı durum ve hata döndürür; tek hatalı dosya başarılı dosyaları geri almaz.

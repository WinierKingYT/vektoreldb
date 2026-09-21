# 28. JSON Schema kullanım rehberi

Makine tarafından doğrulanabilir sözleşmeler `schemas/` altında tutulur:

- `document.schema.json`: kaynak belge kaydı
- `chunk-payload.schema.json`: Qdrant payload kaydı
- `benchmark-result.schema.json`: tekil/repeated retrieval benchmark sonucu
- `concurrency-result.schema.json`: worker seviyesi kapasite sonucu

Şema kuralları:

- Tarihler ISO-8601 UTC.
- `owner_id` V1'de yalnızca `me`.
- `source_type` sınırlı enum.
- Hash biçimi `sha256:<64 hex karakter>`.
- Bilinmeyen alanlar sessizce kabul edilmez.

Şema değişirse karar günlüğü, örnek fixture'lar ve OpenAPI birlikte güncellenir.
Benchmark ve concurrency writer'ları ilgili şemayı diske yazmadan önce uygular.
Geriye dönük uyumsuz değişiklik yeni schema version ve migration gerektirir.

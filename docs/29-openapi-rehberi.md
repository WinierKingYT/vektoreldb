# 29. OpenAPI kullanım rehberi

Kanonik API sözleşmesi kökteki [openapi.yaml](../openapi.yaml) dosyasıdır. Markdown açıklaması ile YAML çelişirse YAML ve karar günlüğü güncellenir.

## Zorunlu kurallar

- V1 ingest, reindex ve delete endpoint'leri mevcut sözleşmedeki `file_ref` ve deterministic ID davranışını izler.
- Arama alanları `query`, `top_k`, `min_score`, allowlist filtreleri ve `rerank`
  ile sınırlıdır; `top_k` 1–50 arasındadır. Retrieval mode istemci tarafından
  seçilmez, sunucu yapılandırmasından gelir.
- `min_score` sonlu bir sayı olmalı ve cosine sözleşmesi gereği `-1`–`1` aralığında kalmalıdır.
- `query` 1–4.000, `file_ref` 1–4.096 karakter aralığındadır; bu sınırlar OpenAPI ve Pydantic doğrulamasında aynıdır.
- Auth ve owner filtresi sunucu tarafındadır.
- `Idempotency-Key`, `content` ingest'i, istemciye açık `retrieval_mode`, sayfalama
  ve genişletilmiş iş durumları roadmap kapsamındadır; uygulanmadan V1 alanı gibi
  belgelenmez.

OpenAPI doğrulaması CI aşamasında yapılır; endpoint, model veya hata kodu değişikliği önce sözleşme testleriyle kontrol edilir.

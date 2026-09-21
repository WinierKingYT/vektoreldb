# 18. Belge yaşam döngüsü

```text
discovered → parsing → parsed → embedding → indexed → active
                         ↘ failed
active → stale → reindexing → active
active → archived → deleted
```

## Kimlik kuralları

- `document_id`: normalize edilmiş kaynak URI için stabil mantıksal kimliktir.
- `content_hash`: ham içerik checksum'ıdır; içerik değişince değişir.
- `chunk_id`: document id + chunk index + chunking version + chunk metninin SHA-256 özeti üzerinden deterministik üretilir. Böylece içerik değiştiğinde yeni chunk kimliği oluşur; aynı içerik tekrar işlendiğinde kimlik korunur.
- İçerik değiştiğinde aynı document id korunur. Reindex'te yeni chunk'lar önce upsert edilir; ardından eski `content_hash`'li chunk'lar temizlenir. Böylece güncelleme sırasında boş arama penceresi azaltılır.

## İdempotency

Aynı `source_uri + content_hash + parser_version + chunking_version + embedding_manifest_id` tekrar işlenirse işlem no-op veya güvenli upsert olur. Yarıda kalan işlem tamamlanmadan belge `active` yapılmaz.

## Silme

Silme; kaynak kaydı, tüm chunk'lar, cache, aktif alias ve saklama süresi dolan snapshot'lar için izlenir. Silme listesi restore sonrasında yeniden uygulanır.

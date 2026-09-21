# 10. API sözleşmesi

Bu sözleşme uygulama katmanı ile retrieval/indexing katmanlarını ayırır. V1 için alan adları ve hata davranışı sabittir.

## Ingest

`POST /v1/documents:ingest`

İstek: `file_ref` desteklenir. Kaynak dosya, izin verilen source root altında
`.md`, `.markdown`, `.txt`, `.org`, `.rst`, `.log`, `.tex`, `.ics`, `.pdf`, `.docx`, `.html`, `.htm`, `.eml`, `.json`, `.jsonl`, `.ndjson`, `.yaml`, `.yml`, `.toml`, `.rtf`, `.csv` veya `.xml`
olmalıdır. Dosya boyutu ve parser kalite sınırları [parser kalite standardı](22-parser-kalite-ve-sinirlari.md)
ile belirlenir.

Cevap: `document_id`, `status`, `chunk_count`, `embedding_manifest_id`.

## Search

`POST /v1/search`

İstek:

```json
{
  "query": "hangi notta ...?",
  "top_k": 8,
  "min_score": null
}
```

Cevap her sonuç için `document_id`, `chunk_id`, `text`, `score`, `source_uri`, `location`, `heading_path`, `title`, `embedding_manifest_id`, `retrieval_stage`, `parser_version`, `document_status` ve `security_flags` taşır. `source_uri`, `location`, `heading_path` ve bu provenance alanları RAG katmanının citation/provenance temelidir; kaynak metni talimat olarak çalıştırılmaz.

Dense retrieval varsayılandır; hybrid, late-interaction, quantized ve reranking
opt-in uygulama ayarlarıyla kullanılabilir. API, `document_ids`, `source_uris`,
`source_types`, `titles` ve `rerank` alanlarını destekler; sahiplik ve durum
filtreleri sunucu tarafından eklenir. Filtre alanları allowlist dışındaki
anahtarları kabul etmez.

`min_score`, cosine skor sözleşmesi nedeniyle sonlu ve `-1` ile `1` arasında olmalıdır; verilmezse sonuçlar skor eşiği olmadan döner.

`query` en fazla 4.000 karakter, `file_ref` en fazla 4.096 karakter olabilir; sınırlar embedding maliyetini ve istek kötüye kullanımını kontrol eder.

## Delete/reindex

- `POST /v1/documents/{document_id}:reindex`: verilen `file_ref` kaynağını yeniden işler.
- `DELETE /v1/documents/{document_id}`: tüm ilişkili chunk'ları kaldırır.

## Hata sözleşmesi

Hatalar `{code, message, retryable, request_id, details}` biçimindedir. V1 validation/route hataları güvenli ortak kodlar kullanır; beklenmeyen provider veya storage hataları istemciye ayrıntı sızdırmadan `internal_error` olarak döner. Ham hassas içerik hata mesajına yazılmaz.

V1 HTTP katmanı validation hatalarını `validation_error`, route içi kontrollü hataları `request_error` koduyla bu envelope içinde döndürür; `request_id` her yanıtta yeni üretilir. Ham kaynak yolu ve içerik hata mesajına eklenmez.

## Sınırlar

İstek gövdesi, dosya boyutu, `top_k`, batch boyutu, timeout ve rate limit için sunucu tarafı üst sınırları vardır. Kullanıcının verdiği filtre alanları allowlist ile doğrulanır.

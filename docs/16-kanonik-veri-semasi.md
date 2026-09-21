# 16. Kanonik veri şeması

Tüm parser, API, manifest ve Qdrant payload alanları bu sözleşmedeki isimleri kullanır.

## Belge

```json
{
  "document_id": "doc_01J...",
  "source_uri": "file:///vault/notlar.md",
  "source_type": "markdown",
  "title": "Notlar",
  "owner_id": "me",
  "visibility": "private",
  "document_status": "active",
  "content_hash": "sha256:...",
  "parser_version": "markdown-1",
  "created_at": "2026-09-12T00:00:00Z",
  "updated_at": "2026-09-12T00:00:00Z"
}
```

## Chunk

Zorunlu alanlar: `chunk_id`, `document_id`, `chunk_index`, `text`, `heading_path`, `location`, `token_count`, `content_hash`, `chunking_version`, `embedding_manifest_id`.

`owner_id` erişim alanıdır; istemciden gelen metadata bunu değiştiremez. İlk sürümde `tenant_id` kullanılmaz. Çok kullanıcılı mimariye geçilirse ayrı bir karar kaydıyla eklenir.

## Kanonik alan adları

`source_type` dosya türüdür, `mime_type` teknik içerik türüdür; `dimensions` embedding manifest'inde, `embedding_dimensions` ise kullanılmaz. Zaman alanları ISO-8601 UTC'dir.

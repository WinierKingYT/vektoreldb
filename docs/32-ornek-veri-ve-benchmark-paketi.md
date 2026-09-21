# 32. Örnek veri ve benchmark paketi

## Fixture seti

En az şu güvenli örnekler hazırlanır:

- başlık ve alt başlık içeren Markdown
- Türkçe karakter içeren TXT
- metin sırası ve sayfa numarası kontrol edilen PDF
- DOCX paragraf ve tablo
- gereksiz menü/footer içeren HTML
- JSON/JSONL kayıtları, NDJSON satırları, CSV başlıkları, XML leaf-node'ları ve düz metin EML gövdesi
- boş, bozuk encoding'li ve desteklenmeyen dosya

## Benchmark satır formatı

```json
{
  "query_id": "q-001",
  "text": "...",
  "relevant_chunk_ids": ["document-id_chunk_hash"],
  "query_type": "semantic"
}
```

Filtreli V1.4 deneylerinde isteğe bağlı `filters` alanı kullanılabilir. Yalnızca
`document_ids`, `source_uris`, `source_types` ve `titles` listeleri kabul edilir;
örneğin `"filters": {"source_types": ["markdown"]}`. Sahiplik ve durum
filtreleri fixture tarafından belirlenemez.

V1 benchmark loader'ı bu alanları strict doğrular: `query_id`, `text`, `relevant_chunk_ids` ve isteğe bağlı `query_type`. `query_type` değerleri `semantic`, `exact_identifier`, `typo`, `morphology`, `long_context` veya `negative` olabilir. `negative` sorgularında `relevant_chunk_ids` boş olmalıdır. `relevance_grade`, `language` ve document-level etiketler ileri değerlendirme şemasına ayrılmıştır ve V1 fixture'ına eklenmemelidir.

Gerçek hassas veri benchmark'a kopyalanmaz. Veri seti retrieval değerlendirmesi
ile LLM cevap değerlendirmesini ayrı tutar. İlk smoke kabulü en az 30 sorgudur;
aktif final sözleşmesi en az 300 sorgu ve her query type için en az 30 sorgudur.

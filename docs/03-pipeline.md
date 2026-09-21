# 3. İçe aktarma, chunking ve sorgu sözleşmesi

## Chunking

Başlangıç kuralı: başlıkları koruyan 400–800 token parçalar, %10–15 overlap. Bu yalnızca başlangıç hipotezidir; gerçek sorgu setiyle ölçülmelidir. PDF tablo/sütunları, OCR, listeler ve kod için ayrı parser/chunking politikaları kullan; her chunk kaynak konumuna geri izlenebilsin.

- Parçayı cümle veya paragraf ortasında kesme.
- Başlık, bölüm yolu ve sayfa/konum bilgisini payload'a ekle.
- Çok kısa parçaları birleştir; çok uzun tabloları ayrı ele al.
- Kaynakta değişen bölümün checksum'ını bulup yalnızca ilgili chunk'ları güncelle.
- Boş, tekrar eden, aşırı kısa veya token sınırını aşan parçaları hata/uyarı olarak işaretle.

## Ingest sözleşmesi

Her kayıt için: `source_uri`, `content_hash`, `document_id`, `chunk_id`, `embedding_manifest_id`, `parser_version`, `chunking_version` ve `updated_at` zorunludur. Parser hataları sessizce atlanmaz; hata kuyruğuna yazılır.

## Hedef sorgu sözleşmesi (roadmap)

Aşağıdaki örnek, filtre ve reranking desteklendiğinde hedeflenen genişletilmiş sözleşmedir; mevcut V1 HTTP API'si yalnızca `query`, `top_k` ve `min_score` kabul eder.

```json
{
  "query": "...",
  "top_k": 8,
  "filters": {"language": "tr", "tags": ["teknik"]},
  "min_score": null,
  "rerank": true
}
```

Mevcut V1 API skor, kaynak kimliği, başlık, metin, konum, embedding manifest'i ve retrieval aşamasını döndürür. `top_k` için üst sınır koy; kullanıcı filtresini doğrudan sorgu diline birleştirme.

## Hybrid ve reranking

Özel isimler, kodlar ve exact terimler için lexical aramayı semantic aramayla birleştirmek faydalıdır. Reranker yalnızca ilk aday kümesine uygulanmalı; latency ve maliyeti ölçülmelidir.

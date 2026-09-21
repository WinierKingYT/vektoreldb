# 1. Mimari ve veri modeli

## Amaç ve kapsam

Uzun vadeli hedef; PDF, Markdown, web çıktısı, kişisel not, DOCX, EML, JSON,
JSONL/NDJSON, CSV ve XML kaynaklarında semantik arama ve kaynaklı RAG'tır.
Mevcut geliştirme diliminde bu türler için suffix-dispatch parser'ları vardır;
OCR, karmaşık tablo/sütun ve kod araması sonraki kalite/araştırma alanlarıdır.
Öncelik tek kullanıcı, özel veri ve düşük işletim yüküdür.

## Hedef mimari

`Kaynaklar → ayrıştırma → chunking → embedding → vektör deposu → filtreli arama → rerank/RAG`

İlk dağıtım tek makinede Qdrant + Python istemcisidir. Qdrant noktaları bir vektör ve JSON payload içerir; koleksiyon boyut ve mesafe metriğini sabitler. FAISS yalnızca yerel, RAM ağırlıklı prototip için; pgvector ise mevcut PostgreSQL, SQL/ACID ve ilişkisel join ihtiyacı baskınsa tercih edilir.

## Nokta şeması

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "vector": "[embedding vector; size is defined by the manifest]",
  "payload": {
    "document_id": "stable-document-id",
    "chunk_id": "chunk-0007",
    "text": "...",
    "source_uri": "file:///.../notlar.md",
    "title": "Başlık",
    "mime_type": "text/markdown",
    "language": "tr",
    "created_at": "2026-09-12T00:00:00Z",
    "content_hash": "sha256:...",
    "embedding_model": "model-name@version",
    "embedding_manifest_id": "local-model-revision-1",
    "tags": ["kişisel", "teknik"],
    "visibility": "private"
  }
}
```

`document_id + chunk_id` deterministik olmalı; yeniden indeksleme upsert ile idempotent çalışmalıdır. Orijinal dosya ve işlenmiş metin vector DB dışında da korunmalı; vector DB tek doğruluk kaynağı değildir. Model veya chunking değişirse eski ve yeni indeksleri karıştırma.

## Index manifest

Her koleksiyonla birlikte embedding model adı/sürümü, boyut, mesafe, normalizasyon, parser ve chunking sürümü, oluşturulma tarihi, kaynak snapshot/checksum'ı ve benchmark sonucu saklanır.

## Arama akışı

1. Sorgunun dilini ve erişim kapsamını belirle.
2. Sorguyu aynı embedding modeliyle vektöre çevir.
3. Yetki/metadata filtresini aramaya dahil et.
4. İlk `k` adayını al; gerekirse lexical arama veya reranker ile yeniden sırala.
5. Minimum skor ve kaynak çeşitliliği koşullarını uygula.
6. Sonuç yoksa bunu açıkça bildir; düşük skorlu metni gerçekmiş gibi üretme.

Qdrant dokümantasyonuna göre payload indeksleri filtreli aramayı hızlandırır ve mümkünse veri yüklenmeden önce oluşturulmalıdır. HNSW yaklaşık aramadır; `ef_search` yükseldikçe recall genellikle artar, gecikme ve bellek maliyeti de artabilir.

# 17. Qdrant koleksiyon şeması

## V1: dense-only

İlk koleksiyon yalnızca tek dense vektör kullanır. Qdrant point ID'si UUID veya unsigned integer olmalıdır; bileşik mantıksal kimlik point ID olarak kullanılmaz. Önerilen üretim: `UUIDv5(namespace, document_id + ":" + chunk_id)`.

Mantıksal `document_id` ve `chunk_id` payload'da tutulur; bu sayede belge güncelleme/silme işlemleri filtre ile yapılabilir.

Reindex değişimi `replace_document` sözleşmesini izler: yeni point'ler önce upsert edilir, ardından aynı `document_id` altındaki eski `content_hash`'li point'ler temizlenir. Yeni backend'ler bu sıralamayı korumalıdır.

V1 uyumluluk manifest'i iki kaynaktan doğrulanır: collection config `vector_size` ve `distance` değerlerini, point payload'ları ise `embedding_manifest_id` değerini taşır. Adapter mevcut point'leri tarayıp aktif provider manifest'iyle eşleşmeyen veya manifest'i eksik point'leri reddeder. `parser_version`, `chunking_version` ve oluşturulma zamanı payload/backup manifest'inde tutulur; bunlar değişirse kontrollü re-index gerekir.

## Filtre indeksleri

V1'de uygulama tarafından `document_id`, `owner_id`, `document_status`, `source_uri`, `source_type` ve `title` payload indeksleri oluşturulur. Her sorguya sunucu tarafında `owner_id = me` ve `document_status = active` koşulları eklenir. `source_type`, `source_uri` ve `title` kullanıcı allowlist filtresi olarak kullanılabilir; `language` ve `tags` bu sürümde filtre sözleşmesinde yoktur.

## V2: hybrid hazırlığı

Sparse veya multi-vector eklenmesi mevcut vektör konfigürasyonuyla karıştırılmaz; yeni koleksiyon ve tam re-index gerekir. V2'de named vectors (`dense`, `sparse`, gerekirse `late`) ayrı manifest ile tanımlanır. [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)

Qdrant point kimlikleri UUID/unsigned integer ile sınırlıdır. [Qdrant Points](https://qdrant.tech/documentation/manage-data/points/)

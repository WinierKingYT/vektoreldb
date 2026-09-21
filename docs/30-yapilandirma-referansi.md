# 30. Yapılandırma referansı

| Değişken | Örnek | Açıklama |
|---|---|---|
| `VDB_QDRANT_URL` | `path:qdrant_storage` | Qdrant endpoint'i veya local persistence yolu |
| `VDB_COLLECTION_NAME` | `personal_documents_v1` | Aktif koleksiyon |
| `VDB_RETRIEVAL_MODE` | `dense` veya `hybrid` | Dense V1 baseline; `hybrid` V1.2 deney yolu |
| `VDB_HYBRID_COLLECTION_NAME` | `personal_documents_hybrid_v1` | Hybrid named-vector koleksiyonu |
| `VDB_LATE_COLLECTION_NAME` | `personal_documents_late_v1` | V1.5 multi-vector late-interaction koleksiyonu |
| `VDB_QUANTIZED_COLLECTION_NAME` | `personal_documents_quantized_v1` | V1.6 quantized dense koleksiyonu |
| `VDB_EMBEDDING_PROVIDER` | `local` | Embedding sağlayıcısı |
| `VDB_EMBEDDING_MODEL` | `intfloat/multilingual-e5-base` | Model adı |
| `VDB_EMBEDDING_REVISION` | `d128750597153bb5987e10b1c3493a34e5a4502a` | Model revision/commit; değişirse yeniden indeksleme gerekir |
| `VDB_EMBEDDING_BASE_URL` | `https://api.openai.com/v1` | Yalnızca opt-in harici provider için OpenAI-compatible `/embeddings` kökü; uzak endpoint HTTPS, HTTP yalnızca loopback test adresleri |
| `VDB_EMBEDDING_TIMEOUT_SECONDS` | `30` | Harici embedding istek timeout'u |
| `VDB_EMBEDDING_MAX_RETRIES` | `2` | Harici provider için 0–5 arası sınırlı retry |
| `VDB_EMBEDDING_BATCH_SIZE` | `32` | Harici provider batch boyutu; 1–256 arası |
| `VDB_EMBEDDING_CACHE_SIZE` | `256` | Harici provider in-memory cache kapasitesi; 0–4096 arası, 0 kapalı |
| `VDB_SOURCE_MAX_BYTES` | `10000000` | Kaynak dosyası başına güvenli üst sınır; ingest ve inventory birlikte kullanır |
| `VDB_SOURCE_MAX_FILES` | `5000` | `ingest-dir` başına desteklenen kaynak dosyası sayısı üst sınırı; limit aşımında yazım başlamaz |
| `VDB_SOURCE_MAX_TOTAL_BYTES` | `1000000000` | `ingest-dir` girdilerinin toplam kaynak byte bütçesi; RAM/çalışma süresi garantisi değildir |
| `VDB_VECTOR_DIMENSION` | `768` | Provider vector boyutu |
| `VDB_DISTANCE_METRIC` | `cosine` | Koleksiyon mesafe metriği |
| `VDB_HNSW_EF` | boş veya `64` | Sorgu başına opsiyonel HNSW arama bütçesi |
| `VDB_RERANKER_MODE` | `off` veya `lexical` | V1.3 reranker; varsayılan kapalı |
| `VDB_QUERY_PLANNER_MODE` | `off` veya `selectivity` | V1.4 filtre seçiciliği planlayıcısı; varsayılan kapalı |
| `VDB_DATA_DIR` | `data` | Kaynak ve çalışma verisi kökü |

Secret değerleri `.env` dosyasına commit edilmez. Sağlayıcı, model ve koleksiyon değişimi manifest doğrulamasından geçmeden başlatılmaz. Production'da image ve dependency sürümleri sabitlenir.

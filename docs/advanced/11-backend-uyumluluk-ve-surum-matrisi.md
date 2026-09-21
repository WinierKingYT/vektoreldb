# Backend uyumluluk ve sürüm matrisi

Bu matris algoritma araştırması ile seçilen ürünün gerçek yeteneklerini ayırır. Literatürde bir algoritmanın bulunması, Qdrant'ın aynı özelliği native sunduğu anlamına gelmez.

| Teknik | Qdrant V1/V2 | FAISS | DiskANN | ScaNN | Not |
|---|---|---|---|---|---|
| HNSW | native dense index | index family | ayrı graph yaklaşımı | backend'e bağlı | parametre isimleri eşdeğer değildir |
| IVF/PQ | native olarak varsayılmaz | native index ailesi | PQ yardımcı rol | AVQ/partition yaklaşımı | backend migration gerekir |
| Disk-backed graph | storage/memmap seçenekleri | index türüne bağlı | native yaklaşım | backend'e bağlı | SSD/cache testi şart |
| Sparse+dense fusion | named vectors + Query API | uygulama katmanı | uygulama katmanı | uygulama katmanı | fusion semantiği ayrıca yazılır |
| Multi-vector rerank | named/multivector | özel uygulama | özel uygulama | özel uygulama | çoğunlukla rerank aşaması |

## Minimum sürüm kaydı

Qdrant özelliği kullanıldığında manifest'te minimum sürüm ve test edilen sürüm tutulur. Araştırma snapshot'ında (12 Eylül 2026) Qdrant release listesinde v1.19.0 latest, Milvus release notes'ta v3.0.1 güncel sürüm olarak görünmektedir; bunlar otomatik pin değildir.

Qdrant için belgelenen eşikler: Query API v1.10.0, DBSF v1.11.0, inline storage v1.16.0, weighted RRF v1.17.0 ve unified memory tier v1.19.0. Resmî dokümantasyonun
13 Eylül 2026 doğrulamasında v1.19 memory-tier ayarları ve Turbo4/multivector
seçenekleri de görünür durumdadır; bu projede Turbo4 kullanılmaz, yalnızca ileride
ayrı bir deney adayıdır. Kullanılan image/client sürümü uygulama öncesi release
notes ile tekrar doğrulanır.

Qdrant image ve client tagsiz/latest kullanılmaz. Milvus veya ayrı FAISS/DiskANN/ScaNN backend'i seçilirse kendi sürüm matrisi açılır; Qdrant varsayımları taşınmaz.

## Parametre adları

Literatürdeki `efSearch`, ürün API'sinde `ef` veya `hnsw_ef`; IVF'te `nprobe`, graph'ta candidate budget olarak farklı adlandırılabilir. Her backend için “kavramsal parametre → gerçek API alanı → test edilen değer” tablosu tutulur.

## Kaynaklar

- [Qdrant indexing](https://qdrant.tech/documentation/manage-data/indexing/)
- [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)
- [Qdrant memory tiers](https://qdrant.tech/documentation/ops-configuration/memory-tiers/)
- [Qdrant multitenancy](https://qdrant.tech/documentation/manage-data/multitenancy/)
- [Milvus architecture](https://milvus.io/docs/architecture_overview.md)
- [FAISS repository](https://github.com/facebookresearch/faiss)
- [ScaNN algorithms](https://github.com/google-research/google-research/blob/master/scann/docs/algorithms.md)
- [Qdrant releases](https://github.com/qdrant/qdrant/releases)
- [Qdrant quantization](https://qdrant.tech/documentation/manage-data/quantization/)
- [Qdrant capacity planning](https://qdrant.tech/documentation/capacity-planning/)
- [Milvus release notes](https://milvus.io/docs/release_notes.md)

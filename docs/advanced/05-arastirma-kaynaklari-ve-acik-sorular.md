# İleri araştırma kaynakları ve açık sorular

## Kaynak sınıfları

### Algoritma ve indeks

- HNSW: Malkov & Yashunin, 2016 — graph hierarchy, neighbor selection, logarithmic search behavior.
- FAISS/GPU: Johnson, Douze & Jégou, 2017 — exact/approximate/compressed search and GPU k-selection.
- DiskANN: Subramanya et al., NeurIPS 2019 — SSD-backed billion-scale graph search.
- ScaNN: Google Research, ICML 2020 line — anisotropic vector quantization and partition/pruning.

### Ürün ve sistem davranışı

- Qdrant indexing — filter-aware HNSW and payload index ordering.
- Qdrant hybrid queries — prefetch, RRF and DBSF.
- Qdrant multivector — late interaction and rescoring without unnecessary HNSW.
- Qdrant scaling/consistency — shards, replicas, Raft and write guarantees.
- Milvus consistency — strong, bounded, session and eventual read/write trade-offs.

### RAG değerlendirme

- RAGAS — reference-free context and answer dimensions.
- ARES — automated judges, synthetic data and prediction-powered inference.

## Kanıt düzeyi

| Konu | Kaynak tipi | Son karar |
|---|---|---|
| HNSW trade-off | özgün araştırma + ürün docs | benchmark gerekir |
| Disk-backed ANN | özgün araştırma | SSD workload testi gerekir |
| Hybrid fusion | ürün docs + retrieval teorisi | RRF baseline, ağırlık validation ile |
| Multi-vector rerank | özgün/ürün teknik kaynak | yalnızca candidate rerank |
| Quantization | özgün araştırma + capacity docs | recall maliyeti ölçülmeden açılmaz |
| Filtered ANN | özgün araştırma + ürün docs | selectivity sınıflarıyla ölçülür |
| Distributed consistency | ürün docs | workload'a göre profil seçilir |
| RAG judge | özgün araştırma | insan kalibrasyonu zorunlu |

## Açık araştırma soruları

1. Türkçe domain corpus'unda hangi model ve instruction formatı en yüksek retrieval kalitesini veriyor?
2. Metadata filtre seçiciliği hangi noktada HNSW yerine exact/fallback gerektiriyor?
3. HNSW, IVF/PQ ve DiskANN aynı corpus'ta hangi recall–p95 Pareto'sunu veriyor?
4. Quantization hangi bit seviyesinde kabul edilebilir nDCG kaybı yaratıyor?
5. Dense+sparse RRF, dense-only'ye göre hangi sorgu sınıflarında anlamlı kazanıyor?
6. Late interaction rerank kalite artışı, ek RAM/latency maliyetini karşılıyor mu?
7. Güncelleme yoğunluğu arttığında graph/segment optimizasyonu nasıl davranıyor?
8. Snapshot restore sonrası alias, deletion ledger ve index manifest nasıl atomik doğrulanıyor?
9. Local provider ile harici provider arasında kalite, gizlilik ve toplam sahip olma maliyeti nasıl dengeleniyor?
10. Otomatik RAG judge sonuçları insan etiketleriyle hangi confidence aralığında uyuşuyor?

## Araştırma kapanış koşulu

Araştırma, her açık soru için ya kaynak destekli bir sonuç ya da ölçülebilir deney planı bulunduğunda tamamlanmış sayılır. Kaynakların iddiası ile kendi corpus benchmark sonucu ayrıştırılmadan “en iyi indeks/model” sonucu yazılmaz.

## Kaynak bağlantıları

- [HNSW paper](https://arxiv.org/abs/1603.09320)
- [FAISS paper](https://arxiv.org/abs/1702.08734)
- [DiskANN research](https://www.microsoft.com/en-us/research/?p=634449)
- [ScaNN overview](https://research.google/blog/announcing-scann-efficient-vector-similarity-search/)
- [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)
- [Qdrant multivectors](https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations/)
- [Qdrant horizontal scaling](https://qdrant.tech/documentation/scaling/horizontal-scaling/)
- [RAGAS](https://arxiv.org/abs/2309.15217)
- [ARES](https://arxiv.org/abs/2311.09476)
- [ANN-Benchmarks](https://arxiv.org/abs/1807.05614)
- [Qdrant storage](https://qdrant.tech/documentation/manage-data/storage/)
- [Qdrant optimizer](https://qdrant.tech/documentation/operations/optimizer/)
- [Filtered-DiskANN paper](https://harsha-simhadri.org/pubs/Filtered-DiskANN23.pdf)
- [Qdrant filtering](https://qdrant.tech/documentation/search/filtering/)
- [Qdrant consistency guarantees](https://qdrant.tech/documentation/scaling/consistency-guarantees/)
- [Milvus consistency](https://milvus.io/docs/consistency.md)
- [ScaNN algorithms](https://github.com/google-research/google-research/blob/master/scann/docs/algorithms.md)

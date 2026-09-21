# 35. Multi-vector ve late interaction

Tek vektör uzun belgelerde ayrıntı kaybedebilir. ColBERT benzeri late-interaction yaklaşımı token düzeyinde çoklu vektör üretir ve sorgu zamanında MaxSim ile daha hassas sıralama yapar.

Bu yapı ilk aşamada yalnızca reranking için düşünülür; her token vektörünü HNSW ile indekslemek RAM ve insert maliyetini büyütebilir. Qdrant, reranking vektöründe HNSW'yi kapatıp adaylar üzerinde yeniden puanlamaya izin verir. [Qdrant multivector rehberi](https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations/)

Kabul kriterleri:

- dense-only'ye göre ölçülebilir nDCG/precision artışı
- p95 latency ve RAM bütçesi içinde kalma
- uzun chunk'larda gerçek kalite kazanımı
- fallback olarak dense-only arama

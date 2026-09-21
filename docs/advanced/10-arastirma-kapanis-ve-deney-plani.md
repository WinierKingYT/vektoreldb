# İleri araştırma kapanış ve deney planı

## Faz 1 — Algoritmik baseline

Exact, HNSW ve IVF/PQ aynı synthetic + temsilî kişisel corpus üzerinde ölçülür. Hedefler: ANN recall, build time, update freshness, p95/p99, RAM ve disk.

## Faz 2 — Retrieval kalitesi

Dense-only, sparse-only, RRF hybrid ve late-interaction rerank karşılaştırılır. Sorgular semantic, exact identifier, typo, Turkish morphology, long-context ve negative sınıflarına ayrılır.

## Faz 3 — Sistem davranışı

Filtre selectivity, concurrent ingest/search, compaction, cold start, WAL replay, snapshot restore ve failover test edilir.

## Faz 4 — Sıkıştırma ve ölçek

Scalar/PQ quantization, on-disk/cached storage ve gerekirse DiskANN/dağıtık shard planı ölçülür. Bu fazda kapasite hesabı gerçek payload/index/snapshot boyutlarıyla güncellenir.

## Faz 5 — Güvenlik ve red-team

ACL bypass, poisoned document, prompt injection, sensitive metadata, provider leakage ve restore sonrası deletion ledger test edilir.

## Araştırmanın tamamlanma koşulu

Her fazda baseline, deney kartı, ham metrik, yorum, negatif sonuç ve karar kaydı bulunmalıdır. Son rapor, “hangi teknik daha iyi?” yerine “hangi workload koşulunda hangi tekniğin hangi bedelle seçildiğini” söylemelidir.

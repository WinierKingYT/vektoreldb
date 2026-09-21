# İleri vektör veritabanı araştırma metodolojisi

## Araştırma sorusunu sınırlandırma

“En iyi vector database” sorusu ölçülemez. Soru; corpus büyüklüğü, boyut, update oranı, filtre selectivity, concurrency, hedef recall, p95/p99 latency, donanım ve gizlilikle sınırlandırılır.

## Baseline merdiveni

1. Exact brute-force: ANN ve relevance referansı.
2. Exact + payload filter: filtreli ground truth.
3. HNSW: update esnekliği olan baseline.
4. Hybrid dense+sparse: exact terim sınıfları.
5. Rerank/multi-vector: precision iyileştirmesi.
6. Quantized/disk-backed: kapasite baskısı.
7. Distributed: shard, replica ve consistency testi.

Bir üst basamak, alt basamakta ölçülmüş darboğaz veya kalite açığı varsa denenir.

## Benchmark hijyeni

ANN-Benchmarks çalışması ortak arayüz ve recall–performans eğrileriyle algoritma karşılaştırma ihtiyacını gösterir.[^1] Kendi ölçümümüzde end-to-end embedding, network, payload ve serialization latency ayrı tutulur; üçüncü taraf leaderboard sonucu kendi corpus sonucunun yerine geçmez.

## Deney kartı

```text
ID / hipotez / corpus-query split / baseline / tek değişken
donanım-sürümler / metrikler / güven aralığı / maliyet-güvenlik etkisi
rollback / karar
```

## Negatif sonuçlar

Bir tekniğin işe yaramaması kalıcı bilgidir. Hybrid yalnızca exact isim sorgularında kazanıyorsa genel varsayılan yapılmaz; multi-vector kaliteyi artırıp p99'u bozuyorsa yalnızca dar candidate set için tutulur.

## Kanıt hiyerarşisi

1. Aynı corpus ve hardware üzerinde tekrarlanabilir ölçüm
2. Özgün araştırma makalesi ve açık benchmark
3. Resmî ürün dokümantasyonu
4. Üçüncü taraf benchmark
5. Blog veya pazarlama iddiası

[^1]: Fu et al., [ANN-Benchmarks](https://arxiv.org/abs/1807.05614), 2018.

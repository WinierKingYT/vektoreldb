# ANN indeksleri: derinlemesine karşılaştırma

## HNSW'nin davranış modeli

HNSW graph'ında arama bir giriş noktasından başlar, üst katmanlarda hızlı yakınsama yapar ve alt katmanda aday havuzunu genişletir. `efSearch` arama frontier'ının genişliğidir; yüksek değerler daha çok graph düğümü ziyaret ederek recall'ı artırabilir, fakat p95/p99 latency ve CPU'yu yükseltir. `M` graph'ın bağlantı yoğunluğudur; bağlantı sayısı artınca recall ve RAM artabilir.

HNSW'de yüksek ortalama recall düşük tail latency anlamına gelmez. Kümelenmiş veri, filtreli sorgu ve sıcak/soğuk segment dağılımı ayrı percentile raporu ister. `M` graph bağlantı yoğunluğunu, `efConstruction` build aday havuzunu, `efSearch` query aday havuzunu belirler. Qdrant API'sindeki `hnsw_ef`/`ef`, literatür `efSearch` kavramıyla ilişkilidir fakat otomatik olarak aynı isim ve kapsamda değildir; `full_scan_threshold` gibi ürün eşikleri ayrıca kaydedilir.

## IVF/PQ'nin davranış modeli

IVF için coarse quantizer eğitim datasını temsil etmelidir; dengesiz listeler `nprobe` arttığında beklenenden fazla tarama doğurur. PQ codebook'ları alt uzaylardaki dağılımı yakalamazsa mesafe sıralaması bozulur. `nlist`, `nprobe`, code size, residual/PQ ve gerekirse OPQ ayrı parametrelerdir. Bu yüzden quantizer training set'i üretim corpus'unun zaman ve domain dağılımını temsil etmelidir; yeni dağılımda yeniden eğitim gerekir.

## DiskANN'nin farklı trade-off'u

DiskANN graph'ın önemli kısmını SSD'ye taşıyarak RAM kapasitesi ile disk kapasitesini birlikte tasarım parametresi yapar; RAM'i ortadan kaldırmaz. Vamana graph, PQ kod/cache ve beam width birlikte çalışır. Büyük graph'larda rastgele I/O ve cache miss tail latency'yi belirler; güncelleme yoğunluğu, compaction ve NVMe dayanıklılığı yalnızca benchmark QPS'ından daha önemlidir.

## Deney tasarımı

Her indeks için aynı:

- vector corpus ve metric
- query set ve relevance labels
- `k`
- warm/cold cache koşulu
- concurrency
- update oranı

ölçülür. Sonuçlar recall–p95–RAM–disk Pareto tablosunda raporlanır. ANN recall için exact index referanstır; kullanıcı relevance'i ayrı etikettir.

## ScaNN pipeline'ı

ScaNN yaklaşımındaki yüksek seviye pipeline; partition ile aday alanını daraltma, approximate scoring ile ucuz aday puanlama ve rescore ile daha hassas mesafe hesaplamasıdır. Anisotropic quantization özellikle MIPS yönündeki hatayı dikkate alır; bu doğrudan Qdrant özelliği değil, ayrı backend/indeks yaklaşımıdır.

## Seçim sonucu

Kişisel corpus küçükken HNSW veya exact arama daha güvenilir baseline'dır. IVF/PQ ve DiskANN ancak RAM, disk veya latency darboğazı ölçüldükten sonra değerlendirilir. Algoritma seçimi modelden bağımsız değildir; cosine/dot/L2 metriği ve vector normalization ile birlikte ele alınır.

## Kaynaklar

- [HNSW original paper](https://arxiv.org/abs/1603.09320)
- [DiskANN research](https://www.microsoft.com/en-us/research/?p=634449)
- [FAISS research](https://arxiv.org/abs/1702.08734)
- [ScaNN research overview](https://research.google/blog/announcing-scann-efficient-vector-similarity-search/)
- [ScaNN algorithms](https://github.com/google-research/google-research/blob/master/scann/docs/algorithms.md)

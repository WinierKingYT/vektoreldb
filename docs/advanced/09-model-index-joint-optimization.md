# Model–indeks ortak optimizasyonu

## Temel ilke

Embedding modeli, distance metric, normalization, dimension reduction, index ve reranker birlikte bir retrieval sistemi oluşturur. Bunlardan birini değiştirip diğerlerini sabit varsaymak yanlış karşılaştırma üretebilir.

## Optimizasyon eksenleri

- model semantic quality ve Türkçe domain uyumu
- vector dimension ve truncation
- cosine/dot/L2 uyumu
- HNSW `M`/`ef` veya IVF `nlist`/`nprobe`
- quantization bit seviyesi
- candidate budget ve reranker
- payload filter selectivity
- hardware/cache sıcaklığı

## Deney tasarımı

Önce model + exact retrieval ile semantic ceiling ölçülür. Sonra aynı modelde ANN parametreleri ayarlanır. Ardından quantization ve reranker tek tek eklenir. Model ile indeks parametreleri aynı deneyde birlikte değiştirilecekse factorial veya nested design yazılır; aksi halde kazanımın kaynağı bilinemez.

## Karar ölçütü

Bir konfigürasyon şu dört koşulu birlikte sağlamalıdır: relevance artışı, hedef tail latency, kabul edilebilir kaynak maliyeti ve veri politikası uyumu. Tek bir public benchmark skoru kişisel corpus için karar değildir.

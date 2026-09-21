# 36. Quantization ve depolama optimizasyonu

Quantization vektör boyutunu ve RAM/disk ihtiyacını azaltabilir; fakat recall kaybı ve yeniden indeksleme maliyeti oluşturabilir.

## Uygulama sırası

1. Float32 exact/ANN baseline ölç.
2. Scalar veya binary quantization adayını aynı benchmark'ta ölç.
3. Recall düşüşü, p95 latency, RAM ve disk etkisini kaydet.
4. Kabul eşiği geçilirse yalnızca büyük koleksiyonlarda etkinleştir.

Küçük kişisel corpus'ta quantization yerine basit ve doğru arama tercih edilir. Qdrant kapasite planlamasında boyut, veri tipi, payload, indeks ve replikasyonun birlikte hesaplanmasını önerir. [Qdrant capacity planning](https://qdrant.tech/documentation/capacity-planning/)

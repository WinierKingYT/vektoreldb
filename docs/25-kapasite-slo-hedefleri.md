# 25. Kapasite ve SLO hedefleri

İlk hedefler kesin gerçek değil, kabul testi başlangıç değerleridir:

| Ölçüt | V1 hedefi |
|---|---:|
| Search p95 | ≤ 500 ms |
| Search p99 | ≤ 1500 ms |
| Ingest retryable hata oranı | < %1 |
| Başarılı restore | ≤ 30 dakika |
| Günlük embedding bütçesi | 100.000 input token |
| Benchmark Recall@5 regresyonu | ≤ 2 puan |

Tek makine kapasitesi; kaynak, payload, indeks ve snapshot büyüklüğü birlikte ölçülür. Hedef tutmazsa önce veri/model/filtre etkisi ayrıştırılır, sonra donanım veya indeks ayarı değiştirilir.

RPO ve RTO, ilk restore tatbikatından sonra kesinleştirilir; başlangıç önerisi RPO 24 saat, RTO 30 dakikadır.

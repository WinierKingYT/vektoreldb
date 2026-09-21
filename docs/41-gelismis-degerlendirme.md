# 41. Gelişmiş değerlendirme ve deney tasarımı

## Ayrı katmanlar

- Retriever: Recall@k, MRR, nDCG, exact ANN recall
- Context: precision/recall, duplicate oranı, token bütçesi
- Generator: doğruluk, kaynak bağlılığı, halüsinasyon
- Sistem: p50/p95/p99 latency, hata, maliyet

Test seti train/validation/test olarak ayrılır. Füzyon ağırlıkları ve eşikler validation'da ayarlanır; test seti yalnızca son karşılaştırmada kullanılır.

Türkçe ekler, eş anlamlılar, typo, özel isim, negatif sorgu, OCR, tablo ve uzun belge sınıfları ayrı raporlanır. Her model/chunking/indeks değişikliği önceki sürümle regression karşılaştırmasına girer.

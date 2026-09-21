# 41. Gelişmiş değerlendirme ve deney tasarımı

## Ayrı katmanlar

- Retriever: Recall@k, MRR, nDCG, exact ANN recall
- Context: precision/recall, duplicate oranı, token bütçesi
- Generator: doğruluk, kaynak bağlılığı, halüsinasyon
- Sistem: p50/p95/p99 latency, hata, maliyet

Test seti train/validation/test olarak ayrılır. Füzyon ağırlıkları ve eşikler validation'da ayarlanır; test seti yalnızca son karşılaştırmada kullanılır.

Türkçe ekler, eş anlamlılar, typo, özel isim, negatif sorgu, OCR, tablo ve uzun belge sınıfları ayrı raporlanır. Her model/chunking/indeks değişikliği önceki sürümle regression karşılaştırmasına girer.

İnsan cevap değerlendirmeleri için `rag-answer-evaluations.schema.json` kullanılır.
Artifact ham cevap/source metni taşımaz; relevance, faithfulness, citation
correctness ve abstention correctness puanlarını fixture/corpus/embedding/generation
provenance'ına bağlar. Aynı provenance paylaşmayan kayıtlar tek özet altında
birleştirilmez. Bu kayıtlar 300+ fixture hazırlandıktan sonra doldurulacak final
cevap kalite kanıtıdır; retrieval citation bütünlüğü tek başına bunun yerine geçmez.

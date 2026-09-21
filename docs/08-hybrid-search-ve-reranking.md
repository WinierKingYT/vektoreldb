# 8. Hybrid search ve reranking

## Neden hybrid?

Dense arama anlam ve eş anlamlıları yakalar; sparse/lexical arama özel isim, kod, ISBN, dosya adı ve exact ifadelerde daha güçlü olabilir. Bu iki yöntemin faydası veri ve sorgu tipine göre ölçülür; varsayılan olarak eklenmez.

## Önerilen aşamalar

```text
dense adayları (20–50)
        + sparse adayları (20–50)
        → RRF/DBSF füzyonu
        → isteğe bağlı reranker (10–30)
        → duplicate azaltma ve context bütçesi
```

Qdrant, aynı noktada named dense/sparse vektörleri ve prefetch tabanlı çok aşamalı sorguları destekler. Değerlendirme seti yoksa RRF güvenli başlangıçtır; ağırlıklı füzyon için train/validation ayrımı gerekir. [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)

## Reranking politikası

Reranker tüm corpus üzerinde değil, ilk aday kümesi üzerinde çalıştırılır. Böylece precision artışı ile latency/CPU maliyeti dengelenir. Her testte dense-only, sparse-only, hybrid ve hybrid+rerank ayrı raporlanır.

Ham dense ve BM25 skorları doğrudan toplanmaz; ölçekleri farklı olabilir. Rank tabanlı RRF veya doğrulanmış skor normalizasyonu kullanılır.

## Ne zaman eklenir?

- Kullanıcı sorguları exact terimler içeriyorsa sparse arama eklenir.
- Dense-only Recall@k yetersizse hybrid denenir.
- İlk adaylarda doğru belge var fakat sıralama kötüyse reranker denenir.
- Latency veya kaynak maliyeti kabul sınırını aşarsa özellik varsayılan olmaktan çıkarılır.

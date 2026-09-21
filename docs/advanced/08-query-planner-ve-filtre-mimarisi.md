# Query planner ve filtre mimarisi

## Planlama problemi

Bir arama planı şu sorulara cevap vermelidir: filtre önce mi vector traversal ile birlikte mi uygulanacak, kaç aday üretilecek, hangi segmentler okunacak, payload diskten mi RAM'den mi alınacak, exact fallback ne zaman devreye girecek?

## Filtre alanları

Payload index yalnızca hızlandırma değil, planın öngörülebilirliği için de önemlidir. Qdrant strict mode, indekslenmemiş filtreli erişimi sınırlayabilir; yüksek cardinality ve birleşik filtrelerde planın aday kaybı ile latency etkisi ayrı ölçülür.[^1]

## Selectivity-aware plan

```text
eşleşme oranı düşük (katı filtre) → indexed filter + exact/rescore fallback
eşleşme oranı orta               → filter-aware ANN + geniş candidate budget
eşleşme oranı yüksek (zayıf filtre) → normal ANN + indexed filter
```

Bu sınıflar sabit eşik değildir; corpus üzerinde histogram/telemetry ile öğrenilir. Kullanıcı filtresi güvenlik için daima server-side zorunlu kalır, fakat performans planı seçiciliğe göre değişebilir.

## Global top-k problemi

Segment başına top-k almak global top-k'yi garanti etmez; segmentler arası aday bütçesi ve merge aşaması yeterli olmalıdır. Hybrid'de dense/sparse prefetch limitleri final `limit + offset` ihtiyacını karşılamalıdır. [Qdrant filtering](https://qdrant.tech/documentation/search/filtering/) ve [hybrid query](https://qdrant.tech/documentation/search/hybrid-queries/) belgeleri bu planlama ayrıntılarını tanımlar.

## Gözlemlenebilir plan

Her arama loglamadan şu sayısal özetleri taşır: segment count, visited candidates, filtered candidates, fallback, prefetch limits, merge time ve final result count. Ham query/document metni loglanmaz.

[^1]: Qdrant, [FAQ and strict mode](https://qdrant.tech/documentation/faq/).

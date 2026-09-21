# Filtreli, hybrid ve çok aşamalı retrieval

## Filtre seçiciliği

Filtre seçiciliği, koşulu sağlayan corpus oranıdır. Düşük oranlı (katı/yüksek seçicilikli) filtrelerde ANN graph'ı yeterli geçerli komşu bulamayabilir; geniş oranlı (zayıf/düşük seçicilikli) filtrelerde normal graph traversal daha iyi çalışabilir. Orta bölgede payload index, over-fetch, adaptive search ve exact fallback karşılaştırılır.

Her sorguda `candidate_count`, `valid_after_filter`, `filter_selectivity`, `fallback_used` ve final relevance kaydedilir. Filtreli sorgular filtresiz benchmark'tan ayrı değerlendirilir.

## Hybrid füzyon

Dense ve sparse sonuç listeleri aynı score uzayında değildir. RRF rank'leri birleştirerek bu problemi azaltır; ağırlıklı RRF yalnızca validation set'te ayarlanmalıdır. Hybrid'in değeri exact identifier, özel isim, kod, tarih ve typo sorgu sınıflarında ayrı ölçülür.

## Late interaction

Late interaction token düzeyindeki ilişkileri korur ve ilk adayları daha hassas sıralayabilir. Çoklu vektörleri full ANN olarak indekslemek yerine dense/sparse prefetch sonrası rerank etmek kaynak maliyetini sınırlar. Qdrant multi-vector dokümanı bu nedenle rerank alanında HNSW'yi kapatma seçeneğini vurgular.[^1]

## İleri retrieval sözleşmesi

```text
query → access filter → dense/sparse prefetch
      → rank fusion → optional late interaction
      → document diversification → context packing
```

Her aşamanın latency ve kalite katkısı ayrı raporlanır. Reranker kaliteyi artırmıyorsa yalnızca “daha ileri” olduğu için açık tutulmaz.

[^1]: Qdrant, [Multivector representations](https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations/).

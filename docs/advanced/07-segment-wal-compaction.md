# Segment, WAL ve compaction iç mimarisi

## Neden önemli?

Vector database yazma, arama ve optimize etme işlerini aynı veri yapısında yürütmez. Qdrant'ta collection segment'lere ayrılır; her segment kendi vector/payload storage ve indekslerine sahiptir. WAL değişiklikleri sıralar ve anormal kapanmada yeniden oynatılabilmesini sağlar.[^1]

## Write/read yolu

```text
write → WAL sequence → appendable segment → optimizer → sealed/indexed segment
search → active segments → per-segment candidates → deduplicate → global top-k
```

Aynı point geçici olarak birden fazla segmentte bulunabilir; arama deduplication ile son sürümü seçer. Bu durum upsert sonrası görünürlük, segment sayısı ve global top-k birleştirmesini etkiler.

## Compaction ve vacuum

Delete çoğunlukla tombstone ile başlar; fiziksel temizleme vacuum/compaction'a bırakılır. Çok sayıda küçük segment arama fan-out'unu artırır; çok büyük segment rebuild süresini ve update gecikmesini artırır. Optimizer copy-on-write ile rebuild sırasında okunabilirliği koruyabilir.[^2]

## İleri tuning sinyalleri

- appendable segment büyüklüğü
- segment sayısı ve yaş dağılımı
- tombstone oranı
- optimizer CPU/disk contention
- search p95 sırasında compaction
- WAL boyutu ve replay süresi

Bu metrikler izlenmeden “daha sık compaction” veya “daha büyük segment” kararı verilmez.

[^1]: Qdrant, [Storage](https://qdrant.tech/documentation/manage-data/storage/).
[^2]: Qdrant, [Optimizer](https://qdrant.tech/documentation/operations/optimizer/).

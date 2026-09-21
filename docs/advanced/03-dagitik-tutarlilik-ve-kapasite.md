# Dağıtık tutarlılık, kapasite ve recovery

## Dikeyden yataya geçiş

Dikey ölçekleme network hop eklemez ve işletim açısından daha basittir. Yatay ölçekleme veri hacmi, I/O veya fault tolerance gerektirdiğinde seçilir. Shard sayısı, replication factor, coordinator trafiği ve load balancer birlikte planlanır.

## Tutarlılık profilleri

İki ayrı profil belgelenir:

- **Freshness-first:** yazıdan sonra aramada görünürlük öncelikli; daha yüksek latency/replication maliyeti kabul edilir.
- **Availability-first:** kısa süreli stale sonuç kabul edilir; read latency ve erişilebilirlik önceliklidir.

Her profil için read-after-write testi, node failure testi ve stale window ölçülür. Milvus consistency seviyeleri strong, bounded staleness, session ve eventual seçenekleriyle bu trade-off'u açıkça modeller.[^1]

## Kapasite modeli

```text
disk ≈ raw vectors + payload + vector index + payload index + WAL + snapshots
RAM  ≈ hot vectors/index + graph + payload indexes + query working set
```

Replication, snapshot retention ve compaction için büyüme payı eklenir. Quantization sonrası yalnızca vector boyutunun değil recall ve decode maliyetinin de ölçülmesi gerekir.

## Recovery

Restore, snapshot dosyasını açmaktan ibaret değildir: collection config, manifest, alias, source snapshot, deletion ledger ve benchmark smoke test birlikte geri getirilir. Qdrant snapshot'larının alias'ları içermediği için bu varlıklar ayrı yönetilir; snapshot sürüm uyumluluğu ve dağıtık node/shard kapsamı ayrıca migration/recovery dokümanından doğrulanır.[^2]

[^1]: Milvus, [Consistency](https://milvus.io/docs/consistency.md).
[^2]: Qdrant, [Snapshots](https://qdrant.tech/documentation/operations/snapshots/) ve [Migration/Recovery](https://qdrant.tech/documentation/migration-recovery-options/).

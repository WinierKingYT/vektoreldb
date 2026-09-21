# 38. Dağıtık deployment ve yüksek erişilebilirlik

Kişisel V1 tek node'dur. Dağıtıma ancak veri tek node'a sığmadığında, disk I/O bottleneck olduğunda veya erişilebilirlik hedefi gerektiğinde geçilir. Qdrant da dikey ölçeklemeyi yatay ölçeklemeden önce önerir. [Qdrant scaling rehberi](https://qdrant.tech/documentation/scaling/)

## Geçiş planı

1. Dikey kaynak artışını ölç.
2. Replikasyon ve shard sayısını belirle.
3. Load balancer ve health check ekle.
4. Node kaybı ve restore tatbikatı yap.
5. Ağ gecikmesini ve coordinator yükünü benchmark'a dahil et.

Dağıtık yapı otomatik olarak daha ucuz veya daha hızlı değildir; network, operasyon ve tutarlılık maliyeti getirir.

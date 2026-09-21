# 31. Geliştirici kurulum rehberi

Bu belge mevcut V1 uygulaması üzerinde yerel geliştirme ve release öncesi hazırlık sırasını tanımlar.

1. Python sürümünü ve dependency lockfile'ı doğrula.
2. Varsayılan local Qdrant persistence ile çalış; server Qdrant doğrulaması için [kurulum dokümanındaki](02-kurulum.md) pinlenmiş image'i ayrıca başlat.
3. `schemas/` ve `openapi.yaml` doğrulamasını çalıştır.
4. Test fixture klasörüne yalnızca güvenli örnek veri koy.
5. `uv run vdb doctor` ile local provider/storage health check çalıştır.
6. Küçük ingest smoke testinde belge/chunk sayısını doğrula.
7. Search smoke testinde kaynak konumu ve owner filtresini doğrula.
8. Benchmark başlamadan üretim verisini kullanma; gerçek corpus benchmarkı ayrı kabul kapısıdır.

Geliştirme ortamı üretim snapshot'larına veya gerçek hassas dosyalara varsayılan olarak erişemez.

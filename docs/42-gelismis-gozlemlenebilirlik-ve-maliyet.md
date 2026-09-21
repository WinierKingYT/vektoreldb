# 42. Gelişmiş gözlemlenebilirlik ve maliyet

Her istekte correlation/request id tutulur. Hassas metin loglanmadan şu sinyaller izlenir:

- provider/model/manifest
- candidate sayısı ve retrieval stage
- filtre tipi ve sonuç sayısı
- latency aşamaları
- token ve embedding maliyeti
- düşük skor/boş sonuç
- cache hit/miss

Maliyet attribution'ı ingest, search, rerank ve storage olarak ayrılır. Local modelde CPU/GPU zamanı; harici modelde token ve hata retry maliyeti hesaplanır.

Anomali örnekleri: aynı belge tekrar tekrar embed ediliyor, filtreli sonuçlar aniden boşalıyor, p95 artıyor, provider retry oranı yükseliyor.

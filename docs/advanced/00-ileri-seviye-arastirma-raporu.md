# İleri Seviye Vektörel Veritabanı Araştırma Raporu

## Yönetici sonucu

İleri seviye bir vector database, yalnızca embedding saklayan bir servis değildir. Gerçek tasarım; yaklaşık en yakın komşu (ANN) algoritması, filtre semantiği, veri güncelliği, sıkıştırma, aday üretme ve yeniden sıralama, dağıtık yerleşim, geri kurtarma ve ölçüm döngüsünün birlikte tasarlanmasıdır.

Kişisel sistem için en önemli sonuç şudur: ileri tekniklerin çoğu veri hacmi ve sorgu yoğunluğu büyümeden değer üretmez. Bu nedenle mimari, her özelliği erkenden etkinleştirmek yerine “hangi darboğaz hangi tekniği hak ediyor?” sorusuna göre kademeli olmalıdır.

## 1. Problem modeli

Bir retrieval isteği şu hedefleri aynı anda optimize eder:

```text
kalite (relevance/recall) ↔ latency (p95/p99) ↔ kaynak (RAM/disk/CPU/GPU) ↔ güncellik ↔ izolasyon
```

Exact k-NN, ANN karşılaştırması için referans sonucu verir fakat maliyeti corpus büyüklüğüyle doğrusal artar. Kullanıcı açısından alaka için ayrıca insan/uzman relevance etiketi gerekir. ANN maliyeti azaltırken recall kaybını kabul eder; bu nedenle “en hızlı indeks” veya “en yüksek recall” tek başına doğru seçim değildir.

## 2. ANN algoritmaları

### HNSW

HNSW, farklı mesafe ölçeklerini temsil eden hiyerarşik proximity graph katmanları kurar. Üst katmanlar aramayı kaba biçimde yönlendirir, alt katmanlar adayları iyileştirir. Malkov ve Yashunin çalışması, ölçek ayrımının aramayı hızlandırdığını ve komşu seçme sezgisinin kümelenmiş veride önemli olduğunu gösterir.[^1]

Pratik parametreler `M`, `efConstruction` ve arama `efSearch`'tir. `M` graph bağlantılarını ve RAM'i, construction genişliği indeks oluşturma maliyetini, search genişliği ise recall/latency dengesini etkiler. HNSW yüksek güncelleme esnekliği ve güçlü recall sağlar; bedeli graph RAM'i ve filtre seçiciliği düştüğünde graph traversal'ın verimsizleşebilmesidir.

### IVF ve Product Quantization

IVF corpus'u coarse centroids/list'lere böler; sorgu yalnızca `nprobe` list üzerinde çalışır. PQ vektörü alt uzaylara bölüp codebook merkezleriyle sıkıştırır. IVF+PQ yüksek hacimde disk/RAM maliyetini azaltabilir, fakat centroid eğitimi, veri dağılımı ve `nprobe` seçimi kaliteyi belirler. GPU tabanlı FAISS çalışması, exact, approximate ve compressed-domain aramayı birlikte optimize ederek billion-scale ölçekte bu yaklaşımın değerini göstermiştir.[^2]

### DiskANN

DiskANN graph'ın önemli kısmını SSD üzerinde tutarak RAM gereksinimini azaltır; RAM'i ortadan kaldırmaz. Microsoft araştırması, billion-point SIFT1B üzerinde 64 GB RAM ile yüksek recall ve düşük gecikme hedefini gösterir; sonuç, RAM sınırının indeks tasarımını belirlediği durumlarda HNSW'den farklı bir mühendislik noktasıdır.[^3] SSD latency, random I/O, cache sıcaklığı ve güncelleme davranışı bu seçimin merkezindedir.

### ScaNN

ScaNN partitioning, pruning ve anisotropic vector quantization kombinasyonuyla özellikle maximum inner product aramasını optimize eder. Google'ın açıklamasındaki temel fikir, sıkıştırma kaybını yalnızca genel uzaklığı değil sorgu yönündeki hatayı dikkate alacak biçimde yönetmektir.[^4] Bu, model metriği ile indeks sıkıştırmasının birlikte seçilmesi gerektiğini gösterir.

### Seçim matrisi

| Durum | İlk aday | Ana risk |
|---|---|---|
| Küçük/orta corpus, sık update | HNSW | RAM ve filtreli recall |
| Milyonlarca nokta, RAM rahat | HNSW veya IVF | tuning maliyeti |
| RAM sınırlı, SSD hızlı | DiskANN/disk tabanlı graph | I/O tail latency |
| Milyar ölçek, sıkıştırma gerekli | IVF+PQ/ScaNN | quantization recall kaybı |
| GPU batch throughput | FAISS GPU/benzeri | latency ile throughput ayrımı |

## 3. Filtreli ANN

Vector similarity ile metadata filtresi aynı sorguda çalıştığında “önce ANN sonra filtre” güvenilir sonuç sayısını azaltabilir; “önce filtre sonra exact” ise seçicilik ve aday sayısına göre pahalıdır. Filtre-aware graph, payload indeksleri ve adaptive fallback bu iki uç arasındaki boşluğu kapatmaya çalışır.

Qdrant filtreli HNSW için payload indeksleriyle graph bağlantılarını zenginleştirir; payload indekslerini collection oluşturulduktan sonra ve veri ingest edilmeden önce tanımlamak graph'ın filtre farkındalığını iyileştirir.[^5] Microsoft'un Filtered-DiskANN çalışması da filtrelerin graph aramasına doğrudan dahil edilmesi problemini ayrı bir algoritmik konu olarak ele alır.[^6]

İleri tasarımda her filtre için şu sinyaller ölçülür: seçicilik, sonuç başına taranan aday, fallback exact oranı, filtreli recall ve p95. Evrensel `efSearch` veya `top_k` değeri yoktur.

## 4. Hybrid ve çok aşamalı retrieval

Dense vector anlamsal yakınlığı, sparse retrieval exact terimleri, late interaction ise token düzeyindeki eşleşmeleri yakalar. Qdrant Query API prefetch ile birden fazla retrieval aşamasını ve RRF/DBSF füzyonunu destekler.[^7]

Raw dense ve BM25 skorları doğrudan toplanmamalıdır; ölçekleri sorgudan sorguya değişir. Etiketli değerlendirme seti varsa ağırlıklı füzyon validation üzerinde öğrenilebilir; yoksa rank-based RRF daha emniyetli başlangıçtır.

Late interaction'da her belge yüzlerce token vektörü taşıyabilir. ColBERT yaklaşımı tek vektör pooling'in kaybettiği ayrıntıyı korur; fakat her token'ı ANN graph'a koymak RAM ve ingest maliyetini yükseltir. Bu yüzden dense/sparse ilk aday üretir, multi-vector yalnızca adayları rerank eder.[^8]

## 5. Quantization ve memory tiers

Quantization üç farklı yerde etkili olabilir: saklanan vector, graph/indeks yapısı ve rerank vektörü. Scalar quantization basit ve öngörülebilir; PQ daha yüksek sıkıştırma sağlar fakat codebook ve distance approximation getirir. Binary/low-bit yöntemler ancak benchmark'ta kabul edilebilir recall ile anlamlıdır.

Kapasite hesabı yalnızca `N × D × bytes` değildir. Payload, payload indeksleri, graph kenarları, segment overhead'i, cache ve replication eklenmelidir. Qdrant dokümantasyonu vector, index ve payload için pinned/cached/cold bellek katmanlarını ayırır.[^9]

## 6. Tutarlılık, güncellik ve recovery

Retrieval sistemi için “write başarılı” ile “hemen aramada görünür” aynı şey değildir. Distributed sistemlerde read-after-write, bounded staleness ve eventual consistency açıkça seçilmelidir. Milvus bu seviyeleri kendi ürün semantiğiyle tanımlar.[^10] Qdrant'ta replication ve `write_consistency_factor` öncelikle kaç replikadan acknowledgment bekleneceğini etkiler; okuma görünürlüğü ve sıralama ayrıca doğrulanmalıdır.[^11]

İndeks değişiminde immutable manifest + yeni collection + validation + alias switch, yerinde mutasyondan daha güvenlidir. Snapshot yalnızca vector/payload verisini değil, hangi alias'ın aktif olduğunu, schema manifest'ini ve silme listesini de operasyonel olarak birlikte gerektirir.

## 7. Dağıtık mimari ve multitenancy

Dikey ölçekleme, ağ ve coordinator maliyeti getirmediği için ilk tercihtir. Yatay ölçek, veri tek node'a sığmadığında veya fault tolerance/throughput hedefi gerektiğinde anlamlıdır. Shard sayısı gelecekteki node dağılımını, replication factor ise okuma/yazma maliyetini ve dayanıklılığı belirler.[^12]

Çok tenant'lı sistemlerde tenant başına collection bir izolasyon seçeneğidir fakat collection overhead'i yaratır. Ortak collection + indexed tenant payload daha verimli olabilir; büyük tenant'lar için dedicated shard/tiered yaklaşım düşünülebilir.[^13] Filtreyi sonuçtan sonra uygulamak güvenlik sınırı değildir.

## 8. Değerlendirme bilimi

Exact k-NN yalnızca ANN recall referansıdır; relevance ground truth değildir. İki ayrı etiket gerekir:

1. İnsan/uzman relevance: hangi sonuç ne kadar alakalı?
2. Exact ANN: yaklaşık indeks, exact aramada bulunan sonucu bulabildi mi?

Retrieval için Recall@k, MRR ve nDCG; RAG için context relevance, faithfulness ve answer relevance ayrı izlenir. RAGAS reference-free sinyaller önerir; ARES ise sentetik veri, hafif judge modelleri ve prediction-powered inference ile daha az insan etiketiyle değerlendirme yaklaşımı sunar.[^14][^15] Bunlar insan değerlendirmesinin yerine otomatik kör güvence olarak kullanılmamalıdır.

## 9. İleri güvenlik

Embedding güvenlik sınırı değildir: vector inversion, metadata sızıntısı, poisoned document, prompt injection ve snapshot kopyası ayrı tehditlerdir. Retrieval çıktısı LLM için talimat değil kanıttır; kaynak güven seviyesi, ACL filtresi ve provenance response boyunca taşınır.

Harici embedding provider seçimi bir performans kararı kadar veri işleme kararıdır. PII redaction, provider policy, bölge, retention, log redaction ve silme/backup süresi birlikte belgelenmelidir.

## 10. İleri seviye karar çerçevesi

Her yeni teknik için şu deney kartı hazırlanır:

```text
Hipotez → veri/sorgu sınıfı → baseline → tek değişken → metrikler
→ maliyet → güvenlik etkisi → rollback → karar
```

Önerilen sıra: önce ölçülebilir dense baseline, sonra filtre davranışı, sonra hybrid/rerank, ardından quantization ve en son dağıtık/çok tenant mimarisi. Bu sıra, karmaşıklığı kalite kanıtından önce büyütmeyi engeller.

## 11. Deney protokolü

Tek bir ortalama latency yerine cold/warm cache, concurrency, filter selectivity, candidate count ve p50/p95/p99 birlikte kaydedilir. Exact filtreli arama, ANN için doğru ground truth referansıdır; kullanıcı alakası için ayrı relevance etiketleri gerekir.

```text
Recall@k = |exact_top_k ∩ ann_top_k| / |exact_top_k|
```

Filtreli sonuçlar selectivity bucket'larına ayrılır. Hiperparametreler validation split'te seçilir; test split'i yalnızca final karşılaştırmada kullanılır. Model revision, donanım, Qdrant sürümü ve index manifest'i olmadan benchmark yeniden üretilebilir sayılmaz.

Late interaction için kavramsal skor:

```text
score(q, d) = Σ_i max_j sim(q_i, d_j)
```

Bu MaxSim biçimi token düzeyindeki sinyali korur; token sayısı arttıkça storage ve query compute maliyeti büyür.

## 12. Araştırma sınırı

Bu rapor özgün ANN çalışmaları, resmî ürün dokümanları ve RAG değerlendirme literatürünü sentezler. Ancak kişisel corpus için “en iyi” model veya indeks, Türkçe domain dağılımı, filtre selectivity, update oranı, cache sıcaklığı ve donanım ölçülmeden iddia edilmez. Sonraki teknik adım uygulama kodu değil; güvenli corpus, etiketli query seti, exact baseline ve tekrarlanabilir benchmark harness'idir.

## Kaynaklar

[^1]: Malkov & Yashunin, [HNSW paper](https://arxiv.org/abs/1603.09320), 2016.
[^2]: Johnson, Douze & Jégou, [Billion-scale similarity search with GPUs](https://arxiv.org/abs/1702.08734), 2017.
[^3]: Subramanya et al., [DiskANN](https://www.microsoft.com/en-us/research/?p=634449), NeurIPS 2019.
[^4]: Google Research, [ScaNN and anisotropic vector quantization](https://research.google/blog/announcing-scann-efficient-vector-similarity-search/), 2020.
[^5]: Qdrant, [Filterable HNSW and indexing](https://qdrant.tech/documentation/manage-data/indexing/).
[^6]: Gollapudi et al., [Filtered-DiskANN](https://dcreager.net/papers/Gollapudi2023/), 2023.
[^7]: Qdrant, [Hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/).
[^8]: Qdrant, [Multivector and late interaction](https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations/).
[^9]: Qdrant, [Capacity planning](https://qdrant.tech/documentation/capacity-planning/).
[^10]: Milvus, [Consistency levels](https://milvus.io/docs/consistency.md).
[^11]: Qdrant, [Consistency guarantees](https://qdrant.tech/documentation/scaling/consistency-guarantees/).
[^12]: Qdrant, [Horizontal scaling](https://qdrant.tech/documentation/scaling/horizontal-scaling/).
[^13]: Qdrant, [Multitenancy](https://qdrant.tech/documentation/manage-data/multitenancy/).
[^14]: Es et al., [RAGAS](https://arxiv.org/abs/2309.15217), 2023.
[^15]: Saad-Falcon et al., [ARES](https://arxiv.org/abs/2311.09476), 2023.

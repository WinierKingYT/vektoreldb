# V1.7 kapasite ve tekrarlanabilir ölçüm deney kartı

## Kapsam

Bu deney, V2.0 adayını seçmek için V1.7 dense retrieval'ı sabit baseline
olarak ölçer. Sonuçlar küçük PromtGen corpus'u için smoke kanıtıdır; kapasite
ve ölçek kararı yalnızca temsilî kişisel corpus üzerinde verilebilir.

## Sabit deney sözleşmesi

- Provider, model revision, dimension, metric, parser ve chunking sürümleri
  benchmark çıktısında tutulur.
- Dense baseline ve seçilen opt-in mod aynı corpus/query fixture üzerinde
  karşılaştırılır.
- İlk sorgu warm-up olarak ayrılır; cold-start ayrıca raporlanır.
- Her konfigürasyon üç bağımsız tekrar çalıştırılır; ortalama yerine her tekrar
  ve p50/p95/p99 ayrı saklanır.
- Pozitif sorgular query-type Recall@k, MRR@k ve nDCG@k; negative sorgular
  negative success rate ile değerlendirilir.

## Ölçülecek boyutlar

| Boyut | Ölçüm | Kanıt |
|---|---|---|
| Kalite | Recall/MRR/nDCG, negative success | Benchmark JSON |
| Gecikme | embedding, retrieval ve toplam p50/p95/p99 | Audit + benchmark JSON |
| Kapasite | point/chunk sayısı, payload/index/storage boyutu | Qdrant ve dosya ölçümü |
| Kaynak | process CPU time, RSS/peak memory, disk kullanımı | Host ölçüm kaydı |
| Tazelik | ingest tamamlanmasından görünür aramaya kadar süre | Ingest/retrieval timestamp |
| Dayanıklılık | snapshot boyutu, restore süresi, RPO/RTO | Restore run log |
| Eşzamanlılık | concurrency seviyesine göre throughput/error/tail latency | Load-test tablosu |

## Corpus ve sorgu matrisi

Minimum kabul paketi:

- en az 300 etiketli sorgu;
- semantic, exact identifier, typo, Turkish morphology, long-context ve
  negative sınıflarının her biri;
- en az üç belge boyutu kovası: küçük, orta ve büyük;
- gerçek metadata filtreleri ve en az üç filter-selectivity kovası;
- aynı corpus'un checksum'ı ve kaynak gizlilik sınıflandırması.

Sorguların test split'i eşik seçmek için kullanılmaz. Eşik validation split'te
belirlenir; final sonuç yalnızca test split'te bir kez raporlanır.
Kod tarafındaki `evaluate_abstention_threshold` yalnızca sorgu türü ve skor
listeleriyle privacy-safe kabul/ret oranlarını hesaplar. `choose_abstention_threshold`
validation kalite tabanlarını sağlayan en yüksek eşiği seçer; uygun eşik yoksa
sessizce varsayılan üretmez ve fail-closed hata verir. Bu primitive final ölçümün
yerine geçmez, fakat eşik seçimini tekrarlanabilir kılar.

## Deney akışı

1. Host, Python, Qdrant image/client, model revision ve ayar manifest'ini kaydet.
2. Temiz bir collection oluştur, corpus'u ingest et ve point/storage boyutunu
   kaydet.
3. Dense baseline'ı warm-up sonrasında üç tekrar çalıştır.
4. Filtre selectivity ve concurrency matrisini ayrı koş; hata ve tail latency
   artışını kalite metriklerinden ayır.
5. Snapshot al, yeni izole konuma restore et; snapshot boyutu ve süreyi kaydet.
6. Aynı deneyi seçilen tek V2 adayıyla tekrarla.
7. Karar günlüğüne ham dosya yollarını, özet sonuçları, başarısız koşulları ve
   rollback kararını ekle.

Backup sırasında `--corpus-manifest` verilirse parser sürümleri doğrulanmış
corpus manifestinden backup manifestine aktarılır. Corpus checksum'ı da
backup'a yazılır; snapshot alınmadan önce manifest checksum ve chunk kimliği
sözleşmesi kontrol edilir. Geçersiz manifest provider/Qdrant servisi açılmadan
reddedilir.
Restore sırasında aynı corpus sözleşmesi `--corpus-manifest` ile verilirse
backup corpus checksum'ı karşılaştırılır ve uyuşmazlıkta restore başlatılmaz.

Geliştirme sırasında kullanılacak bounded concurrency primitive'i
`run_concurrency_probe` adını taşır. Sorgu metni veya belge metni loglamadan
toplam istek, hata, throughput, p50/p95/p99 latency ve hata sınıfı dağılımı
üretir. Hata mesajı hiçbir zaman çıktıya alınmaz; böylece geçici servis/provider
hataları ayrıştırılabilirken sorgu veya belge içeriğinin sızma riski azaltılır.
Concurrency 1–64, repetitions 1–100 ve toplam probe istekleri 100.000 ile
sınırlıdır; matrix çalıştırıcısı ayrıca tüm seviyelerin toplamını da aynı
100.000 istek bütçesiyle sınırlar ve kontrolü iş listesi oluşturulmadan önce
yapar. Bu yardımcı final load testinin yerine geçmez ve gerçek
corpus/server ölçümü yapılmadan kapasite iddiası oluşturmaz.
CLI terminal çıktısı makinece parse edilebilir JSON'dur; `--output` verilirse
aynı JSON dosyaya yazılır.
Başarı, hata izolasyonu ve sınır değerleri `tests/test_benchmark.py` içinde
hızlı unit testlerle korunur; bu testler gerçek kapasite sonucu değildir.

CLI eşdeğeri:

```powershell
vdb concurrency-probe --fixture data/benchmarks/queries-v1.json `
  --concurrency 4 --repetitions 2 `
  --output data/benchmarks/runs/concurrency-c4-r2.json
```

CLI kalite ölçümünde aynı fixture'ı üç kez saklamak için:

```powershell
vdb benchmark --fixture data/benchmarks/queries.json --limit 5 --repeat 3 `
  --output data/benchmarks/runs/dense-2026-09-13.json
```

Kapasite matrisi için worker seviyeleri ayrı probe koşuları olarak yürütülür;
her koşu aynı fixture ve `k` değeriyle çalıştırılır. Matrix yardımcı fonksiyonu
seviyeleri sıralı/tekil tutar, her probe'un bounded istek bütçesini korur ve
sonuçlarda yalnızca worker sayısı, istek sayısı, hata türü sayıları ve latency
özetlerini taşır. Her probe/matrix sonucu ayrıca opsiyonel fixture checksum,
corpus checksum ve embedding manifest kimliğini taşır; bu alanlar aynı ölçümün
yanlış veri/model ile karşılaştırılmasını önler. Sorgu veya belge metni matrix
çıktısına alınmaz. Gerçek final
koşusunda önerilen seviyeler `1, 2, 4, 8, 16` olup, host/server sınırına göre
değiştirilebilir.

CLI ile matrix çalıştırma örneği:

```powershell
vdb concurrency-probe --fixture data/benchmarks/queries-v1.json `
  --concurrency-levels 1 2 4 8 16 --repetitions 2 `
  --output data/benchmarks/runs/concurrency-matrix.json
```

Bu kullanımda çıktı `{ "runs": [...] }` zarfında her worker seviyesini taşır;
eski `--concurrency 4` kullanımı tek probe JSON'unu üretmeye devam eder.
Matrix writer'ı seviyelerin tekil olmasını ve aynı worker seviyesinin iki kez
raporlanmamasını doğrular; çıktı yalnızca `ConcurrencyResult.to_dict()` alanlarını
taşır.
Tekil benchmark ve concurrency matrix writer'ları sırasıyla
`benchmark-result.schema.json` ve `concurrency-result.schema.json` ile
fail-closed doğrulanır; bozuk veya eksik artefact diske yazılmaz.
Tekrarlı koşular ve matrix seviyeleri arasında fixture/corpus/model provenance
değerleri farklıysa aggregate yazımı da reddedilir.

`--repeat 1` varsayılandır ve mevcut tek sonuç JSON şemasını korur. `--repeat`
2–20 arasında olduğunda terminal her koşuyu numarasıyla yazdırır ve çıktı
`{ "runs": [...] }` zarfında her koşunun ham sonucunu saklar. Aynı zarfın
`summary` alanında ortalama/minimum/maksimum değerleri de taşınır; ham koşular
kaybolmaz. Terminal özetinde wall-clock
`elapsed_seconds` ile process `cpu_seconds` ayrı gösterilir.

Final ölçümde yanlış veya eksik fixture ile provider/Qdrant başlatmamak için
acceptance preflight seçenekleri kullanılabilir:

```powershell
vdb benchmark --fixture data/benchmarks/queries-v1.json `
  --fixture-manifest data/benchmarks/query-fixture-manifest.json `
  --corpus-manifest data/manifests/corpus-manifest.json `
  --labels data/benchmarks/labels-v1.json
```

Preflight fixture, manifest, corpus checksum/parser/chunking sürümü ve label eşleşmesini
ölçüm servisleri başlamadan kontrol eder; mevcut `contract-only` manifest bunu
bilinçli olarak reddeder. CLI sözleşme hatasını traceback yerine kısa bir
stderr mesajı ve `2` çıkış koduyla bildirir.

## Sonuç kaydı

Her tekrar için benchmark'ın ürettiği ham sonuç ve host/server ölçümlerini
birleştiren bir **deney zarfı** tutulmalıdır. Aşağıdaki örnek deney zarfıdır;
`vdb benchmark` doğrudan yalnızca kalite, latency, `cpu_seconds`, `rss_mb`,
hata ve query-type alanlarını üretir. Model/corpus/Qdrant ve restore alanları
çalıştırma sarmalayıcısı veya deney günlüğü tarafından doldurulur.

```json
{
  "run_id": "2026-09-13-dense-r1",
  "corpus_checksum": "sha256:...",
  "query_fixture": "data/benchmarks/...json",
  "model_manifest_id": "...",
  "qdrant_version": "...",
  "mode": "dense",
  "repeat": 1,
  "query_count": 300,
  "quality": {"recall_at_k": 0.0, "mrr_at_k": 0.0, "ndcg_at_k": 0.0},
  "latency_ms": {"p50": 0.0, "p95": 0.0, "p99": 0.0},
  "cpu_seconds": 0.0,
  "rss_mb": null,
  "disk_bytes": null,
  "freshness_ms": {"p95": 0.0},
  "restore": {"snapshot_bytes": 0, "duration_seconds": 0.0},
  "errors": 0
}
```

RSS ve disk alanları mevcut araç tarafından üretilemiyorsa `null` bırakılır;
benchmark process CPU süresi ve gözlenen process RSS değerini üretir. RSS bir
host/Qdrant toplamı veya garantili peak değildir. Ölçüm eksikliği karar günlüğünde
açıkça belirtilmelidir; tahmin edilen kaynak değeri gerçek ölçüm gibi yazılmaz.

## V2 adayını açma kararı

Aday ancak ilgili darboğazı çözdüğünü gösterirse açılır. Genel koruma eşikleri:
Recall regresyonu en fazla 2 yüzde puanı, p95 artışı en fazla %20, hata oranında
anlamlı artış yok ve güvenlik testlerinde bypass yok. Hiçbir aday bu koşulları
sağlamazsa V1.7 dense varsayılanı korunur ve eksik ölçüm tamamlanır.

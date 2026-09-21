# V2.0 geçiş kapısı ve aday deney matrisi

## Amaç

V1.7 kişisel ve tek makine odaklı sistemin sınırları ölçülmeden V2.0 kapsamına
geçilmez. Bu belge, ileri özelliklerin teknik olarak ilgi çekici olduğu için
değil, gerçek iş yükünde ölçülebilir bir darboğazı çözdüğü için açılmasını
sağlar. Her aday ayrı bir feature flag, deney kartı ve rollback planıyla
uygulanır; V1 varsayılanı korunur.

## V2.0 açılış koşulları

V2.0 planlama aşaması ancak aşağıdaki kanıtların tamamı bulunduğunda açılır:

1. Temsilî kişisel corpus, üretim benzeri metadata ve en az 300 etiketli sorgu
   ile üç tekrarlı benchmark kaydı vardır.
2. V1.7 dense baseline için query-type Recall/MRR/nDCG, p95/p99, hata oranı,
   ingest tazeliği, disk/RAM ve snapshot/restore süresi kaydedilmiştir.
3. En az bir kapasite sınırı ölçülmüştür: veri boyutu, eşzamanlı sorgu, ingest
   kuyruğu, RAM, disk veya restore süresi.
4. V2 adayının çözdüğü darboğaz, mevcut opt-in V1.2–V1.6 yollarıyla
   çözülemiyor veya kabul edilen maliyet sınırını aşıyordur.
5. Aday için veri güvenliği, provenance, RAG sınırı, geriye dönük uyumluluk ve
   geri dönüş prosedürü yazılmıştır.

Bu koşullar sağlanmıyorsa sonraki iş V2 kodu değil, veri seti ve kapasite
ölçümünü güçlendirmektir.

## Adaylar ve kanıt eşikleri

| Aday | Açılma sinyali | İlk deney | Zorunlu koruma |
|---|---|---|---|
| Multimodal | Görsel/PDF tablo içeriği metinle kayboluyor | Metin-only ve multimodal retrieval karşılaştırması | Kaynak sayfa/varlık provenance'ı |
| Graph-RAG | Sorular belge içi varlık/ilişki yürüyüşü gerektiriyor | Entity-link precision, path recall ve answer support | Grafik kanıtı retrieval metninden ayrılır |
| Çoklu kullanıcı | İkinci kullanıcı veya tenant ihtiyacı oluşuyor | ACL bypass ve tenant isolation testi | Owner/tenant filtresi sunucu tarafında zorunlu |
| Sharding | Tek koleksiyon RAM/disk veya throughput sınırına çarpıyor | Tek shard ve shard routing karşılaştırması | Deterministik routing ve reshard rollback |
| HA/dağıtık tutarlılık | Tek makine arızası kabul edilemez hale geliyor | WAL/snapshot/failover ve RPO/RTO testi | Restore ve deletion ledger doğrulaması |

Birden fazla sinyal varsa önce veri erişim güvenliğini etkileyen çoklu kullanıcı
izolasyonu, sonra kapasite/erişilebilirlik, en son multimodal veya Graph-RAG
ele alınır. Bu sıra bir zorunlu teknoloji seçimi değil, risk azaltma sırasıdır.

## Deney sözleşmesi

Her V2 adayı için deney kartı şu alanları içermelidir:

- değişmeyen API, payload, embedding manifest ve provenance alanları;
- baseline ve aday yapılandırması, model/revision, indeks ve donanım;
- corpus sürümü, sorgu sınıfları ve train/validation/test ayrımı;
- Recall@k, MRR/nDCG, negatif başarı, p50/p95/p99 ve hata/fallback oranı;
- RAM, disk, snapshot boyutu, ingest tazeliği, concurrency ve restore süresi;
- güvenlik testleri, bilinen başarısızlıklar ve veri silme davranışı;
- varsayılanı değiştirme eşiği, feature flag ve rollback adımları.

Varsayılanın değişmesi için aday; ilgili darboğazı çözmeli, kaliteyi baseline'a
göre 2 puandan fazla düşürmemeli, p95'i %20'den fazla kötüleştirmemeli ve
güvenlik regresyonu üretmemelidir. Eşik sağlanmazsa aday opt-in kalır veya
çıkarılır.

## Aşamalı uygulama

```text
V1.7 baseline ve kapasite ölçümü
          ↓
tek aday için deney kartı + izole flag
          ↓
offline kalite + güvenlik + kaynak testi
          ↓
küçük corpus üzerinde runtime smoke
          ↓
temsilî corpus üzerinde tekrarlı benchmark
          ↓
karar günlüğü: varsayılan / opt-in / geri çek
```

V2.0, bu adaylardan en az birinin geçiş kapısını geçmesiyle bir release etiketi
değil, ölçüm sonucu doğrulanmış bir mimari genişleme olarak ele alınır. Aday
başarısızsa mevcut V1 koleksiyonları, API sözleşmesi ve RAG entegrasyon sınırı
çalışmaya devam eder.

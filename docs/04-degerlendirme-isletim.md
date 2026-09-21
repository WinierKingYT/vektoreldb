# 4. Değerlendirme, güvenlik ve işletim

## Ölçüm

En az 30–100 gerçek sorgudan oluşan, beklenen kaynak chunk'ları etiketlenmiş bir test seti tut:

- Recall@k ve MRR: doğru parçayı bulma.
- nDCG@k: sıralama kalitesi.
- p50/p95 latency, hata oranı ve embedding maliyeti.
- Filtreli ve filtresiz sorguları ayrı raporla.

Exact brute-force sonuçlarını yalnızca ANN karşılaştırma referansı olarak kullan; relevance ground truth için insan/uzman etiketleri gerekir. HNSW/IVF recall'ını bu referansa göre karşılaştır. Chunk boyutu, overlap, model, `k`, `ef_search` ve reranker değişikliklerini tek tek deneyerek karar günlüğüne yaz.

## Güvenlik

- Her sorguda erişim filtresini sunucu tarafında uygula; istemciye güvenme.
- Hassas metni loglama; kaynak ve skor loglarını maskele.
- Koleksiyon, snapshot ve API anahtarlarını ayrı yetkilendir.
- Prompt injection içeren kaynakları güvenilir talimat sayma; retrieval çıktısını veri olarak işaretle.
- Silme işlemlerini checksum/document_id ile doğrula ve geri alınabilir snapshot al.

## Yeniden indeksleme

Model, parser veya chunking değişiminde çift koleksiyonlu blue/green geçiş kullan: yeni koleksiyonu oluştur, benchmark ile doğrula, sonra uygulama alias'ını değiştir. Rollback için eski koleksiyonu kabul eşiği doğrulanana kadar sakla.

## Yedekleme ve izleme

Snapshot geri yüklemeyi düzenli test et. Kaynak dosyaları ve index manifest'i de yedekle. Nokta sayısı, boş/eksik embedding, filtreli sıfır sonuç oranı, p95 latency, indeks boyutu ve model sürümü için alarm üret. RPO/RTO hedeflerini yazılı tut.

## Başlangıç kabul kriterleri

- Aynı kaynak iki kez yüklenince nokta sayısı değişmiyor.
- Yetkisiz tenant/visibility sonucu dönmüyor.
- Test setinde hedeflenen Recall@k ve p95 latency sağlanıyor.
- Snapshot geri yükleme tatbikatı başarılı.
- Düşük skor durumunda sistem kaynak yok diyebiliyor.

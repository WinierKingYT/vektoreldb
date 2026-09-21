# 12. Operasyon runbook'u

## Günlük kontrol

- Qdrant health durumu
- disk/RAM kullanımı
- bekleyen ingest ve hata kuyruğu
- boş embedding veya düşük kaliteli parser çıktısı
- sorgu p95 latency ve hata oranı
- son snapshot zamanı

## İçe aktarma başarısızsa

1. `request_id` ve `document_id` ile hatayı bul.
2. Parser mı provider mı Qdrant mı olduğunu ayır.
3. Retryable ise sınırlı exponential backoff uygula.
4. Aynı hash ile idempotent yeniden çalıştır.
5. Düzelmiyorsa dead-letter kaydı oluştur; başarılı olmayan belgeyi index'e alma.

## Arama yavaşsa

Önce sorgu boyutu, filtre alanı, payload indeksleri, sonuç `top_k`, p95 ve indekslenmiş veri oranını kontrol et. Reindex sırasında yeni point'lerin önce yazılıp eski content hash'li chunk'ların sonra temizlendiğini doğrula. Sonra HNSW arama bütçesi, disk/RAM baskısı ve reranker kullanımını ölç. Benchmark olmadan parametre değişikliğini kalıcılaştırma.

## Bozuk veya yanlış sonuç varsa

Kaynak metni, parser çıktısını, chunk sınırını, model manifest'ini ve filtreyi sırayla doğrula. Hızlı çözüm olarak skor eşiğini rastgele yükseltme; bunun yerine benchmark üzerinde kök nedeni ayır.

## Backup/restore

1. Kaynak dosya, embedding/parser/chunking sürümlerini içeren manifest ve Qdrant snapshot'ını al.
2. Snapshot checksum'ını doğrula.
   İsteğe bağlı `vdb restore <snapshot> --manifest <manifest.json>` ile collection ve embedding manifest uyumluluğunu da doğrula.
3. İzole bir hedefte restore et.
4. Nokta sayısı, koleksiyon konfigürasyonu, örnek aramalar ve erişim testlerini çalıştır.
5. Sonuçları tarih ve sürüm ile kaydet.

Qdrant snapshot'ı collection alias'larını kapsamaz; alias/aktif koleksiyon bilgisi ayrıca yedeklenmelidir. [Qdrant snapshot rehberi](https://qdrant.tech/documentation/operations/snapshots/)

## Değişiklik yönetimi

Model, parser, chunking, şema veya Qdrant sürümü değişikliğinde: karar kaydı → yeni manifest → izole test → benchmark → snapshot → geçiş → gözlem → rollback penceresi. Local snapshot/restore sırasında client geçici olarak kapatılır; restore yeni storage'ı staging alanda hazırlar, mevcut storage'ı geçici yedekte tutar ve kopyalama hatasında otomatik geri alır. Başarılı snapshot ve restore sonrasında aynı store client'ı yeniden açılır, geçersiz restore ise mevcut store'u kullanılabilir bırakır.

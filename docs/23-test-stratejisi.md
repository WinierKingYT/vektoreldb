# 23. Test stratejisi

## Katmanlar

1. Unit: hash, UUIDv5, chunk id, token sınırı ve filtre oluşturma.
2. Fixture: her desteklenen dosya türünde beklenen metin/konum çıktısı.
3. Contract: API şeması, hata kodu, pagination ve idempotency.
4. Integration: parser → provider → Qdrant → search.
5. Retrieval: benchmark Recall/MRR/nDCG.
6. Security: owner filtresi, log redaction, zararlı dosya ve prompt injection.
7. Recovery: snapshot restore, stale chunk temizliği ve rollback.

## Minimum fixture seti

Türkçe karakter, başlık, tablo, liste, duplicate içerik, bozuk encoding, boş dosya, çok uzun dosya, taranmış PDF ve yetki sınırı testleri bulunur.

Her değişiklikte hızlı unit/contract testleri; parser, model veya retrieval değişiminde tam benchmark çalışır.

Etiketli retrieval fixture'ının final kabul testi `fixture-validate --labels`
ve `--corpus-manifest` ile yapılır. `status=ready` manifesti, sorgu/dağılım
kapıları geçse bile label dosyası veya güncel corpus manifesti olmadan kabul
edilmemelidir; `fixture-coverage` ise hazırlık aşaması olduğundan ikisi olmadan
çalışabilir.

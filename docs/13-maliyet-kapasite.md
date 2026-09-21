# 13. Maliyet ve kapasite planı

## Kaynak kalemleri

- kaynak dosyaların depolaması
- parse edilmiş metin ve metadata
- dense/sparse/multi-vector depolaması
- indeks ve payload RAM'i
- snapshot ve yedekler
- local model CPU/GPU/RAM kullanımı
- harici embedding token maliyeti
- ağ ve gözlemleme maliyeti

## Basit tahmin

```text
toplam embedding maliyeti
  = toplam_input_token × sağlayıcı_birim_fiyatı

yaklaşık vektör ham boyutu
  = nokta_sayısı × boyut × bytes_per_value
```

Gerçek kapasite tahminine payload, indeks, segment, snapshot ve büyüme payı eklenir. İlk tahmin ölçüm yerine geçmez.

## Local/harici seçim eşiği

Az ve hassas veri için local model; hızlı başlangıç, yüksek model kalitesi veya düşük işletim yükü için harici model değerlendirilebilir. Karar yalnızca para üzerinden değil, veri gizliliği ve p95 latency ile verilir.

## İzlenecek limitler

- disk doluluk alarmı: %70 uyarı, %85 aksiyon
- RAM baskısı ve swap
- günlük embedding token/adet
- batch başarısızlık oranı
- snapshot boyutu ve restore süresi
- sorgu p95/p99 latency

Eşikler donanıma göre ilk benchmark sonrasında kesinleştirilir.

# 24. Sürüm ve dependency politikası

## Pinleme

Qdrant Docker image tag'i, Python sürümü, parser kütüphaneleri, istemci sürümleri ve embedding model revision'ları tagsiz/latest kullanılmadan sabitlenir.

## Güncelleme süreci

1. Değişiklik ve güvenlik notlarını incele.
2. İzole ortamda smoke/integration test çalıştır.
3. Benchmark ve restore testi yap.
4. Karar günlüğünü güncelle.
5. Eski sürüm için rollback yolu sakla.

Qdrant snapshot restore sürüm uyumluluğu ayrıca kontrol edilir; yalnızca image güncellemesiyle restore garantisi varsayılmaz.

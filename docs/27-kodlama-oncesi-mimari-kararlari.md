# 27. Kodlama öncesi mimari kararları

## Bağlayıcı V1 kararları

- Tek kullanıcı; erişim kimliği `owner_id = me`.
- Qdrant tek makine üzerinde çalışır.
- İlk retrieval modu dense-only'dir; hybrid v2 migration'ıdır.
- Point ID UUIDv5; mantıksal id'ler payload'dadır.
- `document_id` kaynak URI'den, `content_hash` içerikten türetilir.
- Model seçimi için local varsayılan korunur; harici aday opt-in'dir ve final
  kişisel corpus benchmark'ı sonrasında karşılaştırılır.
- Ingest/update/delete asenkron ve idempotent'tir.
- Skor eşiği manifest ve benchmark'a bağlıdır; evrensel sabit yoktur.
- Orijinal kaynaklar vector DB dışında korunur.

## Başlangıçta açık olup güncel durumda izlenen kararlar

- local ve OpenAI adaylarının kesin model/revision seçimi
- gerçek benchmark sorguları ve etiketleri
- kaynak klasörleri
- parser kütüphanelerinin kesin sürümleri
- ilk restore tatbikatı ve donanım ölçümü

Bu maddeler kodlama öncesi tasarım girdileriydi; mevcut implementasyon bunları
manifest, deney kartı ve final kabul kapılarıyla izlemeye devam eder. Kalıcı
collection/API değişiklikleri yine final ölçüm ve rollback kanıtı olmadan
varsayılan davranışa alınmaz.

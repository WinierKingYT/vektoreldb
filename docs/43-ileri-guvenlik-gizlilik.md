# 43. İleri güvenlik ve gizlilik

## Veri minimizasyonu

Embedding'e hassas olmayan gerekli metni gönder; secret, token, kimlik ve gereksiz kişisel alanları redakte et. Harici provider kullanımı sınıf bazında engellenebilir.

## Saldırı senaryoları

- poisoned document ve prompt injection
- retrieval result üzerinden talimat enjeksiyonu
- metadata filtre bypass
- embedding inversion/erişimli vektör sızıntısı
- snapshot ve log kopyalarının sızması

## Kontroller

Kaynak güven seviyesi, kullanıcı yetkisi ve model talimatları ayrı tutulur. Retrieval çıktısı LLM'e “veri” olarak aktarılır. Şüpheli içerik karantinaya alınır; güvenlik olayları kaynak metni içermeyen audit kayıtlarıyla izlenir.

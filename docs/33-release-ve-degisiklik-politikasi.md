# 33. Release ve değişiklik politikası

## Sürüm türleri

- Patch: doküman, hata düzeltmesi veya geriye uyumlu parser düzeltmesi.
- Minor: yeni desteklenen veri türü veya geriye uyumlu API alanı.
- Major: embedding uzayı, kanonik şema, erişim modeli veya API uyumsuzluğu.

## Release kapısı

- Şema/OpenAPI doğrulaması başarılı.
- Unit, contract, integration ve güvenlik testleri başarılı.
- Parser/model/retrieval değişikliklerinde benchmark regression eşiği geçilmiş.
- Snapshot ve rollback planı hazır.
- Karar günlüğü ve CHANGELOG güncel.

## Rollback

Önce aktif alias eski koleksiyona alınır; sonra başarısız yeni koleksiyon izole edilir. Kaynak ve manifest korunur. Rollback sonrasında hata kök nedeni ve etkilenen belgeler raporlanır.

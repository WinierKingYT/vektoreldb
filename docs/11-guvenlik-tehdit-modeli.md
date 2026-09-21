# 11. Güvenlik ve tehdit modeli

## Güven sınırları

Kaynak dosya, parser, embedding sağlayıcısı, Qdrant, API istemcisi ve LLM birbirinden ayrı güven sınırlarıdır. Retrieval çıktısı güvenilir talimat değil, dış veri olarak değerlendirilir.

## Tehditler ve kontroller

| Tehdit | Kontrol |
|---|---|
| Yetkisiz belge sonucu | Sunucu tarafında zorunlu erişim filtresi |
| Prompt injection | Kaynak metnini talimatlardan ayırma, içerik işaretleme |
| Harici sağlayıcıya veri sızıntısı | Redaksiyon, açık provider seçimi, veri politikası kontrolü ve HTTP ingest için zorunlu source_root |
| Anahtar sızıntısı | Secret store/env, log redaction |
| Zararlı dosya | Boyut/tür sınırı, kaynak kökü dışına yönlenen symlink reddi, DOCX arşiv üye yolu/açılmış boyut sınırı, şifreli PDF reddi ve PDF extraction sınırı, sandbox parser, malware taraması |
| Metadata ile yetki yükseltme | Kullanıcı metadata'sını yetki kaynağı kabul etmeme |
| Snapshot sızıntısı | Şifreli depolama, kısıtlı erişim ve local restore'da canonical traversal/duplicate/symlink/special-file üye reddi; staging/rollback ve başarılı restore sonrası client yeniden açılması |
| Silinen verinin kalması | Vector DB, kaynak, cache ve yedek yaşam döngüsü |

## Erişim ilkeleri

- Varsayılan erişim: deny.
- Her sorgu kullanıcı/owner kapsamı ile birleştirilir.
- `visibility`, `owner_id` ve `document_status` sunucu tarafından belirlenir.
- Loglarda belge metni, sorgu metni ve embedding yazılmaz; gerekirse hash/request id kullanılır.
- Harici embedding kullanımı ayrı bir açık ayar ve audit olayıdır.

## Silme ve veri saklama

Silme isteği document id ve content hash ile doğrulanır. İlişkili chunk'lar, arama cache'i ve aktif indeks kaldırılır; backup saklama süresi ayrıca belgelenir. Geri yükleme sonrası silme listesi yeniden uygulanır.

## Güvenlik kabul kriterleri

- Yetkisiz belge için tek bir sonuç dönmez.
- Kullanıcı filtresini kaldıran istekler reddedilir.
- Snapshot ve API anahtarı erişimi test edilir.
- Hassas veri içeren test sorguları loglarda görünmez.
- Parser başarısızlığı servis çökmesine veya sessiz veri kaybına yol açmaz.

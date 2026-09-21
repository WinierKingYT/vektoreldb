# 19. Kimlik ve erişim modeli

## V1 kişisel model

Tek kullanıcı olduğu için kanonik alan `owner_id = me` değeridir. `tenant_id` kullanılmaz. İleride çok kullanıcı eklenirse `owner_id` üstünde tenant/ACL tasarımı ayrı migration olarak yapılır.

## Güvenlik alanları

`owner_id`, `document_status`, `visibility` ve erişim kapsamı sunucu tarafından atanır veya doğrulanır. İstemci bunları serbestçe yetki yükseltecek biçimde gönderemez.

## Zorunlu filtre

Her search/get/delete isteği sunucu tarafından `owner_id = authenticated_owner` ve `document_status = active` ile birleştirilir. Filtre uygulanmadan önce sonuçları getirip sonradan elemek güvenli kabul edilmez.

## Testler

- Eksik kimlik doğrulama reddedilir.
- Başka owner id isteyen filtre reddedilir veya güvenli biçimde boş sonuç döner.
- Arşivlenmiş belge normal aramada görünmez.
- Metadata güncellemesi owner alanını değiştiremez.

# 21. Embedding model registry

## Amaç

Kullanılabilir embedding modelleri merkezi bir kayıtla tanımlanır; uygulama rastgele model adı alamaz.

Her model kaydı: `manifest_id`, `provider`, `model`, `revision`, `dimensions`, `distance`, `normalized`, `query_encoding`, `document_encoding`, `max_input_tokens`, `license`, `data_policy`, `status` ve benchmark sonuçlarını içerir.

## İlk adaylar

Bir local Sentence Transformers modeli ve bir OpenAI-compatible embedding modeli
benchmark adayıdır. V1 runtime'ın varsayılanı local
`intfloat/multilingual-e5-base` provider'ıdır; revision
`d128750597153bb5987e10b1c3493a34e5a4502a`, 768 boyut ve cosine metric ile
pinlenmiştir. Harici provider adapter'ı kodda mevcut olsa da yalnızca açık
`VDB_EMBEDDING_PROVIDER=openai` seçimi, anahtar ve veri paylaşımı kararıyla
opt-in kullanılabilir; kalite/maliyet karşılaştırması final kişisel corpus
benchmark'ına kadar açık kalır.

## Sağlayıcı davranışı

Provider; batch sınırı, giriş sırası, boş input davranışı, timeout, retryable hata, rate limit ve çıktı boyutunu bildirir. Girdi sırası korunur; başarısız batch kısmen başarılı kabul edilmez.

## Geçiş

Registry'de `active`, `candidate`, `deprecated` durumları bulunur. Yeni model candidate olarak test edilir; kabul edilirse yeni koleksiyon manifest'ine bağlanır.

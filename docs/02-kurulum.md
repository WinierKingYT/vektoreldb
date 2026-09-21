# 2. Kurulum ve ilk indeksleme

## Seçim tablosu

| İhtiyaç | Başlangıç seçimi |
|---|---|
| Kişisel tek makine, metadata filtreleri | Qdrant |
| Çok küçük offline prototip, RAM içi | FAISS |
| Zaten PostgreSQL kullanılıyor, SQL/ACID önemli | pgvector |

Bu doküman Qdrant yolunu esas alır. Sağlayıcı değişse de veri modeli ve değerlendirme sözleşmesi korunur.

## Docker olmadan local persistence

V1 varsayılanı `path:qdrant_storage`'dır. Bu mod Qdrant client'ın local disk persistence özelliğini kullanır ve tek makinede Docker daemon gerektirmez. Bu nedenle Docker şu an geliştirme akışının veya yerel kullanımın ön koşulu değildir. Payload index'leri local modda performans etkisi sağlamaz; filtre performansı ve snapshot davranışının server Qdrant üzerindeki doğrulaması daha sonraki entegrasyon testine bırakılmıştır.

Local modda `vdb backup` Qdrant storage klasörünü tar arşivi olarak dışarı aktarır ve SHA-256 checksum'ı manifest'e yazar; `vdb restore <archive> --checksum <sha256>` arşivi doğrulayıp storage'ı yeniler. Server snapshot checksum'ı da Qdrant yanıtından manifest'e taşınır. Restore işlemi mevcut local storage'ı değiştirir ve işlem sonrası CLI yeniden başlatılmalıdır.

`.env` içinde:

```text
VDB_QDRANT_URL=path:qdrant_storage
```

## Docker ile server Qdrant

Docker yalnızca server-mode Qdrant entegrasyonunu, gerçek payload index davranışını ve container ortamındaki snapshot/restore akışını doğrulamak için gereklidir. Docker Compose, server storage ile snapshot dizinlerini local Qdrant yolundan ayrı named volume'larda tutar; bu, Windows bind-mounted filesystem uyarılarını ve snapshot performans sorunlarını önler. Qdrant `v1.19.0` image'ında server snapshot restore konumu node içindeki `file:///qdrant/snapshots/<collection>/<snapshot>` URI'sıdır; snapshot adı tek başına yeterli değildir. Local persistence ile kodlama, birim testleri ve server smoke doğrulaması birbirinden bağımsız yürütülebilir.

```powershell
docker run --name personal-qdrant -p 6333:6333 -p 6334:6334 `
  -v personal-qdrant-storage:/qdrant/storage `
  -v personal-qdrant-snapshots:/qdrant/snapshots qdrant/qdrant:<PINNED_VERSION>
```

Üretimde kimlik doğrulama, TLS, yedekleme ve erişim ağını ayrıca yapılandır. Geliştirme verisini üretim verisinden ayır.

## Koleksiyon sözleşmesi

- Boyut: embedding modelinin gerçek çıktısıyla doğrula; elle varsayma.
- Mesafe: cosine, dot-product veya Euclidean seçimini modelle birlikte kaydet.
- HNSW: önce varsayılanlarla başla; benchmark olmadan agresif ayar yapma.
- İsteğe bağlı `VDB_HNSW_EF`, sorgu başına HNSW arama bütçesini belirler; boş bırakılırsa Qdrant varsayılanı kullanılır.
- V1 filtre alanları: `owner_id` ve `document_status` sorgu tarafında zorunludur; server modunda `document_id`, `source_uri`, `source_type` ve `title` payload indeksleri oluşturulur. Bu dört alan kullanıcı allowlist filtresi olarak kullanılabilir.
- Yükleme: batch upsert, retry ve checksum kontrolü kullan.

Mevcut collection yeniden açılırken boyut ve cosine mesafe sözleşmesi provider ile karşılaştırılır; uyumsuzlukta ingest başlamadan hata verilir. Bu, yanlış model ile aynı collection'a yazmayı engeller.

Bir kaynak klasöründeki desteklenen dosyaları deterministik sırayla toplu almak
için `vdb ingest-dir data/sources` kullanılabilir. Desteklenmeyen uzantılar
atlanır; tek dosya parse/embedding hatası diğer dosyaları durdurmaz ve hata
özeti yalnızca dosya yolu ile hata türünü içerir; parser/provider exception'ları
dosya seviyesinde izole edilir. Her dosya kendi replacement
işlemiyle işlendiği için başarısız dosya mevcut indeks sürümünü değiştirmez.

## Sağlık kontrolü

İlk çalıştırmada koleksiyonun boyutunu, nokta sayısını, model sürümünü, örnek vektör normunu ve filtre indekslerini raporla. Yeniden başlatma sonrası aynı checksum için ikinci yükleme nokta sayısını çoğaltmamalıdır.

Embedding modeli bulunamazsa ingest açık bir runtime hatasıyla durur; eksiksiz local Hugging Face cache hazırlanmalı veya model bir kez indirilebilmelidir. Bu durumda mevcut indeks değiştirilmez.

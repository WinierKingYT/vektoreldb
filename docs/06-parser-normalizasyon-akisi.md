# 6. Parser ve normalizasyon akışı

## Ortak pipeline

```text
dosya keşfi
  → tür/encoding tespiti
  → parser
  → metin temizleme
  → bölüm ve konum çıkarma
  → kalite kontrolü
  → chunking
  → embedding
  → batch upsert
  → doğrulama
```

Her aşama sürümlü, gözlemlenebilir ve tekrar çalıştırılabilir olmalıdır.

## JSONL

JSONL'de her boş olmayan satır bağımsız bir JSON kaydıdır; `location.line` ile
orijinal satır numarası korunur. Herhangi bir satır parse edilemezse kaynak dosya
başarısız sayılır ve bozuk kayıt sessizce atlanmaz.

## Markdown/TXT

- UTF-8 olarak normalize et.
- Başlık seviyelerini `heading_path` olarak koru.
- Kod bloklarını düz metinle karıştırma.
- Satır sonlarını ve gereksiz boşlukları normalize et.

## PDF

- Sayfa numarasını her bölümde sakla.
- Metin sırasını örnek sayfalarda görsel olarak doğrula.
- Çok sütunlu sayfalarda okuma sırası kontrolü yap.
- Tablo, dipnot ve başlıkları ayrı kalite sınıflarıyla değerlendir.
- Metin çıkmayan sayfalarda OCR gerektiğini işaretle.

PyMuPDF metin çıkarabilir; ancak düz metin çıktısı her zaman okuyucunun beklediği doğal sırayı vermeyebilir. Bu nedenle PDF parser sonucu otomatik olarak doğru kabul edilmez. [PyMuPDF metin çıkarma rehberi](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)

## DOCX

- Paragraf sırasını koru.
- Başlık stillerini bölüm yoluna çevir.
- Tabloları satır başlıklarıyla birlikte metinleştir.
- Yorum, dipnot ve gizli metin için açık politika belirle.

## HTML

- Ana içerik, başlık, tarih ve kaynak URL'sini koru.
- Menü, reklam, cookie banner ve tekrar eden footer'ı çıkar.
- HTML kaynağını ve temiz metni ayrı sakla.

## JSON/CSV

- Şema ve encoding'i doğrula.
- Her kayıt için stabil kayıt kimliği üret.
- Alan adlarını metne bağlam ekleyecek biçimde kullan.
- Çok yüksek cardinality veya sır niteliğinde alanları embedding'e sokma.

## EML

- Konu başlığını belge başlığı olarak koru.
- Yalnızca dosya adı taşımayan `text/plain` gövde parçalarını al; HTML gövdesi
  ve attachment'ları
  embedding hattına taşıma.
- Mesajdaki bölüm sırasını ve satır konumunu provenance metadata'sında koru.
- E-posta adresleri ve kişisel içerik local-first gizlilik sınıfından çıkarılmamalı;
  harici provider kullanımı ayrıca açık opt-in gerektirir.

## XML

- Yalnızca yerel XML export'larını parse et; dış bağlantı veya entity çözümleme yapma.
- DTD ve entity declaration içeren belgeleri fail-closed reddet.
- Leaf-node metnini al, node yolunu `location.path` olarak koru; attribute ve yorumları
  embedding metnine dahil etme.
- Namespace isimlerini local-name ile normalize et; karmaşık tablo/özel şema
  semantiği için ayrı parser kalite değerlendirmesi gerekir.

## Kalite kontrolleri

- karakter ve token sayısı
- boşluk/encoding hatası
- tekrar oranı
- çıkarılan metnin kaynak boyutuna oranı
- beklenen sayfa/kayıt sayısı
- hata ve uyarı sayısı

Kalite eşiğini geçmeyen belge index'e alınmaz veya `needs_review` olarak işaretlenir.

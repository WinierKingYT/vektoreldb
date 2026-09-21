# 22. Parser kalite standardı

## Başlangıç sınırları

Kaynak dosyası sınırı dosya başına 10 MB'dir (`validate_source_path`). Parser için ayrı bir çalışma zamanı timeout'u ve OCR katmanı henüz uygulanmaz. Desteklenen suffix'ler `.md`, `.markdown`, `.txt`, `.org`, `.rst`, `.log`, `.tex`, `.ics`, `.pdf`, `.docx`, `.html`, `.htm`, `.eml`, `.json`, `.jsonl`, `.ndjson`, `.yaml`, `.yml`, `.rtf`, `.csv` ve `.xml`'dir; bilinmeyen suffix açık hata ile reddedilir. `.org`, `.rst`, `.log`, `.tex` ve `.ics` dosyaları ek semantik yorumlama yapmadan güvenli plain-text parser'a yönlendirilir; `.ics` için takvim alanı ayrıştırma/normalizasyon garantisi yoktur. PDF metadata title'ı ve DOCX core-properties title'ı varsa belge başlığına taşınır. DOCX Heading1–Heading6 stilleri `heading_path` metadata'sına taşınır; karmaşık tablo/sütun yerleşimi ve PDF OCR kalite garantisi verilmez.
Corpus inventory de aynı 10 MB ve kaynak-kökü sınırını uygular; büyük, dışarı
taşan veya okunamayan destekli dosyayı tüm taramayı durdurmadan `failed` kaydıyla
raporlar. Bu kayıtlarda içerik hash'i üretilmez.
Parser API'leri (`parse_source`, `parse_source_file`, `parse_text_file`) de varsayılan 10 MB kaynak boyutu sınırını uygular; doğrudan parser
çağrısında ihtiyaç varsa `max_bytes` açıkça verilmelidir. Sınır `VDB_SOURCE_MAX_BYTES` ile güvenli biçimde artırılabilir; ingest, reindex ve corpus inventory bu değeri parser'a da aktarır; aynı ayar CLI,
server ingest ve inventory akışlarında kullanılmalıdır.
Kütüphane çağrılarında `source_root` verilmemiş olsa bile aynı boyut sınırı
uygulanır; root doğrulaması ise yalnızca yapılandırılmış kaynak kökü olan
akışlarda ayrıca devrededir.
Klasör ingest'i ve corpus inventory ayrıca varsayılan 5.000 desteklenen dosya ve
1.000.000.000 byte toplam kaynak bütçesine sahiptir (`VDB_SOURCE_MAX_FILES`,
`VDB_SOURCE_MAX_TOTAL_BYTES`). Bu bütçeler tarama kabul kapısıdır; çıktıdaki
extract edilen metin, parser çalışma süresi veya tepe RAM için garanti değildir.
Limit aşımında toplu ingest embed/store aşamasına, inventory ise dosya parse'ına
ve manifest/rapor yazımına başlamadan reddedilir. Kaynak başına parser limitleri
ve DOCX/PDF iç sınırlar yine ayrıca uygulanır.

## Mevcut parser davranışı

- YAML/YML: tek YAML belgesi; UTF-8 BOM desteklenir; `yaml.safe_load` ile
  veri olarak okunur ve deterministik, sıralı JSON metnine dönüştürülür.
  Çoklu YAML belgeleri ve Python nesnesi tag'leri desteklenmez.

- RTF: Temel kontrol kelimeleri, paragraf/satır sonları, sekme, Unicode ve cp1252
  hex kaçışları metne dönüştürülür. Gömülü resim/nesne, makro, font tablosu ve
  karmaşık stil semantiği taşınmaz; parser sonucu biçimsel belge eşdeğeri değildir.

- Markdown/TXT ve plain-text alias'ları: UTF-8 (BOM'lu dahil), UTF-16 ve UTF-32 BOM'lu
  dışa aktarımlar desteklenir; satır konumları korunur. BOM'suz farklı encoding'ler
  otomatik tahmin edilmez ve bozuk UTF-8 açık hata üretir.
- PDF: `pypdf` ile sayfa bazlı metin çıkarımı; parser regresyonları arasında gerçek `pypdf` ile oluşturulmuş minimal sentetik PDF smoke testi vardır. Hiçbir sayfadan metin çıkmazsa dosya, genel boş-belge hatası yerine taranmış/görsel içerik olasılığını ve olası OCR gereksinimini belirten açık hatayla reddedilir; bu durum tek başına girdinin tarama olduğunu kanıtlamaz. Bu test kişisel/çeşitli PDF corpus kalitesinin kanıtı değildir; taranmış PDF, OCR, tablo ve çok sütunlu okuma sırası garanti edilmez. pypdf normal çıkarım sırasının kaynak içerik akışıyla aynı olacağını garanti etmez; layout modu ayrı deneydir ve varsayılan yapılmamıştır. Sıkıştırılmış page content stream'i açılırken bellek kullanımı dosya boyutunu aşabilir; 10 MB kaynak ve 50 milyon çıkarılmış karakter sınırı süreç düzeyinde bellek/timeout izolasyonu sağlamaz. Şifreli PDF'ler ve 50 milyon karakteri aşan extraction fail-closed reddedilir. Ayrıntılar: [pypdf metin çıkarımı ve bellek notları](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).
- DOCX (`docx-v4`): XML içinden paragraf ve temel tablo satırı metni; hücreler `|` ile ayrılır. Paragraf ve hücre içindeki `w:tab`, `w:br` ve `w:cr` sırasıyla sekme/satır sonu olarak korunur; nested tablo metni üst hücreye tekrar katılmaz ve satır olarak ayrıca çıkarılır. `word/document.xml` ve `docProps/core.xml` içinde DTD/entity declaration'ları parse öncesi fail-closed reddedilir. Görsel, dipnot, yorum, gizli metin ve karmaşık stil/konum fidelity'si garanti edilmez. Çıktı sürümü değiştiği için önceden indekslenmiş DOCX kaynakları yeniden indekslenmelidir. ZIP üye yolları POSIX/Windows traversal, absolute path ve NUL karakterine karşı doğrulanır; duplicate/symbolic-link üyeler, şifreli veya 50 MB üzeri açılmış paketler fail-closed reddedilir. Bu koruma XML parser kaynak tüketimi için genel bir izolasyon/timeout garantisi değildir ([Python XML güvenlik uyarıları](https://docs.python.org/3/library/xml.html)).
- HTML (`html-v4`): yerel dosyada görünür metin; `script`, `style`, `nav`, `header`, `footer` ve `aside` alanları atılır. Atlanan etiketler tag-aware yığınla izlenir; eşleşmeyen kapanış etiketi filtrelemeyi erken sonlandırmaz, açık üst etiketin kapanması ise bozuk iç içe atlanan alt etiketleri de kapatır. Dış bağlantı takip edilmez; script çalıştırılmaz.
- JSON: tek nesne veya liste kayıtları; UTF-8 BOM desteklenir; deterministik, sıralı JSON metnine dönüştürülür.
- JSONL/NDJSON: UTF-8 BOM desteklenir; boş olmayan her satır ayrı JSON kaydıdır; `location.line` korunur ve
  bozuk satır dosyayı fail-closed yapar.
- CSV: UTF-8 BOM desteklenir; `DictReader` ile satırlar alan adı-değer metnine dönüştürülür.
- XML: UTF-8 yerel XML export'larında yalnızca leaf-node metni ve node yolu alınır;
  DTD/entity declaration içeren girdiler fail-closed reddedilir. Namespace'ler
  local-name ile normalize edilir; attribute, yorum ve karmaşık tablo semantiği
  korunmaz.
- EML: konu ve yalnızca dosya adı taşımayan düz metin gövdesi alınır; HTML gövdesi
  ve ek dosyalar işlenmez.

Bu dilim parser dispatch ve kanonik belge üretimini sağlar; kapsamlı format kalite testleri ve uzun süreli ölçümler goal'un son doğrulama kapısında yapılacaktır.

Toplu ingest akışında her dosya bağımsızdır. Bir dosyanın parse veya embedding
hatası `failed` özeti olarak tutulur; desteklenmeyen uzantı recursive taramada
seçime alınmaz.

## Kalite durumu

- `ok`: metin ve konum beklenen kaliteyi sağlıyor.
- `needs_review`: düşük metin çıkarma oranı, OCR gereksinimi, tablo/sütun belirsizliği veya yüksek tekrar.
- `failed`: parse edilemedi, timeout oldu veya güvenlik kontrolünden geçmedi.

`needs_review` belge varsayılan olarak active index'e alınmaz. Kullanıcı açıkça onaylarsa ayrı işaretle indekslenebilir.

## İzolasyon

Parser'lar şu anda çağıran uygulama sürecinde senkron çalışır; ayrı worker process, çalışma zamanı timeout'u, peak-RAM limiti veya geçici çalışma alanı izolasyonu uygulanmamıştır. Koruyucu boyut sınırları vardır: kaynak dosyası 10 MB, DOCX açılmış ZIP üyeleri toplamı 50 MB ve PDF çıkarılmış metni toplamı 50 milyon karakter. Bunlar bellek ya da süre için sert garanti değildir: PDF sayfası metni limit kontrolünden önce belleğe çıkarılır; DOCX XML ağacı ve HTML/JSON metni de parser sürecinde işlenir. Bu nedenle gerçek/çeşitli kişisel corpus denemelerinde süreç başına runtime/RAM gözlenmeli; timeout veya worker izolasyonunun gerekli olup olmadığı ölçümle kararlaştırılmalıdır. Dış bağlantı gerektiren HTML işlemleri varsayılan olarak kapalıdır; yerel HTML ile web tarama birbirinden ayrıdır.

## Kalıcı regresyon güvencesi

`tests/test_parsers.py`, HTML görünür metin filtresini, JSON/JSONL/CSV deterministik
kayıt üretimini, JSONL satır provenance'ını, DOCX paragraf ve temel tablo konumlarını ve bilinmeyen suffix
reddini korur. `tests/test_ingest.py` ise `ingest-dir` sıralamasını, desteklenen
dosyaların indekslenmesini ve bozuk bir dosyanın diğer dosyaları durdurmamasını
doğrular. Bunlar uzun süreli kalite/kapasite ölçümü değildir; gerçek corpus
ölçümünün önkoşulu olan hızlı regresyon kontrolleridir.

## Ölçümler

Beklenen sayfa/kayıt sayısı, çıkarılan metin oranı, token sayısı, boş/tekrar oranı ve uyarı sayısı her işte saklanır.
Corpus manifesti ayrıca kaynak format sayılarını, parse hatası türlerinin dağılımını
ve advisory duplicate sayısını metin içermeden kalıcılaştırır. Bu alanlar yeni
manifestlerde üretilir ve geriye dönük uyumluluk için eski manifestlerde zorunlu değildir.
Inventory kayıtları parse edilmiş kaynaklar için çıkarılan karakter toplamını ve
boş olmayan section sayısını da taşır; manifest bunların toplamını tutar. Bu
metrikler içerik sızdırmaz, yalnızca extraction hacmini karşılaştırmaya yarar ve
tek başına semantik doğruluk kanıtı değildir. `corpus-inventory` CLI özeti de
`extracted_chars` toplamını gösterir.

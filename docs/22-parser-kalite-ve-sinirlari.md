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
- PDF: `pypdf` ile sayfa bazlı metin çıkarımı; parser regresyonları arasında gerçek `pypdf` ile oluşturulmuş minimal sentetik PDF smoke testi vardır. Bu test kişisel/çeşitli PDF corpus kalitesinin kanıtı değildir; taranmış PDF, OCR, tablo ve çok sütunlu okuma sırası garanti edilmez. Şifreli PDF'ler ve 50 milyon karakteri aşan extraction fail-closed reddedilir.
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

Parser işlemleri dosya türü allowlist'i, timeout, bellek/dosya boyutu limiti ve geçici çalışma alanı ile izole edilir. Dış bağlantı gerektiren HTML işlemleri varsayılan olarak kapalıdır; yerel HTML ile web tarama birbirinden ayrıdır.

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

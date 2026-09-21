# 26. Kaynak envanteri ve veri sınıflandırması

## İndekslenebilir kökler

İlk sürümde yalnızca kullanıcı tarafından açıkça tanımlanan klasörler taranır. `.git`, `.hg`, `.svn`, virtualenv, `node_modules`, `__pycache__`, secrets/credentials, cache, geçici ve build/dist klasörleri varsayılan exclude listesindedir. Bu liste hem `corpus-inventory` hem `ingest-dir` için aynıdır. Inventory, parser'a kaynak kökü doğrulamasından geçmiş canonical path'i verir; böylece symlink ve provenance kontrolü aynı path üzerinde uygulanır.

## Yerel çıktı ve Git gizliliği

Kişisel corpus için inventory çıktısını `data/derived/corpus-inventory.json`,
manifest'i `data/manifests/corpus-manifest.json` altında tut. Bu klasörler
`.gitignore` içindedir ve CLI varsayılanları da bu konumları kullanır. Inventory
ham belge metnini içermez; yine de göreli dosya yolu, content hash, document/chunk
kimlikleri ve boyut/format metadata'sı hassas olabilir. Bunlar açık inceleme
olmadan public repo'ya, issue'ya veya paylaşılmış benchmark'a eklenmemelidir.

`data/benchmarks/` altında izlenen corpus/fixture dosyaları yalnızca sentetik
repository test paketidir. Kişisel corpus taramasında benchmark klasöründeki
bu statik artifact'lerin üzerine yazma; gerçek kullanımın manifestlerini yerel
manifest klasöründe tut. Bilinçli bir paylaşım kararı verilirse önce dosya
yollarını, hash'leri, chunk ID'leri, sorgu metinlerini ve label'ları incele.

## Sınıflar

- `public`: dışarı açılması kritik olmayan içerik
- `personal`: kişisel not ve çalışma belgeleri
- `sensitive`: kimlik, finans, sağlık veya sır içeren içerik
- `restricted`: embedding sağlayıcısına gönderilmesi yasak içerik

Sınıf, provider seçimini ve loglama politikasını belirler. `restricted` içerik yalnızca uygun local provider ile işlenir veya index dışı bırakılır.

## Envanter alanları

Inventory çıktısı ham metin taşımaz; göreli yol, suffix, byte boyutu, size bucket,
content checksum'ı, parser/source türü, parser sürümü, section/chunk sayıları,
çıkarılan karakter hacmi, chunk ID'leri, duplicate işareti ve son işleme durumunu
tutar. `source_uri`, değişiklik zamanı ve içerik sınıflandırması indeks payload'ında
ayrı provenance alanlarıdır; inventory bunları şu an tekrar etmez.

Parser biçimsel olarak hata vermeden boş görünür metin ürettiğinde parser sözleşmesi
fail-closed kalır; inventory kaydı `extraction_status=empty` ve hata türüyle
ayırt edilir. Manifestteki `empty_extraction_count` bu kaynakları yalnızca sayar,
metin veya yol yayınlamaz.

Recursive taramada yalnızca güvenlik allowlist'indeki suffix'ler işlenir. Desteklenmeyen
dosyalar inventory'ye dahil edilmez ve corpus checksum'ına girmez; böylece bir görsel,
cache veya başka indekslenmeyen dosyanın eklenmesi mevcut benchmark provenance'ını
gereksiz yere değiştirmez. Kullanıcı klasörü için desteklenen suffix listesi
[parser kalite standardında](22-parser-kalite-ve-sinirlari.md) tutulur.
YAML/YML yapılandırma export'ları ve temel RTF notları da allowlist içindedir; parser yalnızca
`safe_load` kullanır ve Python nesnesi oluşturan tag'leri çalıştırmaz.
CLI özeti ayrıca varsayılan exclude dizinleri altında bulunan dosya sayısını
(`excluded_files`) verir; bu sayı privacy-safe bir fark açıklamasıdır ve corpus
checksum'ına dahil edilmez. Allowlist dışındaki dosyalar da
`unsupported_files`/`unsupported_suffixes` sayaçlarıyla görünür olur; bunların
yolları, içeriği ve checksum'ları raporlanmaz ve corpus checksum'ına dahil edilmez.

## Kopya kaynak incelemesi

Corpus manifesti ayrıca `size_bucket_counts` alanıyla küçük, orta ve büyük
kaynakların sayısını taşır. Bu alan yalnızca boyut dağılımıdır; kaynak metni,
yol veya embedding içermez ve fixture sorgularının bu kovaları kapsayıp
kapsamadığından ayrı değerlendirilir.

`vdb corpus-inventory` çıktısı kaynak metnini içermez. Aynı ham byte checksum'ına
sahip dosyalarda `duplicate_of`, path derinliği daha az olan (eşitlikte alfabetik)
relative path'i inceleme için kanonik aday olarak gösterir. Bu işaret otomatik
merge veya silme değildir; aynı içerik farklı klasörlerde farklı provenance amacı
taşıyabilir. Corpus dışına alma kararı yalnızca kullanıcı incelemesinden sonra
verilir.

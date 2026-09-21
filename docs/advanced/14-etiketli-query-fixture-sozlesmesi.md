# 14. 300+ etiketli sorgu fixture sözleşmesi

## Amaç

Bu sözleşme, kişisel corpus üzerinde retrieval ve RAG değerlendirmesi için en az
300 etiketli sorgudan oluşan, tekrar üretilebilir ve hassas içeriği gereksiz yere
çoğaltmayan fixture paketini tanımlar. Mevcut küçük fixture'lar smoke kanıtıdır;
bu belge onları üretim kalitesi benchmark'ı olarak sunmaz.

## Paket yapısı

```text
data/benchmarks/
  corpus-manifest.json       # kaynak sürümü, checksum, gizlilik sınıfı
  corpus-inventory.json      # metinsiz tür/boyut/parser/chunk özeti
  query-fixture-manifest.json
  queries-vX.json            # sorgu kayıtları; hassas metin yerel kalır
  labels-vX.json             # relevance ve annotation provenance
  splits-vX.json             # train/validation/test üyelikleri
```

300 sorguluk paket tek dosya olmak zorunda değildir. Çalışma sırasında sorgular
konu, belge grubu veya annotator dilimine göre shard'lara ayrılabilir. Shard'ları
birleştirmek için:

```powershell
vdb fixture-merge queries `
  --input data/benchmarks/shards/semantic-a.json data/benchmarks/shards/typo-a.json `
  --output data/benchmarks/queries-v1.json

vdb fixture-merge labels `
  --input data/benchmarks/labels/shards/annotator-a.json data/benchmarks/labels/shards/annotator-b.json `
  --output data/benchmarks/labels-v1.json
```

Komut her shard'ı mevcut strict loader ile doğrular; duplicate `query_id` veya
casefold/whitespace normalize edildiğinde aynı çıkan sorgu varsa birleşimi
fail-closed durdurur. Label birleşiminde duplicate `query_id` veya corpus,
parser ve chunking provenance uyumsuzluğu reddedilir. Sorgu
metinleri ve label içeriği hata çıktısına yazılmaz. Birleşim başarılı olsa bile
`fixture-coverage` ve `fixture-validate` ayrıca çalıştırılmalı; merge komutu
`status=ready`, manuel relevance doğrulaması veya corpus binding kanıtı üretmez.

`query-fixture-manifest.json` bu paketin minimum sayısını, sorgu türlerini,
split oranını ve üretim sürümünü taşır. Sorgu kayıtları `query_id`, `text`,
`relevant_chunk_ids`, `query_type` ve gerektiğinde filtre alanlarını içerir.
İsteğe bağlı `split`, `size_bucket` ve `filter_selectivity` alanları benchmark
analizine taşınır; bilinmeyen alanlar reddedilir.
Etiket kaydında annotator, tarih, karar notu ve label kaynağı bulunur; ham
belge metni benchmark çıktısına kopyalanmaz.

`labels-vX.json` ayrı tutulduğunda her `query_id` için annotator, tarih, karar
notu, relevance chunk kümesi ve corpus/parser/chunking provenance taşır. CLI
`fixture-validate --labels ...` ile label kimliklerini, relevance değerlerini ve
provenance alanlarını fixture ve manifest ile birebir eşleştirir.
`fixture-coverage --labels ...` ise aynı provenance eşleşmesini ölçüm başlatmadan
`label_provenance_status` ve `label_provenance_mismatch_count` alanlarıyla raporlar.
`--output` verilirse bu privacy-safe coverage raporu JSON olarak saklanır; dosya
ham sorgu metni, belge metni veya label karar notu içermez.
Raporda `corpus_parser_versions`, varsa `fixture_parser_versions` ve bunların
eşleşme sonucu olan `parser_versions_binding_status` alanları
yalnızca parser sürüm kimliklerinin sıralı listesini taşır; kaynak içeriği taşımaz.
`corpus_checksum` ve `fixture_corpus_checksum` alanları artifact'in hangi veri
paketine bağlı olduğunu doğrulamak için hash değerlerini taşır; ham veri taşımaz.
`fixture_checksum` ise sorgu fixture dosyasının SHA-256 fingerprint'idir; fixture
değiştiğinde coverage artifact'i yeniden üretilmelidir.
Coverage artifact'i `schemas/fixture-coverage-report.schema.json` ile doğrulanır;
CLI ve kütüphane writer'ı aynı sözleşmeyi kullanır.
`source=derived` etiketler geliştirme sırasında saklanabilir; `status=ready`
kabulünde her derived kayıt gözden geçirilmiş olarak `manual` veya `reviewed`
kaynağına dönüştürülmelidir.

## Minimum dağılım

300 sorgu minimumdur; önerilen dağılım her tür için en az 30 sorgudur. Mevcut
loader bu türleri (`semantic`, `exact_identifier`, `typo`, `morphology`,
`long_context`, `negative`) strict doğrular; `filtered` ayrı metadata boyutudur:

| Tür | Amaç |
|---|---|
| semantic | anlam eşleşmesi |
| exact_identifier | dosya, sınıf, kod veya özel ad |
| typo | yazım hatası ve gürültü |
| morphology | Türkçe eklenme/çekim çeşitliliği |
| long_context | daha uzun açıklama ve çoklu kanıt |
| negative | corpus'ta cevabı olmayan sorgu |
| filtered | metadata/selectivity davranışı |

`filtered` mevcut benchmark loader'ında ayrı bir `query_type` değildir; filtre
alanı ve selectivity etiketi olarak uygulanır. Türler birbirini dışlamak zorunda değildir; ancak her sorguda birincil tür
tek ve denetlenebilir olmalıdır. Belge boyutları küçük/orta/büyük, filtre
selectivity ise düşük/orta/yüksek kovaları kapsamalıdır.

`vdb corpus-inventory` komutu desteklenen yerel dosyaları recursive tarar;
relative path, byte size, checksum, parser/chunk sayıları ve hata türünü yazar.
Ham byte checksum'ı aynı olan kopyalarda `duplicate_of` alanı, daha sığ
relative path'i kanonik aday olarak gösterir. Bu yalnızca inceleme sinyalidir;
otomatik merge veya silme yapılmaz ve manifest kaynakların provenance'ını korur.
Aynı komut deterministik, metinsiz `corpus-manifest.json` üretir; corpus checksum'ı
etiket paketinin provenance bağlantısıdır. Kaynak metni, embedding veya Qdrant çağrısı yapmaz; fixture hazırlığının
corpus kapsamını görmeye yarayan privacy-safe ön adımıdır.
Manifest ayrıca canonical JSON Schema ile runtime'da doğrulanır.

Hazırlık sırasında `vdb fixture-coverage --fixture ... --manifest ...` komutu
final kabul kapısını çalıştırmadan sorgu sayısını, tür/split/boyut/selectivity
dağılımını ve eksik kovaları raporlar. Bu komut embedding provider veya Qdrant
başlatmaz; `fixture-validate` ise yalnızca gerçek, `status=ready` paket için
son kabul kapısı olarak kalır.
Coverage normalize edilmiş duplicate sorguları da yalnızca sayısal olarak
raporlar. Split'ler arasında duplicate varsa `cross_split_duplicate_count` sıfır
olmadığı için `coverage_complete` false kalır; bu, validation/test leakage riskini
erken görünür kılar.
Final `fixture-validate` kapısı normalize duplicate sorguları da reddeder; aynı
sorgunun tekrarını artırarak 300 eşiğini yapay biçimde geçmek mümkün değildir.
`coverage_complete=true` sayısal dağılım kapılarının hazır olduğunu gösterir.
`--corpus-manifest` verildiğinde buna checksum ve parser sürüm binding'inin
geçerli olması da dahildir; ancak gerçek relevance doğrulaması ve reviewed
etiket kalitesi yine `fixture-validate --labels` ve insan incelemesiyle kanıtlanır.
Komuta `--corpus-manifest` verilirse her pozitif sorgunun referans chunk ID'leri
güncel corpus manifestine karşı privacy-safe biçimde kontrol edilir. Fixture
checksum'ı da varsa aynı manifestle eşleştirilir. Eski veya başka corpus'a ait
ID/checksum değerleri `corpus_binding_status=mismatch` ve sayısal durum
alanlarıyla raporlanır; sorgu metni çıktıya taşınmaz.
İsteğe bağlı `--labels` dosyası verildiğinde rapor ayrıca label sayısını,
etiketsiz sorgu sayısını ve fixture dışında kalan label sayısını gösterir;
etiket metni veya sorgu metni rapora yazılmaz.

Gerçek sorgu paketini etiketlemeye başlamak için mevcut `query_id` ve önerilmiş
relevance chunk ID'lerini, kaynak metnini kopyalamadan inceleme taslağına
çıkarabilirsin:

CLI'da `--corpus-manifest` zorunludur; böylece taslak provenance değerlerini
gerçek corpus sözleşmesinden alır.
Template üretimi corpus manifest schema'sını doğrular ve relevance chunk ID'leri
manifestte yoksa fail-closed durur; bu durumda etiketleme başlamadan önce fixture
yeniden corpus üzerinden üretilmelidir.
`fixture-coverage --labels --corpus-manifest` aynı kontrolü label dosyasındaki
relevance ID'leri için de yapar; sonuçta `unknown_labeled_chunk_count` ve
`labels_with_unknown_chunks` alanlarıyla yalnızca sayısal, privacy-safe uyarı verir.
Corpus manifesti `chunk_size_buckets` alanını sağlıyorsa bu mapping'in bütün
`chunk_ids` değerlerini kapsaması gerekir. Kısmi mapping, fixture yalnızca
eşlenmiş chunk'lara değinse bile `chunk_size_bucket_binding_status=mismatch`
olarak raporlanır; böylece boyut dağılımı eksik provenance ile final ölçüm
başlatılamaz.
Corpus manifesti fixture coverage'a verildiğinde checksum ve parser sürüm kümesi
declaration'ları da zorunlu final koşuldur; bunlardan biri `not-declared` ise
rapor `coverage_complete=false` üretir.

```powershell
vdb fixture-label-template `
  --fixture data/benchmarks/queries-v1.json `
  --corpus-manifest data/manifests/corpus-manifest.json `
  --output data/benchmarks/labels-v1-template.json
```

Bu çıktı bilerek `source=derived` ve `REVIEW_REQUIRED` notuyla gelir; final
etiket değildir. Annotator, tarih, karar notu, relevance ve provenance alanları
insan tarafından doğrulanmalı; kaynak `manual` veya `reviewed` yapılmadan ve
`fixture-validate --labels` geçmeden ölçüm başlatılmamalıdır. Template sorgu veya
belge metni içermez. `fixture-coverage --labels` çıktısı da derived ve
inceleme-gerektiren etiketleri ayrı sayar; tüm query ID'leri bulunsa bile bu
durum `labels_status=review-required` olarak görünür, `complete` sayılmaz.

Corpus manifesti aktif `chunking_version` değerini de taşır; fixture preflight
bu değeri fixture ile birebir eşleştirir. Böylece aynı kaynak checksum'ına sahip
olsa bile farklı chunking çıktılarıyla üretilmiş etiketler kabul edilmez.
HTML kaynakları `html-v4` parser sürümüyle bloklara ayrılır; `<title>`, başlıklar ve
`heading_path` bilgisi kanonik bölümlerde korunur. Bu nedenle HTML parser
çıktısı değiştiğinde mevcut HTML belgeleri yeniden indekslenmelidir.
DOCX core title ve başlık stilleri de aynı yapısal metadata’ya taşınır. `docx-v4`
paragraf/hücre içi sekme ve açık satır sonlarını korur, iç içe tablo içeriğini
üst hücre metninde çoğaltmaz. Parser sürümü provenance'ta
izlenir; DOCX parser çıktısı değiştiğinde yeniden indeksleme gerekir.
Chunking farklı `heading_path` değerlerini tek chunk’ta birleştirmez. Bu davranış
`paragraph-pack-v2` sürümüyle provenance sözleşmesine dahildir; parser veya
chunking sürümü değiştiğinde fixture etiketleri yeniden doğrulanmalıdır.

## Split ve etiket kalitesi

### Relevance yargılama protokolü

Mevcut şema chunk relevance'ını ikili olarak temsil eder: chunk ya sorgu için
kullanılabilir kanıt taşır ya da taşımaz. Bu, küçük/kişisel V1.7 kapsamı için
bilinçli sadeliktir; `relevant_chunk_ids` dışındaki chunk'lara dair “incelendi ve
ilgisiz bulundu” iddiası üretmez. Ancak mevcut evaluator ayrı bir “unjudged”
durumu saklamaz; metriğe verilen relevance kümesinde olmayan chunk'lar ölçümde
relevant sayılmaz. Bu yüzden aday havuzu yeterince incelenmemiş bir sorgu
`manual`/`reviewed` yapılmamalı, `derived` ve `review-required` kalmalıdır.
TREC'in relevance tanımı da belgenin raporda kullanılabilir bilgi taşımasına
dayanır; qrels yalnızca kendi koleksiyonu ve
judgment kapsamı için tamamlanmış kabul edilir
([NIST TREC relevance judgments](https://trec.nist.gov/data/reljudge_eng.html)).

Her sorguyu etiketlerken:

1. Sorguyu, mevcut corpus sürümünü ve hedeflenen cevap bilgisini sabitle; sorguyu
   yalnızca tek bir gold chunk'tan kopyalayarak yazma. Doğal dil, Türkçe ekler,
   yazım hatası, tanımlayıcı ve negative türleri ayrı çeşitlilik boyutlarıdır.
2. Sorguyu en az iki farklı aday bulma yoluyla (ör. lexical/exact ve dense; varsa
   opt-in hybrid/rerank) çalıştırıp aday havuzlarının birleşimini incele. Bu
   pooling yaklaşımı, yalnızca mevcut dense sisteminin bulduğu chunk'ları doğru
   sayma yanlılığını azaltır; havuzun tamlığını kanıtlamaz. NIST TREC de
   relevance judgment üretiminde pooling kullanır.
3. Aday metinleri sorgu-kaynak eşleşmesini anlamaya yetecek bağlamla incele.
   Rank ve skorları mümkünse gizle. Sırf aynı konu/anahtar kelimeyi paylaşan
   chunk'ı relevant sayma; chunk sorguyu cevaplamak veya cevaba doğrudan kanıt
   sağlamak için gerçekten kullanılabilmelidir.
4. Cevap birden çok parçaya dayanıyorsa gerekli bütün chunk'ları etiketle.
   Parçalardan biri tek başına eksik bağlam yaratıyorsa, parçaların birlikte
   cevap için gerekli olup olmadığını kısa `decision_note` ile belirt. Aynı
   cevabı tekrar eden kopyaları sırf kopya oldukları için ayrı kanıt sayma.
5. `negative` sorguyu yalnızca corpus'un tamamını ve parse/inventory hatalarını
   kontrol ettikten sonra negative yap: `relevant_chunk_ids` boş olmalı ve
   sorgunun cevabı corpus'ta gerçekten bulunmamalıdır. Sadece sistemin top-k
   sonuçlarında çıkmayan cevap negative değildir. Kaynak/parse kapsamı belirsizse
   sorgu etiketlenmez; `review-required` kalır.
6. Her kararın corpus checksum, parser/chunking sürümü, annotator ve tarihle
   bağını koru. Derived öneriler gözden geçirilmeden `manual`/`reviewed`
   sayılmaz. Uyuşmazlıkta karar notu bırak; hangi judgment kapsamının
   incelendiği doğrulanamıyorsa onu sessizce “non-relevant”e çevirmeyip yeniden
   incele.

Tek kişilik projede ikinci annotator zorunlu değildir. Bunun yerine final
`test` split'inden ayrı tutulan küçük bir kör tekrar örneklemi belirlenir ve
kararlar zaman aralığı bırakılarak yeniden incelenir; değişen kararlar not edilir.
Bu, annotator'lar arası anlaşma ölçüsü değildir ve öyle raporlanmamalıdır.
Fixture'ın 300 sorguya ulaşması tek başına kalite kanıtı değildir: tekrar
ifadelerle sayıyı doldurmak yerine farklı intent, source family, corpus boyutu
ve negative durumları kapsamalıdır. Heterojen retrieval veri kümelerinin farklı
task/domain dağılımlarıyla sınanması BEIR'in temel motivasyonlarındandır
([BEIR paper](https://arxiv.org/abs/2104.08663)); bunun kişisel corpus için
doğrudan aynı benchmark tasarımını zorunlu kıldığı değil, tek tip sorgu setinin
genelleme iddiasını daralttığı sonucu çıkarılır.

Coverage raporundaki `size_bucket_counts` fixture sorgularının belge boyutu
dağılımını, `corpus_size_bucket_counts` ise corpus manifestindeki gerçek kaynak
dağılımını gösterir. İkinci alan legacy corpus manifestlerinde `null` olabilir.
Bu ayrım, corpus'ta large kaynak bulunmadığı durumla large sorgu etiketlerinin
henüz yazılmadığı durumu birbirine karıştırmayı önler.

Corpus manifestindeki `chunk_size_buckets` eşlemesi mevcutsa coverage, pozitif
sorguların `size_bucket` etiketini relevance chunk'larıyla da karşılaştırır.
Uymayan etiketler `queries_with_size_bucket_mismatch` ile sayılır ve corpus
binding durumunu `mismatch` yapar; eski manifestlerde bu alt kontrol
`not-available` kalır.

- Önerilen split: 60% development, 20% validation, 20% test. Manifestteki
  `split_tolerance` (mevcut sözleşmede 0.05) dışındaki sapmalar kabul edilmez.
- Threshold ve reranker ayarı yalnızca development/validation üzerinde yapılır.
- Final test split'i tek seferlik raporlanır; test etiketleri ayar kararına
  geri beslenmez.
- Negative sorgularda `relevant_chunk_ids` boş olmalıdır.
- En az iki gözden geçirme gerektiren anlaşmazlıklar karar günlüğüne yazılır.
- Her etiket corpus checksum'ı ve chunking/parser sürümüyle eşleştirilir.

Bu protokolün `relevant_chunk_ids` için ürettiği kararlar ikilidir; `nDCG` gibi
metriklerde bu proje için yalnızca ikili qrels kullanılır. Dereceli relevance
karar kalitesini artıracak ölçülmüş bir ihtiyaç hâline gelirse schema, label
coverage ve metric davranışı birlikte sürümlenmelidir; V1.7 benchmark'ına sessizce
eklenmez.

## Gizlilik ve provenance

Fixture yerel kalır; hassas sorgu ve belge metni loglara, benchmark özetlerine
ve commit geçmişine taşınmaz. Dış embedding provider kullanılırsa ham sorgu
gönderimi açık bir opt-in kararı olmadan yapılmaz. Sonuç raporu yalnızca
checksum, metrik ve hata özetini içerir.

## Kabul kapısı

Manifestteki sayılar ve dağılımlar doğrulanmadan 300 sorguluk benchmark
"tamamlandı" sayılmaz. Bu sözleşmenin yazılması altyapı tamamlandı anlamına
gelmez; gerçek corpus'tan etiketli veri doldurulması ve kapsamlı ölçüm goal'un
son doğrulama aşamasında yapılacaktır.

Kod tarafındaki `validate_fixture_requirements` yalnızca `status: "ready"`
manifestini kabul eder; `contract-only` manifest ve mevcut küçük fixture bu
kapıdan geçmez.

`ready` manifestte split oranları 1'e toplamlanmalı; her sorgu `development`,
`validation` veya `test` split'lerinden birini açıkça belirtmeli. Corpus
checksum'ı, parser/chunking sürümü ve embedding manifest kimliği boş bırakılamaz.
Repository içindeki `paragraph-pack-v1` değerleri yalnızca eski sözleşme
regresyon testlerine aittir; aktif chunking sürümü `paragraph-pack-v2`'dir.
Gerçek fixture hazırlanırken güncel parser/chunking sürümleri ve yeni chunk
kimlikleriyle yeniden etiketleme yapılmalıdır.
Karma formatlı corpus fixture’larında parser provenance tek değerle
özetlenmez. Fixture manifesti ve etiket kayıtları `parser_version: mixed`
özetini, ayrıca sıralı ve tekilleştirilmiş `parser_versions` listesini taşır;
ayrıntılı liste authoritative provenance bilgisidir. Tek parser’lı eski
manifest ve etiketler geriye dönük olarak kabul edilir.
Manifestin kendisi `schemas/query-fixture-manifest.schema.json` ile doğrulanır;
paket alanları, durum değeri, bucket listeleri ve `ready` durumunda provenance
alanlarının boş olmaması runtime kabulünden önce kontrol edilir. Böylece fixture
kapısı yalnızca sorgu kayıtlarını değil, kabul sözleşmesinin biçimini de denetler.

CLI kullanımı:

```powershell
vdb fixture-validate `
  --fixture data/benchmarks/queries-v1.json `
  --manifest data/benchmarks/query-fixture-manifest.json `
  --corpus-manifest data/manifests/corpus-manifest.json `
  --labels data/benchmarks/labels-v1.json
```

`--corpus-manifest` verildiğinde fixture checksum'ı ve parser sürümü gerçek
corpus manifestiyle de eşleştirilir. Komut embedding modeli veya Qdrant
başlatmadan yalnızca fixture sözleşmesini kontrol eder.
Manifestteki `chunk_ids` alanı da gerçek corpus'tan üretilir; etiketli bir
sorgunun `relevant_chunk_ids` kümesi bu listede olmayan bir kimlik içerirse
fixture kabul edilmez. Böylece etiketler yalnızca checksum'a değil, mevcut
chunk kimliklerine de bağlanır.

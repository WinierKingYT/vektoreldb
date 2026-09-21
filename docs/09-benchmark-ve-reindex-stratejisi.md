# 9. Benchmark ve yeniden indeksleme stratejisi

## Benchmark veri seti

İlk kişisel veri seti için 30–100 sorgu hazırlanır. Her satırda sorgu, beklenen document/chunk id ve `query_type` bulunur. V1 fixture'ı `semantic`, `exact_identifier`, `typo`, `morphology`, `long_context` ve `negative` sınıflarının her birini içerir. Pozitif sorgular Recall/MRR/nDCG'e, `negative` sorgular ise ayrı `negative_success_rate` metriğine girer. Gerçek dosya içeriği benchmark'a gereksiz yere kopyalanmaz; yalnızca gerekli kimlikler ve güvenli test metni tutulur.

## Deney matrisi

Tek seferde yalnızca bir değişken değiştir:

- model
- chunk boyutu/overlap
- dense veya hybrid retrieval
- top-k
- score threshold
- reranker
- HNSW arama bütçesi

Her deneyde Recall@k, MRR veya nDCG, p50/p95 latency, boş sonuç oranı, depolama ve embedding maliyeti raporlanır. Retrieval başarısı ile LLM cevap başarısı ayrı ölçülür.

`vdb benchmark` sonucu sorgu sayısı, Recall@k, MRR@k, nDCG@k, toplam süre,
process CPU süresi (`cpu_seconds`), gözlenen process RSS (`rss_mb`), p50/p95/p99
sorgu gecikmesi, `error_rate` ve negative sorgular için
`negative_success_rate` alanlarını JSON olarak saklar. Her sonuç ayrıca fixture
checksum'ı, corpus checksum'ı ve embedding manifest kimliğini taşıyabilir; böylece
ölçüm artefact'i yanlış veri/model ile sessizce karıştırılamaz. Negative sorguların eşik
davranışını ölçmek için isteğe bağlı `--min-score` arama eşiği verilebilir;
varsayılan eşik yoktur. Üretimde eşik kullanılacaksa `VDB_RETRIEVAL_MIN_SCORE`
ile açıkça ve yalnızca validation split'te kalibre edilmiş değer tanımlanır;
kod içine evrensel sabit gömülmez. İstek üzerindeki `min_score`, yapılandırılmış
varsayılanı geçersiz kılar. Benchmark varsayılan olarak ilk sorguyu warm-up kabul
eder; model cold-start süresi steady-state p95/p99 SLO’suna dahil edilmez. RSS
model yüklemesini içerebilir ve Qdrant/host toplam belleği değildir. Bu alanlar
kişisel corpus ölçümü yapılmadan kabul eşiği olarak yorumlanmaz.

Kod içindeki `assert_regression_within` baseline ve aday sonucu aynı sorgu sayısıyla karşılaştırır; Recall kaybını yüzde puan olarak ölçer ve varsayılan 2 puanlık regresyon bütçesini aşarsa başarısız olur.

## Ground truth

Küçük corpus'ta exact/brute-force arama referans alınır. ANN sonuçları bu referansa göre recall ile karşılaştırılır. Skor eşiği evrensel sabit değildir; model ve veri kümesine göre benchmark'tan türetilir.

## Re-index akışı

1. Yeni manifest oluştur.
2. Yeni koleksiyonu boş oluştur.
3. Kaynak snapshot'ından yeniden parse/chunk/embed et.
4. Nokta sayısı, hata kuyruğu, boyut ve örnek kaynak konumlarını doğrula.
5. Benchmark'ı eski koleksiyonla karşılaştır.
6. Kabul kriterlerini sağlarsa alias/uygulama ayarını değiştir.
7. Eski koleksiyonu rollback süresi boyunca sakla.

Qdrant snapshot'ları koleksiyon konfigürasyonu, noktalar ve payload'ları içerir; alias'lar ayrıca taşınmadığı için geçiş planında ayrıca korunmalıdır. Snapshot restore uyumluluğu Qdrant sürümleriyle sınırlıdır ve migration/recovery koşulları ayrıca doğrulanmalıdır. [Qdrant snapshots](https://qdrant.tech/documentation/operations/snapshots/)

## Kabul kriteri örneği

- Recall@5 eski sürümden 2 puandan fazla düşmemeli.
- p95 latency hedefin üzerinde olmamalı.
- Yetki filtresi testlerinde sıfır sızıntı olmalı.
- Hatalı/eksik embedding sayısı sıfır veya açıklanmış olmalı.
- Restore tatbikatı başarılı olmalı.

# 15. RAG context ve cevap kalite sınırı

## Sorumluluk sınırı

Vektörel database retrieval adaylarını ve provenance bilgisini üretir; LLM
cevabı üretmez. RAG sistemi bu çıktıyı **güvenilmeyen kanıt** olarak alır.
Kaynak metni talimat gibi yorumlamak, retrieval katmanının görevi değildir.

```text
query
  -> retrieval + access filter + optional threshold
  -> ranked evidence (text + citation + score + location)
  -> RAG context builder
  -> generation / abstention decision
  -> answer + citations + quality evaluation
```

## Context sözleşmesi

RAG adapter'ı her kanıt için en az şu alanları korur:

- `chunk_id`, `document_id`, `source_uri` ve `location`
- `title`, `score`, `retrieval_stage`, `embedding_manifest_id`
- parser/document status ve varsa güvenlik uyarısı
- context içindeki kanıt sırası

Ham metin context'e girebilir; ancak audit/log/benchmark özetine kopyalanmaz.
Context builder kanıtları XML/JSON sınırlarıyla veri olarak işaretlemeli ve
kaynak metnindeki talimatların sistem talimatı olmadığını generation prompt'unda
açıkça belirtmelidir. Kaynak metni XML text olarak escape edilir; metadata
attribute değerleri ayrıca quote-aware encode edilir, böylece belge başlığı ve
heading içindeki tırnaklar kanıt etiketinin attribute yapısını değiştiremez.

Kod tarafındaki `build_rag_context` bu paketleme işini yapar: bütün kanıt
bloklarını veya hiç blok eklememeyi tercih eder, `max_chars` bütçesini aşmaz ve
citation metadata'sını ayrı tuple olarak döndürür. Bu fonksiyon generation
çağırmaz ve kaynak içeriğini çalıştırmaz.
Bir chunk birden fazla retrieval aşamasından tekrar dönerse yalnızca ilk sıralı
kayıt context'e alınır; citation marker'ları eklenen kanıtlar için ardışık üretilir;
böylece karakter bütçesi ve citation kimlikleri aynı
kanıtın kopyalarıyla tüketilmez. Context ayrıca aday, eklenen, bütçe nedeniyle
atlanmış kanıt, duplicate aday sayılarını ve kullanılan karakter sayısını taşır;
bunlar context kalite ölçümünün privacy-safe temelidir.
Evidence bloğu `heading_path` bilgisini de escape edilmiş metadata olarak taşır;
generator bölüm bağlamını görür, ancak bu alan kaynak metninden gelen bir
talimat olarak yorumlanmaz.

Kaynak metni XML/HTML karakterleriyle birlikte prompt-injection benzeri ifadeler
içerse dahi context içinde escape edilmiş veri olarak kalır; bu davranış kalıcı
RAG güvenlik testiyle korunur.

`RetrievalResult` ve `ContextCitation` ayrıca `retrieval_stage`,
`parser_version`, `document_status`, `heading_path` ve `security_flags` alanlarını korur. Bu
alanlar cevap üretiminde talimat olarak yorumlanmaz; kanıtın kökenini, güvenlik
durumunu ve hangi retrieval yolundan geldiğini denetlenebilir tutar.

Generation sonrasında `validate_rag_answer_citations` ile cevapta geçen
`E1`, `[E1]` biçimli marker'ların context içinde gerçekten bulunup bulunmadığı
kontrol edilebilir; marker'lar başka bir identifier'ın içine gömülmüşse marker
olarak sayılmaz. Sonuçtaki `valid` alanı en az bir bilinen marker bulunup hiçbir
geçersiz marker bulunmadığını belirtir; bu yalnızca citation bütünlüğüdür;
factuality, relevance
ve faithfulness ölçümü değildir.

`evaluate_rag_citation_coverage`, beklenen relevance etiketlerindeki chunk'ların
cevapta citation olarak ne kadar kapsandığını ayrıca ölçer. `citation_precision`
geçersiz marker oranını, `coverage` ise beklenen chunk kümesinin citation ile
karşılanma oranını ifade eder. Bu iki metrik de metnin doğru yorumlandığını veya
cevabın faithful olduğunu kanıtlamaz; insan etiketleri ve cevap değerlendirmesi
ayrı kalır.

## Cevap politikası

- Eşik altında veya boş retrieval sonucunda RAG sistemi “yeterli kanıt yok”
  diyebilmelidir.
- Retrieval audit olayı `abstention`, `abstention_reason` (`no_candidates` veya
  `below_min_score`) ve eşik nedeniyle elenen aday sayısını taşır. Bu alanlar
  ham sorgu/metin içermez; RAG katmanı bunları cevap vermeme kararına girdi
  olarak kullanabilir.
- HTTP `/v1/search` yanıtı da aynı privacy-safe nedeni, toplam aday sayısını ve
  eşik nedeniyle elenen aday sayısını taşır; boş sonuç artık istemci tarafında
  neden ayrıştırılmadan yorumlanmaz.
- `assess_rag_generation` context'i generation katmanına devretmeden önce
  boş/eşik-altı retrieval'i ve `needs_review`/güvenlik işaretli kanıtı fail-closed
  reddeder. Context bütçesi nedeniyle kanıt atlandıysa (`truncated=true`) karar
  ayrıca `context_truncated` nedeniyle fail-closed reddedilir. Context metni,
  kullanılan karakter sayısı ve dahil edilen citation sayısı birbiriyle
  uyuşmuyorsa `invalid_context` kararı üretilir; eksik kanıtla
  generation yapılmaz. Aktif ve eksiksiz kanıt varsa yalnızca
  “generation'a uygun kanıt mevcut” kararı verir; cevabın doğru veya faithful
  olduğunu iddia etmez. Handoff sonucu yine de truncation durumunu taşır.
- Cevap, dayandığı chunk citation'larını taşımadan başarılı sayılmaz.
- Cevapta retrieval kanıtı yoksa modelin genel bilgisinden gelen bölüm ayrı
  işaretlenmeli veya kişisel bilgi sorularında cevap reddedilmelidir.
- `min_score` validation split'te seçilir; test split'te bir kez doğrulanır.
- `min_score` mevcut sürümde yalnızca dense cosine retrieval için geçerlidir ve
  varsa reranking öncesinde dense aday skoruna uygulanır. Hybrid veya
  late-interaction store ile eşik istenirse sistem eşik kalibrasyonu bulunmadığı
  için aramayı başlatmadan reddeder; eşiksiz arama modları çalışmaya devam eder.
  Bu sınır önemlidir: Qdrant RRF skoru rank füzyonundan, late-interaction MaxSim
  skoru ise token vektör benzerliklerinin toplamından üretir; ikisi de cosine
  eşiğiyle değiştirilebilir değildir ([Qdrant RRF](https://qdrant.tech/documentation/search/hybrid-queries/), [Qdrant multivector/MaxSim](https://qdrant.tech/documentation/manage-data/vectors/)).
- Dense aday eşiğini geçen sonuçlar yeniden sıralanabilir; reranker skoru farklı
  ölçekte olabileceği için eşik/olasılık olarak kullanılmaz. Örneğin Sentence
  Transformers MS MARCO CrossEncoder sigmoid uygulanmadığında logit döndürebilir;
  sigmoid sıralamayı değiştirmeden skoru 0–1 aralığına getirir ([kullanım rehberi](https://www.sbert.net/docs/cross_encoder/usage/usage.html), [CrossEncoder API](https://www.sbert.net/docs/package_reference/cross_encoder/model.html)). Reranker'a özgü confidence eşiği bu sürümde desteklenmez.
- Threshold seçimi için validation skorları üzerinde pozitif kabul ve negative
  başarı tabanlarını birlikte değerlendiren bounded helper kullanılabilir; uygun
  eşik yoksa RAG katmanı sessiz bir değer uydurmaz.

## Değerlendirme katmanları

Retrieval ve generation ayrı raporlanır:

| Katman | Minimum ölçüm |
|---|---|
| Retrieval | Recall@k, MRR, nDCG, negative success, citation coverage |
| Context | context precision/recall, duplicate rate, token bütçesi, aday/eklenen/atlanan kanıt ve kullanılan karakter sayısı |
| Answer | relevance, faithfulness, citation correctness, abstention correctness |
| Sistem | p50/p95/p99, hata, CPU/RAM, provider maliyeti |

Otomatik judge tek başına kabul kriteri değildir; insan etiketli calibration
set'i, split disiplini ve hata örnekleriyle birlikte değerlendirilir. Bu proje
ilk aşamada context/provenance sözleşmesini sağlar; uzun süreli cevap kalitesi
ölçümü 300+ sorgu fixture'ı hazırlandıktan sonra yapılacaktır.

### Privacy-safe cevap değerlendirme artifact'i

`rag-answer-evaluations.schema.json` yalnızca insan değerlendirmesi için şu
alanları saklar: `query_id`, evaluator/zaman, `answered` veya `abstained`
durumu, 0–2 arası relevance/faithfulness/citation-correctness puanları,
abstention correctness ve fixture/corpus/embedding/generation provenance'ı.
Ham cevap, kaynak metni, sorgu metni veya serbest not alanı artifact'e alınmaz.
`load_rag_answer_evaluations` şemayı ve duplicate query kimliklerini doğrular;
`summarize_rag_answer_evaluations` farklı corpus/fixture/model koşullarının
yanlışlıkla tek özette birleştirilmesini reddeder. Bu özet insan yargısının
kanıtıdır; otomatik factuality veya faithfulness üretmez.

Bu artifact'i Qdrant veya embedding başlatmadan kontrol etmek için `vdb
rag-evaluation-summary --input <evaluations.json> --output <summary.json>`
komutu kullanılabilir. Komut yalnızca privacy-safe özeti stdout'a ve seçilen
çıktı dosyasına yazar; ham değerlendirme metni üretmez.

## RAG entegrasyon rollback'u

RAG adapter'ı bozulursa vector DB retrieval endpoint'i bağımsız çalışmaya devam
eder. Adapter değişikliği retrieval collection'ını değiştirmemeli; context
formatı geriye dönük uyumsuzsa sürümlenmeli ve eski adapter'a dönülebilmelidir.

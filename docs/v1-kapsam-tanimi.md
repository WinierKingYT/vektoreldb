# V1 Kodlama Öncesi Kapsam Tanımı

## 1. Amaç

V1; tek kullanıcının kişisel dosyalarını güvenli biçimde içe aktardığı, normalize edip chunk'ladığı, embedding ürettiği ve Qdrant üzerinde kaynak bilgisi korunarak arayabildiği local-first bir retrieval sistemi olacaktır. Bu sistem, daha sonra kişisel RAG uygulamasının retrieval katmanı olarak kullanılacaktır.

V1 bir sohbet uygulaması veya model eğitme sistemi değildir. LLM ile cevap üretimi ayrı bir RAG katmanında yapılacaktır.

## 2. Kullanıcı ve çalışma sınırı

| Alan | V1 kararı |
|---|---|
| Kullanıcı | Tek kullanıcı |
| Yetki | `owner_id = me`; sunucu tarafında zorunlu filtre |
| Çalışma | Local-first, tek makine |
| Veritabanı | Qdrant adapter üzerinden |
| Embedding | Yerel model; harici provider adapter'ı desteklenecek |
| Dil | Öncelik Türkçe; metadata ile diğer diller engellenmeyecek |
| Veri kaynağı | Kullanıcının açıkça verdiği yerel dosyalar |
| Otomatik web taraması | Kapsam dışı |

## 3. İlk dikey dilim

Kodlama bu akışla başlayacaktır:

```text
Markdown/TXT dosyası
  → kaynak kimliği ve checksum
  → normalize metin
  → deterministik chunk
  → tek embedding modeli
  → Qdrant upsert
  → exact baseline ve HNSW arama
  → kaynaklı sonuç
```

İlk dikey dilim; ingest, search, delete ve yeniden ingest davranışlarını uçtan uca kanıtlamadan genişletilmeyecektir.

## 4. V1'e dahil olanlar

- Markdown ve TXT ile çalışan parser
- PDF, DOCX, HTML, EML, JSON, JSONL/NDJSON, CSV ve XML için sözleşmeye uygun parser altyapısı
- Kanonik document/chunk şeması
- Deterministik document/chunk/point ID'leri
- Parser ve chunking sürüm metadata'sı
- Yerel embedding provider ve provider adapter sözleşmesi
- Qdrant collection oluşturma, payload indeksleri ve upsert
- Idempotent ingest, update, delete ve reindex
- Exact baseline ve HNSW retrieval
- Kaynak URI, başlık, bölüm/sayfa ve provenance döndürme
- API/OpenAPI sözleşmesi ve temel CLI/iş akışı
- Benchmark fixture, etiketli sorgular ve temel latency/recall ölçümü
- Snapshot/restore, structured log ve temel health check

## 5. V1 dışı

- Çok kullanıcılı tenant izolasyonu ve dağıtık sharding
- Yüksek erişilebilirlik, replica orchestration ve failover otomasyonu
- Hybrid dense+sparse arama
- Reranking ve multi-vector/late interaction
- Quantization veya DiskANN/ScaNN gibi ileri backend optimizasyonları
- Multimodal embedding ve OCR ağırlıklı veri akışı
- Graph-RAG ve entity graph
- Otomatik web taraması
- LLM cevap üretimi, prompt yönetimi ve agent workflow'u
- Model fine-tuning

## 6. RAG entegrasyon sınırı

Vektörel veritabanı yalnızca retrieval sonucunu üretir. RAG katmanı bu sonucu alıp context packing, citation, prompt ve LLM generation işlemlerini yapar.

Retrieval response en az şu alanları taşımalıdır:

- `document_id`, `chunk_id`
- `source_uri`, başlık ve konum
- chunk metni
- similarity score
- embedding manifest/model bilgisi
- erişim metadata'sı
- retrieval aşaması ve varsa fallback bilgisi

Bu sınır sayesinde RAG sistemi farklı LLM'lerle çalışabilir ve veritabanı değişmeden cevap üretim katmanı değiştirilebilir.

## 7. Kapsam kabul kriterleri

Kapsam kodlamaya hazır sayılır ancak şu koşullarda tamamlanmış kabul edilir:

- İlk dikey dilim gerçekçi fixture ile uçtan uca çalışır.
- Aynı dosyanın tekrar ingest edilmesi duplicate üretmez.
- Güncelleme ve silme eski chunk'ları temizler.
- Her sonuç kaynağına ve konumuna geri izlenebilir.
- Exact baseline ile HNSW karşılaştırması raporlanır.
- Model/parser/chunking değişikliğinde reindex zorunluluğu kontrol edilir.
- Snapshot restore smoke test'i geçer.
- Desteklenmeyen dosyalar sessizce yok sayılmaz.
- Bu belgede dışarıda bırakılan özellikler ilk sürüme eklenmez.

## 8. Kapsam değişikliği kuralı

Yeni bir özellik eklenmeden önce karar günlüğüne şu dört bilgi yazılır: kullanıcı ihtiyacı, etkilenen sözleşmeler, eklenen test/operasyon maliyeti ve V1 teslim tarihine etkisi. Bu bilgiler olmadan kapsam genişletilmez.

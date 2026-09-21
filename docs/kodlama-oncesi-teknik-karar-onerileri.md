# Kodlama Öncesi Teknik Karar Önerileri

Bu belge, teknik geçmişi olmayan kullanıcı için V1 başlangıç varsayılanlarını tanımlar. Kararlar benchmark ve ilk dikey dilimden sonra kesinleştirilebilir; ancak kodlama bu güvenli varsayılanlarla başlayabilir.

## 1. Python ve proje altyapısı

**Öneri:** CPython 3.12 + `uv` + `pyproject.toml` + `pytest` + `ruff`.

Python 3.12; kütüphane uyumluluğu ve kararlılık açısından temkinli başlangıçtır. `uv`, Python sürümünü, sanal ortamı ve kilitli bağımlılıkları tek proje içinde yönetebilir; proje sürümü `.python-version` ile sabitlenir. Resmî uv dokümantasyonu `requires-python` ve proje ortamı kullanımını destekler.[^1]

İlk uygulama şekli: çekirdek Python kütüphanesi + CLI. HTTP API, çekirdek akış doğrulandıktan sonra ince bir FastAPI katmanı olarak eklenir. Bu, parser/embedding/storage sorunlarını web katmanından ayırır.

## 2. İlk embedding modeli

**Öneri:** İlk yerel aday `intfloat/multilingual-e5-base`; kalite yetersiz kalırsa `BAAI/bge-m3` karşılaştırmaya alınır.

`multilingual-e5-base` 94 dili destekleyen, yaklaşık 0.3B parametreli ve 512 token sınırına sahip daha hafif bir başlangıç modelidir.[^2] Kişisel local-first kullanımda indirme/RAM maliyeti daha makuldür. BGE-M3 100'den fazla dil, 1024 boyut ve 8192 token desteğiyle daha kapsamlıdır; ancak model boyutu ve işletim maliyeti daha yüksektir.[^3]

V1'de tek model kullanılır. E5 kullanılırsa query ve passage önekleri provider adapter'ında sabitlenir; model değişirse yeni collection/reindex gerekir. Model seçimi en az 30 etiketli Türkçe sorgu üzerinde kesinleştirilir.

## 3. Harici embedding provider

**Öneri:** Adapter sözleşmesi ilk günden hazırlanır; harici provider varsayılan değildir.

Kişisel veya hassas veri için varsayılan yol yerel modeldir. Harici provider yalnızca kullanıcı açıkça etkinleştirdiğinde çalışır; gönderilen metin, provider adı, model sürümü ve maliyet loglanır. API anahtarı kaynak dosyada veya Git geçmişinde tutulmaz.

Harici sağlayıcı ile yerel model aynı `embed(texts, purpose, model_revision)` sözleşmesini uygular. Provider değişikliği mevcut vektörlerle karıştırılmaz; yeni manifest ve kontrollü reindex gerekir.

## 4. Distance metric ve dimension

**Öneri:** E5 için 768 boyut, cosine similarity ve normalize edilmiş embedding.

Modelin boyutu ve metriği collection sözleşmesinde sabitlenir. Normalizasyon ve similarity davranışı adapter testinde doğrulanır; yalnızca isim benzerliğine güvenilmez. Yeni model farklı boyut/metrik getirirse aynı collection'a yazılmaz.

## 5. Veri ve klasör politikası

**Öneri:** Ham kaynaklar, çalışma çıktıları ve Qdrant verisi ayrılır.

```text
data/
  sources/       # kullanıcının ham dosyaları
  derived/       # parser, normalize ve chunk çıktıları
  manifests/     # ingest/index/provider manifest'leri
  benchmarks/    # sorgular, etiketler ve sonuçlar
  snapshots/     # yedekler
qdrant_storage/  # yalnızca Qdrant'ın yerel verisi
```

Ham kaynaklar silinmeden veya üzerine yazılmadan korunur. Qdrant tek doğruluk kaynağı değildir. Secrets `.env` veya işletim sistemi secret store ile yönetilir; `.gitignore` kapsamına alınır.

## 6. İlk API ve kullanıcı akışı

**Öneri:** Önce CLI, sonra aynı servisleri kullanan HTTP API.

İlk komutlar:

```text
vdb doctor
vdb ingest <path>
vdb search "sorgu"
vdb delete <document-id>
vdb reindex --manifest <id>
vdb backup
vdb restore <snapshot>
```

HTTP API daha sonra aynı uygulama servislerini çağırır: `POST /documents:ingest`, `POST /search`, `DELETE /documents/{document_id}`, `POST /reindex`, `GET /health`. API, dosya sistemi veya Qdrant client ayrıntılarını dışarı sızdırmaz.

## 7. Benchmark ve başarı eşikleri

**Öneri:** İlk hedef mutlak bir skor değil, ölçülebilir baseline ve regression korumasıdır.

- En az 30 sorgu: semantic, exact identifier, typo, Türkçe biçimbilim, uzun bağlam ve negative sınıfları
- Exact arama: kalite referansı
- HNSW: exact'e göre recall kaybı raporu
- p50/p95/p99 latency ve hata oranı
- Her sorguda beklenen belge/chunk veya kabul edilebilir sonuç kümesi

İlk eşikler veri seti ölçülmeden “başarıldı” sayılmaz. Başlangıç kabulü: kritik sorgularda sonuç kaybı olmaması, genel recall'ın exact baseline'a göre küçük ve açıklanabilir bir farkla kalması, p95'in yerel kullanımda kabul edilebilir olmasıdır. Sayısal eşikler ilk benchmark çalışmasından sonra karar günlüğüne yazılır.

## 8. Hata, güvenlik ve yedekleme

**Öneri:** Hatalı dosya raporlanır ve ingest sonucu kısmi başarı olarak görünür; sessizce atlanmaz.

- Her işlemde correlation/request ID
- Parser hatası, provider hatası ve storage hatası ayrı sınıflar
- Path traversal ve dosya boyutu sınırı
- Loglarda varsayılan olarak tam metin yok
- API key yalnızca secrets kaynağından
- Snapshot + manifest birlikte yedeklenir
- Restore sonrası health check ve örnek arama zorunlu

## 9. RAG ile birleşme kararı

Vektörel veritabanı retrieval servisi olur; RAG uygulaması bunu çağırır. Retrieval cevabı chunk metni, kaynak konumu, score, `document_id`, `chunk_id` ve provenance taşımalıdır. Context packing, citation kuralları ve LLM generation RAG tarafında kalır.

## 10. Başlangıç kararı özeti

| Alan | Başlangıç varsayılanı |
|---|---|
| Runtime | CPython 3.12 |
| Dependency | uv + pyproject + lockfile |
| Test/lint | pytest + ruff |
| Backend | Qdrant local |
| Embedding | multilingual-e5-base, local |
| Vector | 768 dim, cosine, normalized |
| İlk format | Markdown/TXT |
| İlk arama | exact baseline + HNSW |
| İlk arayüz | CLI; sonra HTTP API |
| Kullanıcı | tek kullanıcı |
| RAG | ayrı retrieval consumer |

Bu varsayılanlar 30 sorguluk benchmark tamamlanmadan “nihai en iyi seçim” olarak kabul edilmez.

[^1]: [uv — Python versions](https://docs.astral.sh/uv/concepts/python-versions/) ve [uv — configuring projects](https://docs.astral.sh/uv/concepts/projects/config/).
[^2]: [intfloat/multilingual-e5-base model card](https://huggingface.co/intfloat/multilingual-e5-base).
[^3]: [BAAI/bge-m3 model card](https://huggingface.co/BAAI/bge-m3).

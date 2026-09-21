# Local runtime smoke testi

Bu prosedür server Qdrant ve local embedding modelinin birlikte çalıştığını doğrular. V1 geliştirmesini bloklamaz; local persistence akışı Docker olmadan test edilebilir. Docker server smoke geçişi tamamlanmıştır; prosedür tekrarlanabilir doğrulama olarak korunur.

Local-first doğrulamasında model cache'inin gerçekten yeterli olduğunu kanıtlamak için test ortamında `HF_HUB_OFFLINE=1` ayarlanabilir. Bu değişken, cache eksikse sessizce ağ kullanımına düşmek yerine testi başarısız bırakır.
CLI ile aynı kontrol `vdb doctor --offline` komutuyla yapılabilir; model cache'te yoksa ağ indirmesi beklenmeden açık hata döner. `vdb doctor` ise mevcut varsayılan davranışını korur.

## Ön koşullar

- Docker Desktop, yalnızca server Qdrant testleri için çalışır durumda olmalı. V1 local persistence modu Docker gerektirmez.
- `uv sync --dev` tamamlanmış olmalı.
- Kaynak dosyalar yalnızca `data/sources/` altında bulunmalı.

## Server Qdrant ile çalıştırma

Server testinden önce `.env` içinde `VDB_QDRANT_URL=http://localhost:6333` ayarlanmalıdır; aksi halde uygulama varsayılan local persistence modunda çalışır.

Compose server-mode Qdrant local persistence'tan ayrı `qdrant_server_storage` ve `qdrant_server_snapshots` named volume'larını kullanır.

```text
docker compose up -d
uv run vdb doctor
uv run vdb ingest data/sources/example.md
uv run vdb search "örnek sorgu"
$env:VDB_QDRANT_URL="http://localhost:6333"; uv run pytest -q tests/test_qdrant_server_integration.py
uv run uvicorn personal_vector_db.server:app --host 127.0.0.1 --port 8000
```

İlk local embedding çağrısı `intfloat/multilingual-e5-base` modelini indirir. Model indirilemezse ingest başarısız olur; bu durumda Qdrant değil embedding provider logları incelenir.

## Beklenen kontroller

- `vdb doctor` çıktısı `ok`.
- Collection `personal_documents_v1` oluşturulmuş olmalı.
- `owner_id` ve `document_status` payload index'leri mevcut olmalı.
- Ingest sonucu chunk sayısı ve document ID döndürmeli.
- Search sonucu text, score, source URI, location ve manifest bilgisi taşımalı.
- Aynı dosya tekrar ingest edildiğinde duplicate point oluşmamalı.
- Delete sonrası arama sonucu boşalmalı.
- Local modda `vdb backup` tar snapshot ve manifest oluşturmalı; server modunda Qdrant snapshot ve manifest oluşturmalı.
- Restore sonrası health ve örnek search yeniden geçmeli.

## Sorun ayrıştırma

| Belirti | İlk kontrol |
|---|---|
| `doctor` unavailable | Docker Desktop, port 6333 ve container logları |
| model download hatası | internet/cache/disk ve embedding provider |
| schema/dimension hatası | model manifest'i ve collection dimension |
| sonuç yok | `owner_id`, `document_status`, source path ve ingest sonucu |
| restore hatası | snapshot location, checksum, collection/model uyumu |

## Doğrulama kaydı

13 Eylül 2026 tarihinde Docker Desktop `29.7.2` ve Qdrant `v1.19.0` ile healthcheck geçti; payload-index/lifecycle ve collection snapshot/restore testleri `2 passed` oldu. Restore senaryosu Qdrant node içindeki `file:///qdrant/snapshots/<collection>/<snapshot>` URI'sını kullanır ve hedef collection'ı restore öncesi kaldırır.

## Local ve server storage izolasyonu

Local Qdrant (`path:qdrant_storage`) ile Docker Qdrant aynı storage klasörünü aynı anda açmamalıdır. Qdrant storage dosyaları üzerinde eşzamanlı local/server erişimi kilitlenme veya veri bütünlüğü riski doğurabilir. Server smoke testinden önce local CLI/API süreçlerini durdur; iki çalışma biçimini kalıcı olarak paralel kullanmak gerekiyorsa server için ayrı bir volume/klasör tanımla.

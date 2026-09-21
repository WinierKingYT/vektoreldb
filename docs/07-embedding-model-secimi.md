# 7. Embedding modeli seçimi

## Karar ilkesi

Modeli popülerliğe göre değil, kendi Türkçe sorgu setimizdeki retrieval kalitesine, veri gizliliğine ve işletim maliyetine göre seçeriz. İlk karşılaştırmada en az bir local model ve bir harici model aynı corpus üzerinde ölçülür.

## Local ve harici seçenek

| Kriter | Local | Harici API |
|---|---|---|
| Gizlilik | Veri makinede kalır | Sağlayıcı politikasına bağlı |
| Maliyet | Donanım ve işletim | Kullanım başına ücret |
| Başlangıç kolaylığı | Model/runtime kurulumu gerekir | API entegrasyonu kolay |
| Tekrarlanabilirlik | Model dosyası sabitlenebilir | API/model sürümü takip edilmeli |
| Latency | Donanıma bağlı | Ağ ve kota bağımlı |

## Zorunlu manifest alanları

`provider`, `model`, `model_revision`, `dimensions`, `distance`, `normalized`, `query_encoding`, `document_encoding`, `created_at` ve `chunking_version` saklanır. Bu alanlardan biri bilinmiyorsa üretim indeksi oluşturulmaz.

Sentence Transformers, retrieval modellerinde sorgu ve doküman için ayrı encoding yöntemleri sağlayabilir; seçilen modelin bunu gerektirip gerektirmediği ayrıca kontrol edilir. [Sentence Transformers kullanım rehberi](https://sbert.net/docs/sentence_transformer/usage/usage.html)

## Model kabul kriterleri

- Türkçe soru-cevap ve anahtar kelime sorgularında hedef Recall@5'i sağlamalı.
- Uzun Türkçe karakterlerde ve yazım varyasyonlarında hata vermemeli.
- Token limiti ve truncate davranışı açıkça bilinmeli.
- Aynı girdide deterministik veya kabul edilebilir derecede kararlı sonuç üretmeli.
- Lisans ve veri paylaşımı koşulları projeye uygun olmalı.
- Boyut, latency ve depolama maliyeti kişisel kullanım sınırları içinde olmalı.

Model değişimi doğrudan mevcut koleksiyonda yapılmaz; yeni koleksiyon, benchmark ve rollback planı gerekir.

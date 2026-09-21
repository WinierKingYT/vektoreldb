# 39. Multimodal ve özel veri türleri

## Görsel

Görsel için OCR metni, görsel açıklaması ve gerekirse image embedding ayrı alanlarda tutulur. Görsel vektörü text vektörüyle aynı uzayda değilse named vector veya ayrı collection kullanılır.

## Tablo

Tabloyu yalnızca düz metne çevirmek yerine başlık, satır bağlamı ve kaynak konumunu koru. Sayısal toplama/filtreleme için vector search tek başına kullanılmaz; yapılandırılmış sorgu katmanı gerekir.

## Kod

Kod için fonksiyon/sınıf sınırları, dil, repository, branch ve sembol metadata'sı gerekir. Kod araması V2'dir; genel metin chunking'iyle karıştırılmaz.

## Ses/video

Önce zaman damgalı transcript, sonra multimodal embedding değerlendirilir. Ham medya index'in tek doğruluk kaynağı değildir.

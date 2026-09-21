# 0. Kapsam ve desteklenen veri türleri

## İlk sürüm amacı

İlk sürüm, tek kullanıcının kişisel dokümanlarını yerel bir bilgi tabanında aramasını ve kaynak göstererek RAG uygulamalarında kullanmasını sağlar.

Öncelikler:

- Verinin kontrolünü kullanıcıda tutmak
- Local embedding veya harici embedding sağlayıcısı seçebilmek
- Kaynak dosyaya ve sayfa/bölüm konumuna geri dönebilmek
- Yeniden indekslemeyi güvenli ve tekrarlanabilir yapmak
- Arama kalitesini ölçebilmek

## Destek matrisi

| Tür | Sürüm | Çıktı | Özel kural |
|---|---:|---|---|
| Markdown/TXT/Org/RST/LOG/TEX/ICS | Mevcut | UTF-8 metin | Markdown başlıkları yorumlanır; diğerleri plain text olarak korunur |
| RTF | İlk parser dilimi | Temel metin | Unicode/cp1252 kaçışları ve paragraf sonları çıkarılır; gömülü nesneler ve karmaşık stiller yok |
| PDF | İlk parser dilimi | Sayfa bazlı metin | OCR ve karmaşık tablo/sütun düzeni yok |
| DOCX | İlk parser dilimi | Paragraf metni | Tablolar ve tam stil/konum korunmaz |
| HTML | İlk parser dilimi | Görünür metin | Script/style/navigasyon alanları atılır |
| JSON/JSONL/NDJSON/YAML/CSV/XML | İlk parser dilimi | Kayıt, satır veya XML leaf-node metni | Alan adları embedding metnine dahil edilir; JSONL/NDJSON satır konumu, YAML deterministik kaydı ve XML node yolu korunur |
| XLSX | 2 | Tablo/kayıt | Hücre bağlamı ve hesaplanmış değer politikası gerekir |
| Kod | 2 | Fonksiyon/sınıf parçaları | Dil, dosya ve sembol metadata'sı gerekir |
| Görsel/taranmış PDF | 3 | OCR veya multimodal metin | OCR kalite eşiği zorunlu |

Mevcut geliştirme diliminde Markdown/TXT ve kişisel plain-text alias'larına (`.org`, `.rst`, `.log`, `.tex`, `.ics`) ek olarak PDF, DOCX, HTML, EML, JSON,
JSONL/NDJSON, YAML/YML, RTF, CSV ve XML için suffix-tabanlı parser dispatch'i eklendi. XLSX, görsel, ses/video
ve özel kod araması daha sonraki adaylardır; desteklenmeyen dosya sessizce
atlanmaz, açık bir “desteklenmiyor” durumu üretir.

## Her kaynak için ortak çıktı

Parser, hangi dosya türünden gelirse gelsin şu alanları üretmelidir:

```json
{
  "document_id": "sha256:...",
  "source_uri": "file:///...",
  "source_type": "pdf",
  "title": "Belge başlığı",
  "language": "tr",
  "content_hash": "sha256:...",
  "sections": [
    {
      "text": "Temizlenmiş metin",
      "location": {"page": 3, "heading_path": ["Bölüm", "Alt bölüm"]}
    }
  ]
}
```

Orijinal dosya değişmeden saklanır. Parser çıktısı, chunk çıktısı ve embedding manifest'i birbirinden ayrıdır; böylece parser değişiminde kaynak dosyayı yeniden bulmak gerekmez.

## Kabul kriterleri

- Aynı dosya iki kez işlendiğinde aynı `document_id` oluşur.
- Boş metin, bozuk encoding ve parser hatası başarı olarak işaretlenmez.
- Her chunk kaynak dosyaya ve konuma geri izlenebilir.
- Desteklenmeyen format sessizce atlanmaz.
- Dosya türü, parser sürümü ve hata bilgisi manifest'e yazılır.

# İleri değerlendirme ve güvenlik

## Değerlendirme katmanları

ANN layer: exact recall, graph visits, index build time, update freshness.

Retrieval layer: Recall@k, MRR, nDCG, filter recall, duplicate rate, candidate efficiency.

Generation layer: context precision/recall, faithfulness, answer relevance, citation correctness.

System layer: p50/p95/p99 latency, error rate, CPU/RAM/disk, provider cost and recovery time.

RAGAS reference-free metrikler sunar; ARES context relevance, faithfulness ve answer relevance'i daha az insan etiketiyle değerlendirmek için otomatik judge ve PPI kullanır.[^1][^2] Otomatik judge sonuçları insan etiketli calibration set'i ve güven aralığı olmadan tek başına kabul kriteri yapılmaz.

## Güvenlik tehdit modeli

1. **Access leakage:** filtre sorgu sonrasında uygulanırsa yetkisiz sonuç görünür.
2. **Poisoning:** kötü niyetli belge retrieval ile model davranışını etkiler.
3. **Prompt injection:** kaynak metni talimat gibi yorumlanır.
4. **Metadata leakage:** belge adı, score veya source URI hassas bilgi sızdırır.
5. **Vector leakage:** erişilebilen embedding veya snapshot üzerinden veri çıkarımı denenir.
6. **Provider leakage:** harici embedding API'sine hassas veri taşınır.

## İleri kontroller

- ACL filtreleri server-side ve immutable context'ten üretilir.
- Retrieval metni XML/JSON sınırlarıyla “untrusted evidence” olarak aktarılır.
- Belge güven seviyesi, parser uyarısı ve provenance cevapta taşınır.
- Snapshot, WAL, log ve cache aynı silme/retention politikasına bağlanır.
- Harici provider için veri sınıfı bazlı allow/deny policy uygulanır.
- Red-team sorguları ve adversarial dokümanlar benchmark'a eklenir.

[^1]: Es et al., [RAGAS](https://arxiv.org/abs/2309.15217).
[^2]: Saad-Falcon et al., [ARES](https://arxiv.org/abs/2311.09476).

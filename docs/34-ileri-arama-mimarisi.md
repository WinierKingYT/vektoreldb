# 34. İleri arama mimarisi

## Arama katmanları

```text
query analysis → dense/sparse retrieval → fusion → reranking → diversification → context packing
```

V1'in varsayılanı dense retrieval'dır. V1.2'den itibaren dense ve sparse named
vector'lar aynı noktada tutulabilen hybrid yol opt-in olarak vardır; V1.3
reranking, V1.5 late interaction ve V1.6 quantization da ölçüm amaçlı opt-in
kalır. Füzyon raw skorları doğrudan toplamak yerine RRF/DBSF ile yapılır.
[Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)

## Candidate budget

İlk aşama recall için geniş (`20–100`), reranking daha pahalı olduğu için dar (`10–30`) aday kümesi kullanır. Bu sayılar varsayılan değil, benchmark parametreleridir.

## Diversification

Aynı document'tan gelen chunk'lar sınırlandırılır; başlık, kaynak ve bölüm çeşitliliği korunur. Sonuçlar context window'a sığacak şekilde token bütçesiyle paketlenir.

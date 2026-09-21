# 40. Graph-RAG ve ilişkisel retrieval

Vector search benzer içeriği, graph retrieval ise varlıklar ve ilişkileri bulur. Graph-RAG yalnızca şu ihtiyaçlar ortaya çıktığında eklenir:

- belge/kişi/proje/olay ilişkileri kritikse
- çok adımlı ilişki soruları dense search ile kaçıyorsa
- entity extraction güvenilir biçimde değerlendirilebiliyorsa

Önerilen akış: entity extraction → entity resolution → relation validation → graph traversal → vector evidence → kaynaklı cevap. Graph verisi vector DB payload'ına gizlenmez; ayrı bir source of truth ve provenance gerekir.

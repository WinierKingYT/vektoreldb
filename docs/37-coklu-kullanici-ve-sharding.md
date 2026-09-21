# 37. Çoklu kullanıcı ve sharding

V1 tek kullanıcıdır. Gelecekte çok kullanıcılı yapıda başlangıç tercihi tek collection + payload tabanlı partition'dır; kullanıcı başına collection oluşturmak kaynak overhead'i yaratabilir.

## Geçiş seçenekleri

- küçük/orta tenant: ortak collection ve indexed `tenant_id`
- büyük tenant: dedicated shard veya collection
- yüksek izolasyon: ayrı collection/cluster

Tenant filtresi her sorguda zorunludur. Shard sayısı ve replikasyon kapasite benchmark'ına göre seçilir; tenant büyüklüğü dengesizse tiered yaklaşım değerlendirilebilir. [Qdrant multitenancy rehberi](https://qdrant.tech/documentation/tutorials/multiple-partitions/)

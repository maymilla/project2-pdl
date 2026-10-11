// type: read
// params: {"id": 54928}
MATCH (me:Pengguna {id_pengguna: $id})-[:MEMBUAT]->(:Pesanan {status_pesanan: 'selesai'})
      -[:BERISI]->(:Produk)<-[:MENJUAL]-(s:Pengguna)
WITH me, collect(DISTINCT s) AS penjual_me
MATCH (other:Pengguna)-[:MEMBUAT]->(:Pesanan {status_pesanan: 'selesai'})
      -[:BERISI]->(:Produk)<-[:MENJUAL]-(s2:Pengguna)
WHERE other <> me AND s2 IN penjual_me
WITH penjual_me, other, count(DISTINCT s2) AS sama
MATCH (other)-[:MEMBUAT]->(:Pesanan {status_pesanan: 'selesai'})
      -[:BERISI]->(:Produk)<-[:MENJUAL]-(s3:Pengguna)
WITH penjual_me, other, sama, count(DISTINCT s3) AS n_other
RETURN other.id_pengguna AS id_pengguna,
       toFloat(sama) / (size(penjual_me) + n_other - sama) AS jaccard
ORDER BY jaccard DESC, id_pengguna
LIMIT 10;

// type: read
// params: {}
MATCH (b:Pengguna)-[:MEMBUAT]->(o:Pesanan {status_pesanan: 'selesai'})
      -[:BERISI]->(:Produk)<-[:MENJUAL]-(s:Pengguna)
WITH b, s, count(DISTINCT o) AS jumlah_pesanan
WHERE jumlah_pesanan > 1
RETURN b.id_pengguna AS id_pembeli,
       s.id_pengguna AS id_penjual,
       jumlah_pesanan
ORDER BY jumlah_pesanan DESC, id_pembeli, id_penjual
LIMIT 10;

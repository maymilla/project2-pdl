// type: read
// params: {}
MATCH (:Pengguna)-[:MENYUKAI]->(p:Produk)<-[:MENJUAL]-(penjual:Pengguna)
RETURN p.id_produk AS id_produk,
       p.nama_produk AS nama_produk,
       penjual.nama AS penjual,
       count(*) AS jumlah_favorit
ORDER BY jumlah_favorit DESC, id_produk
LIMIT 10;

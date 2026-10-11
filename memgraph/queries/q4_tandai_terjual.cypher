// type: write
// params: {}
MATCH (:Pesanan {status_pesanan: 'selesai'})-[:BERISI]->(p:Produk)
WITH DISTINCT p
SET p.status_produk = 'terjual'
RETURN count(p) AS affected_rows;

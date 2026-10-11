// type: write
// params: {}
MATCH (:Pengguna)-[f:MENYUKAI]->(:Produk {status_produk: 'terjual'})
WITH f
DELETE f
RETURN count(f) AS affected_rows;

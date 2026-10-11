// type: write
// params: {"id_pesanan": 2000001, "id_pembeli": 2, "id_penjual": 1, "id_produk_arr": [1]}
MATCH (b:Pengguna {id_pengguna: $id_pembeli}),
      (s:Pengguna {id_pengguna: $id_penjual})
WITH b, s, $id_produk_arr AS ids
UNWIND ids AS pid
MATCH (s)-[:MENJUAL]->(p:Produk {id_produk: pid, status_produk: 'tersedia'})
WITH b, s, ids, p
ORDER BY p.id_produk
WITH b, s, ids, collect(p) AS products, count(DISTINCT p) AS unique_products
WHERE size(products) = size(ids)
  AND unique_products = size(ids)
CREATE (b)-[:MEMBUAT]->(o:Pesanan {
    id_pesanan: $id_pesanan,
    id_pembeli: b.id_pengguna,
    id_penjual: s.id_pengguna,
    tanggal_pesanan: date(),
    status_pesanan: 'menunggu_pembayaran'
})
WITH o, products
UNWIND range(0, size(products) - 1) AS i
WITH o, products[i] AS p, i
CREATE (o)-[:BERISI {
    no_urut: i + 1,
    jumlah: 1,
    harga: p.harga_jual
}]->(p)
WITH o, count(*) AS detail_rows
RETURN o.id_pesanan AS id_pesanan, detail_rows;

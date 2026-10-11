-- type: write
-- params: {"id_pesanan": 2000001, "id_pembeli": 2, "id_penjual": 1, "id_produk_arr": [1]}
WITH pes AS (
    INSERT INTO pesanan (
        id_pesanan, id_pembeli, id_penjual, tanggal_pesanan, status_pesanan
    )
    VALUES (
        %(id_pesanan)s, %(id_pembeli)s, %(id_penjual)s,
        CURRENT_DATE, 'menunggu_pembayaran'
    )
    RETURNING id_pesanan
)
INSERT INTO detail_pesanan (id_pesanan, no_urut, id_produk, jumlah, harga)
SELECT pes.id_pesanan,
       ROW_NUMBER() OVER (ORDER BY p.id_produk),
       p.id_produk,
       1,
       p.harga_jual
FROM pes, produk p
WHERE p.id_produk = ANY(%(id_produk_arr)s)
  AND p.id_penjual = %(id_penjual)s
  AND p.status_produk = 'tersedia';

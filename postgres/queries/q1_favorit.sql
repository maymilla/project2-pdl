-- type: read
-- params: {}
SELECT p.id_produk, p.nama_produk, u.nama AS penjual, COUNT(*) AS jumlah_favorit
FROM produk_favorit f
JOIN produk p ON p.id_produk = f.id_produk
JOIN pengguna u ON u.id_pengguna = p.id_penjual
GROUP BY p.id_produk, p.nama_produk, u.nama
ORDER BY jumlah_favorit DESC, p.id_produk
LIMIT 10;

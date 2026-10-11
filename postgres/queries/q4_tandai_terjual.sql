-- type: write
-- params: {}
UPDATE produk
SET status_produk = 'terjual'
WHERE id_produk IN (
    SELECT d.id_produk
    FROM detail_pesanan d
    JOIN pesanan p ON p.id_pesanan = d.id_pesanan
    WHERE p.status_pesanan = 'selesai'
);

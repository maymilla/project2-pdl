-- type: read
-- params: {}
SELECT ps.id_pembeli, ps.id_penjual, COUNT(*) AS jumlah_pesanan
FROM pesanan ps
WHERE ps.status_pesanan = 'selesai'
GROUP BY ps.id_pembeli, ps.id_penjual
HAVING COUNT(*) > 1
ORDER BY jumlah_pesanan DESC, ps.id_pembeli, ps.id_penjual
LIMIT 10;

-- type: write
-- params: {}
DELETE FROM produk_favorit f
USING produk p
WHERE p.id_produk = f.id_produk
  AND p.status_produk = 'terjual';

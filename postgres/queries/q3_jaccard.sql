-- type: read
-- params: {"id": 54928}
WITH up AS (
    SELECT DISTINCT ps.id_pembeli AS id_pengguna, ps.id_penjual
    FROM pesanan ps
    WHERE ps.status_pesanan = 'selesai'
),
sizes AS (
    SELECT id_pengguna, COUNT(*) AS n
    FROM up
    GROUP BY id_pengguna
),
shared AS (
    SELECT o.id_pengguna, COUNT(*) AS s
    FROM up m
    JOIN up o ON o.id_penjual = m.id_penjual
        AND o.id_pengguna <> m.id_pengguna
    WHERE m.id_pengguna = %(id)s
    GROUP BY o.id_pengguna
)
SELECT sh.id_pengguna,
       sh.s::float / (sm.n + s2.n - sh.s) AS jaccard
FROM shared sh
JOIN sizes s2 ON s2.id_pengguna = sh.id_pengguna
CROSS JOIN (SELECT n FROM sizes WHERE id_pengguna = %(id)s) sm
ORDER BY jaccard DESC, sh.id_pengguna
LIMIT 10;

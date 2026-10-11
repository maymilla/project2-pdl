MATCH (n) DETACH DELETE n;

CREATE INDEX ON :Pengguna(id_pengguna);
CREATE INDEX ON :Produk(id_produk);
CREATE INDEX ON :Pesanan(id_pesanan);
CREATE INDEX ON :Produk(status_produk);
CREATE INDEX ON :Pesanan(status_pesanan);

// Unique constraints are intentionally omitted because Memgraph version compatibility varies.
// If the chosen Memgraph release supports CREATE CONSTRAINT, it can be added here.

DROP TABLE IF EXISTS produk_favorit, detail_pesanan, pesanan, produk, pengguna CASCADE;

CREATE TABLE pengguna (
    id_pengguna     INT PRIMARY KEY,
    nama            VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    tanggal_daftar  DATE NOT NULL
);

CREATE TABLE produk (
    id_produk       INT PRIMARY KEY,
    id_penjual      INT NOT NULL REFERENCES pengguna(id_pengguna),
    nama_produk     VARCHAR(150) NOT NULL,
    harga_jual      INT NOT NULL CHECK (harga_jual >= 0),
    status_produk   VARCHAR(20) NOT NULL DEFAULT 'tersedia'
                    CHECK (status_produk IN ('tersedia', 'terjual')),
    tanggal_dibuat  DATE NOT NULL
);

CREATE TABLE pesanan (
    id_pesanan      INT PRIMARY KEY,
    id_pembeli      INT NOT NULL REFERENCES pengguna(id_pengguna),
    id_penjual      INT NOT NULL REFERENCES pengguna(id_pengguna),
    tanggal_pesanan DATE NOT NULL,
    status_pesanan  VARCHAR(30) NOT NULL
                    CHECK (status_pesanan IN ('menunggu_pembayaran', 'dibayar', 'selesai', 'dibatalkan')),
    CHECK (id_pembeli <> id_penjual)
);

CREATE TABLE detail_pesanan (
    id_pesanan  INT NOT NULL REFERENCES pesanan(id_pesanan),
    no_urut     INT NOT NULL,
    id_produk   INT NOT NULL REFERENCES produk(id_produk),
    jumlah      INT NOT NULL CHECK (jumlah > 0),
    harga       INT NOT NULL CHECK (harga >= 0),
    PRIMARY KEY (id_pesanan, no_urut),
    UNIQUE (id_pesanan, id_produk)
);

CREATE TABLE produk_favorit (
    id_pengguna INT NOT NULL REFERENCES pengguna(id_pengguna),
    id_produk   INT NOT NULL REFERENCES produk(id_produk),
    PRIMARY KEY (id_pengguna, id_produk)
);

CREATE INDEX ON produk(id_penjual);
CREATE INDEX ON pesanan(id_pembeli);
CREATE INDEX ON pesanan(id_penjual);
CREATE INDEX ON detail_pesanan(id_produk);
CREATE INDEX ON produk_favorit(id_produk);

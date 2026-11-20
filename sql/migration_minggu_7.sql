-- ============================================================================
-- Migration Minggu 7: Modul Jadwal & Ruang (MySQL 8.0+)
-- Memisahkan jadwal dari mata_kuliah menjadi ruangan, dosen, kelas, dan jadwal.
-- ============================================================================

CREATE TABLE IF NOT EXISTS ruangan (
    kode      VARCHAR(16)  NOT NULL,
    nama      VARCHAR(100) NOT NULL,
    kapasitas INT          NOT NULL,
    PRIMARY KEY (kode),
    CONSTRAINT ck_ruangan_kapasitas_pos CHECK (kapasitas >= 1)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dosen (
    id   INT          NOT NULL AUTO_INCREMENT,
    nidn VARCHAR(20)  NOT NULL,
    nama VARCHAR(120) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_dosen_nidn UNIQUE (nidn)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS kelas (
    id         INT         NOT NULL AUTO_INCREMENT,
    kode_mk    VARCHAR(16) NOT NULL,
    nama_kelas VARCHAR(16) NOT NULL,
    kuota      INT         NOT NULL,
    semester   CHAR(5)     NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_kelas_mk_nama_sem UNIQUE (kode_mk, nama_kelas, semester),
    CONSTRAINT fk_kelas_mk
        FOREIGN KEY (kode_mk) REFERENCES mata_kuliah (kode_mk) ON DELETE RESTRICT,
    CONSTRAINT ck_kelas_kuota_pos CHECK (kuota >= 1),
    CONSTRAINT ck_kelas_semester_len CHECK (CHAR_LENGTH(semester) = 5)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS jadwal (
    id           INT         NOT NULL AUTO_INCREMENT,
    kelas_id     INT         NOT NULL,
    ruangan_kode VARCHAR(16) NOT NULL,
    dosen_id     INT         NOT NULL,
    hari         INT         NOT NULL COMMENT '1=Senin .. 6=Sabtu',
    jam_mulai    TIME        NOT NULL,
    jam_selesai  TIME        NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_jadwal_kelas
        FOREIGN KEY (kelas_id) REFERENCES kelas (id) ON DELETE CASCADE,
    CONSTRAINT fk_jadwal_ruangan
        FOREIGN KEY (ruangan_kode) REFERENCES ruangan (kode) ON DELETE RESTRICT,
    CONSTRAINT fk_jadwal_dosen
        FOREIGN KEY (dosen_id) REFERENCES dosen (id) ON DELETE RESTRICT,
    CONSTRAINT ck_jadwal_hari_range CHECK (hari >= 1 AND hari <= 6),
    CONSTRAINT ck_jadwal_jam_valid  CHECK (jam_mulai < jam_selesai),
    INDEX idx_jadwal_hari_ruangan (hari, ruangan_kode),
    INDEX idx_jadwal_hari_dosen   (hari, dosen_id)
) ENGINE=InnoDB;

-- Menambahkan kolom opsional kelas_id pada krs_detail untuk capacity check
ALTER TABLE krs_detail
    ADD COLUMN kelas_id INT NULL AFTER kode_mk,
    ADD CONSTRAINT fk_krs_detail_kelas
        FOREIGN KEY (kelas_id) REFERENCES kelas (id) ON DELETE SET NULL;

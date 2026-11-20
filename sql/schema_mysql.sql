-- ============================================================================
-- SIMAK Mini — Modul KRS (Minggu 5)
-- Skema Database MySQL 8.0+ (4 Tabel KRS + Tabel Skala Nilai + Referensi PMB)
-- ============================================================================

-- Referensi tabel dari Modul PMB (hanya mahasiswa approved yang punya NIM unik)
CREATE TABLE IF NOT EXISTS mahasiswa (
    nim        VARCHAR(20)  NOT NULL,
    nama       VARCHAR(120) NOT NULL,
    prodi      VARCHAR(80)  NOT NULL DEFAULT 'Teknik Informatika',
    status_pmb VARCHAR(20)  NOT NULL DEFAULT 'approved',
    PRIMARY KEY (nim)
) ENGINE=InnoDB;

-- Tabel 1: Mata Kuliah (penyederhanaan 1 MK = 1 kelas sebelum modul jadwal minggu ke-7)
CREATE TABLE IF NOT EXISTS mata_kuliah (
    kode_mk     VARCHAR(16)  NOT NULL,
    nama        VARCHAR(120) NOT NULL,
    sks         INT          NOT NULL,
    hari        INT          NOT NULL COMMENT '1=Senin .. 6=Sabtu',
    jam_mulai   TIME         NOT NULL,
    jam_selesai TIME         NOT NULL,
    PRIMARY KEY (kode_mk),
    CONSTRAINT ck_mk_sks_range  CHECK (sks >= 1 AND sks <= 4),
    CONSTRAINT ck_mk_hari_range CHECK (hari >= 1 AND hari <= 6),
    CONSTRAINT ck_mk_jam_valid  CHECK (jam_mulai < jam_selesai)
) ENGINE=InnoDB;

-- Tabel 4: Prerequisites (self-referencing many-to-many ke mata_kuliah)
-- Composite PK (kode_mk, kode_prasyarat) mencegah duplikasi pasangan prasyarat
-- sekaligus menyediakan indeks utama untuk pencarian berdasarkan kode_mk.
CREATE TABLE IF NOT EXISTS prerequisites (
    kode_mk        VARCHAR(16) NOT NULL,
    kode_prasyarat VARCHAR(16) NOT NULL,
    PRIMARY KEY (kode_mk, kode_prasyarat),
    CONSTRAINT fk_prereq_mk
        FOREIGN KEY (kode_mk) REFERENCES mata_kuliah (kode_mk) ON DELETE CASCADE,
    CONSTRAINT fk_prereq_prasyarat
        FOREIGN KEY (kode_prasyarat) REFERENCES mata_kuliah (kode_mk) ON DELETE CASCADE,
    CONSTRAINT ck_prereq_not_self CHECK (kode_mk <> kode_prasyarat)
) ENGINE=InnoDB;

-- Tabel 2: KRS (tingkat kartu: status & dosen PA dijaga di satu tempat)
-- UniqueConstraint (nim, semester) mencegah 1 mahasiswa punya >1 KRS per semester
-- sekaligus otomatis membentuk composite index (equality: nim, range: semester).
CREATE TABLE IF NOT EXISTS krs (
    id          INT         NOT NULL AUTO_INCREMENT,
    nim         VARCHAR(20) NOT NULL,
    semester    CHAR(5)     NOT NULL COMMENT 'Format tetap 5 char, misal 20251 (Ganjil 2025)',
    status      ENUM('draft', 'submitted', 'approved', 'revision') NOT NULL DEFAULT 'draft',
    dosen_pa_id VARCHAR(32) NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_krs_nim_semester UNIQUE (nim, semester),
    CONSTRAINT fk_krs_mahasiswa
        FOREIGN KEY (nim) REFERENCES mahasiswa (nim) ON DELETE RESTRICT,
    CONSTRAINT ck_krs_semester_len CHECK (CHAR_LENGTH(semester) = 5)
) ENGINE=InnoDB;

-- Tabel 3: KRS Detail (baris mata kuliah di dalam KRS)
-- UniqueConstraint (krs_id, kode_mk) adalah lapis penjaga terakhir anti double enrollment
-- sekaligus otomatis membentuk composite index (krs_id, kode_mk).
CREATE TABLE IF NOT EXISTS krs_detail (
    id      INT         NOT NULL AUTO_INCREMENT,
    krs_id  INT         NOT NULL,
    kode_mk VARCHAR(16) NOT NULL,
    nilai   VARCHAR(2)  NULL COMMENT 'Kosong saat KRS aktif; diisi setelah semester selesai',
    PRIMARY KEY (id),
    CONSTRAINT uq_krs_detail_krs_mk UNIQUE (krs_id, kode_mk),
    CONSTRAINT fk_krs_detail_krs
        FOREIGN KEY (krs_id) REFERENCES krs (id) ON DELETE CASCADE,
    CONSTRAINT fk_krs_detail_mk
        FOREIGN KEY (kode_mk) REFERENCES mata_kuliah (kode_mk) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Tabel Pembantu: Skala Nilai (memetakan huruf ke bobot numerik agar tidak
-- terjebak perbandingan string 'B' < 'C' atau 'D' > 'C').
CREATE TABLE IF NOT EXISTS skala_nilai (
    huruf VARCHAR(2)    NOT NULL,
    bobot DECIMAL(3, 2) NOT NULL,
    PRIMARY KEY (huruf)
) ENGINE=InnoDB;

INSERT IGNORE INTO skala_nilai (huruf, bobot) VALUES
    ('A',  4.00),
    ('A-', 3.70),
    ('B+', 3.30),
    ('B',  3.00),
    ('B-', 2.70),
    ('C+', 2.30),
    ('C',  2.00),
    ('D',  1.00),
    ('E',  0.00);

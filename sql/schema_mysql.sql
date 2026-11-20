-- ============================================================================
-- SIMAK Mini — Modul KRS (Minggu 5 & 6)
-- Skema Database MySQL 8.0+ (4 Tabel KRS + Audit Log + Notifikasi + Skala Nilai)
-- ============================================================================

CREATE TABLE IF NOT EXISTS mahasiswa (
    nim         VARCHAR(20)  NOT NULL,
    nama        VARCHAR(120) NOT NULL,
    prodi       VARCHAR(80)  NOT NULL DEFAULT 'Teknik Informatika',
    status_pmb  VARCHAR(20)  NOT NULL DEFAULT 'approved',
    dosen_pa_id VARCHAR(32)  NULL,
    PRIMARY KEY (nim)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mata_kuliah (
    kode_mk     VARCHAR(16)  NOT NULL,
    nama        VARCHAR(120) NOT NULL,
    sks         INT          NOT NULL,
    hari        INT          NOT NULL COMMENT '1=Senin .. 6=Sabtu',
    jam_mulai   TIME         NOT NULL,
    jam_selesai TIME         NOT NULL,
    is_wajib    BOOLEAN      NOT NULL DEFAULT TRUE,
    PRIMARY KEY (kode_mk),
    CONSTRAINT ck_mk_sks_range  CHECK (sks >= 1 AND sks <= 4),
    CONSTRAINT ck_mk_hari_range CHECK (hari >= 1 AND hari <= 6),
    CONSTRAINT ck_mk_jam_valid  CHECK (jam_mulai < jam_selesai)
) ENGINE=InnoDB;

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

CREATE TABLE IF NOT EXISTS krs (
    id            INT         NOT NULL AUTO_INCREMENT,
    nim           VARCHAR(20) NOT NULL,
    semester      CHAR(5)     NOT NULL COMMENT 'Format tetap 5 char, misal 20251',
    status        ENUM('draft', 'submitted', 'approved', 'revision') NOT NULL DEFAULT 'draft',
    dosen_pa_id   VARCHAR(32) NULL,
    submitted_at  DATETIME    NULL,
    approved_at   DATETIME    NULL,
    revision_note TEXT        NULL,
    updated_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    version       INT         NOT NULL DEFAULT 1 COMMENT 'Optimistic locking counter',
    PRIMARY KEY (id),
    CONSTRAINT uq_krs_nim_semester UNIQUE (nim, semester),
    CONSTRAINT fk_krs_mahasiswa
        FOREIGN KEY (nim) REFERENCES mahasiswa (nim) ON DELETE RESTRICT,
    CONSTRAINT ck_krs_semester_len CHECK (CHAR_LENGTH(semester) = 5)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS krs_detail (
    id      INT         NOT NULL AUTO_INCREMENT,
    krs_id  INT         NOT NULL,
    kode_mk VARCHAR(16) NOT NULL,
    nilai   VARCHAR(2)  NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_krs_detail_krs_mk UNIQUE (krs_id, kode_mk),
    CONSTRAINT fk_krs_detail_krs
        FOREIGN KEY (krs_id) REFERENCES krs (id) ON DELETE CASCADE,
    CONSTRAINT fk_krs_detail_mk
        FOREIGN KEY (kode_mk) REFERENCES mata_kuliah (kode_mk) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Log audit persetujuan/revisi (ditulis atomik bersama perubahan status KRS)
CREATE TABLE IF NOT EXISTS krs_approval_log (
    id         INT         NOT NULL AUTO_INCREMENT,
    krs_id     INT         NOT NULL,
    action     VARCHAR(20) NOT NULL COMMENT 'submit | approve | revise',
    actor_id   VARCHAR(32) NOT NULL,
    note       TEXT        NULL,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_approval_log_krs (krs_id),
    CONSTRAINT fk_approval_log_krs
        FOREIGN KEY (krs_id) REFERENCES krs (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Notifikasi dalam DB (dikirim keluar pasca-commit via Observer Pattern di Minggu 7)
CREATE TABLE IF NOT EXISTS notifikasi (
    id         INT          NOT NULL AUTO_INCREMENT,
    nim        VARCHAR(20)  NOT NULL,
    krs_id     INT          NOT NULL,
    judul      VARCHAR(120) NOT NULL,
    pesan      TEXT         NOT NULL,
    is_read    BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_notifikasi_nim (nim),
    CONSTRAINT fk_notifikasi_mahasiswa
        FOREIGN KEY (nim) REFERENCES mahasiswa (nim) ON DELETE CASCADE,
    CONSTRAINT fk_notifikasi_krs
        FOREIGN KEY (krs_id) REFERENCES krs (id) ON DELETE CASCADE
) ENGINE=InnoDB;

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

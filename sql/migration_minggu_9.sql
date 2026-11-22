-- ============================================================================
-- Migrasi Database Minggu 9-10 — Modul Nilai & Transkrip
-- 1. Tabel `grades` (nilai mahasiswa per MK per semester + presensi)
-- 2. Tabel `grade_history` (audit trail perubahan nilai)
-- 3. Trigger `trg_grades_after_update_audit` (otomatis insert ke grade_history)
-- 4. View `v_grade_history_mahasiswa` (riwayat perubahan nilai per mahasiswa)
-- ============================================================================

CREATE TABLE IF NOT EXISTS grades (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nim             VARCHAR(20) NOT NULL,
    kode_mk         VARCHAR(16) NOT NULL,
    semester        CHAR(5) NOT NULL,
    nilai_huruf     VARCHAR(2) NOT NULL,
    nilai_angka     DECIMAL(3, 2) NOT NULL,
    presensi_persen DECIMAL(5, 2) NOT NULL DEFAULT 100.00,
    updated_by      VARCHAR(64) NOT NULL DEFAULT 'system',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_grades_nim_mk_sem UNIQUE (nim, kode_mk, semester),
    CONSTRAINT ck_grades_semester_len CHECK (LENGTH(semester) = 5),
    CONSTRAINT ck_grades_presensi_range CHECK (presensi_persen >= 0 AND presensi_persen <= 100),
    CONSTRAINT ck_grades_angka_range CHECK (nilai_angka >= 0 AND nilai_angka <= 4),
    CONSTRAINT fk_grades_mhs FOREIGN KEY (nim) REFERENCES mahasiswa(nim) ON DELETE RESTRICT,
    CONSTRAINT fk_grades_mk FOREIGN KEY (kode_mk) REFERENCES mata_kuliah(kode_mk) ON DELETE RESTRICT,
    INDEX idx_grades_nim_sem (nim, semester)
);

CREATE TABLE IF NOT EXISTS grade_history (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    grade_id    INT NOT NULL,
    old_value   VARCHAR(2) NOT NULL,
    new_value   VARCHAR(2) NOT NULL,
    changed_by  VARCHAR(64) NOT NULL,
    changed_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason      TEXT NOT NULL,
    CONSTRAINT fk_grade_history_grade FOREIGN KEY (grade_id) REFERENCES grades(id) ON DELETE CASCADE,
    INDEX idx_grade_history_grade_time (grade_id, changed_at)
);

-- Trigger audit pada MySQL (di lapisan aplikasi juga dicatat atomik bersama reason)
DELIMITER $$
CREATE TRIGGER trg_grades_after_update_audit
AFTER UPDATE ON grades
FOR EACH ROW
BEGIN
    IF OLD.nilai_huruf <> NEW.nilai_huruf THEN
        INSERT INTO grade_history (grade_id, old_value, new_value, changed_by, changed_at, reason)
        VALUES (
            NEW.id,
            OLD.nilai_huruf,
            NEW.nilai_huruf,
            NEW.updated_by,
            CURRENT_TIMESTAMP,
            'Perubahan nilai melalui SQL UPDATE'
        );
    END IF;
END$$
DELIMITER ;

-- View riwayat perubahan nilai per mahasiswa
CREATE OR REPLACE VIEW v_grade_history_mahasiswa AS
SELECT
    gh.id AS history_id,
    g.nim,
    m.nama AS nama_mahasiswa,
    g.kode_mk,
    mk.nama AS nama_mk,
    g.semester,
    gh.old_value,
    gh.new_value,
    gh.changed_by,
    gh.changed_at,
    gh.reason
FROM grade_history gh
JOIN grades g ON g.id = gh.grade_id
JOIN mahasiswa m ON m.nim = g.nim
JOIN mata_kuliah mk ON mk.kode_mk = g.kode_mk
ORDER BY gh.changed_at DESC, gh.id DESC;

-- ============================================================================
-- Uji Query Prasyarat (NOT EXISTS) & Perbandingan EXPLAIN Sebelum vs Sesudah Indeks
-- Jalankan di MySQL 8.0+ untuk mengambil bukti EXPLAIN.
-- ============================================================================

-- 1. Query Prasyarat (NOT EXISTS dengan tabel skala_nilai)
-- Mencari seluruh prasyarat mata kuliah 'IF201' (Struktur Data) yang BELUM lulus
-- oleh mahasiswa NIM '20240001' (Budi) pada semester sebelum '20251' dengan nilai minimal C (bobot >= 2.00).
EXPLAIN
SELECT mk.kode_mk, mk.nama
FROM prerequisites p
JOIN mata_kuliah mk ON mk.kode_mk = p.kode_prasyarat
WHERE p.kode_mk = 'IF201'
  AND NOT EXISTS (
      SELECT 1
      FROM krs_detail kd
      JOIN krs k ON k.id = kd.krs_id
      JOIN skala_nilai sn ON sn.huruf = kd.nilai
      WHERE k.nim = '20240001'
        AND k.semester < '20251'
        AND kd.kode_mk = p.kode_prasyarat
        AND sn.bobot >= 2.00
  )
ORDER BY mk.kode_mk;

-- ============================================================================
-- 2. Simulasi Tabel TANPA Indeks (untuk membuktikan type = ALL / Full Table Scan)
-- ============================================================================
CREATE TEMPORARY TABLE tmp_krs_no_idx (
    id INT NOT NULL,
    nim VARCHAR(20) NOT NULL,
    semester CHAR(5) NOT NULL
);

CREATE TEMPORARY TABLE tmp_krs_detail_no_idx (
    id INT NOT NULL,
    krs_id INT NOT NULL,
    kode_mk VARCHAR(16) NOT NULL,
    nilai VARCHAR(2) NULL
);

-- Sebelum indeks -> perhatikan kolom `type = ALL` (Full Table Scan)
EXPLAIN
SELECT mk.kode_mk, mk.nama
FROM prerequisites p
JOIN mata_kuliah mk ON mk.kode_mk = p.kode_prasyarat
WHERE p.kode_mk = 'IF201'
  AND NOT EXISTS (
      SELECT 1
      FROM tmp_krs_detail_no_idx kd
      JOIN tmp_krs_no_idx k ON k.id = kd.krs_id
      JOIN skala_nilai sn ON sn.huruf = kd.nilai
      WHERE k.nim = '20240001'
        AND k.semester < '20251'
        AND kd.kode_mk = p.kode_prasyarat
        AND sn.bobot >= 2.00
  );

-- ============================================================================
-- 3. Tambahkan Indeks Eksplisit dengan Urutan Kolom yang Benar
--    Aturan: kolom equality (=) didahulukan, kolom range (<) belakangan.
-- ============================================================================
CREATE INDEX idx_tmp_krs_nim_semester ON tmp_krs_no_idx (nim, semester);
CREATE INDEX idx_tmp_krs_detail_krs_mk ON tmp_krs_detail_no_idx (krs_id, kode_mk);

-- Sesudah indeks -> perhatikan kolom `type` berubah menjadi `ref` / `eq_ref` / `range`
EXPLAIN
SELECT mk.kode_mk, mk.nama
FROM prerequisites p
JOIN mata_kuliah mk ON mk.kode_mk = p.kode_prasyarat
WHERE p.kode_mk = 'IF201'
  AND NOT EXISTS (
      SELECT 1
      FROM tmp_krs_detail_no_idx kd
      JOIN tmp_krs_no_idx k ON k.id = kd.krs_id
      JOIN skala_nilai sn ON sn.huruf = kd.nilai
      WHERE k.nim = '20240001'
        AND k.semester < '20251'
        AND kd.kode_mk = p.kode_prasyarat
        AND sn.bobot >= 2.00
  );

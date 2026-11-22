# OPAR — Minggu 9–10 (Modul Nilai & Transkrip)

## O — Objective
Membangun Modul Nilai & Transkrip pada SIMAK Mini yang mencakup:
1. Grade Management (input nilai A–E, konversi huruf -> angka, validasi presensi >= 75%, edit nilai dengan audit trail `grade_history`).
2. GPA Calculator (`calculate_ips`, `calculate_ipk` dengan aturan nilai >= D & MK diulang ambil tertinggi, `get_transcript`).
3. Generator Transkrip Resmi PDF (ReportLab) & template HTML profesional mirip ijazah resmi (+ ekspor CSV).
4. Form web dosen (`/grades-portal`) yang langsung memperbarui IPK otomatis saat nilai diinput/diedit.
5. Pengujian otomatis mencakup 12 kasus perhitungan IPK, presensi < 75%, audit trail, dan PDF generator.

## P — Plan
1. Tambah model ORM `Grade` & `GradeHistory` (`app/models/grade.py`) dan hierarki exception `GradeError` (`app/exceptions.py`).
2. Bangun `app/services/gpa_calculator.py`, `app/services/grade_service.py`, `app/services/transcript_pdf.py`, dan `app/services/transcript_html.py`.
3. Bangun router `app/routers/grades.py` & halaman web dosen `app/static/grades_portal.html`.
4. Tambahkan SQL migrasi + trigger + view (`sql/migration_minggu_9.sql`) dan 12+ kasus uji di `tests/test_minggu_9.py`.

## A — Action
- Menginstall `reportlab`, mengimplementasikan seluruh service, router, UI portal dosen, dan dokumentasi.
- Menjalankan `python -m pytest -v` untuk memverifikasi seluruh test suite Minggu 5–10.

## R — Reflection
- Memisahkan fungsi kalkulasi murni (`calculate_ipk_from_records`) dari query database membuat pengujian 12 kasus tepi IPK (nilai sempurna, semester awal kosong, MK diulang naik/turun/3x, nilai E, pembulatan) sangat cepat dan mudah diverifikasi.
- Penggunaan ReportLab dengan logo vektor `Drawing` menjamin PDF transkrip selalu ter-generate stabil di Windows tanpa masalah dependensi sistem operasi.

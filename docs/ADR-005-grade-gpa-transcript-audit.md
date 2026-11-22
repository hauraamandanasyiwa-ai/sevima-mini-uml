# ADR-005: Arsitektur Modul Nilai, Kalkulator GPA (`Decimal`), Audit Trail, & Transkrip PDF

**Status:** Diterima (Minggu 9–10)  
**Konteks:** Melanjutkan proyek terintegrasi SIMAK Mini dengan Modul Nilai & Transkrip (input/edit nilai, perhitungan IPS/IPK otomatis, audit trail perubahan nilai, serta generator transkrip PDF & HTML).

## Keputusan 1: Perhitungan IPS & IPK Menggunakan `Decimal` (`ROUND_HALF_UP`)
- **Alasan:** Perhitungan IPK memakai `float` rawan ketidaktepatan biner (mis. `3.499999999` vs `3.50` yang menentukan predikat *Cum Laude*). Menggunakan `Decimal` dan pembulatan `ROUND_HALF_UP` ke 2 angka desimal menjamin hasil deterministik.
- **Aturan Kelulusan & Pengulangan:**
  - Sesuai Step 1 spesifikasi: hanya mata kuliah lulus (`nilai >= D`, yakni `A` s.d. `D`; `E` tidak lulus) yang dihitung dalam IPK.
  - Jika mata kuliah diulang di beberapa semester, `calculate_ipk_from_records()` mengambil **nilai tertinggi** per `kode_mk` sehingga SKS tidak terhitung ganda.
  - Edge case mahasiswa semester 1 / belum ada nilai lulus mengembalikan `Decimal("0.00")`.

## Keputusan 2: Audit Trail Atomik di Lapisan Service + SQL Trigger & View
- Setiap `PUT /grades/{grade_id}` mewajibkan kolom `reason` dan `changed_by` non-kosong, lalu menyimpan perubahan pada tabel `grades` dan menyisipkan baris audit ke `grade_history` dalam **satu transaksi atomik**.
- Untuk kebutuhan database MySQL produksi, [migration_minggu_9.sql](file:///c:/Users/Wawa/OneDrive/Documents/MINGGUUUU%209/sql/migration_minggu_9.sql) juga menyertakan trigger `trg_grades_after_update_audit` dan view `v_grade_history_mahasiswa`.

## Keputusan 3: PDF Resmi dengan ReportLab + Template HTML Dinamis Siap Cetak
- Menggunakan **ReportLab** (`SimpleDocTemplate`, `Table`, vektor `Drawing` untuk logo universitas) agar PDF dapat di-generate langsung di Windows/Linux tanpa ketergantungan binary GTK/Cairo eksternal.
- Selain PDF (`GET /transcripts/{nim}/pdf`), disediakan pula template HTML + CSS profesional mirip ijazah resmi (`GET /transcripts/{nim}/html`) dan ekspor CSV (`GET /transcripts/{nim}/csv`).

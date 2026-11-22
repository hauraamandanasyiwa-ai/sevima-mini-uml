# AI Usage Log — Minggu 9–10

| No | Komponen | Kebutuhan & Aturan Bisnis | Verifikasi |
|---|---|---|---|
| 1 | GPA Calculator (`app/services/gpa_calculator.py`) | `calculate_ips`, `calculate_ipk` (hanya MK lulus `>= D`, MK diulang ambil nilai tertinggi, kosong -> `0.00`), `get_transcript`, dan predikat kelulusan (`Cum Laude >= 3.50`, `Sangat Memuaskan 3.00–3.49`, dst). | Diuji dengan 12 kasus parameterisasi di `tests/test_minggu_9.py` termasuk pembulatan `Decimal` `ROUND_HALF_UP`. |
| 2 | Grade Management & Audit Trail (`app/services/grade_service.py`) | Tolak presensi `< 75%`, wajib `reason` saat edit nilai, simpan `GradeHistory` atomik bersama update `Grade`, serta sinkronisasi ke `krs_detail.nilai`. | Diuji presensi `74.99%` (400) vs `75.00%` (201), edit tanpa alasan ditolak, dan histori tampil di `/grades/history/{nim}`. |
| 3 | PDF & HTML Generator (`app/services/transcript_pdf.py`, `transcript_html.py`) | Layout transkrip resmi: logo universitas, judul `TRANSKRIP AKADEMIK`, biodata, tabel per semester `[Kode MK | Nama MK | SKS | Nilai | Mutu]`, footer Total SKS / IPK / Predikat / TTD Dekan. | Diuji output PDF valid (`%PDF-`, ukuran > 1.5KB) dan HTML memuat seluruh bagian resmi. |
| 4 | Portal Web Dosen (`app/static/grades_portal.html`) | Form input/edit nilai, IPK otomatis ter-update, tombol preview HTML / download PDF / CSV, dan tampilan tabel audit trail. | Diverifikasi melalui `TestClient` dan pengecekan endpoint `/grades-portal`. |

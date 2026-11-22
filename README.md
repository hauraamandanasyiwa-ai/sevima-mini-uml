# SIMAK Mini — Modul Nilai & Transkrip (Minggu 9–10)

Implementasi terintegrasi **SEVIMA Mini** untuk mata kuliah Pemrograman Berorientasi Objek menggunakan **FastAPI**, **SQLAlchemy 2.0**, **Pydantic v2**, dan **ReportLab** (melanjutkan Modul KRS Minggu 5–6, Modul Jadwal & Ruang Minggu 7–8, dan kini **Modul Nilai & Transkrip Minggu 9–10**).

## Ringkasan Deliverable Minggu 9–10

1. **Grade Management (30%)** — `app/models/grade.py`, `app/services/grade_service.py`, `app/routers/grades.py`
   - Input nilai mahasiswa per mata kuliah per semester (`A`, `A-`, `B+`, `B`, `B-`, `C+`, `C`, `D`, `E`).
   - Konversi huruf -> angka (`A=4.00`, `B=3.00`, `C=2.00`, `D=1.00`, `E=0.00`) menggunakan `Decimal`.
   - Edit nilai dengan **audit trail** wajib (`grade_history`: `id`, `grade_id`, `old_value`, `new_value`, `changed_by`, `changed_at`, `reason`) dan view riwayat per mahasiswa (`GET /grades/history/{nim}`).

2. **GPA Calculator (30%)** — `app/services/gpa_calculator.py`
   - `calculate_ips(session, nim, semester)` -> IP semester.
   - `calculate_ipk(session, nim)` -> IP kumulatif (hanya hitung MK lulus `>= D`, MK diulang ambil nilai tertinggi, belum ada nilai -> `0.00`).
   - `get_transcript(session, nim)` -> full academic record per semester + ringkasan kumulatif.

3. **PDF Generator & Template HTML Resmi (25%)** — `app/services/transcript_pdf.py`, `app/services/transcript_html.py`
   - Generator PDF resmi memakai **ReportLab** (`GET /transcripts/{nim}/pdf`): logo universitas, judul `TRANSKRIP AKADEMIK`, biodata (NIM, Nama, Prodi, Angkatan), tabel per semester `[Kode MK | Nama MK | SKS | Nilai | Mutu]` + IPS, serta footer (Total SKS, IPK, Predikat, TTD Dekan).
   - Template HTML + CSS profesional mirip ijazah resmi (`GET /transcripts/{nim}/html`) + ekspor CSV (`GET /transcripts/{nim}/csv`).

4. **Business Rules (10%)**
   - Nilai ditolak jika **presensi < 75%** (`InsufficientAttendanceError`, HTTP 400).
   - Lulus MK jika nilai `>= D` (`E` tidak lulus dan diabaikan dari IPK).
   - Predikat kelulusan otomatis: **Cum Laude** (`>= 3.50`), **Sangat Memuaskan** (`3.00–3.49`), **Memuaskan** (`2.75–2.99`), **Cukup** (`2.00–2.74`).

5. **Form Web Dosen & Tests (5%)**
   - Portal input/edit nilai dosen di `http://127.0.0.1:8000/grades-portal` (IPK ter-update otomatis, audit trail live, tombol Download PDF).
   - 12 kasus unit test perhitungan IPK + pengujian presensi, audit trail, PDF/HTML/CSV, dan API di `tests/test_minggu_9.py`.
   - Migrasi SQL + Trigger Audit + View di `sql/migration_minggu_9.sql`.

## Cara Menjalankan

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Buka di browser:
- **Portal Nilai & Transkrip (Minggu 9–10):** `http://127.0.0.1:8000/grades-portal`
- **Conflict Resolver Dashboard (Minggu 8):** `http://127.0.0.1:8000/conflict-resolver`
- **Swagger API Docs:** `http://127.0.0.1:8000/docs`

### Menjalankan Seluruh Test Suite

```powershell
python -m pytest -v
```

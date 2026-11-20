# AI Usage Log — Modul KRS (Minggu 5)

Dokumen ini mencatat prompt kunci, proses review kritis, dan revisi sesuai **AI-First Charter** (tidak pernah menempelkan data mahasiswa sungguhan ke prompt; hanya memakai data dummy seperti Budi & mata kuliah contoh).

---

## 1. Prompt Kunci yang Digunakan

### Langkah 1 — Chain of Responsibility & KRS Manager
- **Konteks yang ditambahkan ke prompt dokumen tugas:**
  - Python 3.12+, FastAPI, SQLAlchemy 2.0, Pydantic v2.
  - Nama model: `MataKuliah`, `prerequisites` (`Table`), `KRS`, `KRSDetail`, `SkalaNilai`, enum `KRSStatus`.
  - Aturan nilai minimal C memakai tabel pemetaan bobot `skala_nilai` (`bobot >= 2.00`), bukan perbandingan string.
  - Rumus irisan jadwal ketat: `hari1 == hari2 and mulai1 < selesai2 and mulai2 < selesai1` (bersambung tidak bentrok).
  - Rantai berhenti di kegagalan pertama untuk `add_course`, sedangkan `validate_krs` mengumpulkan semua error.

### Langkah 3 — Query Prasyarat & Optimasi Indeks
- **Prompt:** Menulis SQL `NOT EXISTS` untuk mengambil seluruh prasyarat dari mata kuliah `X` yang belum diluluskan mahasiswa dummy `Budi` pada semester `< semester_aktif` dengan bobot nilai minimal `2.00` (C), lengkap dengan skrip `EXPLAIN` sebelum dan sesudah indeks pada MySQL.

---

## 2. Checklist Verifikasi Kritis (Review Hasil AI)

| No | Item Pemeriksaan | Status | Bukti di Kode |
| :--- | :--- | :---: | :--- |
| 1 | Apakah arah self-referencing `primaryjoin` & `secondaryjoin` pada `MataKuliah.prasyarat` benar (tidak terbalik)? | LULUS | `app/models/krs.py` + `test_self_referencing_prerequisite_direction` |
| 2 | Apakah bentrok jadwal memakai rumus irisan interval (`mulai1 < selesai2 and mulai2 < selesai1`), bukan hanya jam mulai yang sama? | LULUS | `app/validators/conflict.py` + `test_schedule_conflict_cases` (kasus Basis Data 08:00-10:30 vs Statistika 09:00-11:00) |
| 3 | Apakah nilai dibandingkan dengan bobot numerik (`skala_nilai`), bukan perbandingan string (`nilai >= 'C'`)? | LULUS | `app/queries/prerequisite.py` + `test_prerequisite_validator_grade_weights_and_previous_semester` |
| 4 | Apakah total tepat 24 SKS masih diizinkan, dan 25+ SKS ditolak dengan pesan menyebut angka? | LULUS | `app/validators/sks.py` (`MAX_SKS = 24`) + `test_sks_validator_allows_exact_24_and_rejects_over` |
| 5 | Apakah bebas masalah N+1 pada query prasyarat? | LULUS | Satu query `NOT EXISTS` di `app/queries/prerequisite.py` |
| 6 | Apakah pesan error menyebut nama mata kuliah secara spesifik? | LULUS | Seluruh 4 validator di `app/validators/` |
| 7 | Apakah validasi & insert berada dalam 1 transaksi dengan `with_for_update()` dan commit sekali di akhir? | LULUS | `app/services/krs_manager.py` |
| 8 | Apakah hanya menggunakan data dummy (Budi, Siti, MK contoh) tanpa data mahasiswa sungguhan? | LULUS | `tests/conftest.py`, `sql/explain_benchmark.sql` |

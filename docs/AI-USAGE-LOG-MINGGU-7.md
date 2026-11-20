# AI Usage Log — Minggu 7 (Detektor Bentrok 3D & Scheduling Service)

Dokumen ini mencatat prompt kunci, perbandingan model, serta **revisi manual terhadap 5 bug klasik AI** sesuai AI-First Charter.

---

## 1. Fitur & Prompt Kunci
- **Fitur:** Model domain (`Ruangan`, `Dosen`, `Kelas`, `Jadwal`), Detektor Bentrok 3 Dimensi (`room_conflict` & `lecturer_conflict`), `SchedulingService` (`create`, `update`, `delete`, `get_all_conflicts`, `check_capacity`), dan pengujian Example-Based + Hypothesis.
- **Perbaikan Prompt Langkah 1:**
  - Menegaskan aturan **interval setengah terbuka** `[jam_mulai, jam_selesai)` dengan contoh kuliah bersambung `08:00-09:40` & `09:40-11:20` yang tidak boleh bentrok.
  - Menegaskan tipe waktu `datetime.time` (bukan string) + validasi Pydantic.
  - Meminta output `@dataclass(frozen=True)` dengan `Literal["room_conflict", "lecturer_conflict"]` dan pasangan ID terurut.
  - Meminta dua versi (naif sebagai acuan + teroptimasi sweep) beserta tes diferensial yang membuktikan keduanya ekuivalen.

---

## 2. Revisi Manual terhadap 5 Bug Klasik AI

| No | Bug Klasik yang Sering Muncul | Revisi Manual yang Diterapkan | Penjaga Permanen (Test) |
| :--- | :--- | :--- | :--- |
| 1 | Perbandingan memakai `<=` / `>=` sehingga kuliah bersambung `09:40` dianggap bentrok | Menggunakan `<` pada `is_time_overlap` dan `>` pada filter `active` di sort-and-sweep | `test_conflict_detector.py` (kasus ke-3: `08:00-09:40` vs `09:40-11:20`) |
| 2 | Jam dibandingkan sebagai string (`"9:00" > "10:00"`) | Menggunakan kolom SQLAlchemy `Time` dan validasi Pydantic `datetime.time` | `app/models/schedule.py`, `app/schemas/schedule.py` |
| 3 | Lupa memeriksa kesamaan `hari` sehingga Senin dan Rabu di ruang sama dianggap bentrok | Memeriksa `a.hari == b.hari` dan mengelompokkan berdasarkan `(hari, ruangan_kode)` & `(hari, dosen_id)` | `test_conflict_detector.py` (kasus ke-4: beda hari) |
| 4 | Loop ganda penuh melaporkan pasangan dua kali: `(A, B)` dan `(B, A)` | Menggunakan `itertools.combinations(schedules, 2)` + helper `pasangan()` yang mengurutkan ID | `test_property_differential_sweep_matches_naive_exactly` (cek `Counter`) |
| 5 | Melaporkan `time_overlap` sebagai konflik padahal ruang dan dosen berbeda | Menghapus tipe `time_overlap`; hanya `room_conflict` dan `lecturer_conflict` yang sah | `test_conflict_detector.py` (kasus ke-6) |

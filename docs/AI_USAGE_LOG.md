# AI Usage Log — Modul PMB (Minggu 3)

> **Kepatuhan AI-First Charter:**
> - Tidak ada data pribadi asli (nama, email, nomor HP, alamat sungguhan) yang dimasukkan ke dalam prompt maupun pengujian.
> - Seluruh data uji menggunakan data fiktif dengan domain `@example.com`.
> - Seluruh kode hasil AI telah dibaca, dijalankan, dan diverifikasi secara langsung.

---

## Log Interaksi Utama

| No | Tanggal | Tahap | Ringkasan Prompt / Revisi | Verifikasi Manual yang Dilakukan |
|----|---------|-------|---------------------------|----------------------------------|
| 1 | 2026-11-20 | Analisis Tugas | Menganalisis transkrip materi Minggu 3 untuk memetakan deliverable wajib, constraint 2 lapis, dan potensi jebakan output AI. | Membandingkan hasil analisis dengan poin-poin deliverable (3 tabel, 5 constraint, Alembic upgrade/downgrade, endpoint register). |
| 2 | 2026-11-20 | Skema & Model SQLAlchemy 2.0 | Meminta pembuatan model `ProgramStudi`, `JalurMasuk`, dan `CalonMahasiswa` memakai SQLAlchemy 2.0 (`Mapped`/`mapped_column`), `phone` bertipe `String(15)`, `StatusPMB` Enum dengan `create_constraint=True`, kolom `nim` nullable+unique, dan `PRAGMA foreign_keys=ON`. | Menjalankan `alembic upgrade head`, memeriksa struktur tabel lewat SQLite `.schema`, dan menguji penolakan data invalid langsung di level database (FK salah, status ilegal, email duplikat). |
| 3 | 2026-11-20 | Migrasi Alembic | Membuat script revisi `0001_initial_pmb` dengan urutan `upgrade()` dari tabel referensi ke tabel anak, dan `downgrade()` sebaliknya. | Menjalankan siklus `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` dan memastikan tidak ada error Foreign Key. |
| 4 | 2026-11-20 | REST API FastAPI | Membangun arsitektur terpisah (`models/`, `schemas/`, `services/`, `routers/`, `database.py`), validasi Pydantic (regex HP Indo & `EmailStr`), DI `get_db()`, dan error handling `201`, `400`, `409`. | Menjalankan verifikasi endpoint `POST /api/pmb/register` untuk kasus valid (`201`), email ganda (`409`), nomor HP salah (`400`), dan prodi tidak ada (`400`). |

---

## Prompt Terbaik (Best Prompt) — Minggu 3

```text
Buatkan model SQLAlchemy 2.0 (DeclarativeBase, Mapped, mapped_column) dan script migrasi Alembic (upgrade & downgrade) untuk modul PMB dengan ketentuan:
1. 3 tabel terpisah: program_studi (id, kode 3 char unique, nama, fakultas), jalur_masuk (id, nama unique), dan calon_mahasiswa (id, nama_lengkap, email unique+index, phone String(15), tanggal_lahir, alamat, program_studi_id FK, jalur_masuk_id FK, status Enum pending/approved/rejected dengan create_constraint=True, nim nullable unique, created_at server_default, approved_at nullable).
2. Aktifkan PRAGMA foreign_keys=ON pada koneksi SQLite.
3. Pisahkan kode backend FastAPI ke folder models, schemas, services, routers, dan database.py dengan Dependency Injection get_db().
4. Validasi format nomor HP Indonesia (^(\+62|62|0)8[1-9][0-9]{6,10}$) di Pydantic dan jelaskan lapisan penegakan tiap constraint.
5. Gunakan data dummy fiktif @example.com untuk pengujian.
```

---

## Log Interaksi Utama — Minggu 4 (Format Silabus)

| Minggu | Fitur | Tujuan | LLM / Tool | Prompt Kunci | Tautan Kode AI Awal | Revisi Manual | Hasil Uji |
|--------|-------|--------|------------|--------------|---------------------|---------------|-----------|
| Minggu 4 | Approve/Reject & State Machine | Membangun `PUT /api/pmb/approve/{id}` dan `PUT /api/pmb/reject/{id}` dengan aturan transisi status & idempotensi | Antigravity AI (Gemini) | "Buatkan state machine PMBService untuk approve dan reject: `pending -> approved/rejected`, status akhir tidak bisa dibalik (409), approve ulang idempotent mengembalikan 200 + NIM lama tanpa menaikkan counter, dan tangani 404/400/409." | `app/services/pmb_service.py`, `app/routers/pmb.py` | Menambahkan pemeriksaan `with_for_update()` pada baris `CalonMahasiswa`, memastikan `approved_at` memakai `datetime.now(timezone.utc)`, dan memverifikasi bahwa `approve` pada prodi berkode non-3-digit mengembalikan `400`. | Lulus (`test_approve_generate_nim`, `test_approve_idempotent`, `test_approve_not_found`, `test_approve_rejected_returns_409`, `test_approve_invalid_kode_prodi_returns_400`, `test_reject_idempotent_and_guards`). |
| Minggu 4 | Generator NIM Aman Race Condition | Membuat fungsi `generate_nim` yang aman untuk multi-worker (tanpa `threading.Lock`) | Antigravity AI (Gemini) | "Implementasikan generator NIM format 11 digit `YYYYPPPNNNN` memakai tabel `nim_counter` (PK `tahun`, `kode_prodi`) dengan `SELECT ... FOR UPDATE`, `db.flush()` tanpa `commit()` di dalam generator, cek batas 9999, plus retry `IntegrityError` di service." | `app/models/nim_counter.py`, `app/services/nim_generator.py`, `alembic/versions/0002_add_nim_counter.py` | Mengganti pendekatan lock memori Python (`threading.Lock`) ke database row lock (`nim_counter` + `with_for_update()`), mengisi `last_number=0` secara eksplisit saat insert pertama, dan memisahkan pure function `format_nim()` untuk unit test. | Lulus seluruh unit test `tests/test_nim_generator.py` dan uji rollback Alembic `upgrade -> downgrade -1 -> upgrade`. |
| Minggu 4 | Endpoint Status & Statistik | Menyediakan `GET /api/pmb/status/{id}` (tanpa bocor data pribadi) dan `GET /api/pmb/stats` (`GROUP BY`) | Antigravity AI (Gemini) | "Buat endpoint status dengan Pydantic schema terbatas dan endpoint stats menggunakan `func.count` + `GROUP BY` + `outerjoin` agar prodi dan jalur masuk dengan 0 pendaftar tetap tampil." | `app/schemas/pmb.py`, `app/services/pmb_service.py` | Memastikan `StatusOut` tidak menyertakan `alamat`, `tanggal_lahir`, `phone`, maupun `email`, serta memastikan `per_status` selalu memuat kunci `pending`, `approved`, dan `rejected`. | Lulus (`test_get_status_success_and_not_found`, `test_get_stats_aggregation_and_zero_counts`). |
| Minggu 4 | Automated Testing & Coverage | Menulis unit & integration test dengan `pytest`, SQLite in-memory, `dependency_overrides`, target coverage ≥ 80% | Antigravity AI (Gemini) | "Buat `tests/conftest.py` (SQLite in-memory `StaticPool`, `check_same_thread=False`, `dependency_overrides[get_db]`) serta test suite lengkap dengan pola Arrange-Act-Assert." | `tests/conftest.py`, `tests/test_nim_generator.py`, `tests/test_pmb_api.py` | Menambahkan verifikasi tambahan pada `test_approve_idempotent`: setelah pendaftar 1 di-approve 2x, pendaftar 2 harus tetap mendapat nomor urut `0002` (bukan `0003`). | Lulus semua test dengan coverage > 90% (`pytest --cov=app --cov-report=term-missing --cov-fail-under=80`). |

---

## Refleksi OPAR (Observe – Plan – Act – Reflect) — Minggu 4

- **Observe:**
  1. Pada implementasi generator NIM standar, pola *read-modify-write* tanpa kunci database berisiko menghasilkan NIM ganda ketika dua admin menyetujui pendaftar berbeda secara bersamaan (*race condition*).
  2. Penggunaan `threading.Lock` di Python terlihat aman saat uji lokal, tetapi gagal di produksi yang menjalankan banyak worker/proses.
  3. Spesifikasi format NIM di dokumen tugas ambigu (contoh memakai strip, docstring tidak memakai strip).
- **Plan:**
  1. Memindahkan penguncian ke database menggunakan tabel `nim_counter` + `SELECT ... FOR UPDATE` + `UNIQUE` constraint pada kolom `nim` + mekanisme retry pada `IntegrityError`.
  2. Menyatukan baca counter, increment, dan update status `CalonMahasiswa` dalam satu transaksi atomik (`flush()` di generator, `commit()` sekali di `PMBService.approve()`).
  3. Memutuskan format 11 digit angka murni (`YYYYPPPNNNN`) dan mendokumentasikannya di `docs/ADR-002-pmb-approve-nim-testing.md`.
- **Act:**
  - Menambahkan model `NimCounter`, migrasi Alembic `0002_add_nim_counter.py`, fungsi `format_nim()` dan `generate_nim()`, endpoint `approve`, `reject`, `status`, dan `stats`, serta suite pengujian `pytest`.
- **Reflect:**
  - Test otomatis berbasis SQLite in-memory sangat efektif memverifikasi logika bisnis, validasi, idempotensi, dan urutan NIM, tetapi **SQLite mengabaikan klausa `FOR UPDATE`**, sehingga perilaku *row-level locking* MySQL belum teruji di bawah beban konkurensi nyata dan tetap memerlukan pengujian manual/load test pada instance MySQL di lingkungan staging/produksi.

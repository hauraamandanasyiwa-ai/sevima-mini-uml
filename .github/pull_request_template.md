## Fitur / Isu yang Diselesaikan
- [x] Implementasi alur state machine `PUT /api/pmb/approve/{id}` dan `PUT /api/pmb/reject/{id}` pada `PMBService` (penanganan `200`, `400`, `404`, `409`).
- [x] Implementasi generator NIM (`YYYYPPPNNNN`, 11 digit tanpa strip) yang **idempotent** dan **aman terhadap race condition** memakai tabel `nim_counter` + `SELECT ... FOR UPDATE` + `UNIQUE` constraint + retry.
- [x] Penambahan migrasi Alembic `0002_add_nim_counter` lengkap dengan `upgrade()` dan `downgrade()`.
- [x] Implementasi `GET /api/pmb/status/{id}` (output terbatas tanpa membocorkan data pribadi) dan `GET /api/pmb/stats` (`COUNT`, `GROUP BY`, `OUTER JOIN`).
- [x] Penulisan unit & integration test dengan `pytest` + `pytest-cov` (coverage ≥ 80%).
- [x] Dokumentasi Swagger UI (`/docs`), `docs/ADR-002-pmb-approve-nim-testing.md`, dan `docs/AI_USAGE_LOG.md`.

## Apa yang Dibantu AI
- Pembuatan kerangka awal model `NimCounter`, migrasi Alembic `0002_add_nim_counter`, method `PMBService` (`approve`, `reject`, `get_status`, `get_stats`), router FastAPI, dan test suite `pytest`.
- Seluruh kode ditinjau baris per baris, direvisi (termasuk memindahkan mekanisme locking dari memori Python ke row lock database dan memastikan `flush()` tidak melakukan `commit()` prematur), lalu diverifikasi dengan `alembic` dan `pytest`.

## 3 Prompt Terbaik
1. **NIM Generator Race-Condition Safe:**
   > "Implementasikan fungsi `generate_nim(db, tahun, kode_prodi)` untuk FastAPI + SQLAlchemy 2.0 multi-worker. Gunakan tabel `nim_counter` (PK `tahun`, `kode_prodi`) dengan `SELECT ... FOR UPDATE`, inisialisasi `last_number=0` eksplisit, batas maks 9999, hanya panggil `db.flush()` (bukan `commit()`), dan bungkus di `PMBService.approve()` dengan retry pada `IntegrityError`."
2. **State Machine & Idempotensi Approve/Reject:**
   > "Implementasikan `PMBService.approve()` dan `reject()` dalam satu transaksi atomik. `pending -> approved` (catat `approved_at` UTC + generate NIM), `approved -> approve` idempotent kembalikan `200` dengan NIM lama tanpa menaikkan counter, `rejected -> approve` dan `approved -> reject` kembalikan `409 Conflict`, ID tidak ditemukan `404`, kode prodi invalid `400`."
3. **Statistik SQL & Pytest Fixture:**
   > "Buatkan query statistik PMB memakai `func.count`, `GROUP BY`, dan `outerjoin` agar prodi/jalur masuk dengan 0 pendaftar tetap tampil, serta fixture `pytest` dengan SQLite in-memory (`StaticPool`, `check_same_thread=False`) dan `app.dependency_overrides[get_db]`."

## Risiko dan Limitasi
- **Uji Konkurensi Locking Belum Dijalankan di MySQL Produksi:** Test otomatis menggunakan SQLite in-memory yang mengabaikan klausa `FOR UPDATE` dan memakai *database-level lock*. Perilaku *row-level lock* di bawah beban bersamaan (*concurrent load*) perlu diuji langsung pada MySQL (InnoDB) atau PostgreSQL sebelum rilis produksi.
- **Autentikasi Admin Belum Tersedia:** Endpoint `approve`, `reject`, dan `stats` belum dilindungi autentikasi/otorisasi JWT/RBAC karena berada di luar cakupan Materi 2 (akan ditambahkan pada tahap pengamanan API).
- **Kapasitas Nomor Urut 4 Digit:** Setiap kombinasi `(tahun, kode_prodi)` dibatasi maksimal `9999` mahasiswa per tahun sesuai format NIM 11 digit (`YYYYPPPNNNN`).

## Cara Uji
```powershell
# 1. Aktifkan virtual environment dan install dependensi
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Uji migrasi Alembic (upgrade & rollback)
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# 3. Jalankan seluruh tes dan cek coverage minimal 80%
pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# 4. Jalankan server dan buka Swagger UI di http://127.0.0.1:8000/docs
uvicorn app.main:app --reload
```

## Screenshot / Log Pengujian
*(Tempelkan output `pytest --cov=app --cov-report=term-missing --cov-fail-under=80` dan tangkapan layar Swagger UI `/docs` saat membuat Pull Request).*

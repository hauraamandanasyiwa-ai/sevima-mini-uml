# ADR-001: Keputusan Teknis Implementasi Modul PMB (Minggu 3)

- **Status:** Accepted
- **Tanggal:** 2026-11-20
- **Konteks:** Implementasi Materi 2 (Minggu 3) — menerjemahkan desain UML modul Penerimaan Mahasiswa Baru (PMB) menjadi skema database, migrasi, dan REST API.

---

## 1. Framework Backend: FastAPI + Pydantic v2
- **Keputusan:** Menggunakan FastAPI dengan Pydantic v2 (`pydantic[email]`).
- **Alasan:**
  - Otomatis menghasilkan dokumentasi interaktif OpenAPI / Swagger UI (`/docs`).
  - Integrasi validasi input yang ketat menggunakan type hints Python.
  - Mendukung Dependency Injection bawaan (`Depends(get_db)`) sehingga router tetap tipis dan mudah diuji pada Minggu 4.

## 2. Database & ORM: SQLite + SQLAlchemy 2.0 + Alembic
- **Keputusan:** Menggunakan SQLite pada tahap pengembangan, ORM SQLAlchemy 2.0 (`DeclarativeBase`, `Mapped`, `mapped_column`), dan Alembic untuk migrasi.
- **Alasan:**
  - SQLite cukup satu file (`pmb.db`) tanpa setup server tambahan, serta mudah dipindahkan ke MySQL cukup dengan mengubah `DATABASE_URL` di `app/database.py`.
  - Karena SQLite mematikan Foreign Key secara default, koneksi SQLAlchemy dipasangi event listener `PRAGMA foreign_keys=ON`.
  - Alembic menyimpan riwayat perubahan skema lengkap dengan `upgrade()` dan `downgrade()` yang teruji.

## 3. Pemisahan Tabel Referensi `jalur_masuk`
- **Keputusan:** Memisahkan `jalur_masuk` menjadi tabel tersendiri dengan Foreign Key `jalur_masuk_id` di tabel `calon_mahasiswa`.
- **Alasan:** Memenuhi deliverable tiga tabel (`program_studi`, `jalur_masuk`, `calon_mahasiswa`) dan menjaga normalisasi data (tidak menaruh string bebas SNBP/SNBT/Mandiri langsung di `calon_mahasiswa`).

## 4. Penegakan Constraint Dua Lapis
- **Keputusan:** Memasang aturan validasi di aplikasi (Pydantic) sekaligus di database (SQLAlchemy/Alembic).
- **Rincian:**
  - `UNIQUE` (`email`, `nim`, `program_studi.kode`, `jalur_masuk.nama`) → **Database** + pengecekan awal di **Service** (plus penanganan `IntegrityError` untuk *race condition*).
  - `NOT NULL` & `Foreign Key` → **Database** (`PRAGMA foreign_keys=ON`) + **Pydantic** + **Service**.
  - `Status Enum` (`pending`, `approved`, `rejected`) → **Database** (`CHECK` constraint via `create_constraint=True`) + **Python Enum**.
  - `Format Nomor HP Indonesia` (`08`, `628`, `+628`) → **Pydantic** (regex `^(\+62|62|0)8[1-9][0-9]{6,10}$`), sedangkan **Database** menyimpan sebagai `VARCHAR(15)` karena SQLite tidak memiliki fungsi regex bawaan.

## 5. Status Code Validasi Input (`400` vs `422`)
- **Keputusan:** Memasang custom exception handler `RequestValidationError` di `app/main.py` untuk mengembalikan **`400 Bad Request`** (menggantikan default FastAPI `422 Unprocessable Entity`).
- **Alasan:** Spesifikasi pengujian pada dokumen tugas mengharapkan kode `400` untuk format nomor HP yang tidak valid. Handler ini memastikan respons konsisten dengan kontrak tes tugas dan tidak membocorkan *stack trace* internal.

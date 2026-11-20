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

## Prompt Terbaik (Best Prompt)

```text
Buatkan model SQLAlchemy 2.0 (DeclarativeBase, Mapped, mapped_column) dan script migrasi Alembic (upgrade & downgrade) untuk modul PMB dengan ketentuan:
1. 3 tabel terpisah: program_studi (id, kode 3 char unique, nama, fakultas), jalur_masuk (id, nama unique), dan calon_mahasiswa (id, nama_lengkap, email unique+index, phone String(15), tanggal_lahir, alamat, program_studi_id FK, jalur_masuk_id FK, status Enum pending/approved/rejected dengan create_constraint=True, nim nullable unique, created_at server_default, approved_at nullable).
2. Aktifkan PRAGMA foreign_keys=ON pada koneksi SQLite.
3. Pisahkan kode backend FastAPI ke folder models, schemas, services, routers, dan database.py dengan Dependency Injection get_db().
4. Validasi format nomor HP Indonesia (^(\+62|62|0)8[1-9][0-9]{6,10}$) di Pydantic dan jelaskan lapisan penegakan tiap constraint.
5. Gunakan data dummy fiktif @example.com untuk pengujian.
```

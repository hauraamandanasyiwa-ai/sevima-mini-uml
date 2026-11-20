# Modul PMB (Penerimaan Mahasiswa Baru) — e-SVMA Mini (Minggu 3 & 4)

Implementasi lengkap **Materi 2 (Minggu 3 & 4)** Mata Kuliah Pemrograman Berorientasi Objek menggunakan **Python, SQLAlchemy 2.0, Alembic, Pydantic v2, FastAPI, dan Pytest**.

## Struktur Project

```text
.
├── .github/
│   └── pull_request_template.md          # Template PR sesuai silabus
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 0001_initial_pmb_tables.py    # 3 tabel utama PMB
│       └── 0002_add_nim_counter.py       # Tabel counter NIM (composite PK)
├── app/
│   ├── database.py                       # Engine SQLite/MySQL + PRAGMA foreign_keys=ON + get_db()
│   ├── main.py                           # Entrypoint FastAPI + custom validation handler (400)
│   ├── models/                           # Model SQLAlchemy 2.0 (4 tabel)
│   │   ├── calon_mahasiswa.py
│   │   ├── jalur_masuk.py
│   │   ├── nim_counter.py
│   │   └── program_studi.py
│   ├── schemas/                          # Validasi & response Pydantic v2
│   │   └── pmb.py
│   ├── services/                         # Aturan bisnis, state machine & generator NIM
│   │   ├── nim_generator.py
│   │   └── pmb_service.py
│   └── routers/                          # Endpoint HTTP (/api/pmb/*)
│       └── pmb.py
├── docs/
│   ├── ADR-001-pmb-implementation.md     # Keputusan teknis Minggu 3
│   ├── ADR-002-pmb-approve-nim-testing.md # Keputusan desain Minggu 4
│   └── AI_USAGE_LOG.md                   # Log penggunaan AI + OPAR
├── tests/
│   ├── conftest.py                       # Fixture SQLite in-memory & dependency_overrides
│   ├── test_nim_generator.py             # Unit & DB test generator NIM
│   └── test_pmb_api.py                   # Integration test seluruh endpoint PMB
├── alembic.ini
├── requirements.txt
└── seed.py
```

## Ringkasan Endpoint API

| Method | Endpoint | Deskripsi | Status Code |
|--------|----------|-----------|-------------|
| `POST` | `/api/pmb/register` | Mendaftarkan calon mahasiswa baru (`status = pending`) | `201`, `400`, `409` |
| `PUT` | `/api/pmb/approve/{id}` | Menyetujui pendaftar & generate NIM (idempotent) | `200`, `400`, `404`, `409` |
| `PUT` | `/api/pmb/reject/{id}` | Menolak pendaftar (`pending -> rejected`) | `200`, `404`, `409` |
| `GET` | `/api/pmb/status/{id}` | Cek status & NIM tanpa membocorkan data pribadi | `200`, `404` |
| `GET` | `/api/pmb/stats` | Statistik dashboard admin (`GROUP BY` + `OUTER JOIN`) | `200` |

## Keputusan Desain Penting (Minggu 4)
- **Format NIM (`YYYYPPPNNNN`):** 11 digit angka murni tanpa tanda strip (4 digit tahun + 3 digit kode prodi + 4 digit nomor urut *zero-padded* mulai `0001`–`9999`, direset per kombinasi tahun dan prodi). Detail di [ADR-002](docs/ADR-002-pmb-approve-nim-testing.md).
- **Idempotensi & State Machine:** `approved` dan `rejected` adalah status akhir. Memanggil `approve` dua kali pada pendaftar yang sama mengembalikan `200 OK` dengan NIM lama tanpa menaikkan counter.
- **Penanganan Race Condition:** Menggunakan tabel `nim_counter` dengan `SELECT ... FOR UPDATE` (`with_for_update()`), `db.flush()` di generator dan satu `db.commit()` atomik di `PMBService.approve()`, ditambah `UNIQUE` constraint + retry pada `IntegrityError` (bukan `threading.Lock` Python).

## Cara Menjalankan

### 1. Buat Virtual Environment & Install Dependensi
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Jalankan & Uji Migrasi Alembic (Upgrade & Rollback)
```powershell
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

### 3. Isi Data Referensi Awal (`program_studi` & `jalur_masuk`)
```powershell
python seed.py
```

### 4. Jalankan Pengujian & Cek Coverage (Target ≥ 80%)
```powershell
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

### 5. Jalankan Server FastAPI & Buka Swagger UI
```powershell
uvicorn app.main:app --reload
```
Buka dokumentasi interaktif di browser:
- Swagger UI: **http://127.0.0.1:8000/docs**
- ReDoc: **http://127.0.0.1:8000/redoc**

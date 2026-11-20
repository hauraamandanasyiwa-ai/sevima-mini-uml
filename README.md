# Modul PMB (Penerimaan Mahasiswa Baru) — Minggu 3

Implementasi **Materi 2 (Minggu 3)** Mata Kuliah Pemrograman Berorientasi Objek: *Dari UML ke Kode* menggunakan **Python, SQLAlchemy 2.0, Alembic, Pydantic v2, dan FastAPI**.

## Struktur Project

```text
.
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_pmb_tables.py
├── app/
│   ├── database.py               # Engine SQLite + PRAGMA foreign_keys=ON + get_db()
│   ├── main.py                   # Entrypoint FastAPI + custom validation handler (400)
│   ├── models/                   # Model SQLAlchemy 2.0 (3 tabel)
│   ├── schemas/                  # Validasi Pydantic (RegisterRequest, PendaftarOut)
│   ├── services/                 # Aturan bisnis (PMBService)
│   └── routers/                  # Endpoint HTTP (/api/pmb/register)
├── docs/
│   ├── ADR-001-pmb-implementation.md
│   └── AI_USAGE_LOG.md
├── alembic.ini
├── requirements.txt
└── seed.py
```

## Cara Menjalankan

### 1. Buat Virtual Environment & Install Dependensi
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Jalankan & Uji Migrasi Alembic (Upgrade & Rollback)
```powershell
# Terapkan migrasi
alembic upgrade head

# Uji rollback migrasi (menghapus tabel secara berurutan tanpa error FK)
alembic downgrade -1

# Terapkan ulang migrasi agar database siap dipakai
alembic upgrade head
```

### 3. Isi Data Referensi Awal (`program_studi` & `jalur_masuk`)
```powershell
python seed.py
```

### 4. Jalankan Server FastAPI
```powershell
uvicorn app.main:app --reload
```
Buka Swagger UI di browser: **http://127.0.0.1:8000/docs**

## Contoh Pengujian Endpoint `POST /api/pmb/register`

Payload valid (mengembalikan **`201 Created`** dengan `status: "pending"`):
```json
{
  "nama_lengkap": "Siti Rahmawati",
  "email": "siti.rahmawati@example.com",
  "phone": "081234567890",
  "tanggal_lahir": "2007-05-14",
  "alamat": "Jl. Merdeka No. 10, Bandung",
  "program_studi_id": 1,
  "jalur_masuk_id": 1
}
```

Skenario negatif yang wajib menghasilkan error sesuai kontrak:
- Kirim email yang sama dua kali → **`409 Conflict`** (`"Email sudah terdaftar"`)
- Nomor HP tidak valid (mis. `"021123456"` atau `"08012345678"`) → **`400 Bad Request`**
- `program_studi_id` tidak ada (mis. `999`) → **`400 Bad Request`** (`"Program studi tidak ditemukan"`)

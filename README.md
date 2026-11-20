# SIMAK Mini — Modul KRS (Minggu 5 Bagian 1)

Implementasi **Modul Kartu Rencana Studi (KRS)** mata kuliah Pemrograman Berorientasi Objek menggunakan **FastAPI**, **SQLAlchemy 2.0**, dan **Pydantic v2**.

## Ringkasan Deliverable Minggu 5

1. **Skema Database KRS (20%)** — `app/models/krs.py` & `sql/schema_mysql.sql`
   - 4 tabel inti: `mata_kuliah`, `prerequisites` (self-referencing many-to-many `Table`), `krs`, `krs_detail` + tabel pembantu `skala_nilai` + referensi `mahasiswa` (NIM unik dari modul PMB).
   - Dilengkapi `CHECK CONSTRAINT` (`sks` 1..4, `hari` 1..6, `jam_mulai < jam_selesai`) dan `UNIQUE CONSTRAINT` (`uq_krs_nim_semester`, `uq_krs_detail_krs_mk`).
2. **KRS Manager Service (40%)** — `app/services/krs_manager.py`
   - Pintu tunggal lapisan service (bebas logika HTTP, Single Responsibility).
   - Dependency Injection untuk daftar validator (Open/Closed Principle).
   - `add_course()` & `remove_course()` dengan row lock `with_for_update()`, penjaga status (`DRAFT`/`REVISION`), satu transaksi commit sekali di akhir, dan penanganan `IntegrityError`.
   - `validate_krs()` mengumpulkan semua error dalam satu layar sebelum submit.
   - `submit_krs()` & `approve_krs()` disiapkan sebagai placeholder untuk Minggu 6 (State Machine).
3. **Rantai Validasi — Chain of Responsibility (25%)** — `app/validators/`
   - `ValidationResult` (`frozen=True`), `KRSContext`, `Validator(ABC)` (Template Method), `build_validation_chain()`.
   - 4 Validator berurutan: `DuplicateValidator` → `SKSValidator` (`MAX_SKS = 24`) → `ConflictValidator` (rumus irisan interval `<`) → `PrerequisiteValidator`.
4. **Query Prasyarat `NOT EXISTS` & Optimasi Indeks (`EXPLAIN`)** — `app/queries/prerequisite.py`, `sql/explain_benchmark.sql`, `docs/QUERY-PRASYARAT-EXPLAIN.md`.
5. **Dokumentasi Desain & AI Charter** — `docs/ADR-001-validation-chain.md`, `docs/AI-USAGE-LOG.md`.

## Cara Menjalankan

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Jalankan unit & integration tests:

```bash
pytest -v
```

> **Catatan MySQL:** Untuk menguji *row-level lock* (`SELECT ... FOR UPDATE`) dan *benchmark* `EXPLAIN`, jalankan dengan MySQL 8.0+ melalui environment variable `DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/simak_db` serta script `sql/schema_mysql.sql` dan `sql/explain_benchmark.sql`.

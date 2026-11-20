# SIMAK Mini — Modul KRS Lengkap (Minggu 5 & Minggu 6)

Implementasi lengkap **Modul Kartu Rencana Studi (KRS)** mata kuliah Pemrograman Berorientasi Objek menggunakan **FastAPI**, **SQLAlchemy 2.0**, **Pydantic v2**, dan **Hypothesis**.

## Ringkasan Deliverable (Bobot 100% + Bonus 10%)

1. **Database Schema (20%)** — `app/models/krs.py` & `sql/schema_mysql.sql`
   - 4 tabel inti (`mata_kuliah`, `prerequisites`, `krs`, `krs_detail`) + `skala_nilai` + `krs_approval_log` + `notifikasi` + referensi `mahasiswa`.
   - `CHECK CONSTRAINT`, `UNIQUE CONSTRAINT`, composite PK, serta kolom `version` untuk Optimistic Locking.
2. **KRS Manager Service (40%)** — `app/services/krs_manager.py`
   - `add_course()`, `remove_course()`, `validate_krs()`, `submit_krs()`, `approve_krs()`, dan `revise_krs()`.
   - State Machine terenkapsulasi di `KRS.check_transition()` & `KRS.transition()` (tabel transisi 4 state × 2 aktor).
   - Otorisasi 2 lapis: peran (`409 TransitionError`) + kepemilikan Dosen PA (`403 ForbiddenError`).
   - Pessimistic locking (`with_for_update()`) di semua method pengubah KRS + Optimistic locking (`version` + `krs.touch()`).
   - Transaksi ACID tunggal pada `approve_krs` & `revise_krs` (status + timestamp + log audit + notifikasi DB).
3. **Validation Rules — Chain of Responsibility (25%)** — `app/validators/` & `app/queries/prerequisite.py`
   - `DuplicateValidator` → `SKSValidator` (`MAX_SKS = 24`) → `ConflictValidator` (irisan interval `<`) → `PrerequisiteValidator` (`NOT EXISTS` + bobot `skala_nilai >= 2.00`).
4. **Unit, Integration, API & Property-Based Testing (10%)** — `tests/`
   - `test_state_machine.py`: 32 kombinasi exhaustive (4 sah + 28 ilegal via `itertools.product`).
   - `test_property_based.py`: **Hypothesis** (1.000 kombinasi acak SKS dengan 2 assert + 500 kombinasi jadwal bentrok dengan pemeriksa himpunan slot independen).
   - `test_krs_transactions.py`: example-based (Kalkulus 2, bentrok Senin 08:00), otorisasi 2 lapis, ACID rollback test, dan optimistic locking test.
   - `test_api.py`: `TestClient` memverifikasi kode `201`, `200`, `400`, `403`, `409` lewat single exception handler polimorfik.
5. **AI Usage Log, ADR, OPAR & PR Template (5%)** — `docs/ADR-001-validation-chain.md`, `docs/ADR-002-state-machine.md`, `docs/QUERY-PRASYARAT-EXPLAIN.md`, `docs/AI-USAGE-LOG.md`, `docs/OPAR-MINGGU-6.md`, `.github/pull_request_template.md`.
6. **Challenge Opsional (+10% Bonus)** — `app/services/krs_recommender.py` & `tests/test_recommender.py`
   - Rekomendasi KRS berbasis **CSP Backtracking** (prioritas MK wajib > pilihan, bebas bentrok, <= 24 SKS) dengan guardrail wajib lolos seluruh validator KRS (`POST /krs/{nim}/{semester}/recommend`).

## Cara Menjalankan

```powershell
python -m pip install -r requirements.txt
python -m pytest -v
python -m uvicorn app.main:app --reload --port 8002
```

Buka Swagger UI di **`http://127.0.0.1:8002/docs`**.

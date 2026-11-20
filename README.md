# SIMAK Mini — Modul Jadwal & Ruang (Minggu 7)

Kelanjutan proyek SEVIMA Mini (Modul KRS Minggu 5–6 + **Modul Jadwal & Ruang Minggu 7 Bagian 1**) menggunakan **FastAPI**, **SQLAlchemy 2.0**, **Pydantic v2**, dan **Hypothesis**.

## Ringkasan Deliverable Minggu 7

1. **Model Domain & Migration** — `app/models/schedule.py`, `sql/migration_minggu_7.sql`, `sql/schema_mysql.sql`
   - 4 model baru: `Ruangan`, `Dosen`, `Kelas`, `Jadwal` (+ kolom `kelas_id` pada `krs_detail`).
   - `CheckConstraint` (`hari 1..6`, `jam_mulai < jam_selesai`) & 2 indeks gabungan (`idx_jadwal_hari_ruangan`, `idx_jadwal_hari_dosen`).
2. **Detektor Bentrok 3 Dimensi (2 Versi)** — `app/services/conflict_detector.py`
   - Interval setengah terbuka `[jam_mulai, jam_selesai)` (kuliah bersambung `09:40` tidak bentrok).
   - Versi 1: `detect_schedule_conflicts_naive()` ($O(n^2)$ dengan `itertools.combinations` sebagai acuan).
   - Versi 2: `detect_schedule_conflicts()` ($O(n \log n + k)$ dengan Grouping `(hari, ruangan)` & `(hari, dosen)` + Sort-and-Sweep).
3. **Scheduling Service & Capacity Check (35%)** — `app/services/scheduling_service.py`
   - `create_jadwal()`, `update_jadwal()`, `delete_jadwal()`, `get_all_conflicts()`, `check_capacity()` (`max(kuota, terdaftar) <= kapasitas`).
   - Pessimistic locking berurutan (`Ruangan` → `Dosen`) anti-deadlock + `session.add()` paling akhir anti-autoflush.
4. **API Polimorfik & Seed Data** — `app/routers/schedule.py`, `app/schemas/schedule.py`, `app/exceptions.py`, `app/main.py`
   - Endpoint: `POST /schedules`, `PUT /schedules/{id}`, `DELETE /schedules/{id}`, `GET /schedules/conflicts`, `GET /schedules`.
   - Seed data awal sengaja menyertakan 1 `room_conflict` dan 1 `lecturer_conflict` untuk langsung diuji di `GET /schedules/conflicts`.
5. **Pengujian & Dokumentasi**
   - `tests/test_conflict_detector.py`, `tests/test_schedule_properties.py` (2 properti Hypothesis: bebas bentrok & differential testing), `tests/test_scheduling_service.py`, `tests/test_schedule_api.py`.
   - `docs/ADR-003-conflict-detection-algorithm.md`, `docs/AI-USAGE-LOG-MINGGU-7.md`, `docs/OPAR-MINGGU-7.md`, `.github/pull_request_template.md`.

## Cara Menjalankan

```powershell
python -m pytest -v
python -m uvicorn app.main:app --reload --port 8003
```

Buka Swagger UI di **`http://127.0.0.1:8003/docs`**.

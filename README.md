# SIMAK Mini — Modul Jadwal & Ruang Lengkap (Minggu 7 & 8)

Implementasi terintegrasi **SEVIMA Mini** untuk mata kuliah Pemrograman Berorientasi Objek menggunakan **FastAPI**, **SQLAlchemy 2.0**, dan **Pydantic v2** (melanjutkan Modul KRS Minggu 5–6 dan Modul Jadwal & Ruang Minggu 7–8).

## Ringkasan Deliverable Materi 4 (Minggu 7 & 8)

1. **Scheduling Service & Deteksi Bentrok 3 Dimensi (35%)** — `app/models/schedule.py`, `app/services/conflict_detector.py`, `app/services/scheduling_service.py`
   - Model `Ruangan`, `Dosen`, `Kelas`, `Jadwal` (plus kolom `sequence` untuk iCalendar).
   - Detektor bentrok interval setengah terbuka `[jam_mulai, jam_selesai)` dengan algoritma Naif `O(n^2)` (oracle) dan teroptimasi Grouping + Sort-and-Sweep `O(n log n + k)`.
   - Pessimistic lock urutan tetap (`Ruangan -> Dosen`), capacity check `max(kuota, terdaftar) <= kapasitas`, dan HTTP `409 Conflict` terstruktur.

2. **Observer Pattern + Transactional Outbox + 3 Kanal Log (25%)** — `app/observers/`, `app/models/outbox.py`, `app/runtime.py`
   - `EventType` (`schedule_changed`, `schedule_deleted`), `ScheduleEvent` (`frozen=True`), `ScheduleObserver(Protocol)`, `ScheduleSubject` (`attach` idempoten, `detach`, `notify` dengan salinan daftar & `try/except` per observer).
   - 3 Subscriber konkret: `StudentObserver`, `LecturerObserver` (termasuk dosen lama jika dosen diganti), dan `AdminObserver`.
   - 3 Kanal simulasi log (`LogChannel`: `email`, `sms`, `push`) dengan **kunci idempotensi** (`event_id:recipient:channel`) untuk *at-least-once delivery + deduplication*.
   - **Transactional Outbox** (`notification_outbox`): ditulis dalam transaksi yang sama dengan perubahan jadwal & invalidasi KRS; dikirim **setelah `COMMIT`** oleh `OutboxDispatcher` (`with_for_update(skip_locked=True)`, retry maks 5 kali).
   - Dirangkai **sekali** saat aplikasi start (`init_notification_runtime()` di `lifespan`).

3. **Conflict Resolver UI & AI Rescheduler dengan 4-Stage Validator (20%)** — `app/services/ai_rescheduler.py`, `app/routers/conflict_resolver.py`, `app/static/conflict_resolver.html`
   - Daftar slot tersedia dihitung oleh kode sendiri (`compute_available_slots`), bukan dikarang AI.
   - Interface `LLMClient(Protocol)` (mendukung Gemini Flash via `GEMINI_API_KEY`, fallback lokal offline untuk demo, serta `FakeLLMClient` untuk unit test deterministik).
   - **4 Saringan Output AI** (`validate_ai_suggestions`): (1) parsing aman `[`..`]`, (2) skema Pydantic per item, (3) ruangan ada di DB & kapasitas mencukupi, (4) `detect_schedule_conflicts` dengan calon `id=-1`.
   - Dashboard HTML di `/conflict-resolver`, seluruh endpoint `/admin/*` diproteksi peran `admin_akademik` (`X-Role: admin_akademik`), dan tombol **Terapkan** memakai prinsip satu pintu (`SchedulingService.update_jadwal()`).

4. **Integrasi KRS (15%)** — `app/models/krs.py`, `app/services/krs_invalidator.py`
   - Menambahkan aktor `KRSAktor.SYSTEM = "system"` pada `KRS_TRANSITIONS` (`SUBMITTED -> REVISION`, `APPROVED -> REVISION`).
   - Perubahan status wajib lewat `krs.transition(KRSStatus.REVISION, KRSAktor.SYSTEM)` di dalam transaksi `SchedulingService` yang sama (tanpa `commit()` terpisah).
   - Tes parameterisasi state machine diperbarui menjadi **48 kombinasi (6 sah, 42 ilegal)**.

5. **Ekspor Kalender iCalendar (`.ics`)** — `app/services/ical_exporter.py`, `GET /schedules/export.ics`
   - Format RFC 5545 dengan pemisah baris CRLF (`\r\n`), `UID` stabil (`jadwal-{id}@sevima-mini.ac.id`), `SEQUENCE` naik setiap update, `DTSTART/DTEND` ber-TZID `Asia/Jakarta`, dan `RRULE:FREQ=WEEKLY;UNTIL=...Z` (UTC).

6. **Testing & Dokumentasi (5%)**
   - **UML Sequence Diagram Observer Pattern (Wajib):** `docs/SEQUENCE-OBSERVER-PATTERN.md` (`COMMIT` sebelum `NOTIFY`).
   - **ADR-004:** `docs/ADR-004-observer-outbox-ai-rescheduler.md`.
   - **OPAR & AI Usage Log Minggu 8:** `docs/OPAR-MINGGU-8.md`, `docs/AI-USAGE-LOG-MINGGU-8.md`.
   - **Migrasi SQL Minggu 8:** `sql/migration_minggu_8.sql`.
   - **Automated Tests:** `tests/test_state_machine.py` (48 kombinasi) & `tests/test_minggu_8.py` (SpyObserver, BrokenObserver, Integration Test KRS Rina + Outbox + 3 Kanal, FakeLLM 4-Stage Filter, Idempotensi Retry, iCalendar `.ics`, Role Guard & Conflict Resolver API).

## Cara Menjalankan & Demo Singkat

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Skenario Demo Minggu 8 (3 Menit)
1. Buka dashboard **Conflict Resolver** di `http://127.0.0.1:8000/conflict-resolver` (atau Swagger UI di `http://127.0.0.1:8000/docs`).
2. Perhatikan di panel **Status KRS Mahasiswa**: KRS milik **Rina (`20240003`)** berstatus `approved` (mengambil kelas `IF202-A` dan `IF203-A`), dan di panel **Daftar Bentrok Jadwal** terdapat 2 bentrok awal (`room_conflict` & `lecturer_conflict`).
3. Klik **Minta Saran AI** pada jadwal yang bentrok (mis. `#3 IF203-A`), lalu klik **Terapkan** pada salah satu saran yang lolos 4 saringan.
4. Tunjukkan 3 hasil langsung di layar & terminal:
   - Daftar bentrok berkurang otomatis.
   - Panel **Log Notifikasi** & output terminal menampilkan log pengiriman 3 kanal (`[EMAIL]`, `[SMS]`, `[PUSH]`) untuk mahasiswa, dosen, dan admin.
   - Panel **Status KRS Mahasiswa** memperlihatkan KRS milik Rina (`20240003`) otomatis kembali ke status `revision` beserta catatannya.
5. Klik **Ekspor Kalender (.ics)** (`/schedules/export.ics`) untuk mengunduh file iCalendar dengan `UID` stabil dan `SEQUENCE` yang sudah bertambah.

### Menjalankan Seluruh Test Suite

```bash
python -m pytest -v
```

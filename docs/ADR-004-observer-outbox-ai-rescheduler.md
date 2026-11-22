# ADR-004: Observer Pattern, Transactional Outbox, Integrasi KRS, dan 4-Stage AI Rescheduler

**Status:** Diterima (Minggu 8)  
**Konteks:** Melanjutkan Modul Jadwal & Ruang (Minggu 7) pada proyek SIMAK Mini agar perubahan jadwal memberi tahu pihak terdampak secara aman, mengembalikan KRS terdampak ke `revision`, serta membantu admin menyelesaikan bentrok dengan saran AI yang terverifikasi.

---

## Keputusan 1: Kontrak `ScheduleObserver` & `NotificationChannel` Memakai `typing.Protocol`

- **Pilihan:** Menggunakan `typing.Protocol` (structural subtyping) daripada `abc.ABC`.
- **Alasan:** Kelas apa pun (termasuk test double seperti `SpyObserver` dan `BrokenObserver`) cukup mengimplementasikan method `update(event: ScheduleEvent) -> None` tanpa wajib mewarisi kelas dasar tertentu. `ScheduleEvent` dibuat `@dataclass(frozen=True)` agar immutable dan tidak dapat diubah diam-diam oleh satu observer terhadap observer lain.
- **Open/Closed Principle:** Menambah kanal nyata baru (mis. SMTP Email atau Firebase Push) cukup membuat kelas baru yang memenuhi `NotificationChannel.send(...)` tanpa menyentuh `SchedulingService` maupun kelas observer.

## Keputusan 2: Observer di Dalam Proses + Transactional Outbox (`notification_outbox`)

- **Perbedaan Observer vs Pub/Sub:** Pada Observer, `ScheduleSubject` menyimpan referensi langsung ke daftar observer dan memanggil `update()` secara sinkron dalam satu proses. Pada Pub/Sub, penerbit mengirim pesan ke broker/event bus (mis. Redis/RabbitMQ/Kafka) berdasarkan topik tanpa mengenal pelanggannya.
- **Keputusan untuk SIMAK Mini:** Menggunakan Observer di dalam satu proses (sesuai deliverable), dipadukan dengan tabel `notification_outbox` sebagai langkah pertama menuju Pub/Sub.
- **Relasi dengan tabel `notifikasi` (Minggu 6):** Tabel `notifikasi` dipertahankan sebagai kotak masuk (inbox) notifikasi KRS mahasiswa, sedangkan `notification_outbox` berperan khusus sebagai antrean pengiriman event jadwal (`pending` / `sent` / `failed`, `attempts`, `event_id` unik).

## Keputusan 3: Integrasi KRS Melalui Pintu Tunggal `krs.transition()` dengan Aktor `system`

- **Masalah:** Pada Minggu 6, `APPROVED` adalah terminal state.
- **Solusi:** Menambahkan aktor baru `KRSAktor.SYSTEM = "system"` secara eksplisit pada `KRS_TRANSITIONS` untuk dua transisi:
  - `(SUBMITTED, "system") -> REVISION`
  - `(APPROVED, "system") -> REVISION`
- **Konsekuensi:** Tidak ada bypass `krs.status = ...` di mana pun. Seluruh tes parameterisasi state machine diperbarui dari 32 kombinasi (4 sah, 28 ilegal) menjadi **48 kombinasi (6 sah, 42 ilegal)**. `KRSInvalidator` tidak melakukan `commit()` sendiri agar atomik bersama transaksi `SchedulingService`.

## Keputusan 4: Jangan Pernah Percaya Keluaran AI — 4-Stage Validator & Prinsip Satu Pintu

- **Daftar slot tersedia** dihitung terlebih dahulu oleh kode deterministik (`compute_available_slots`) memakai `detect_schedule_conflicts` dari Minggu 7. AI hanya memilih dan memberi alasan.
- **Setiap output LLM wajib melewati 4 saringan** (`validate_ai_suggestions`):
  1. Parsing JSON aman antara `[` pertama dan `]` terakhir (gagal -> `[]`, tidak crash).
  2. Validasi skema Pydantic per item (`hari` 1..6, `jam_mulai < jam_selesai`).
  3. Validasi ruangan eksis di DB dan `kapasitas >= max(kuota, terdaftar)`.
  4. Validasi bentrok menggunakan `detect_schedule_conflicts` dengan calon `JadwalSlot(id=-1, ...)`; jika `-1` muncul di konflik mana pun, saran dibuang.
- **Tombol Terapkan** pada dashboard Conflict Resolver (`POST /admin/conflicts/{id}/apply`) **tidak memiliki jalur khusus** — ia menyusun `ScheduleData` lalu memanggil `SchedulingService.update_jadwal()` yang sama. Jika slot terlanjur terisi admin lain, sistem menolak dengan HTTP 409.

## Keputusan 5: Ekspor Kalender iCalendar (`.ics`)

- Menambahkan kolom `sequence` pada tabel `jadwal` yang naik `+1` setiap kali `update_jadwal()` berhasil.
- Menggunakan `UID:jadwal-{id}@sevima-mini.ac.id`, pemisah baris CRLF (`\r\n`), `DTSTART;TZID=Asia/Jakarta`, dan `RRULE:FREQ=WEEKLY;UNTIL=...Z` (UTC) agar impor ulang ke Google Calendar/Apple Calendar memperbarui event lama tanpa membuat duplikat.

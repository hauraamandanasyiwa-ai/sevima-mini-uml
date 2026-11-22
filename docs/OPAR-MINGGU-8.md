# OPAR — Minggu 8 (Modul Jadwal & Ruang Bagian 2)

## O — Objective (Tujuan)
Menghidupkan modul Jadwal & Ruang agar setiap perubahan/penghapusan jadwal:
1. Memberi tahu mahasiswa, dosen (termasuk dosen lama jika diganti), dan admin melalui Observer Pattern + 3 kanal simulasi log (Email, SMS, Push) secara aman setelah `commit` (Transactional Outbox + kunci idempotensi).
2. Mengembalikan KRS berstatus `submitted` atau `approved` yang terdampak ke status `revision` melalui pintu tunggal `krs.transition(..., "system")`.
3. Menyediakan AI Rescheduler dengan 4-stage validator dan dashboard Conflict Resolver (khusus `admin_akademik`).
4. Menyediakan ekspor jadwal format iCalendar (`.ics`) dan UML Sequence Diagram Observer Pattern.

## P — Plan (Rencana)
1. Perbarui `app/models/krs.py` (aktor `system` + 2 transisi baru), `app/models/schedule.py` (kolom `sequence`), dan tambahkan `app/models/outbox.py` (`OutboxEvent`).
2. Bangun paket `app/observers/` (`events.py`, `channels.py`, `subject.py`, `outbox_dispatcher.py`) + `app/runtime.py` yang merangkai observer sekali saat aplikasi start.
3. Buat `app/services/krs_invalidator.py`, perbarui `app/services/scheduling_service.py` (transaksi atomik jadwal + invalidasi KRS + outbox, lalu dispatch setelah commit).
4. Bangun `app/services/ai_rescheduler.py` (slot tersedia dihitung kode + `LLMClient` protocol + 4-stage validator) dan `app/services/ical_exporter.py`.
5. Tambahkan router `app/routers/conflict_resolver.py` (role guard `admin_akademik` + prinsip satu pintu `apply -> update_jadwal`), endpoint `/schedules/export.ics`, dan UI `app/static/conflict_resolver.html`.
6. Perbarui `tests/test_state_machine.py` (48 kombinasi) dan tambahkan `tests/test_minggu_8.py`, plus dokumen Sequence Diagram Mermaid, ADR-004, dan migrasi SQL.

## A — Action (Tindakan & Verifikasi)
- Menjalankan baseline 73 tes Minggu 7 -> semua lulus.
- Mengimplementasikan seluruh komponen Minggu 8 dan menambahkan auto-upgrade kolom `jadwal.sequence` untuk kompatibilitas DB SQLite Minggu 7.
- Menjalankan `python -m pytest -v` untuk seluruh test suite (Minggu 5–8).

## R — Reflection (Refleksi)
- **Pelajaran penting 1:** Mengirim notifikasi langsung sebelum `commit` adalah bug klasik yang berbahaya; pola Transactional Outbox + `OutboxDispatcher` + kunci idempotensi menyelesaikan masalah atomisitas sekaligus retry tanpa duplikat.
- **Pelajaran penting 2:** Keluaran AI (LLM) bersifat probabilistik dan bisa berhalusinasi (ruangan fiktif, kapasitas kecil, bentrok, atau JSON rusak), sehingga 4-stage validator deterministik dan prinsip satu pintu `update_jadwal()` wajib menjadi penjaga terakhir.

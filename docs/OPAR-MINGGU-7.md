# OPAR — Minggu 7: Concurrency Control pada Scheduling Service

## 1. Observe (Observasi)
Saat dua admin akademik bekerja bersamaan (simulasi dua terminal paralel):
- Admin 1 menambahkan Basis Data A di ruang `A101` Senin `08:00-09:40`.
- Pada detik yang sama, Admin 2 menambahkan Statistika A di ruang `A101` Senin `08:30-10:00`.
- Tanpa penguncian baris, keduanya menjalankan query pencarian bentrok sebelum salah satu `commit()`, keduanya mendapat hasil kosong, dan keduanya berhasil menyimpan jadwal yang bentrok.

Selain itu, jika objek `Jadwal` baru ditambahkan ke `session.add()` sebelum query pencarian bentrok, *autoflush* SQLAlchemy berpotensi membuat jadwal baru terdeteksi bentrok dengan dirinya sendiri.

## 2. Plan (Rencana)
1. Terapkan **pessimistic locking** (`with_for_update()`) pada baris `Ruangan` dan baris `Dosen` sebelum menjalankan query pencarian bentrok di `_simpan()`.
2. Tetapkan **urutan penguncian yang konsisten**: selalu kunci `Ruangan` dulu, lalu `Dosen`, agar dua transaksi paralel tidak mengalami **deadlock**.
3. Lakukan `session.add(jadwal)` **paling akhir** setelah seluruh cek bentrok dan kapasitas lulus, lalu `commit()` sekali.
4. Pada `update_jadwal`, kecualikan `Jadwal.id != jadwal.id` agar menggeser jam kuliah 15 menit tidak bentrok dengan dirinya sendiri.

## 3. Act (Implementasi & Pengujian)
- Mengimplementasikan `_kunci_ruangan_dan_dosen()` dengan urutan tetap (`Ruangan` → `Dosen`), `_cari_bentrok_db(exclude_id=...)`, `check_capacity()`, dan `_simpan()` di `app/services/scheduling_service.py`.
- Menambahkan pengujian unit, integrasi, API, dan property-based di `tests/test_conflict_detector.py`, `tests/test_schedule_properties.py`, `tests/test_scheduling_service.py`, dan `tests/test_schedule_api.py`.

## 4. Reflect (Refleksi & Limitasi)
- **Limitasi SQLite:** Sama seperti modul KRS, SQLite in-memory mengabaikan klausa `SELECT ... FOR UPDATE`, sehingga pembuktian penguncian antar dua admin paralel wajib diuji manual di **MySQL (InnoDB)**.
- **Alternatif Database:** PostgreSQL memiliki `EXCLUDE USING GIST` untuk menolak irisan rentang waktu di level database, namun karena target kita MySQL, kita menggunakan penguncian pesimis di lapisan service.
- **Keputusan Algoritma:** Penundaan `intervaltree` dan pemilihan Grouping + Sort-and-Sweep didokumentasikan secara transparan di `docs/ADR-003-conflict-detection-algorithm.md`.

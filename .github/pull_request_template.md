## Ringkasan Perubahan (Minggu 7 — Modul Jadwal & Ruang Bagian 1)
- Model domain baru: `Ruangan`, `Dosen`, `Kelas`, `Jadwal` lengkap dengan `CHECK CONSTRAINT` (`hari 1..6`, `jam_mulai < jam_selesai`) dan 2 indeks gabungan (`idx_jadwal_hari_ruangan`, `idx_jadwal_hari_dosen`), serta `sql/migration_minggu_7.sql`.
- Detektor bentrok 3 dimensi (`room_conflict` & `lecturer_conflict`) dengan aturan interval setengah terbuka (`<`): versi naif (`itertools.combinations`) sebagai acuan + versi teroptimasi (Grouping + Sort-and-Sweep).
- `SchedulingService`: `create_jadwal`, `update_jadwal` (mengecualikan diri sendiri), `delete_jadwal`, `check_capacity` (`max(kuota, terdaftar) <= kapasitas`), `get_all_conflicts`, dengan pessimistic lock berurutan (`Ruangan` → `Dosen`).
- Lapisan API polimorfik (`ScheduleError.body()` ditimpa oleh `ScheduleConflictError`) dan 4 endpoint utama (`POST /schedules`, `PUT /schedules/{id}`, `DELETE /schedules/{id}`, `GET /schedules/conflicts`) + seed data dengan bentrok disengaja.
- Pengujian lengkap: example-based 5+1 kasus kunci, API `TestClient` (`409` & `422`), dan 2 properti Hypothesis (bebas bentrok dengan verifikasi `Counter` independen + differential testing sweep vs naif).

## Risiko & Limitasi (Transparansi)
1. **Filter Semester Aktif:** Pencarian bentrok di `_cari_bentrok_db` dan `get_all_conflicts` saat ini belum memfilter berdasarkan kolom `kelas.semester` aktif (diasumsikan seluruh jadwal di tabel berada pada semester berjalan); filter semester akan diperketat bersama integrasi KRS penuh di Minggu 8.
2. **Penguncian Pesimis pada SQLite:** Test otomatis berjalan di SQLite yang mengabaikan `SELECT ... FOR UPDATE`; skenario 2 admin paralel perlu diverifikasi manual di MySQL (InnoDB).
3. **Notifikasi Perubahan Jadwal:** `delete_jadwal` dan `update_jadwal` belum mengirim notifikasi ke mahasiswa/dosen; Observer Pattern akan ditambahkan di Minggu 8.

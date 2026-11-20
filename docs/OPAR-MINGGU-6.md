# OPAR — Minggu 6: Concurrency Control & Transaction Management pada Modul KRS

## 1. Observe (Observasi Masalah)
Saat menguji skenario multi-tab / multi-aktor secara bersamaan:
1. Mahasiswa membuka dua tab saat KRS berstatus `revision`: Tab 1 menekan `add_course` (lolos cek status), sementara Tab 2 menekan `submit_krs` dan Dosen PA segera menekan `approve_krs`. Tanpa penguncian yang konsisten di semua method pengubah KRS, mata kuliah yang belum divalidasi bisa masuk ke KRS yang sudah `approved`.
2. Dosen PA membuka halaman KRS versi 2 di layar, sementara mahasiswa sempat mengubah KRS menjadi versi 3 sebelum submit ulang. Jika dosen menekan `approve` tanpa memeriksa versi, dosen menyetujui isi KRS yang berbeda dari yang ia lihat (*stale screen*).
3. Pada `approve_krs`, jika penyimpanan log audit atau notifikasi gagal setelah status berubah menjadi `approved`, KRS akan tercatat disetujui tanpa jejak audit (melanggar *Atomicity*).

## 2. Plan (Rencana Perbaikan)
1. **Pessimistic Locking seragam:** Seluruh method yang mengubah KRS (`add_course`, `remove_course`, `submit_krs`, `approve_krs`, `revise_krs`) wajib mengunci baris `krs` yang sama melalui `_krs_terkunci()` (`SELECT ... FOR UPDATE`) terlebih dahulu, baru memeriksa status setelah kunci didapat.
2. **Optimistic Locking (`version`):** Tambahkan kolom `version` (`version_id_col` di SQLAlchemy) pada tabel `krs`, panggil `krs.touch()` setiap kali `krs_detail` ditambah/dihapus agar versi ikut naik, dan verifikasi `expected_version` pada `approve_krs` / `revise_krs` (tolak dengan `409 KRSLockedError` bila berbeda).
3. **Transaksi ACID Tunggal:** Bungkus perubahan status, `approved_at`, `KRSApprovalLog`, dan `Notifikasi` (baris DB, bukan pengiriman email di tengah transaksi) dalam satu unit transaksi dengan `commit()` sekali di akhir dan `rollback()` pada setiap exception.

## 3. Act (Implementasi & Pengujian)
- Menambahkan `version`, `updated_at`, `submitted_at`, `approved_at`, `revision_note`, `KRSApprovalLog`, dan `Notifikasi` di `app/models/krs.py` dan `sql/schema_mysql.sql`.
- Menerapkan `_krs_terkunci()`, `krs.touch()`, `_ensure_version_matches()`, dan blok `try ... commit / except ... rollback` di `app/services/krs_manager.py`.
- Menambahkan integration tests di `tests/test_krs_transactions.py`:
  - `test_optimistic_locking_rejects_stale_version` (membuktikan `409 KRSLockedError` saat versi lama dikirim).
  - `test_approve_transaction_atomicity_rolls_back_on_failure` (simulasi error saat insert `Notifikasi` → status tetap `submitted`, `approved_at` tetap `None`, dan `KRSApprovalLog` ter-rollback utuh).

## 4. Reflect (Refleksi & Limitasi)
- **Limitasi SQLite:** Pengujian otomatis di `pytest` menggunakan SQLite in-memory yang **mengabaikan klausa `SELECT ... FOR UPDATE`**. Oleh karena itu, pembuktian penguncian pesimis antar transaksi paralel tetap wajib diuji secara manual di **MySQL (InnoDB)** menggunakan `DATABASE_URL=mysql+pymysql://...`.
- **Limitasi Otorisasi:** Parameter `dosen_pa_id` dan `actor_nim` saat ini masih dikirim melalui request body karena modul autentikasi/JWT belum dibangun. Ketika modul login tersedia, nilai tersebut harus diambil dari token sesi agar tidak dapat dipalsukan klien.
- **Notifikasi:** Notifikasi saat ini baru disimpan sebagai baris di tabel `notifikasi` dalam transaksi; pengiriman keluar (email/push) pasca-commit akan dirapikan menggunakan *Observer Pattern* pada Minggu 7.

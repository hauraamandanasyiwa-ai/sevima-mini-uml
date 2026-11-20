## Ringkasan Perubahan
- Implementasi State Machine KRS (`draft`, `submitted`, `approved`, `revision`) dengan tabel transisi eksplisit & enkapsulasi `KRS.check_transition()` / `KRS.transition()`.
- Otorisasi 2 lapis: peran (tabel transisi -> `409`) dan kepemilikan Dosen PA (`dosen_pa_id` -> `403`).
- Transaction Management ACID pada `submit_krs`, `approve_krs`, dan `revise_krs` (status + timestamp + `krs_approval_log` + `notifikasi` DB dalam 1 transaksi) + Optimistic Locking (`version`).
- Single exception handler polimorfik di FastAPI (`KRSError.status_code`).
- Piramida testing lengkap: 32 kombinasi state machine, example-based, property-based (`hypothesis`, 1.000 contoh SKS & 500 contoh jadwal bentrok), ACID rollback test, dan API `TestClient`.
- Challenge opsional (+10%): `KRSRecommender` (CSP Backtracking + guardrail validator).

## Checklist Kriteria Sukses
- [x] Mahasiswa dapat menambah dan menghapus mata kuliah lewat API (`draft`/`revision`).
- [x] Validasi prasyarat berjalan otomatis (query `NOT EXISTS` + `skala_nilai`).
- [x] Pesan error jelas berbahasa Indonesia (menyebut nama MK / alasan & tindakan).
- [x] State transition tidak bisa di-skip (teruji 28 transisi ilegal + `draft -> approved` ditolak).
- [x] Tes lulus dengan berbagai edge case & 1.000 kombinasi acak Hypothesis.

## Risiko & Limitasi (Transparansi)
1. **Identitas Aktor (`dosen_pa_id` & `actor_nim`):** Saat ini masih dikirim lewat request body karena modul autentikasi/login belum ada. Pada sistem produksi, identitas wajib diambil dari sesi/JWT agar tidak bisa dipalsukan.
2. **Penguncian Pesimis pada SQLite:** Unit/integration test menggunakan SQLite yang mengabaikan `SELECT ... FOR UPDATE`. Penguncian baris antar request paralel perlu diverifikasi manual di MySQL (InnoDB).
3. **Pengiriman Notifikasi Eksternal:** Notifikasi baru disimpan sebagai baris di tabel `notifikasi` dalam transaksi; pengiriman email/push pasca-commit akan diimplementasikan lewat Observer Pattern pada Minggu 7.

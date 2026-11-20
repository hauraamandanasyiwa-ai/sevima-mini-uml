# ADR-002: Keputusan Desain Approve/Reject, NIM Generator, dan Testing (Minggu 4)

- **Status:** Accepted
- **Tanggal:** 2026-11-20
- **Konteks:** Implementasi lanjutan Materi 2 (Minggu 4) Modul PMB — alur persetujuan (`approve`/`reject`), generator NIM yang aman terhadap *idempotency* dan *race condition*, endpoint status & statistik, serta pengujian otomatis dengan `pytest`.

---

## 1. Format NIM: 11 Digit Angka Murni (`YYYYPPPNNNN`) Tanpa Tanda Strip
- **Masalah:** Spesifikasi tugas mengandung ambiguitas antara contoh yang menyertakan tanda strip (`2025001-0001`) dan deskripsi/docstring yang tidak menyertakan strip (`YYYY` + `PPP` + `NNNN`).
- **Keputusan:** Menyimpan dan mengembalikan NIM dalam format **11 digit angka murni tanpa strip** (`YYYYPPPNNNN`, contoh `20250010001`).
- **Alasan:**
  - Mudah disimpan, diindeks, diurutkan secara leksikografis, dan divalidasi dengan regex `^\d{4}\d{3}\d{4}$`.
  - Nomor urut 4 digit dengan *zero-padding* (`0001`–`9999`) dihitung ulang per kombinasi `(tahun, kode_prodi)`.
  - Jika suatu saat UI memerlukan tampilan dengan strip, pemformatan dapat dilakukan di lapisan presentasi tanpa mengubah data master.

## 2. Idempotensi Endpoint `PUT /api/pmb/approve/{id}`: Mengembalikan `200 OK`
- **Keputusan:** Memanggil `PUT /api/pmb/approve/{id}` pada pendaftar yang sudah berstatus `approved` mengembalikan **`200 OK`** beserta NIM dan `approved_at` yang sudah ada, tanpa memanggil `generate_nim()` dan tanpa menaikkan counter.
- **Alasan:**
  - Metode HTTP `PUT` secara semantik bersifat idempotent (pemanggilan berulang menghasilkan keadaan akhir yang sama).
  - Melindungi dari *double-click* admin atau *automatic retry* akibat jaringan lambat/timeout agar tidak menghasilkan NIM ganda atau nomor urut bolong.
  - Status akhir (`approved` dan `rejected`) dijaga secara ketat di `PMBService`: `rejected -> approve` dan `approved -> reject` sama-sama mengembalikan **`409 Conflict`**.

## 3. Penanganan Race Condition: Tabel `nim_counter` + `SELECT ... FOR UPDATE` + `UNIQUE` + Retry
- **Masalah:** Menggunakan `threading.Lock` di Python hanya mengunci thread dalam satu proses, sehingga gagal total ketika server produksi berjalan dengan banyak worker (mis. Gunicorn/Uvicorn multi-worker) atau multi-instance.
- **Keputusan:** Memindahkan mekanisme penguncian ke **database** melalui tiga lapis:
  1. **Tabel `nim_counter`** dengan composite primary key `(tahun, kode_prodi)` dan kolom `last_number`.
  2. **Row-level lock (`SELECT ... FOR UPDATE` / `with_for_update()`)** pada baris `calon_mahasiswa` dan `nim_counter`, dijalankan dalam **satu transaksi atomik** (`generate_nim` hanya memanggil `db.flush()`, sedangkan `db.commit()` dilakukan sekali di `PMBService.approve()`).
  3. **Unique constraint** pada `calon_mahasiswa.nim` dan PK `nim_counter` disertai mekanisme **rollback + retry** (maksimal 3 kali) pada `IntegrityError` untuk menutup celah pembuatan baris counter pertama secara bersamaan oleh dua worker.
- **Catatan SQLite vs MySQL:** SQLite mengabaikan klausa `FOR UPDATE` dan memakai *database-level write lock*. Kode SQLAlchemy 2.0 ini langsung mengaktifkan *row-level lock* saat diarahkan ke MySQL (InnoDB) atau PostgreSQL lewat `DATABASE_URL`.

## 4. Strategi Pengujian: SQLite In-Memory + Dependency Override
- **Keputusan:** Menggunakan SQLite in-memory (`sqlite:///:memory:`) dengan `StaticPool` dan `check_same_thread=False` di `tests/conftest.py`, lalu menyuntikkannya ke FastAPI melalui `app.dependency_overrides[get_db]`.
- **Alasan:** Cepat, terisolasi per tes (`create_all` sebelum tes, `drop_all` setelah tes), dan tidak merusak database pengembangan `pmb.db`.
- **Limitasi:** Pengujian SQLite in-memory tidak menguji perilaku *row-level locking* MySQL secara langsung di bawah beban konkurensi nyata (didokumentasikan di PR Template & AI Usage Log).

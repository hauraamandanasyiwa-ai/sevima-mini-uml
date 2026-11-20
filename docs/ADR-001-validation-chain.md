# ADR-001: Perilaku Rantai Validasi KRS, Urutan Validator, dan Aturan Jadwal Bersambung

- **Status:** Accepted
- **Tanggal:** Minggu 5 — Modul KRS (SIMAK Mini)
- **Komponen:** `app/validators/`, `app/services/krs_manager.py`

---

## 1. Konteks

Modul KRS memiliki empat aturan bisnis inti yang diimplementasikan dengan pola **Chain of Responsibility**:
1. Tidak boleh *double enrollment* (`DuplicateValidator`).
2. Total SKS maksimal 24 per semester (`SKSValidator`).
3. Jadwal tidak boleh bentrok (`ConflictValidator`).
4. Prasyarat mata kuliah harus lulus di semester sebelumnya dengan nilai minimal C (`PrerequisiteValidator`).

Ada tiga keputusan desain utama yang harus ditentukan dan didokumentasikan secara eksplisit:
1. **Perilaku rantai saat menemukan kegagalan**: apakah berhenti di kegagalan pertama (*fail-fast*) atau mengumpulkan semua kesalahan sekaligus (*collect-all*)?
2. **Urutan validator di dalam rantai**: dokumen tugas menyebut SKS, prasyarat, bentrok, duplikat — apakah urutan tersebut optimal?
3. **Jadwal bersambung**: apakah kelas yang selesai pukul `10:30` dan kelas berikutnya yang mulai pukul `10:30` dianggap bentrok?

---

## 2. Alternatif yang Dipertimbangkan

### A. Perilaku Rantai Validasi
- **Alternatif 1 (Fail-Fast di semua method):** Rantai selalu berhenti pada validator pertama yang gagal.
  - *Pro:* Cepat, menghindari query database mahal jika aturan in-memory sudah gagal.
  - *Kontra:* Kurang ramah saat mahasiswa memeriksa KRS utuh sebelum submit — jika ada 3 masalah, mahasiswa harus memperbaiki dan mengecek ulang 3 kali.
- **Alternatif 2 (Collect-All di semua method):** Semua validator selalu dijalankan.
  - *Pro:* Menampilkan semua masalah sekaligus.
  - *Kontra:* Boros saat `add_course` (tetap menjalankan query `NOT EXISTS` prasyarat padahal mata kuliah sudah duplikat) dan bertentangan dengan spesifikasi prompt langkah 1 yang meminta rantai berhenti saat gagal.
- **Alternatif 3 (Jalan Tengah / Hybrid — Dipilih):**
  - `add_course()` menjalankan rantai `Validator.validate()` secara **fail-fast** (berhenti pada kegagalan pertama).
  - `validate_krs()` memanggil `validator.check()` secara langsung untuk setiap mata kuliah lalu **mengumpulkan semua hasil gagal** dalam satu daftar.

### B. Urutan Validator
- **Urutan dokumen tugas:** `SKS -> Prerequisite -> Conflict -> Duplicate`.
  - *Kontra:* Jika mahasiswa tanpa sengaja menambah MK yang sudah ada di KRS saat SKS sudah 24, pesan yang muncul justru *"SKS melebihi batas"* alih-alih *"Mata kuliah sudah ada di KRS"*. Selain itu, `PrerequisiteValidator` melakukan query database lebih awal dibanding pemeriksaan in-memory.
- **Urutan terpilih:** `Duplicate -> SKS -> Conflict -> Prerequisite`.
  - *Alasan:* Tiga validator pertama murni in-memory (tanpa query DB tambahan) dan urutan pesannya paling intuitif. `PrerequisiteValidator` diletakkan paling akhir agar query `NOT EXISTS` hanya dijalankan jika 3 syarat dasar sudah lolos.

### C. Jadwal Bersambung
- **Operator `<=`:** `mulai1 <= selesai2 AND mulai2 <= selesai1` (menganggap `08:00-10:30` dan `10:30-13:00` bentrok).
- **Operator `<` (Dipilih):** `mulai1 < selesai2 AND mulai2 < selesai1` (menganggap jadwal bersambung tepat TIDAK bentrok).

---

## 3. Keputusan

1. Menerapkan **Jalan Tengah**: `add_course` memakai *fail-fast* melalui `Validator.validate()`, sedangkan `validate_krs` memakai *collect-all* dengan memanggil `Validator.check()` pada tiap validator.
2. Urutan default rantai validasi adalah:
   `DuplicateValidator -> SKSValidator -> ConflictValidator -> PrerequisiteValidator`.
3. Rumus bentrok jadwal menggunakan irisan interval ketat (`<`), sehingga jadwal bersambung diizinkan.

---

## 4. Konsekuensi

- **Positif:**
  - `add_course` tetap responsif dan meminimalkan beban query prasyarat di malam terakhir pengisian KRS.
  - Mahasiswa mendapatkan umpan balik menyeluruh satu layar sebelum mengajukan KRS lewat `validate_krs`.
  - Memenuhi *Open/Closed Principle*: penambahan aturan baru (misal `TunggakanSPPValidator`) cukup membuat subclass `Validator` baru dan menyuntikkannya lewat constructor `KRSManager` tanpa mengubah kode `KRSManager`.
- **Negatif / Trade-off:**
  - Jika suatu kampus mewajibkan jeda istirahat antar kelas (misal 10 menit), `is_schedule_conflict()` perlu diperluas dengan parameter buffer waktu.

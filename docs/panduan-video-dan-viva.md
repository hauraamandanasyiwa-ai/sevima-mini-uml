# Panduan Video Tutorial (YouTube) & Persiapan Viva — SEVIMA-Mini (Minggu 2)

Dokumen ini disusun sebagai panduan presentasi video tutorial (suara + kamera) dan tanya jawab lisan (**Viva**) agar seluruh relasi, panah, dan *design pattern* dapat dijelaskan sendiri secara percaya diri tanpa bantuan AI.

---

## A. Alur Video Tutorial (Durasi Ideal: 5–8 Menit)

1. **Pembukaan (30 detik):** Perkenalan singkat, sebutkan ini kelanjutan Minggu 1 (*SEVIMA-Mini*) dengan tema Minggu 2: **Refinement, Skenario, SOLID & Design Patterns**.
2. **Demo Prompt & Use Case Diagram (1–1.5 menit):**
   - Tunjukkan `prompts/ai-usage-log.md` (Prompt 7) dan `diagrams/usecase-diagram.mmd`.
   - Jelaskan pemisahan peran (*Dosen Pengampu* vs *Dosen PA*), *System Boundary*, dan perbedaan arah panah `<<include>>` vs `<<extend>>`.
3. **Demo Sequence Diagram PMB & Validasi KRS (2 menit):**
   - Tunjukkan `diagrams/sequence-pmb.mmd`: soroti `UserFactory`, pesan asinkron `-)` ke `NotificationService`, dan *alternate flow* jika berkas tidak lengkap atau email gagal.
   - Tunjukkan `diagrams/sequence-krs.mmd`: soroti `loop` cek prasyarat, *self-call* hitung SKS & jadwal bentrok, pengumpulan semua error di `ValidationResult`, dan 4 cabang `alt`.
4. **Demo Self-Critique AI & Refactor Class Diagram (2 menit):**
   - Tunjukkan perbandingan *Before vs After* (`diagrams/before-after/before-class-diagram-w1.png` vs `after-class-diagram-w2.png`).
   - Jelaskan penambahan `PMBService`, `KRSManager`, `Repository`, `UserFactory`, **Observer Pattern** (`EventBus` + `IEventSubscriber`), **DIP** (`INotificationChannel`), dan **ISP** (`IPengisiKRS`, `IPenyetujuKRS`, `IPenilai`).
5. **Penutup — ADR, GitHub Commit & Kesiapan Minggu 3 (1 menit):**
   - Tunjukkan `docs/ADR-architecture-decisions.pdf`, `docs/Final-UML-diagram.pdf`, dan riwayat commit bertahap di GitHub.

---

## B. Cheat-Sheet Tanya Jawab Lisan (Viva)

### 1. Kenapa arah panah `<<include>>` dan `<<extend>>` berbeda?
- **`<<include>>` (Base → Included):** Langkah wajib. Jika dihilangkan, use case dasar tidak lengkap. Contoh: *Isi KRS* → *Cek Prasyarat*, *Cek Batas SKS*, *Cek Jadwal Bentrok*.
- **`<<extend>>` (Extension → Base):** Langkah opsional/kondisional. Jika dihilangkan, use case dasar tetap utuh. Contoh: *Ajukan Revisi KRS* → *Approve KRS* (hanya terjadi jika Dosen PA menolak); *Bayar Denda* → *Bayar SPP* (hanya jika lewat jatuh tempo); *Terbitkan NIM & Akun* → *Verifikasi Berkas PMB* (hanya jika lulus seleksi).

### 2. Kenapa di Sequence Diagram notifikasi memakai panah asinkron (`-)`)?
- Agar `PMBService` atau `KRSManager` **tidak terblokir** menunggu server email (SMTP) selesai mengirim email. Jika email lambat atau gagal, transaksi utama (simpan KRS `PENDING_APPROVAL` atau verifikasi Admin) tetap sukses dan kegagalan email ditangani lewat retry/logging.

### 3. Kenapa `KRSValidator` mengumpulkan semua error di `ValidationResult`, bukan berhenti di error pertama?
- Demi pengalaman pengguna (UX) yang baik saat masa pengisian KRS padat. Jika mahasiswa kena 2 masalah sekaligus (misal SKS 26 **dan** ada jadwal bentrok), ia langsung tahu semua kesalahannya sekaligus dan tidak perlu bolak-balik submit.

### 4. Jelaskan penerapan 5 prinsip SOLID di Class Diagram kamu!
- **S (SRP):** Tidak ada *God Object* `SistemAkademik`. Setiap class punya 1 tanggung jawab dan < 10 method (`PMBService`, `KRSManager`, `KRSValidator`, `TranscriptService`, `NotificationService`).
- **O (OCP):** Validasi memakai `IValidationRule` (*Strategy*) dan event memakai `IEventSubscriber` (*Observer*). Tambah aturan `CekTunggakanRule` atau `AuditLogSubscriber` cukup buat class baru tanpa ubah kode lama.
- **L (LSP):** `getIPK()` / `updateIPK()` hanya ada di `Mahasiswa`, tidak di `User`, karena `CalonMahasiswa` belum punya IPK. Semua turunan `User` tetap bisa `login()`, `logout()`, dan `tampilkanDashboard()`.
- **I (ISP):** Interface peran dipecah menjadi `IPengisiKRS`, `IPenyetujuKRS`, dan `IPenilai`, sehingga `Mahasiswa` tidak dipaksa memiliki method `inputNilai()`.
- **D (DIP):** `NotificationService` bergantung pada abstraksi `INotificationChannel` (diinjeksi lewat konstruktor), bukan langsung `EmailSender`. Memudahkan ganti ke WhatsApp dan membuat *mock* saat unit test di Minggu 5.

### 5. Jelaskan 3 Design Pattern yang kamu gunakan!
- **Factory Pattern (`UserFactory`):** Memusatkan pembuatan objek user (terutama transisi `CalonMahasiswa` → `Mahasiswa` lengkap dengan NIM dan `-calonMahasiswaId`), karena di OOP objek tidak bisa berganti class saat runtime.
- **Observer Pattern (`IEventPublisher` / `EventBus` & `IEventSubscriber`):** Memisahkan pengirim event (`PMBService`, `KRSManager`) dari penerima (`NotificationService`, `AuditLogSubscriber`). Mendukung *loose coupling* dan OCP.
- **Strategy Pattern (`IValidationRule` + 4 Rule konkret):** Memisahkan setiap aturan bisnis validasi KRS agar bisa ditambah/dilepas secara dinamis tanpa mengubah `KRSValidator`.

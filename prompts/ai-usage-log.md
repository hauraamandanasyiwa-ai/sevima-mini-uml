# AI Usage Log — SEVIMA-Mini (Minggu 1: Eksplorasi & Prompt Engineering)

Dokumen ini disusun sesuai **AI-First Development Charter** mata kuliah Pemrograman Berorientasi Objek (OOP) untuk mendokumentasikan secara transparan penggunaan AI LLM, iterasi *prompt engineering*, hasil validasi kritis, revisi manual, serta refleksi **OPAR** (*Observe, Plan, Act, Reflect*).

---

## 1. Metadata & Kepatuhan AI-First Development Charter

| Informasi | Detail |
| :--- | :--- |
| **Proyek** | SEVIMA-Mini (Sistem Informasi Akademik) |
| **Fase** | Minggu 1 — Eksplorasi Domain, Prompt Engineering & Class Diagram |
| **AI Tools Digunakan** | Gemini LLM, IDE Assistant (VSCode) |
| **Diagram Tool** | Mermaid (`diagrams/class-diagram.mmd`) |
| **Kepatuhan Privasi** | Tidak ada data pribadi/rahasia (NIM asli, NIK, nilai asli mahasiswa) yang dimasukkan ke dalam prompt. |
| **Verifikasi Pemahaman** | Seluruh relasi, kardinalitas, *visibility modifier*, dan pemecahan SOLID telah diaudit dan dipahami secara manual untuk kesiapan *viva*. |

---

## 2. Daftar 6 Prompt Terbaik & Riwayat Iterasi

Setiap prompt disusun dan disempurnakan mengikuti **Anatomi Prompt Desain Sistem (5 Unsur)**: *Role, Konteks, Komponen, Constraint, dan Format Output*.

### Prompt 1 — Eksplorasi Awal (Baseline dari Lembar Tugas)
> **Tujuan:** Menghasilkan kerangka awal Class Diagram untuk sistem akademik.

```text
Anda adalah arsitek sistem. Buat class diagram UML untuk sistem akademik dengan komponen berikut:
- User sebagai base class (Mahasiswa, Dosen, Admin, CalonMahasiswa)
- Course dengan atribut kode, nama, SKS, prasyarat
- Enrollment yang hubungkan Mahasiswa dan Course
- Schedule dengan hari, jam, ruangan
- Grade untuk nilai mahasiswa

Terapkan prinsip SOLID. Gunakan composition untuk relasi kuat dan aggregation untuk relasi lemah. Output dalam format Mermaid.
```

- **Ringkasan Output AI (v1):** Menghasilkan 9 class dasar (`User`, 4 subclass, `Course`, `Enrollment`, `Schedule`, `Grade`), namun semua atribut berstatus `+` (*public*), `User` tidak bertanda `<<abstract>>`, `Payment` belum ada, `Grade` dihubungkan langsung ke `Mahasiswa`, `Course o-- Schedule` salah memakai aggregation, muncul *circular dependency* (`Course -> Schedule -> Dosen -> Course`), serta `Mahasiswa` menumpuk banyak tanggung jawab (*God Object*).

---

### Prompt 2 — Penambahan Modul Wajib, Encapsulation & Kardinalitas
> **Tujuan:** Memperbaiki kekurangan komponen wajib (`Payment`, `ProgramStudi`, `Attendance`), mewajibkan *visibility modifier*, *abstract class*, dan kardinalitas eksplisit.

```text
# Role
Anda adalah senior software architect spesialis OOP.

# Konteks
Kita merancang sistem informasi akademik SEVIMA-Mini yang mencakup 6 modul: PMB, KRS, Jadwal & Ruangan, Nilai & Transkrip, Pembayaran SPP, dan Presensi QR.

# Komponen
- User (<<abstract>>) dengan turunan Mahasiswa, Dosen, Admin, CalonMahasiswa.
- Class inti: Course, Enrollment, Schedule, Grade, Payment, Attendance, ProgramStudi.

# Constraint
- Wajib terapkan encapsulation: atribut sensitif seperti password dan ipk harus private (-), atribut bersama protected (#), method akses public (+).
- Tambahkan method abstrak tampilkanDashboard() untuk polymorphism.
- Wajib tuliskan kardinalitas eksplisit (1, 0..1, 0..*, 1..*) pada setiap relasi.
- Grade harus terhubung dengan Composition ke Enrollment (bukan langsung ke Mahasiswa).
- ProgramStudi menaungi Dosen dan Mahasiswa menggunakan Aggregation.

# Format Output
Berikan kode Mermaid classDiagram yang valid tanpa penjelasan panjang.
```

- **Ringkasan Output AI (v2):** Hierarki `User <<abstract>>`, `Payment`, `ProgramStudi`, `Attendance`, *visibility modifier*, dan kardinalitas sudah muncul. Namun logika validasi KRS, cetak transkrip PDF, dan notifikasi masih menempel di class `Mahasiswa` dan `Enrollment`.

---

### Prompt 3 — Desain Modul KRS dengan Strategy Pattern (OCP & DIP)
> **Tujuan:** Menerapkan aturan bisnis KRS (maksimal 24 SKS, prasyarat, jadwal bentrok, cegah *double enrollment*) menggunakan *Strategy Pattern* agar mudah ditambah aturan baru tanpa memodifikasi class validator.

```text
# Role
Anda adalah senior software architect.

# Konteks
Modul validasi KRS pada sistem akademik SEVIMA-Mini memiliki 4 aturan bisnis:
1. Total SKS maksimal 24 per semester.
2. Mahasiswa wajib lulus mata kuliah prasyarat.
3. Tidak boleh ada jadwal bentrok (hari & jam beririsan).
4. Mencegah double enrollment pada mata kuliah yang sama.

# Komponen
Buat rancangan class menggunakan Strategy Pattern:
- Interface IValidationRule
- Implementasi konkret: MaxSKSValidationRule, PrerequisiteValidationRule, ScheduleConflictRule, DuplicateEnrollmentRule
- Context class: KRSValidator

# Constraint
- Terapkan Open/Closed Principle (OCP) dan Dependency Inversion Principle (DIP).
- Gunakan Aggregation antara KRSValidator dan IValidationRule.
- Gunakan visibility modifier lengkap (+, -, #) dan tipe generik Mermaid (~List~).

# Format Output
Potongan kode Mermaid classDiagram saja.
```

- **Ringkasan Output AI (v3):** Menghasilkan struktur *Strategy Pattern* yang modular. Namun AI sempat menulis `List<Enrollment>` (sintaks Java) yang membuat parser Mermaid error; perlu diubah ke `List~Enrollment~`.

---

### Prompt 4 — Audit SOLID & Refactoring God Object
> **Tujuan:** Mengaudit keseluruhan Class Diagram terhadap pelanggaran prinsip SOLID, khususnya *Single Responsibility Principle* (SRP) dan *Dependency Inversion Principle* (DIP).

```text
# Role
Anda adalah software quality auditor yang ketat terhadap prinsip SOLID.

# Konteks
Audit class diagram Mermaid sistem SEVIMA-Mini berikut terhadap prinsip SOLID, dengan fokus utama pada Single Responsibility Principle (SRP) dan Dependency Inversion Principle (DIP):
[menyertakan diagram hasil iterasi v2 + v3]

# Tugas
1. Identifikasi potensi God Object atau class dengan tanggung jawab ganda.
2. Identifikasi pelanggaran DIP (ketergantungan pada class konkret, bukan abstraksi).
3. Berikan rekomendasi refactor class baru yang fokus (seperti TranscriptService dan INotificationService).

# Format Output
Daftar temuan pelanggaran + potongan refactor Mermaid classDiagram.
```

- **Ringkasan Output AI (v4):** AI mengidentifikasi bahwa `Mahasiswa` melanggar SRP karena memiliki `hitungIPK()`, `cetakTranskripPDF()`, dan `kirimEmailNotifikasi()`. Rekomendasi: ekstrak ke `TranscriptService` dan `INotificationService` + `NotificationService`, lalu injeksikan `INotificationService` ke `KRSValidator`.

---

### Prompt 5 — Penyelesaian Transisi PMB (`CalonMahasiswa` ke `Mahasiswa`)
> **Tujuan:** Memodelkan perubahan status calon mahasiswa yang diterima menjadi mahasiswa aktif secara benar dalam paradigma OOP (karena objek tidak bisa berganti *class* saat runtime).

```text
# Role
Anda adalah arsitek sistem OOP.

# Konteks
Di modul PMB SEVIMA-Mini, ketika CalonMahasiswa dinyatakan lulus seleksi dan diverifikasi Admin, sistem harus menerbitkan NIM dan menghasilkan Mahasiswa aktif tanpa mengubah tipe class objek CalonMahasiswa secara langsung.

# Komponen
Admin, CalonMahasiswa, Mahasiswa, dan MahasiswaFactory.

# Constraint
- Terapkan Factory Pattern (MahasiswaFactory) untuk membuat objek Mahasiswa dari data CalonMahasiswa.
- Simpan keterkaitan asal pendaftar melalui atribut -calonMahasiswaId pada Mahasiswa.
- Pastikan tidak tercipta circular dependency antar class.

# Format Output
Potongan relasi dan definisi class dalam format Mermaid classDiagram.
```

- **Ringkasan Output AI (v5):** Menambahkan `MahasiswaFactory` dengan method `+buatDariCalon(CalonMahasiswa calon, String nim) Mahasiswa`, dipicu oleh `Admin`, dengan relasi dependency searah (`..>`) yang bersih tanpa siklus.

---

### Prompt 6 — Validasi Akhir Anti-Circular Dependency & Sintaks Mermaid
> **Tujuan:** Menggabungkan seluruh modul menjadi satu diagram sinkron, memastikan tidak ada *circular dependency*, dan memvalidasi sintaks Mermaid.

```text
# Role
Anda adalah arsitek sistem dan reviewer UML.

# Konteks
Gabungkan seluruh modul SEVIMA-Mini (Hierarki User, 5 Class Inti + ProgramStudi + Attendance, Strategy Validation, TranscriptService, INotificationService, MahasiswaFactory) menjadi satu file class-diagram.mmd final.

# Constraint
- Periksa graf relasi: pastikan TIDAK ADA circular dependency (misal Course -> Schedule -> Dosen -> Course).
- Perbolehkan self-association Course --> Course khusus untuk prasyarat.
- Pastikan setiap class memiliki kurang dari 10 method (anti God Object).
- Pastikan sintaks Mermaid valid (gunakan ~Type~ untuk generik, <<abstract>>, <<interface>>, tanda kutip untuk kardinalitas).

# Format Output
Satu blok kode Mermaid classDiagram lengkap siap render di GitHub dan Mermaid Live Editor.
```

---

## 3. Perbandingan Hasil AI vs Revisi Manual

Berikut adalah kesalahan nyata yang ditemukan pada output AI awal dan perbaikan manual yang dilakukan setelah proses validasi kritis:

| No | Aspek | Hasil Output AI (Before) | Revisi Manual (After) | Alasan Teknis Revisi Diperlukan |
| :-: | :--- | :--- | :--- | :--- |
| 1 | **Class `User` & Encapsulation** | `class User` konkret; atribut `+password` dan `+ipk` bersifat *public*. | `User` diberi stereotype `<<abstract>>`; `-password` dan `-ipk` diubah ke *private* (`-`); `#nama`, `#email` ke *protected* (`#`). | Tidak ada pengguna tanpa peran (*abstraction*). Password dan IPK tidak boleh diubah langsung dari luar class (*encapsulation*); perubahan IPK hanya lewat aturan resmi (`updateIPK` / `TranscriptService`). |
| 2 | **Kelengkapan Class Inti** | Class `Payment` tidak disertakan pada draft awal karena mengikuti contoh prompt ringkas. | Menambahkan `Payment` (`1 --> 0..*` dari `Mahasiswa`), `ProgramStudi`, dan `Attendance`. | `Payment` adalah salah satu dari 5 class inti wajib di requirement SEVIMA-Mini; `ProgramStudi` memodelkan Aggregation dengan tepat; `Attendance` melengkapi modul Presensi QR. |
| 3 | **Penempatan `Grade`** | `Mahasiswa --> Grade` (nilai dihubungkan langsung ke Mahasiswa). | `Enrollment "1" *-- "0..1" Grade` (Composition dari `Enrollment`). | Nilai selalu melekat pada satu mahasiswa, satu mata kuliah, dan satu semester tertentu (`Enrollment`). Jika enrollment dibatalkan, nilainya ikut tidak berlaku (Composition). |
| 4 | **Composition vs Aggregation** | `Course o-- Schedule` memakai Aggregation (*belah ketupat kosong*). | Diubah menjadi `Course "1" *-- "1..*" Schedule` (Composition) dan `ProgramStudi "1" o-- "1..*" Dosen` (Aggregation). | Jadwal kelas tidak bermakna tanpa mata kuliahnya (*Composition*). Sebaliknya, jika prodi ditutup, Dosen tetap hidup dan bisa pindah prodi (*Aggregation*). |
| 5 | **Circular Dependency** | `Course o-- Schedule`, `Schedule --> Dosen`, `Dosen --> Course` membentuk siklus tertutup. | Arah diputus menjadi `Course *-- Schedule` dan `Dosen "1" --> "0..*" Schedule` (menghapus `Dosen --> Course` dan `Schedule --> Dosen`). | *Circular dependency* menyebabkan *tight coupling*, sulit diuji (*unit test*), dan rawan error saat implementasi modul di Minggu 3–16. |
| 6 | **God Object (Pelanggaran SRP)** | `Mahasiswa` memiliki `validasiKRS()`, `hitungIPK()`, `cetakTranskripPDF()`, dan `kirimEmailNotifikasi()`. | Dipecah menjadi `KRSValidator` + `IValidationRule` (*Strategy*), `TranscriptService`, dan `INotificationService` + `NotificationService`. | Melanggar *Single Responsibility Principle*. Jika format PDF atau aturan SKS berubah, class `Mahasiswa` tidak seharusnya ikut diubah. |
| 7 | **Sintaks Generik Mermaid** | AI menuliskan `List<Course>` dan `List<Enrollment>` yang menyebabkan gagal render di Mermaid. | Diubah menjadi `List~Course~` dan `List~Enrollment~`. | Spesifikasi resmi Mermaid `classDiagram` mewajibkan tanda tilde (`~T~`) untuk tipe generik agar tidak bentrok dengan tag HTML/XML. |

---

## 4. Refleksi OPAR (Observe, Plan, Act, Reflect)

### 1. Observe (Mengamati)
- Pada percobaan awal (Prompt 1), prompt yang kurang spesifik membuat AI menghasilkan diagram yang tampak rapi secara visual tetapi menyimpan kesalahan arsitektur fatal: seluruh atribut bersifat *public*, `Payment` terlewat, muncul *circular dependency* (`Course -> Schedule -> Dosen -> Course`), `Grade` salah penempatan, serta `Mahasiswa` mulai tumbuh menjadi *God Object*.
- AI juga beberapa kali menukar simbol *Aggregation* (`o--`) dan *Composition* (`*--`) serta memakai sintaks generik `<T>` yang merusak render Mermaid.

### 2. Plan (Merencanakan)
- Melakukan analisis domain manual (kata benda & kata kerja) terlebih dahulu di `docs/domain-analysis.md` sebelum menulis prompt lanjutan.
- Menerapkan anatomi prompt 5 unsur (*Role, Konteks, Komponen, Constraint, Format Output*) dan memecah iterasi prompt per fokus: struktur inti & *encapsulation* (v2), *Strategy Pattern* KRS (v3), audit SOLID (v4), *Factory Pattern* PMB (v5), dan validasi anti-siklus (v6).
- Menyusun *checklist* validasi manual: uji *is-a*, uji *wadah dihapus bagian ikut mati*, pengecekan graf bebas siklus, dan verifikasi sintaks Mermaid.

### 3. Act (Melaksanakan)
- Mengeksekusi 6 iterasi prompt dan membandingkan setiap versi output AI.
- Melakukan *commit* bertahap di Git (inisialisasi -> analisis domain -> draft v1 `[AI-assisted]` -> refactoring SOLID `[AI-assisted]` -> dokumentasi AI Usage Log -> ADR PDF).
- Mendokumentasikan setiap keputusan desain penting (termasuk transisi `CalonMahasiswa -> Mahasiswa` via `MahasiswaFactory`) ke dalam dokumen `docs/ADR-architecture-decisions.pdf`.

### 4. Reflect (Merefleksikan)
- **Pelajaran Utama:** AI sangat mempercepat pembuatan *draft* awal UML dan membantu mengaudit pelanggaran SOLID, tetapi AI tetap membutuhkan kendali penuh dari arsitek manusia. Tanpa pemahaman domain dan validasi kritis, kesalahan halus seperti *visibility* `-password`, penempatan `Grade`, dan *circular dependency* akan terbawa hingga fase implementasi kode di Minggu 3–16.
- **Kesiapan Minggu 2 & Viva:** Struktur class saat ini sudah modular, setiap class memiliki tanggung jawab tunggal (< 8 method per class), dan seluruh keputusan desain dapat dijelaskan secara lisan tanpa bantuan AI. Pada Minggu 2, diagram ini siap disinkronkan dengan *Use Case Diagram* dan *Sequence Diagram* (PMB & Validasi KRS).


---
---

# AI Usage Log — SEVIMA-Mini (Minggu 2: Refinement, Skenario & Design Patterns)

Bagian ini mendokumentasikan kelanjutan proses pengembangan berbasis AI pada **Minggu 2** (Langkah 4, 5, dan 6): pembuatan *Use Case Diagram*, *Sequence Diagram* (PMB & Validasi KRS dengan *alternate flow*), audit kritik mandiri oleh AI, refactoring *God Object* & prinsip **SOLID** (SRP, OCP, LSP, ISP, DIP), penerapan pola **Factory + Observer + Strategy**, serta sinkronisasi seluruh diagram.

---

## 1. Metadata Minggu 2 & Kepatuhan Charter

| Informasi | Detail |
| :--- | :--- |
| **Minggu / Fase** | Minggu 2 — Refinement, Skenario, SOLID & Design Patterns |
| **Fitur Utama** | Use Case SEVIMA-Mini, Sequence PMB, Sequence Validasi KRS, Refactor Class Diagram (Observer, ISP, DIP, Service Layer) |
| **AI Tools Digunakan** | Gemini LLM, IDE Assistant |
| **Diagram Tool** | Mermaid (`diagrams/usecase-diagram.mmd`, `diagrams/sequence-pmb.mmd`, `diagrams/sequence-krs.mmd`, `diagrams/class-diagram.mmd`) |
| **Kepatuhan Privasi** | Seluruh contoh data (nomor pendaftaran `"PMB-2026-001"`, contoh nama mata kuliah) menggunakan data dummy, bebas data pribadi/rahasia. |

---

## 2. Daftar 6 Prompt Terbaik Minggu 2 & Riwayat Iterasi

### Prompt 7 — Generate Use Case Diagram SEVIMA-Mini (`include` & `extend`)
> **Tujuan:** Membuat *Use Case Diagram* lengkap dengan batas sistem (*system boundary*), aktor peran (bukan individu), serta relasi `<<include>>` dan `<<extend>>` yang valid.

```text
# Role
Anda adalah software architect spesialis UML.

# Konteks
Kita membangun Use Case Diagram untuk sistem akademik SEVIMA-Mini (lanjutan dari Class Diagram Minggu 1).

# Komponen
- Aktor minimal: Calon Mahasiswa, Mahasiswa, Dosen Pengampu, Dosen PA, Admin Akademik, Sistem PMB, dan Layanan Pembayaran Bank.
- Use case utama: Daftar Calon Mahasiswa, Unggah Berkas PMB, Verifikasi Berkas PMB, Terbitkan NIM & Akun, Isi KRS, Cek Prasyarat, Cek Batas Maks 24 SKS, Cek Jadwal Bentrok, Approve KRS, Ajukan Revisi KRS, Input Nilai, Generate Transkrip, Kelola Mata Kuliah & Jadwal, Catat Presensi QR, Bayar SPP, Bayar Denda Keterlambatan.

# Constraint
- Pisahkan peran Dosen Pengampu dan Dosen PA (bukan satu nama orang).
- Pastikan semua use case berada di dalam System Boundary SEVIMA-Mini dan semua aktor di luar.
- Tandai relasi <<include>> (panah dari use case dasar ke use case wajib) dan <<extend>> (panah terbalik dari use case kondisional ke use case dasar).
- Jelaskan alasan setiap relasi include dan extend yang dibuat.

# Format Output
Kode Mermaid flowchart LR yang rapi + penjelasan singkat setiap relasi.
```

- **Ringkasan Output AI (Before) & Revisi Manual (After):** AI sempat membalik arah panah `<<extend>>` pada *Approve KRS → Ajukan Revisi KRS* dan menaruh *Terbitkan NIM & Akun* sebagai `<<include>>` padahal hanya terjadi jika calon mahasiswa lulus seleksi. Diperbaiki manual sehingga panah `<<extend>>` mengarah dari *Ajukan Revisi KRS → Approve KRS*, *Bayar Denda → Bayar SPP*, dan *Terbitkan NIM & Akun → Verifikasi Berkas PMB*.

---

### Prompt 8 — Sequence Diagram Skenario 1: Pendaftaran Mahasiswa Baru (PMB)
> **Tujuan:** Memodelkan alur pendaftaran hingga penerbitan NIM & akun menggunakan `UserFactory`, pesan asinkron notifikasi, dan *alternate flow* saat berkas tidak lengkap atau email gagal terkirim.

```text
# Role
Anda adalah software architect spesialis pemodelan perilaku (behavioral UML).

# Konteks
Buat Sequence Diagram untuk skenario Pendaftaran Mahasiswa Baru (PMB) SEVIMA-Mini dalam 2 tahap: (1) pendaftaran & unggah berkas oleh CalonMahasiswa, (2) verifikasi oleh Admin dan pembuatan objek Mahasiswa baru.

# Komponen (Wajib Sinkron dengan Class Diagram)
Partisipan: CalonMahasiswa, Admin, PMBService, PMBRepository, UserFactory, NotificationService.

# Constraint
- Gunakan Factory Pattern (UserFactory.buatMahasiswaDariCalon) agar PMBService tidak membuat objek Mahasiswa secara langsung.
- Gunakan pesan asinkron (-)) untuk mengirim notifikasi email agar PMBService tidak terblokir menunggu SMTP.
- Wajib sertakan fragmen alt (alternate flow) untuk: berkas tidak lengkap/format salah, pendaftar tidak lulus, dan pengiriman email gagal (retry/logging).

# Format Output
Kode Mermaid sequenceDiagram dengan autonumber.
```

- **Ringkasan Output AI & Revisi:** Draft awal AI menggabungkan `PMBService` dan database menjadi satu partisipan `System` serta memakai panah sinkron (`->>`) untuk email. Direvisi manual dengan memecah `PMBService` + `PMBRepository` dan mengganti notifikasi menjadi panah asinkron (`-)`) lengkap dengan cabang `alt` saat SMTP gagal.

---

### Prompt 9 — Sequence Diagram Skenario 2: Validasi KRS (Loop, Self-Call & Alternate Flow)
> **Tujuan:** Memodelkan validasi KRS (prasyarat, batas 24 SKS, bentrok jadwal) yang mengumpulkan seluruh error sekaligus dan menggunakan notifikasi asinkron ke Dosen PA.

```text
# Role
Anda adalah software architect spesialis UML.

# Konteks
Buat Sequence Diagram untuk proses Validasi & Pengajuan KRS di SEVIMA-Mini.

# Komponen (Wajib Sinkron dengan Class Diagram)
Partisipan: Mahasiswa, KRSManager, KRSValidator, AkademikRepository, NotificationService, DosenPA.

# Constraint
- Gunakan fragmen loop untuk memeriksa prasyarat & duplikasi setiap mata kuliah melalui AkademikRepository.
- Gunakan self-call pada KRSValidator untuk hitungTotalSKS() (maks 24 SKS) dan cekJadwalBentrok().
- Kumpulkan semua error ke dalam ValidationResult (jangan berhenti di error pertama).
- Wajib ada fragmen alt untuk semua jalur gagal: prasyarat belum lulus, SKS > 24, jadwal bentrok, multiple errors, dan happy path (status PENDING_APPROVAL + notifikasi asinkron ke DosenPA).
- Pesan error harus spesifik dan bisa ditindaklanjuti.

# Format Output
Kode Mermaid sequenceDiagram dengan autonumber.
```

- **Ringkasan Output AI & Revisi:** Output awal AI hanya menampilkan *happy path* dan berhenti di error pertama (*fail-fast*). Direvisi dengan menambahkan `ValidationResult` untuk mengumpulkan semua error sekaligus dan 4 cabang `alt` spesifik sesuai praktik terbaik.

---

### Prompt 10 — Audit Kritik Mandiri AI (Self-Critique 5 Kelemahan Terbesar)
> **Tujuan:** Meminta AI mengkritik desain Minggu 1 + skenario Minggu 2 untuk menemukan celah tersembunyi sebelum finalisasi.

```text
# Role
Anda adalah principal software architect yang sangat kritis saat code & design review.

# Konteks
Evaluasi sinkronisasi antara Class Diagram Minggu 1 dengan Use Case Diagram, Sequence PMB, dan Sequence KRS yang baru dibuat.

# Tugas
Sebutkan 5 kelemahan terbesar diurutkan dari yang paling berisiko (sinkronisasi diagram, potensi God Object, pelanggaran SOLID, dan kesiapan pola Observer/Factory). Berikan rekomendasi perbaikan konkret.
```

- **Temuan Kritis yang Divalidasi:**
  1. **Ketidaksinkronan diagram:** `PMBService`, `PMBRepository`, `KRSManager`, `AkademikRepository`, dan `ValidationResult` muncul di Sequence Diagram tetapi belum ada di Class Diagram Minggu 1.
  2. **Belum ada Observer Pattern:** Notifikasi di Minggu 1 masih berupa pemanggilan langsung `KRSValidator ..> INotificationService` (coupling langsung), padahal Minggu 2 mensyaratkan Observer Pattern untuk event perubahan status KRS/PMB.
  3. **Pelanggaran DIP pada Channel Notifikasi:** `NotificationService` masih menyimpan `-String channel` mentah, bukan abstraksi `INotificationChannel` yang diinjeksi lewat konstruktor.
  4. **Belum ada Interface Segregation (ISP):** Peran `PengisiKRS`, `PenyetujuKRS`, dan `Penilai` belum dipisah menjadi interface kecil.
  5. **Keterbatasan `MahasiswaFactory`:** Perlu digeneralisasi menjadi `UserFactory` agar konsisten menangani pembuatan 4 tipe user sekaligus transisi PMB.

---

### Prompt 11 — Refactor Class Diagram (SOLID Lengkap, Observer, DIP, ISP & Service Layer)
> **Tujuan:** Memperbarui `diagrams/class-diagram.mmd` agar 100% sinkron dengan seluruh Sequence Diagram dan memenuhi seluruh 5 prinsip SOLID + 3 Design Pattern (Factory, Observer, Strategy).

```text
# Role
Anda adalah senior software architect OOP.

# Konteks
Refactor Class Diagram Minggu 1 SEVIMA-Mini berdasarkan hasil audit kritik mandiri agar 100% sinkron dengan sequence-pmb.mmd dan sequence-krs.mmd.

# Perubahan Wajib
1. Tambahkan Service Layer & Repository: PMBService, PMBRepository, KRSManager, AkademikRepository, ValidationResult.
2. Upgrade MahasiswaFactory menjadi UserFactory (Factory Pattern).
3. Tambahkan Observer Pattern: IEventPublisher, EventBus, IEventSubscriber, dengan subscriber NotificationService dan AuditLogSubscriber (bukti OCP).
4. Terapkan DIP pada notifikasi: INotificationChannel dengan implementasi EmailNotificationChannel dan WhatsAppNotificationChannel diinjeksi via konstruktor NotificationService.
5. Terapkan ISP: interface kecil IPengisiKRS, IPenyetujuKRS, IPenilai.
6. Pastikan tidak ada class dengan > 10 method dan bebas circular dependency.

# Format Output
Kode Mermaid classDiagram lengkap yang valid.
```

---

### Prompt 12 — Penyusunan ADR Minggu 2 & Validasi Sinkronisasi Akhir
> **Tujuan:** Menyusun keputusan arsitektur (ADR-005 s.d. ADR-007) lengkap dengan *alternatif & trade-off* serta memverifikasi bahwa setiap partisipan di kedua Sequence Diagram eksis di Class Diagram.

```text
# Role
Anda adalah software architect yang menulis dokumentasi ADR untuk tim pengembang.

# Konteks
Susun ADR tambahan untuk keputusan arsitektur Minggu 2 SEVIMA-Mini:
- ADR-005: Pemecahan Service Layer & Repository (PMBService, KRSManager) untuk mencegah God Object.
- ADR-006: Penerapan Observer Pattern (EventBus) dan DIP (INotificationChannel) untuk notifikasi asinkron.
- ADR-007: Pengumpulan seluruh error validasi (ValidationResult) dan Interface Segregation (ISP).

# Constraint
Setiap ADR wajib memiliki 5 bagian: Konteks, Keputusan, Alternatif & Trade-off, Konsekuensi (+/-), dan Pattern yang diterapkan.
```

---

## 3. Perbandingan Hasil AI vs Revisi Manual (Minggu 2)

| No | Aspek | Hasil Output AI (Before) | Revisi Manual (After) | Alasan Teknis Revisi Diperlukan |
| :-: | :--- | :--- | :--- | :--- |
| 1 | **Arah Panah `<<extend>>` di Use Case** | Panah mengarah dari *Approve KRS* → *Ajukan Revisi KRS* (terbalik). | Dibalik menjadi *Ajukan Revisi KRS* `-. "<<extend>>" .->` *Approve KRS*. | Pada standar UML, `<<extend>>` selalu mengarah dari use case tambahan menuju use case dasar. Jika dihilangkan, *Approve KRS* tetap utuh. |
| 2 | **Partisipan `System` di Sequence Diagram** | AI menaruh semua logika PMB & KRS di satu partisipan generik `System`. | Dipecah menjadi `PMBService`, `PMBRepository`, `UserFactory`, `KRSManager`, `KRSValidator`, `AkademikRepository`, `NotificationService`. | Partisipan tunggal `System` adalah gejala awal *God Object* dan membuat Sequence Diagram tidak sinkron dengan Class Diagram. |
| 3 | **Sequence KRS Tanpa Alternate Flow** | Output awal hanya menggambarkan *happy path* dan berhenti di error pertama. | Ditambahkan 4 cabang `alt` spesifik (prasyarat, SKS > 24, bentrok jadwal, multiple errors) menggunakan `ValidationResult`. | Jalur gagal adalah sumber masalah utama di dunia nyata; mengumpulkan semua error sekaligus mencegah mahasiswa bolak-balik submit KRS. |
| 4 | **Notifikasi Sinkron & Tight Coupling** | `KRSValidator` langsung memanggil `NotificationService` secara sinkron (`->>`) dengan atribut `-String channel`. | Diubah menjadi **Observer Pattern** (`IEventPublisher` / `EventBus`) + pesan asinkron (`-)`) + **DIP** (`INotificationChannel`). | Pengirim tidak perlu menunggu email selesai dikirim; penambahan channel WhatsApp atau `AuditLogSubscriber` tidak perlu mengubah kode `KRSManager` (OCP & mudah di-mock saat unit test). |
| 5 | **Factory & Interface Segregation** | Hanya ada `MahasiswaFactory` dan belum ada pemisahan interface peran. | Digeneralisasi menjadi `UserFactory` dan ditambahkan interface kecil `IPengisiKRS`, `IPenyetujuKRS`, `IPenilai`. | Memenuhi ISP agar `Mahasiswa` tidak pernah mewarisi method `inputNilai()`, serta memusatkan konstruksi seluruh turunan `User` di satu factory. |

---

## 4. Refleksi OPAR Minggu 2 (Observe, Plan, Act, Reflect)

### 1. Observe (Mengamati)
- Saat desain Minggu 1 diuji dengan skenario nyata (PMB & Validasi KRS), terlihat celah yang sebelumnya tidak tampak di *Class Diagram* statis: belum adanya *Service/Manager Layer* (`PMBService`, `KRSManager`), belum adanya lapisan *Repository*, belum diterapkannya **Observer Pattern**, serta arah panah `<<extend>>` yang sering salah dibuat oleh AI.
- AI juga cenderung menghasilkan *Sequence Diagram* hanya untuk *happy path* jika tidak secara eksplisit diminta menambahkan *alternate flow* dan pesan error spesifik.

### 2. Plan (Merencanakan)
- Menyusun *Use Case Diagram* terlebih dahulu untuk memastikan cakupan aktor dan relasi `include`/`extend` benar.
- Merancang dua *Sequence Diagram* utama (PMB & Validasi KRS) dengan partisipan yang eksplisit, panah asinkron, `loop`, self-call, dan `alt` error handling lengkap.
- Memanfaatkan teknik *self-critique* AI untuk menemukan 5 kelemahan terbesar, lalu merefactor `diagrams/class-diagram.mmd` agar seluruh diagram sinkron 100% dan memenuhi kelima prinsip **SOLID** + **Factory, Observer, Strategy**.

### 3. Act (Melaksanakan)
- Membuat `diagrams/usecase-diagram.mmd`, `diagrams/sequence-pmb.mmd`, dan `diagrams/sequence-krs.mmd`.
- Merefactor `diagrams/class-diagram.mmd` (menambahkan `PMBService`, `PMBRepository`, `UserFactory`, `KRSManager`, `AkademikRepository`, `ValidationResult`, `EventBus`/`IEventSubscriber`, `INotificationChannel`, dan interface ISP).
- Menyimpan perbandingan *before vs after* (`diagrams/before-after/`), memperbarui `docs/ADR-architecture-decisions.pdf`, membuat `docs/Final-UML-diagram.pdf`, dan melakukan commit bertahap dengan penanda `[AI-assisted]`.

### 4. Reflect (Merefleksikan)
- **Pelajaran Utama:** Menguji *Class Diagram* menggunakan *Sequence Diagram* adalah cara paling efektif untuk mendeteksi desain yang kurang sinkron atau terlalu gemuk (*God Object*). Meminta AI mengkritik hasilnya sendiri menghasilkan temuan berharga, tetapi keputusan akhir (seperti memilih *Observer + DIP* dan membalik arah `<<extend>>`) tetap menjadi tanggung jawab arsitek manusia.
- **Kesiapan Implementasi Minggu 3 & Viva:** Modul `PMBService`, `PMBRepository`, dan `UserFactory` kini sudah memiliki kontrak method dan alur error handling yang sangat jelas sehingga siap langsung diimplementasikan ke kode dan *unit test* pada Minggu 3. Seluruh panah, relasi, dan pattern telah dipahami secara mendalam untuk sesi *viva*.

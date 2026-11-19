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

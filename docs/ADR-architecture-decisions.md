# Architecture Decision Record (ADR) — SEVIMA-Mini

**Proyek:** Sistem Informasi Akademik SEVIMA-Mini  
**Mata Kuliah:** Pemrograman Berorientasi Objek (OOP) — Minggu 1 & Minggu 2  
**Status:** Final (Disinkronkan dengan Class, Use Case, dan Sequence Diagram)

---

## Ringkasan Keputusan Arsitektur

| Kode | Keputusan Utama | Fokus SOLID / Pattern | Fase |
| :---: | :--- | :--- | :---: |
| **ADR-001** | Hierarki `User <<abstract>>` & Pemisahan Entitas Akademik | Abstraction, LSP, Encapsulation | Minggu 1 |
| **ADR-002** | Pemecahan Many-to-Many via `Enrollment` & Anti-Circular Dependency | Composition vs Aggregation | Minggu 1 |
| **ADR-003** | Strategy Pattern untuk Validasi KRS (`IValidationRule`) | OCP, SRP, Strategy Pattern | Minggu 1 |
| **ADR-004** | Factory Pattern untuk Pembuatan User & Transisi PMB (`UserFactory`) | SRP, Factory Pattern | Minggu 1 & 2 |
| **ADR-005** | Pemecahan Service Layer & Repository (Anti-God Object) | SRP, Modularitas | Minggu 2 |
| **ADR-006** | Observer Pattern (`EventBus`) & DIP (`INotificationChannel`) untuk Notifikasi Asinkron | OCP, DIP, Observer Pattern | Minggu 2 |
| **ADR-007** | Pengumpulan Semua Error Validasi (`ValidationResult`) & Interface Segregation | ISP, UX Error Handling | Minggu 2 |

---

## ADR-001: Hierarki `User <<abstract>>` & Perlindungan Liskov Substitution (LSP)
- **Konteks:** SEVIMA-Mini memiliki 4 peran pengguna (*Mahasiswa, Dosen, Admin, CalonMahasiswa*) yang berbagi atribut autentikasi (`id, nama, email, username, password`) namun memiliki perilaku sangat berbeda. Jika atribut spesifik seperti `ipk` ditaruh di `User`, maka `CalonMahasiswa` dipaksa memiliki IPK padahal belum kuliah.
- **Keputusan:** Menjadikan `User` sebagai *abstract class* dengan method abstrak `tampilkanDashboard()*`, atribut sensitif `-password` bersifat *private*, dan menempatkan method spesifik seperti `getIPK()` / `updateIPK()` hanya di `Mahasiswa`.
- **Alternatif & Trade-off:**
  - *Alternatif A (Satu class `User` dengan kolom `role` + banyak if-else):* Cepat dibuat di awal, tetapi melanggar OCP/LSP dan cepat menjadi *God Object*.
  - *Alternatif B (4 class terpisah tanpa parent):* Tidak ada duplikasi semu, tetapi logika `login()`/`logout()` terduplikasi di 4 tempat.
- **Konsekuensi:** (+) Kode autentikasi terpusat, LSP terjaga, polimorfisme dashboard bersih. (-) Penambahan peran baru membutuhkan subclass baru.
- **Pattern & Prinsip:** Abstraction, Inheritance, Polymorphism, Encapsulation, **LSP**.

---

## ADR-002: Pemecahan Relasi Many-to-Many & Graf Bebas Circular Dependency
- **Konteks:** Relasi antara `Mahasiswa` dan `Course` bersifat *many-to-many* dan memiliki data transaksional (semester, status KRS, nilai). Selain itu, draft awal AI menghasilkan siklus tertutup `Course -> Schedule -> Dosen -> Course`.
- **Keputusan:** Memecah *many-to-many* melalui class asosiasi `Enrollment`, mengikat `Grade` secara *Composition* (`*--`) pada `Enrollment`, serta memutus siklus menjadi relasi searah `Course *-- Schedule` dan `Dosen --> Schedule`.
- **Alternatif & Trade-off:**
  - *Alternatif A (Menghubungkan `Grade` langsung ke `Mahasiswa`):* Lebih sedikit relasi, tetapi gagal merepresentasikan mahasiswa yang mengulang mata kuliah di semester berbeda.
- **Konsekuensi:** (+) Riwayat KRS dan nilai per semester akurat; bebas *circular dependency* sehingga mudah di-unit test. (-) Membutuhkan join/navigasi melalui `Enrollment`.
- **Pattern & Prinsip:** Composition vs Aggregation, Acyclic Dependency.

---

## ADR-003: Strategy Pattern untuk Aturan Validasi KRS (`IValidationRule`)
- **Konteks:** Aturan validasi KRS kampus sering bertambah (saat ini: maks 24 SKS, prasyarat, jadwal bentrok, anti-duplikat; ke depan bisa ditambah aturan tunggakan SPP).
- **Keputusan:** Menerapkan **Strategy Pattern** dengan interface `IValidationRule` yang diagregasikan oleh `KRSValidator`.
- **Alternatif & Trade-off:**
  - *Alternatif A (Percabangan `if-else` panjang di dalam `KRSValidator`):* Lebih sedikit file class, tetapi setiap aturan baru memaksa modifikasi `KRSValidator` (melanggar OCP dan rawan regresi).
- **Konsekuensi:** (+) Penambahan aturan baru (misal `CekTunggakanRule`) cukup membuat class baru tanpa menyentuh `KRSValidator`; tiap rule bisa di-unit test terisolasi. (-) Jumlah class bertambah.
- **Pattern & Prinsip:** **Strategy Pattern**, **OCP**, **SRP**.

---

## ADR-004: Factory Pattern (`UserFactory`) untuk Pembuatan User & Transisi PMB
- **Konteks:** Di OOP, objek `CalonMahasiswa` yang lulus seleksi tidak dapat berubah tipe *class* menjadi `Mahasiswa` saat runtime. Selain itu, pembuatan 4 tipe user (terutama `Mahasiswa` yang wajib memiliki NIM) tidak boleh tersebar dengan `if-else` di berbagai service.
- **Keputusan:** Menggeneralisasi `MahasiswaFactory` (Minggu 1) menjadi **`UserFactory`** dengan method `buatUser(...)` dan `buatMahasiswaDariCalon(calon, nim)` yang menyimpan jejak `-calonMahasiswaId`.
- **Alternatif & Trade-off:**
  - *Alternatif A (Membuat objek `new Mahasiswa(...)` langsung di `PMBService`):* Lebih ringkas, tetapi membocorkan logika inisialisasi NIM/akun ke service dan sulit diubah bila format user berubah.
- **Konsekuensi:** (+) Logika konstruksi user terpusat di satu tempat; siap langsung dipakai pada implementasi modul PMB Minggu 3. (-) Menambah satu lapisan abstraksi pembuatan objek.
- **Pattern & Prinsip:** **Factory Pattern**, **SRP**.

---

## ADR-005: Pemecahan Service Layer & Repository (Anti-God Object)
- **Konteks:** Jika seluruh logika pendaftaran PMB, validasi KRS, penghitungan transkrip, dan penyimpanan data digabung dalam satu class `SistemAkademik`, satu perubahan aturan (misal SPP) berisiko merusak modul lain dan menyulitkan pengerjaan tim.
- **Keputusan:** Memecah orkestrasi bisnis menjadi service modular yang sinkron dengan Sequence Diagram: `PMBService` (+ `PMBRepository`), `KRSManager` (+ `KRSValidator`, `AkademikRepository`), `TranscriptService`, dan `NotificationService`. Setiap class dijaga ketat memiliki < 10 method.
- **Alternatif & Trade-off:**
  - *Alternatif A (Satu class `SistemAkademik` / God Object):* Cepat ditulis di awal, tetapi sangat sulit diuji dan dirawat.
  - *Alternatif B (Langsung arsitektur Microservices terpisah):* Terlalu kompleks (*over-engineering*) untuk skala proyek kuliah SEVIMA-Mini.
- **Konsekuensi:** (+) Modular, sesuai jadwal implementasi mingguan (Minggu 3 PMB, Minggu 5 KRS, dst.), mudah diuji. (-) Membutuhkan koordinasi antar service yang disiplin.
- **Pattern & Prinsip:** **SRP**, Repository Pattern, Modular Monolith.

---

## ADR-006: Observer Pattern (`EventBus`) & DIP (`INotificationChannel`) untuk Notifikasi Asinkron
- **Konteks:** Saat status PMB atau KRS berubah, banyak pihak perlu diberi tahu (Mahasiswa, Dosen PA, hingga kebutuhan masa depan seperti Audit Log). Selain itu, jika `NotificationService` langsung membuat objek `EmailSender`, perpindahan ke WhatsApp atau pembuatan *unit test* akan sulit.
- **Keputusan:**
  1. Menerapkan **Observer Pattern** (`IEventPublisher`/`EventBus` dan `IEventSubscriber`) dengan `NotificationService` serta `AuditLogSubscriber` sebagai subscriber. Pemanggilan dilakukan secara **asinkron** agar proses utama tidak terblokir menunggu SMTP.
  2. Menerapkan **Dependency Inversion Principle (DIP)** dengan menyuntikkan interface `INotificationChannel` (`EmailNotificationChannel`, `WhatsAppNotificationChannel`) melalui konstruktor `NotificationService`.
- **Alternatif & Trade-off:**
  - *Alternatif A (Pemanggilan sinkron langsung ke `EmailSender`):* Lebih sederhana, tetapi jika server email lambat/error, proses submit KRS atau verifikasi Admin ikut gagal/timeout dan sulit di-mock saat unit testing.
- **Konsekuensi:** (+) *Loose coupling*, penambahan subscriber baru (misal audit log) tanpa mengubah `KRSManager`/`PMBService` (OCP), dan *unit test* Minggu 5 dapat memakai *mock notifier* yang cepat. (-) Alur debugging event asinkron memerlukan pencatatan log yang rapi.
- **Pattern & Prinsip:** **Observer Pattern**, **DIP** (Dependency Injection), **OCP**.

---

## ADR-007: Pengumpulan Semua Error Validasi (`ValidationResult`) & Interface Segregation (ISP)
- **Konteks:** Pada validasi KRS, berhenti di kesalahan pertama membuat mahasiswa harus bolak-balik submit. Di sisi lain, menyatukan semua aksi akademik ke satu interface besar `IAktivitasAkademik` akan memaksa `Mahasiswa` memiliki method `inputNilai()`.
- **Keputusan:**
  1. `KRSValidator` mengembalikan objek `ValidationResult` yang menampung seluruh daftar pesan error spesifik sekaligus.
  2. Memecah interface peran sesuai **ISP** menjadi `IPengisiKRS` (untuk `Mahasiswa`), serta `IPenyetujuKRS` dan `IPenilai` (untuk `Dosen`).
- **Alternatif & Trade-off:**
  - *Alternatif A (Fail-fast boolean / exception pertama):* Lebih cepat berhenti, tetapi pengalaman pengguna (UX) buruk saat masa pengisian KRS padat.
  - *Alternatif B (Satu interface `IAktivitasAkademik`):* Mengurangi jumlah interface, tetapi melanggar ISP dan membahayakan keamanan peran.
- **Konsekuensi:** (+) Pesan error informatif & langsung dapat ditindaklanjuti; setiap peran hanya mengimplementasikan kontrak yang relevan. (-) Sedikit tambahan kode untuk agregasi list error.
- **Pattern & Prinsip:** **ISP**, Defensive Error Handling.

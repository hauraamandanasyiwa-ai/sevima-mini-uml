# SEVIMA-Mini — Desain Sistem Akademis dengan UML (Materi 1 · Minggu 1 & 2)

Repositori ini berisi paket desain arsitektur lengkap sistem informasi akademik **SEVIMA-Mini** untuk mata kuliah **Pemrograman Berorientasi Objek (OOP)** dengan pendekatan **AI-First Development**.

- **Minggu 1 (Eksplorasi & Prompt Engineering):** Analisis domain 6 modul akademik, iterasi prompt awal, dan Class Diagram v1.
- **Minggu 2 (Refinement & Skenario):** Pembuatan *Use Case Diagram*, *Sequence Diagram* (PMB & Validasi KRS dengan *alternate flow*), audit kritik mandiri AI, refactoring *God Object* & prinsip **SOLID** lengkap (SRP, OCP, LSP, ISP, DIP), penerapan pola **Factory + Observer + Strategy**, sinkronisasi seluruh diagram, serta dokumentasi **ADR** & **Final UML PDF**.

---

## Struktur Repositori

```text
.
├── diagrams/
│   ├── class-diagram.mmd                   # Class Diagram final Minggu 2 (SOLID, Factory, Observer, Strategy)
│   ├── usecase-diagram.mmd                 # Use Case Diagram (Aktor peran, System Boundary, include/extend)
│   ├── sequence-pmb.mmd                    # Sequence Diagram PMB (Factory, Async Notification, Alternate Flow)
│   ├── sequence-krs.mmd                    # Sequence Diagram Validasi KRS (Loop, Self-call, Alternate Flow)
│   └── before-after/
│       ├── class-diagram-week1-before.mmd  # Baseline Class Diagram Minggu 1 (sebelum refactor Minggu 2)
│       ├── before-class-diagram-w1.png     # Screenshot visual Before (Minggu 1)
│       └── after-class-diagram-w2.png      # Screenshot visual After (Minggu 2)
├── prompts/
│   └── ai-usage-log.md                     # 12 prompt terbaik (Minggu 1 & 2), Before/After, refleksi OPAR
├── docs/
│   ├── domain-analysis.md                  # Analisis kata benda & kata kerja (Minggu 1)
│   ├── ADR-architecture-decisions.md       # Sumber teks ADR-001 s.d. ADR-007
│   ├── ADR-architecture-decisions.pdf      # Architecture Decision Record final (PDF)
│   └── Final-UML-diagram.pdf               # Paket seluruh UML Diagram final (PDF)
└── README.md                               # Ringkasan desain, checklist deliverable & preview diagram
```

---

## Ringkasan Deliverables & Bobot Penilaian (Minggu 2)

| Deliverable | Bobot | File Utama | Status | Ringkasan |
| :--- | :---: | :--- | :---: | :--- |
| **Class Diagram (Revisi)** | **35%** | [`diagrams/class-diagram.mmd`](diagrams/class-diagram.mmd) | Selesai | Bebas *God Object* (< 10 method/class), SOLID lengkap (SRP, OCP, LSP, ISP, DIP), **Factory (`UserFactory`)**, **Observer (`EventBus` + `IEventSubscriber`)**, **Strategy (`IValidationRule`)**, sinkron 100% dengan Sequence Diagram. |
| **Use Case Diagram** | **20%** | [`diagrams/usecase-diagram.mmd`](diagrams/usecase-diagram.mmd) | Selesai | Aktor: Calon Mahasiswa, Mahasiswa, Dosen Pengampu, Dosen PA, Admin Akademik, Sistem PMB, Layanan Bank. Lengkap dengan `<<include>>` dan `<<extend>>` berarah panah valid. |
| **Sequence Diagram** | **25%** | [`diagrams/sequence-pmb.mmd`](diagrams/sequence-pmb.mmd)<br>[`diagrams/sequence-krs.mmd`](diagrams/sequence-krs.mmd) | Selesai | 2 skenario utama (PMB & Validasi KRS) lengkap dengan `loop`, *self-call*, pesan asinkron (`-)`), dan **`alt` (*alternate flow* / error handling spesifik)**. |
| **AI Usage Documentation** | **15%** | [`prompts/ai-usage-log.md`](prompts/ai-usage-log.md) | Selesai | 6 prompt terbaik Minggu 2 (+ 6 Minggu 1), perbandingan *Before vs After*, bukti visual screenshot, dan refleksi **OPAR**. |
| **ADR (PDF)** | **5%** | [`docs/ADR-architecture-decisions.pdf`](docs/ADR-architecture-decisions.pdf) | Selesai | 7 keputusan arsitektur (ADR-001 s.d. ADR-007) lengkap dengan Konteks, Keputusan, Alternatif & Trade-off, Konsekuensi (+/-), dan Pattern. |
| **Final UML PDF** | Wajib | [`docs/Final-UML-diagram.pdf`](docs/Final-UML-diagram.pdf) | Selesai | Kompilasi rapi Class Diagram, Use Case Diagram, Sequence PMB, dan Sequence KRS dalam satu dokumen PDF siap kumpul di EdLink. |

---

## Preview Diagram UML (Mermaid)

### 1. Use Case Diagram (`diagrams/usecase-diagram.mmd`)

```mermaid
flowchart LR
    CalonMahasiswa(["[Aktor] Calon Mahasiswa"])
    Mahasiswa(["[Aktor] Mahasiswa"])
    DosenPengampu(["[Aktor] Dosen Pengampu"])
    DosenPA(["[Aktor] Dosen PA"])
    Admin(["[Aktor] Admin Akademik"])
    SistemPMB(["[Sistem] Sistem PMB"])
    BankGateway(["[Sistem] Layanan Pembayaran Bank"])

    subgraph SEVIMA_Mini ["System Boundary: SEVIMA-Mini"]
        direction TB
        UC_Daftar(["Daftar Calon Mahasiswa"])
        UC_Unggah(["Unggah Berkas PMB"])
        UC_Verif(["Verifikasi Berkas PMB"])
        UC_NIM(["Terbitkan NIM & Akun"])

        UC_IsiKRS(["Isi KRS"])
        UC_CekPrasyarat(["Cek Prasyarat Mata Kuliah"])
        UC_CekSKS(["Cek Batas Maks 24 SKS"])
        UC_CekBentrok(["Cek Jadwal Bentrok"])
        UC_ApproveKRS(["Approve KRS"])
        UC_RevisiKRS(["Ajukan Revisi KRS"])

        UC_InputNilai(["Input Nilai"])
        UC_Transkrip(["Generate Transkrip"])
        UC_KelolaJadwal(["Kelola Mata Kuliah & Jadwal"])
        UC_Presensi(["Catat Presensi QR"])

        UC_BayarSPP(["Bayar SPP"])
        UC_BayarDenda(["Bayar Denda Keterlambatan"])
    end

    CalonMahasiswa --- UC_Daftar
    SistemPMB --- UC_Daftar
    SistemPMB --- UC_Verif
    Admin --- UC_Verif
    Admin --- UC_KelolaJadwal

    Mahasiswa --- UC_IsiKRS
    Mahasiswa --- UC_RevisiKRS
    Mahasiswa --- UC_Transkrip
    Mahasiswa --- UC_Presensi
    Mahasiswa --- UC_BayarSPP

    DosenPA --- UC_ApproveKRS
    DosenPengampu --- UC_InputNilai
    DosenPengampu --- UC_Presensi

    BankGateway --- UC_BayarSPP

    UC_Daftar -. "«include»" .-> UC_Unggah
    UC_IsiKRS -. "«include»" .-> UC_CekPrasyarat
    UC_IsiKRS -. "«include»" .-> UC_CekSKS
    UC_IsiKRS -. "«include»" .-> UC_CekBentrok

    UC_NIM -. "«extend»<br/>[jika lulus seleksi]" .-> UC_Verif
    UC_RevisiKRS -. "«extend»<br/>[jika ditolak Dosen PA]" .-> UC_ApproveKRS
    UC_BayarDenda -. "«extend»<br/>[jika lewat jatuh tempo]" .-> UC_BayarSPP
```

---

### 2. Sequence Diagram — Pendaftaran Mahasiswa Baru / PMB (`diagrams/sequence-pmb.mmd`)

```mermaid
sequenceDiagram
    autonumber
    actor CalonMahasiswa as CalonMahasiswa
    actor Admin as Admin
    participant PMBService as PMBService
    participant PMBRepository as PMBRepository
    participant UserFactory as UserFactory
    participant NotificationService as NotificationService

    rect rgb(239, 246, 255)
        Note over CalonMahasiswa, PMBRepository: Tahap 1 — Pendaftaran Calon Mahasiswa Baru
        CalonMahasiswa->>+PMBService: daftarPMB(dataDiri, berkasPath)
        PMBService->>PMBService: validasiKelengkapanBerkas(dataDiri, berkasPath)

        alt Berkas lengkap dan format valid
            PMBService->>+PMBRepository: simpanPendaftar(calonMahasiswa)
            PMBRepository-->>-PMBService: noDaftar ("PMB-2026-001")
            PMBService-->>CalonMahasiswa: Konfirmasi pendaftaran berhasil + noDaftar
        else Berkas tidak lengkap atau format salah
            PMBService-->>-CalonMahasiswa: Error spesifik ("Ijazah/KTP belum diunggah atau format bukan PDF")
        end
    end

    rect rgb(240, 253, 244)
        Note over Admin, NotificationService: Tahap 2 — Verifikasi Admin, Factory Pattern & Notifikasi Asinkron
        Admin->>+PMBService: verifikasiBerkasPMB(noDaftar, statusLulus)
        PMBService->>+PMBRepository: cariPendaftarByNoDaftar(noDaftar)
        PMBRepository-->>-PMBService: objek CalonMahasiswa

        alt Berkas valid dan dinyatakan LULUS seleksi
            PMBService->>PMBService: generateNIM(tahun, kodeProdi, noUrut)
            PMBService->>+UserFactory: buatMahasiswaDariCalon(calon, nim)
            UserFactory-->>-PMBService: objek Mahasiswa (NIM & akun aktif)

            PMBService->>+PMBRepository: simpanMahasiswa(mahasiswa)
            PMBRepository-->>-PMBService: status tersimpan (OK)

            PMBService-)NotificationService: notifySubscribers("PMB_APPROVED", mahasiswa)
            PMBService-->>Admin: Verifikasi sukses (NIM diterbitkan)

            activate NotificationService
            NotificationService->>NotificationService: kirimEmailAkun(mahasiswa.email, nim, akun)
            alt Pengiriman email berhasil
                NotificationService-)CalonMahasiswa: Email selamat datang berisi NIM & kredensial akun
            else Pengiriman email gagal (SMTP timeout / jaringan error)
                NotificationService->>NotificationService: catatLogGagalDanJadwalkanRetry(mahasiswa.id)
            end
            deactivate NotificationService
        else Berkas tidak valid atau TIDAK LULUS seleksi
            PMBService->>+PMBRepository: updateStatusSeleksi(noDaftar, "DITOLAK", alasan)
            PMBRepository-->>-PMBService: status diperbarui
            PMBService-)NotificationService: notifySubscribers("PMB_REJECTED", calon, alasan)
            PMBService-->>-Admin: Status pendaftar ditandai DITOLAK
            NotificationService-)CalonMahasiswa: Email penolakan disertai alasan spesifik & panduan revisi
        end
    end
```

---

### 3. Sequence Diagram — Validasi & Pengajuan KRS (`diagrams/sequence-krs.mmd`)

```mermaid
sequenceDiagram
    autonumber
    actor Mahasiswa as Mahasiswa
    participant KRSManager as KRSManager
    participant KRSValidator as KRSValidator
    participant AkademikRepository as AkademikRepository
    participant NotificationService as NotificationService
    actor DosenPA as DosenPA

    Mahasiswa->>+KRSManager: submitKRS(mahasiswa, daftarCourse)
    KRSManager->>+KRSValidator: validasiKRS(mahasiswa, daftarCourse)

    KRSValidator->>+AkademikRepository: getRiwayatNilaiLulus(mahasiswa.nim)
    AkademikRepository-->>-KRSValidator: daftarCourseLulus

    KRSValidator->>+AkademikRepository: getEnrollmentAktif(mahasiswa.nim, semesterAktif)
    AkademikRepository-->>-KRSValidator: daftarEnrollmentAktif

    loop Untuk setiap Course dalam daftarCourse
        KRSValidator->>KRSValidator: cekPrasyarat(course, daftarCourseLulus)
        KRSValidator->>KRSValidator: cekDuplicateEnrollment(course, daftarEnrollmentAktif)
    end

    KRSValidator->>KRSValidator: hitungTotalSKS(daftarCourse, daftarEnrollmentAktif)
    KRSValidator->>KRSValidator: cekJadwalBentrok(daftarCourse, daftarEnrollmentAktif)

    KRSValidator-->>-KRSManager: ValidationResult(isValid, daftarError)

    alt Semua validasi LOLOS (daftarError kosong)
        KRSManager->>+AkademikRepository: simpanEnrollment(mahasiswa, daftarCourse, "PENDING_APPROVAL")
        AkademikRepository-->>-KRSManager: daftarEnrollmentTersimpan
        KRSManager-)NotificationService: notifySubscribers("KRS_SUBMITTED", mahasiswa, dosenPA)
        KRSManager-->>Mahasiswa: KRS berhasil diajukan (Status: PENDING_APPROVAL)
        activate NotificationService
        NotificationService-)DosenPA: Notifikasi asinkron: Mahasiswa mengajukan KRS untuk direview
        deactivate NotificationService
    else Prasyarat mata kuliah belum lulus
        KRSManager-->>Mahasiswa: KRS Ditolak — Prasyarat belum lulus (sebutkan mata kuliah prasyarat)
    else Total SKS melebihi batas maksimal 24 SKS
        KRSManager-->>Mahasiswa: KRS Ditolak — Total SKS melebihi batas (misal: 26 SKS > batas 24 SKS)
    else Terjadi bentrok jadwal perkuliahan
        KRSManager-->>Mahasiswa: KRS Ditolak — Jadwal bentrok (sebutkan pasangan mata kuliah & jam)
    else Terdapat lebih dari satu pelanggaran sekaligus (Multiple Errors)
        KRSManager-->>-Mahasiswa: KRS Ditolak — Kembalikan seluruh daftarError spesifik sekaligus
    end
```

---

### 4. Class Diagram Final (`diagrams/class-diagram.mmd`)

Lihat sumber lengkap di [`diagrams/class-diagram.mmd`](diagrams/class-diagram.mmd) (perbandingan dengan Minggu 1 tersedia di [`diagrams/before-after/`](diagrams/before-after/)).

---

## Kesiapan Implementasi Minggu 3 (Modul PMB)
Desain `PMBService`, `PMBRepository`, `UserFactory`, dan `sequence-pmb.mmd` siap langsung diturunkan menjadi kode program (skema tabel pendaftar, endpoint `register` & `approve`, generator NIM `tahun + kodeProdi + noUrut`, validasi input, dan unit test) mulai Minggu ke-3.

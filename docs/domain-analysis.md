# Analisis Domain Sistem Akademis — SEVIMA-Mini

Dokumen ini merupakan hasil **Step 1: Pahami Domain** untuk perancangan arsitektur sistem informasi akademik **SEVIMA-Mini** sebelum proses *prompt engineering* Class Diagram dilakukan.

---

## 1. Gambaran Modul SEVIMA-Mini

Sistem akademik SEVIMA-Mini terdiri atas **6 modul utama**:

1. **PMB (Penerimaan Mahasiswa Baru)**: Calon mahasiswa mendaftar, mengunggah berkas persyaratan, diverifikasi oleh Admin, dan bila lulus seleksi akan dibuatkan objek `Mahasiswa` baru beserta NIM otomatis.
2. **KRS (Kartu Rencana Studi)**: Mahasiswa memilih mata kuliah untuk semester aktif dengan validasi aturan bisnis (maksimal 24 SKS, lulus prasyarat mata kuliah, tidak ada jadwal bentrok, tidak ada pendaftaran ganda / *double enrollment*), lalu menunggu persetujuan Dosen Pembimbing Akademik (PA).
3. **Jadwal & Ruangan**: Pengelolaan hari, jam mulai, jam selesai, ruangan kelas, dan dosen pengampu; digunakan untuk deteksi bentrok jadwal dan sesi presensi.
4. **Nilai & Transkrip**: Dosen menginput nilai angka pada setiap pengambilan mata kuliah (`Enrollment`), sistem mengonversi nilai huruf dan bobot, lalu menghitung IPS, IPK, serta menghasilkan transkrip PDF.
5. **Keuangan / Pembayaran SPP**: Pencatatan tagihan SPP per semester, jumlah tagihan, tanggal pembayaran, dan status (`Lunas` atau `Menunggak`).
6. **Presensi QR Code**: Dosen membuat kode QR untuk sesi jadwal perkuliahan hari itu, mahasiswa melakukan scan QR, sistem memvalidasi jadwal aktif, mencatat kehadiran (`Attendance`), dan mengirim notifikasi ke dosen.

---

## 2. Analisis Kata Benda & Kata Kerja

Sesuai panduan perancangan OOP, kebutuhan sistem dipecah menjadi **kata benda** (kandidat *class* atau *atribut*) dan **kata kerja** (kandidat *method*).

| Modul | Kalimat Requirement | Kata Benda (Kandidat Class / Atribut) | Kata Kerja (Kandidat Method) |
| :--- | :--- | :--- | :--- |
| **PMB** | Calon mahasiswa mendaftar melalui PMB, mengunggah berkas, lalu Admin memverifikasi berkas dan sistem menerbitkan NIM serta akun Mahasiswa baru. | `CalonMahasiswa`, `Admin`, `Mahasiswa`, berkas, noDaftar, statusSeleksi, NIM | `daftarPMB()`, `unggahBerkas()`, `verifikasiBerkasPMB()`, `generateNIM()`, `buatDariCalon()` |
| **KRS** | Mahasiswa mengisi KRS maksimal 24 SKS, harus lulus mata kuliah prasyarat, bebas bentrok jadwal, tidak double enrollment, dan disetujui Dosen PA. | `Mahasiswa`, `Course`, `Enrollment`, `KRSValidator`, `IValidationRule`, `Dosen`, kode, SKS, prasyarat, semester, status | `isiKRS()`, `validasiKRS()`, `validate()`, `ajukan()`, `approveKRS()`, `tolakKRS()` |
| **Jadwal & Ruang** | Setiap mata kuliah memiliki jadwal (hari, jam mulai, jam selesai, ruangan) yang diampu oleh seorang Dosen dalam naungan Program Studi. | `Course`, `Schedule`, `Dosen`, `ProgramStudi`, hari, jamMulai, jamSelesai, ruangan | `kelolaJadwal()`, `isBentrokDengan()`, `getInfoJadwal()` |
| **Nilai & Transkrip** | Dosen menginput nilai pada enrollment mahasiswa; sistem menghitung IPS, IPK, dan mencetak transkrip PDF. | `Dosen`, `Enrollment`, `Grade`, `TranscriptService`, nilaiAngka, nilaiHuruf, bobot, IPK | `inputNilai()`, `konversiHuruf()`, `hitungIPS()`, `hitungIPK()`, `generateTranskripPDF()`, `lihatTranskrip()` |
| **SPP / Keuangan** | Mahasiswa memiliki tagihan pembayaran SPP per semester dengan status lunas atau menunggak. | `Mahasiswa`, `Payment`, semester, jumlah, tanggalBayar, status | `bayar()`, `isLunas()` |
| **Presensi QR** | Dosen membuat QR presensi sesuai jadwal, mahasiswa melakukan scan QR, sistem memvalidasi jadwal, mencatat kehadiran, dan mengirim notifikasi ke dosen. | `Dosen`, `Mahasiswa`, `Schedule`, `Attendance`, `NotificationService`, kodeQR, waktuScan, statusHadir | `buatQRPresensi()`, `scanQRPresensi()`, `catatKehadiran()`, `kirimNotifikasi()` |

### Penyaringan Kandidat Class vs Atribut
Tidak semua kata benda layak menjadi *class*. Kriteria penentuan: **apakah entitas memiliki data dan perilaku sendiri?**
- **Layak jadi Atribut**: `nim`, `nidn`, `sks`, `ipk`, `noDaftar`, `statusSeleksi`, `ruangan`, `nilaiHuruf`, `kodeQR`.
- **Layak jadi Class**: `User` (abstract), `Mahasiswa`, `Dosen`, `Admin`, `CalonMahasiswa`, `ProgramStudi`, `Course`, `Enrollment`, `Schedule`, `Grade`, `Payment`, `Attendance`, serta class layanan/pola desain untuk mematuhi SOLID (`KRSValidator`, `IValidationRule` + implementasinya, `TranscriptService`, `INotificationService` + `NotificationService`, `MahasiswaFactory`).

---

## 3. Identifikasi Entitas Utama & Relasi

### A. Hierarki User (Inheritance & Abstraction)
- `User` dibuat **`<<abstract>>`** karena tidak ada pengguna sistem tanpa peran spesifik.
- Atribut bersama naik ke `User`: `#id`, `#nama`, `#email`, `#username`, `-password` (**wajib private** demi *encapsulation*).
- Method bersama: `+login()`, `+logout()`, dan method abstrak `+tampilkanDashboard()*` (**polymorphism**).
- Turunan (`is-a`): `Mahasiswa`, `Dosen`, `Admin`, `CalonMahasiswa`.
- **Catatan Transisi PMB**: Saat `CalonMahasiswa` dinyatakan diterima, objek tidak dapat berganti *class* di runtime OOP. Oleh karena itu, `MahasiswaFactory` membuat objek `Mahasiswa` baru dan menyimpan atribut `-calonMahasiswaId` sebagai jejak keterkaitannya.

### B. Lima Class Inti & Relasinya
1. **`Course`**: Memiliki self-association ke `Course` lain untuk aturan prasyarat (`0..* --> 0..*`).
2. **`Enrollment`**: Memecah relasi *many-to-many* antara `Mahasiswa` dan `Course` menjadi dua relasi *one-to-many* (`Mahasiswa 1 --> 0..* Enrollment` dan `Course 1 --> 0..* Enrollment`).
3. **`Schedule`**: Terikat kuat (*Composition*) dengan `Course` (`Course 1 *-- 1..* Schedule`), dan diampu oleh `Dosen` (`Dosen 1 --> 0..* Schedule`).
4. **`Grade`**: Terikat kuat (*Composition*) pada `Enrollment` (`Enrollment 1 *-- 0..1 Grade`), **bukan** langsung ke `Mahasiswa`, karena nilai selalu milik satu mahasiswa pada satu mata kuliah di satu semester tertentu.
5. **`Payment`**: Berasosiasi dengan `Mahasiswa` (`Mahasiswa 1 --> 0..* Payment`).

### C. Pengujian Composition vs Aggregation
Uji cepat: *"Jika wadah dihapus, apakah bagian ikut mati?"*
- **Ya (`*--` Composition)**:
  - `Enrollment *-- Grade`: Jika pengambilan mata kuliah dibatalkan/dihapus, nilainya tidak bermakna dan ikut hilang.
  - `Course *-- Schedule`: Jadwal kelas selalu milik suatu mata kuliah.
  - `Schedule *-- Attendance`: Data presensi sesi kelas bergantung pada eksistensi jadwal sesi tersebut.
- **Tidak (`o--` Aggregation)**:
  - `ProgramStudi o-- Dosen`: Jika sebuah program studi ditutup/dilebur, dosen tetap ada dan dapat dipindahkan ke prodi lain.
  - `ProgramStudi o-- Mahasiswa`: Data mahasiswa tetap eksis walaupun prodi mengalami restrukturisasi.
  - `KRSValidator o-- IValidationRule`: Aturan validasi bersifat independen dan dapat dipasang/dilepas secara dinamis (*Strategy Pattern*).

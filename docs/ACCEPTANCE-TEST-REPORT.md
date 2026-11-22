# Laporan Acceptance Test End-to-End — Minggu 10 (Final Modul Nilai & Transkrip)

## Ringkasan Skenario (`tests/test_acceptance_e2e.py`)

Pengujian penerimaan dari ujung ke ujung memverifikasi bahwa seluruh modul SEVIMA Mini (Minggu 5–10) bekerja terpadu tanpa celah:

| Tahap | Modul Terlibat | Aksi yang Diuji | Hasil yang Diverifikasi |
|---|---|---|---|
| 1 | KRS + Jadwal | KRS mahasiswa `20240001` berstatus `approved` mengambil kelas `IF202-A` dengan jadwal aktif | Jadwal tersimpan (`201`), KRS aktif |
| 2 | Observer + Outbox + Integrasi KRS | Admin memindahkan jadwal `IF202-A` ke Rabu 13:00–14:40 | `SEQUENCE` naik ke `1`, KRS otomatis kembali ke `revision` (aktor `system`), log 3 kanal (`email`, `sms`, `push`) terkirim setelah `commit` |
| 3 | Business Rules Nilai | Dosen mencoba input nilai dengan presensi `65%` (< 75%) | Ditolak dengan `HTTP 400` |
| 4 | Grade Management + GPA Calculator | Input nilai `IF101` semester `20242` (`C`) lalu mengulang di `20251` (`A`), plus `IF202` (`B`) | IPK otomatis mengambil nilai tertinggi `IF101` (`A`), total SKS lulus = `6`, IPK = `3.50` (`Cum Laude`) |
| 5 | Audit Trail (`grade_history`) | Dosen mengedit nilai `IF202` dari `B` ke `A-` dengan alasan | IPK otomatis naik ke `3.85`, 1 baris audit trail tercatat di `/grades/history/20240001` |
| 6 | Transcript PDF / HTML / CSV & iCalendar | Mengunduh `/transcripts/20240001/pdf`, `/html`, `/csv`, dan `/schedules/export.ics` | PDF valid (`%PDF-`), HTML menampilkan `TRANSKRIP AKADEMIK` & IPK `3.85`, CSV valid, `.ics` memuat `SEQUENCE:1` |

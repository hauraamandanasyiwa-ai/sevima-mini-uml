# OPAR — Minggu 10 (Finalisasi Modul Nilai & Transkrip + Acceptance Test E2E)

## O — Objective
Menuntaskan sesi 9–10 (Modul Nilai & Transkrip) dengan menambahkan acceptance test end-to-end lintas modul (KRS → Jadwal & Notifikasi → Nilai & Audit Trail → GPA → Transkrip PDF/HTML/CSV) serta memverifikasi seluruh kriteria sukses.

## P — Plan
1. Menyusun skenario acceptance test lintas modul di `tests/test_acceptance_e2e.py`.
2. Mendokumentasikan laporan acceptance test di `docs/ACCEPTANCE-TEST-REPORT.md`.
3. Memverifikasi seluruh test suite Minggu 5–10 lulus 100%.

## A — Action
- Menulis `tests/test_acceptance_e2e.py`, `docs/ACCEPTANCE-TEST-REPORT.md`, dan memperbarui versi aplikasi ke `0.10.0`.
- Menjalankan `python -m pytest -v` di `MINGGUUUU 10`.

## R — Reflection
- Acceptance test dari ujung ke ujung memastikan tidak ada kontradiksi kontrak antar modul yang dibangun di minggu berbeda (mis. perubahan jadwal menginvalidasi KRS, sinkronisasi `grades` ke `krs_detail.nilai`, dan ekspor PDF/HTML/CSV/`.ics`).

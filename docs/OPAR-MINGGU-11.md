# OPAR — Minggu 11 (Modul Keuangan / SPP)

## O — Objective
Membangun Modul Keuangan (SPP) pada SIMAK Mini dengan 5 deliverable utama:
1. Payment Schema (`payment_method`, `billing`, `payment`; status `unpaid`, `partial`, `paid`, `overdue`).
2. Billing Service (generate tagihan SPP per semester sesuai prodi + APScheduler, pembayaran manual/webhook atomik, denda keterlambatan, dan blokir KRS jika menunggak).
3. Dashboard Keuangan real-time (per mahasiswa, collection rate per prodi, grafik pembayaran per bulan).
4. Payment Webhook Simulation (verifikasi signature HMAC-SHA256, `unpaid -> paid`, email receipt).
5. AI Financial Insights (analisis CSV `nim,jumlah,tanggal,status` -> JSON laporan ringkas).

## P — Plan
1. Tambah model ORM `PaymentMethod`, `Billing`, `Payment` (`app/models/billing.py`) & hierarki `BillingError` + `BillingArrearsError`.
2. Bangun `billing_service.py`, `billing_scheduler.py` (APScheduler), `ai_financial_report.py`, dan integrasikan `has_unpaid_arrears()` ke `KRSManager`.
3. Bangun router `app/routers/billing.py` dan UI real-time `app/static/finance_dashboard.html`.
4. Buat `sql/migration_minggu_11.sql` dan suite test `tests/test_minggu_11.py`.

## A — Action
- Menginstall `apscheduler`, mengimplementasikan seluruh komponen Minggu 11, dan menjalankan `python -m pytest -v` untuk seluruh test suite Minggu 5–11.

## R — Reflection
- Memakai `transaction_id` unik untuk idempotensi webhook dan `hmac.compare_digest` untuk verifikasi signature adalah fondasi keamanan & keandalan integrasi payment gateway di dunia nyata.

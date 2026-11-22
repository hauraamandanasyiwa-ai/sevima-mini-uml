# ADR-006: Modul Keuangan (SPP), Webhook HMAC, APScheduler, & Blokir KRS Tunggakan

**Status:** Diterima (Minggu 11)  
**Konteks:** Menambahkan Modul Keuangan (SPP) pada SIMAK Mini yang mencakup manajemen tagihan per semester, pembayaran manual & webhook gateway, cron job otomatis, blokir KRS untuk mahasiswa menunggak, dashboard real-time, serta AI Financial Insights.

## Keputusan 1: Atomisitas & Idempotensi Pembayaran (`process_payment` + Webhook)
- Setiap pemrosesan pembayaran mengunci baris `billing` (`with_for_update()`), menyisipkan baris `payment`, memperbarui `paid_amount` dan `status` (`partial` jika `paid_amount < total`, `paid` jika `paid_amount >= total`), lalu `commit()` **sekali**.
- Kolom `payment.transaction_id` dibuat `UNIQUE` sehingga replay webhook dari payment gateway tidak pernah menimbulkan double-charge.
- Receipt email dikirim melalui `LogChannel("email")` **setelah `commit()`** dengan kunci idempotensi `receipt:{transaction_id}`.

## Keputusan 2: Keamanan Webhook dengan HMAC-SHA256
- Endpoint `POST /billing/webhook/payment` memverifikasi header `X-Webhook-Signature` terhadap `raw_body` memakai `hmac.compare_digest` (tahan *timing attack*). Signature yang tidak valid ditolak dengan HTTP `401 Unauthorized`.

## Keputusan 3: Integrasi Blokir KRS pada `KRSManager`
- `KRSManager.add_course()` dan `KRSManager.submit_krs()` memanggil `has_unpaid_arrears(session, nim)` sebelum mengizinkan transaksi KRS.
- Mahasiswa yang memiliki tagihan berstatus `overdue` atau melewati `due_date` ditolak dengan `BillingArrearsError` (HTTP `403 Forbidden`). Begitu tagihan dilunasi (`status == paid`), akses pengisian KRS otomatis terbuka kembali.

## Keputusan 4: APScheduler untuk Cron Semester & Reminder Harian
- Menggunakan `APScheduler` (`BackgroundScheduler` + `CronTrigger`) yang dimulai pada `lifespan` startup dan dimatikan bersih saat shutdown untuk menjalankan `semester_billing_generator` (tiap awal semester) dan `daily_overdue_reminder` (tiap pagi pukul 07:00).

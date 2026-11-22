# SIMAK Mini — Modul Keuangan / SPP (Minggu 11)

Implementasi terintegrasi **SEVIMA Mini** (KRS Minggu 5–6 + Jadwal & Ruang Minggu 7–8 + Nilai & Transkrip Minggu 9–10 + **Modul Keuangan SPP Minggu 11**) menggunakan **FastAPI**, **SQLAlchemy 2.0**, **Pydantic v2**, **ReportLab**, dan **APScheduler**.

## Ringkasan Deliverable Minggu 11

1. **Payment Schema (25%)** — `app/models/billing.py`, `sql/migration_minggu_11.sql`
   - 3 tabel: `payment_method`, `billing`, `payment`.
   - 4 status resmi: `unpaid`, `partial`, `paid`, `overdue`.

2. **Billing Service & APScheduler (35%)** — `app/services/billing_service.py`, `app/services/billing_scheduler.py`, `app/services/krs_manager.py`
   - `generate_billing(semester, semester_start)`: tarif berdasarkan prodi (Teknik Rp 5.000.000, Ekonomi Rp 4.000.000), `due_date` 14 hari setelah awal semester, status awal `unpaid`, idempoten.
   - Cron job **APScheduler** (`semester_billing_generator` tiap awal semester & `daily_overdue_reminder` harian).
   - `process_payment()`: transaksi database atomik (`paid_amount < total` → `partial`, `>= total` → `paid`), idempoten pada `transaction_id`.
   - Perhitungan denda keterlambatan (`Rp 50.000/minggu`, maks 20% pokok) & **Block KRS otomatis** (`BillingArrearsError`, HTTP 403) jika mahasiswa memiliki tunggakan.

3. **Dashboard Keuangan Real-Time (20%)** — `app/routers/billing.py`, `app/static/finance_dashboard.html`
   - Halaman real-time di `http://127.0.0.1:8000/finance-dashboard`: ringkasan per mahasiswa (`total_tagihan`, `sudah_bayar`, `sisa`), `collection_rate` per program studi, grafik pembayaran per bulan, tombol bayar manual, simulasi webhook, dan trigger reminder.

4. **Payment Webhook Simulation (15%)** — `POST /billing/webhook/payment`
   - Verifikasi keamanan signature **HMAC-SHA256** (`X-Webhook-Signature`), update status billing `unpaid -> paid`, kirim receipt via email (`LogChannel`), dan return `200 OK`.

5. **AI Financial Report (5%)** — `app/services/ai_financial_report.py`, `GET /billing/ai-insights`, `POST /billing/ai-insights/csv`
   - Menganalisis CSV (`nim,jumlah,tanggal,status`) menjadi laporan JSON: `total_revenue_bulan_ini`, `collection_rate`, `top_10_tunggakan`, dan `rekomendasi` reminder untuk tunggakan >2 bulan.

## Cara Menjalankan

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Buka di browser:
- **Dashboard Keuangan SPP (Minggu 11):** `http://127.0.0.1:8000/finance-dashboard`
- **Portal Nilai & Transkrip (Minggu 9–10):** `http://127.0.0.1:8000/grades-portal`
- **Conflict Resolver (Minggu 8):** `http://127.0.0.1:8000/conflict-resolver`
- **Swagger API Docs:** `http://127.0.0.1:8000/docs`

### Contoh Uji Webhook dengan `curl` (PowerShell)
```powershell
$body = '{"billing_id":3,"transaction_id":"CURL-TRX-001","amount":5100000,"status":"paid","method":"VA_BCA"}'
$sig = python -c "import hmac,hashlib; print(hmac.new(b'simak-webhook-secret-2025', r'''$body'''.encode(), hashlib.sha256).hexdigest())"
curl.exe -X POST http://127.0.0.1:8000/billing/webhook/payment -H "Content-Type: application/json" -H "X-Webhook-Signature: $sig" -d $body
```

### Menjalankan Seluruh Test Suite

```powershell
python -m pytest -v
```

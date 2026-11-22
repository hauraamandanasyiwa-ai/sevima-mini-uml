import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.exceptions import BillingArrearsError, InvalidWebhookSignatureError
from app.models.billing import Billing, BillingStatus
from app.models.mahasiswa import Mahasiswa
from app.observers.channels import LogChannel, NotificationLogEntry
from app.services.ai_financial_report import generate_financial_insights_from_csv
from app.services.billing_scheduler import build_billing_scheduler
from app.services.billing_service import (
    BillingService,
    compute_webhook_signature,
)
from app.services.krs_manager import KRSManager


def test_generate_billing_by_prodi_due_date_and_idempotency(db_session: Session) -> None:
    """Step 1: Teknik = 5jt, Ekonomi = 4jt, due_date = +14 hari, status awal 'unpaid', idempoten."""
    db_session.add(
        Mahasiswa(
            nim="20240010",
            nama="Andi Ekonomi",
            prodi="Ekonomi Manajemen",
            dosen_pa_id="PA002",
        )
    )
    db_session.commit()

    service = BillingService(session=db_session)
    sem_start = date(2025, 9, 1)
    created = service.generate_billing(semester="20251", semester_start=sem_start)

    assert len(created) == 3  # Budi (Teknik), Siti (Teknik), Andi (Ekonomi)
    by_nim = {b.nim: b for b in created}
    assert by_nim["20240001"].amount == Decimal("5000000.00")
    assert by_nim["20240010"].amount == Decimal("4000000.00")
    assert all(b.due_date == date(2025, 9, 15) for b in created)
    assert all(b.status == BillingStatus.UNPAID for b in created)

    # Panggil ulang untuk semester sama -> idempoten (0 tagihan ganda)
    second = service.generate_billing(semester="20251", semester_start=sem_start)
    assert second == []


def test_payment_workflow_partial_paid_late_fee_and_receipt_email(db_session: Session) -> None:
    """Step 2: partial -> paid, denda keterlambatan, dan receipt email terkirim."""
    history: list[NotificationLogEntry] = []
    email_ch = LogChannel("email", shared_history=history)
    service = BillingService(session=db_session, email_channel=email_ch)

    bills = service.generate_billing(semester="20251", semester_start=date(2025, 9, 1))
    budi_bill = next(b for b in bills if b.nim == "20240001")

    # Simulasikan terlambat 10 hari setelah due_date (2025-09-15 -> 2025-09-25 = 2 minggu = Rp 100.000)
    overdue = service.mark_overdue_and_calculate_fees(as_of_date=date(2025, 9, 25))
    assert any(b.id == budi_bill.id for b in overdue)
    db_session.refresh(budi_bill)
    assert budi_bill.status == BillingStatus.OVERDUE
    assert budi_bill.denda == Decimal("100000.00")
    assert budi_bill.total == Decimal("5100000.00")

    # Cicilan pertama Rp 2.000.000 < 5.100.000 -> status 'partial'
    bill_after_1, pay_1, is_dup_1 = service.process_payment(
        billing_id=budi_bill.id,
        amount=Decimal("2000000.00"),
        method_code="QRIS",
        transaction_id="TRX-PARTIAL-01",
    )
    assert is_dup_1 is False
    assert bill_after_1.status == BillingStatus.PARTIAL
    assert bill_after_1.sisa == Decimal("3100000.00")

    # Pelunasan sisa Rp 3.100.000 -> status 'paid'
    bill_after_2, pay_2, is_dup_2 = service.process_payment(
        billing_id=budi_bill.id,
        amount=Decimal("3100000.00"),
        method_code="VA_BCA",
        transaction_id="TRX-LUNAS-02",
    )
    assert is_dup_2 is False
    assert bill_after_2.status == BillingStatus.PAID
    assert bill_after_2.sisa == Decimal("0.00")
    assert len(history) == 2
    assert all(entry.channel == "email" for entry in history)


def test_krs_blocked_when_student_has_overdue_arrears_and_unblocked_after_paid(
    db_session: Session,
) -> None:
    """Kriteria Sukses: Mahasiswa dengan tunggakan tidak bisa isi KRS;
    setelah melunasi SPP, mahasiswa bisa kembali mengisi KRS.
    """
    billing_svc = BillingService(session=db_session)
    krs_mgr = KRSManager(session=db_session)

    # Buat tagihan overdue untuk Budi (20240001)
    bill = Billing(
        nim="20240001",
        semester="20251",
        amount=Decimal("5000000.00"),
        denda=Decimal("50000.00"),
        paid_amount=Decimal("0.00"),
        due_date=date.today() - timedelta(days=10),
        status=BillingStatus.OVERDUE,
    )
    db_session.add(bill)
    db_session.commit()

    # Coba isi KRS -> DIBLOKIR dengan BillingArrearsError (HTTP 403)!
    with pytest.raises(BillingArrearsError, match="tunggakan SPP"):
        krs_mgr.add_course("20240001", "20251", "IF101")

    # Lunasi tagihan -> kini pengisian KRS berhasil!
    billing_svc.process_payment(
        billing_id=bill.id,
        amount=bill.total,
        method_code="VA_BCA",
        transaction_id="TRX-UNBLOCK-01",
    )
    detail = krs_mgr.add_course("20240001", "20251", "IF101")
    assert detail.kode_mk == "IF101"


def test_webhook_hmac_verification_idempotency_and_dashboard_api(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Kriteria Sukses: Webhook payment berfungsi (verifikasi signature HMAC,
    update status unpaid -> paid, kirim receipt email, idempoten) & Dashboard real-time.
    """
    r_gen = api_client.post(
        "/billing/generate",
        json={"semester": "20251", "semester_start": "2025-09-01"},
    )
    assert r_gen.status_code == 201
    budi_bill = next(b for b in r_gen.json() if b["nim"] == "20240001")

    webhook_payload = {
        "billing_id": budi_bill["id"],
        "transaction_id": "GW-WEBHOOK-999",
        "amount": 5000000,
        "status": "paid",
        "method": "VA_BCA",
    }
    raw_bytes = json.dumps(webhook_payload).encode("utf-8")

    # 1. Signature salah -> 401 Unauthorized
    r_bad = api_client.post(
        "/billing/webhook/payment",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": "invalid-signature",
        },
    )
    assert r_bad.status_code == 401

    # 2. Signature HMAC-SHA256 valid -> 200 OK & status billing jadi 'paid'
    valid_sig = compute_webhook_signature(raw_bytes)
    r_ok = api_client.post(
        "/billing/webhook/payment",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": valid_sig,
        },
    )
    assert r_ok.status_code == 200
    body = r_ok.json()
    assert body["billing_status"] == "paid"
    assert body["duplicate"] is False
    assert body["receipt_sent"] is True

    # 3. Replay webhook dengan transaction_id sama -> idempoten (duplicate=True, tidak double-charge)
    r_dup = api_client.post(
        "/billing/webhook/payment",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": valid_sig,
        },
    )
    assert r_dup.status_code == 200
    assert r_dup.json()["duplicate"] is True
    assert r_dup.json()["paid_amount"] == 5000000.0

    # 4. Dashboard Keuangan & Halaman HTML
    r_dash = api_client.get("/billing/dashboard")
    assert r_dash.status_code == 200
    dash = r_dash.json()
    assert dash["summary"]["total_terbayar"] == 5000000.0
    assert len(dash["per_mahasiswa"]) >= 2
    assert len(dash["per_prodi"]) >= 1
    assert len(dash["grafik_per_bulan"]) >= 1

    r_ui = api_client.get("/finance-dashboard")
    assert r_ui.status_code == 200
    assert "Dashboard Keuangan" in r_ui.text


def test_ai_financial_insights_from_csv_and_apscheduler_jobs() -> None:
    """Step 3: AI Financial Insights dari CSV + verifikasi cron jobs APScheduler."""
    csv_sample = (
        "nim,jumlah,tanggal,status\n"
        "20240001,5000000,2026-11-05,paid\n"
        "20240002,4000000,2026-11-10,paid\n"
        "20240003,5000000,2026-08-15,overdue\n"
        "20240004,3500000,2026-08-20,overdue\n"
        "20240005,2000000,2026-10-25,unpaid\n"
    )
    report = generate_financial_insights_from_csv(
        csv_sample,
        reference_date=date(2026, 11, 22),
    )

    assert report["total_revenue_bulan_ini"] == 9000000.0
    assert report["collection_rate_persen"] == 40.0
    assert report["top_10_tunggakan"][0]["nim"] == "20240003"
    assert report["top_10_tunggakan"][0]["tunggakan"] == 5000000.0
    assert report["jumlah_tunggakan_lebih_2_bulan"] == 2
    assert "Kirim reminder ke 2 mahasiswa dengan tunggakan >2 bulan" in report["rekomendasi"]

    # Verifikasi APScheduler memiliki 2 cron job terdaftar
    scheduler = build_billing_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert "semester_billing_generator" in job_ids
    assert "daily_overdue_reminder" in job_ids

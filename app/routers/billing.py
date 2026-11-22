import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.billing import Billing
from app.runtime import get_notification_runtime
from app.schemas.billing import (
    BillingOut,
    CSVInsightsInput,
    GenerateBillingInput,
    ManualPaymentInput,
    PaymentOut,
    WebhookPaymentPayload,
)
from app.services.ai_financial_report import (
    export_payment_csv_from_db,
    generate_financial_insights_from_csv,
)
from app.services.billing_service import BillingService, compute_webhook_signature

router = APIRouter(prefix="/billing", tags=["Finance & Billing SPP (Minggu 11)"])


def get_billing_service(db: Session = Depends(get_db)) -> BillingService:
    runtime = get_notification_runtime()
    email_channel = runtime.channels[0] if runtime.channels else None
    return BillingService(session=db, email_channel=email_channel)


def _to_billing_out(b: Billing) -> BillingOut:
    return BillingOut(
        id=b.id,
        nim=b.nim,
        nama=b.mahasiswa.nama if b.mahasiswa else b.nim,
        prodi=b.mahasiswa.prodi if b.mahasiswa else "-",
        semester=b.semester,
        amount=b.amount,
        denda=b.denda,
        total=b.total,
        paid_amount=b.paid_amount,
        sisa=b.sisa,
        due_date=b.due_date,
        status=b.status.value,
    )


@router.get("", response_model=list[BillingOut])
def list_billings(
    nim: Optional[str] = Query(default=None),
    semester: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    service: BillingService = Depends(get_billing_service),
) -> list[BillingOut]:
    """Menampilkan daftar seluruh tagihan SPP."""
    return [
        _to_billing_out(b)
        for b in service.list_billings(nim=nim, semester=semester, status=status_filter)
    ]


@router.post("/generate", response_model=list[BillingOut], status_code=status.HTTP_201_CREATED)
def generate_semester_billing(
    payload: GenerateBillingInput,
    service: BillingService = Depends(get_billing_service),
) -> list[BillingOut]:
    """Step 1: Generate tagihan SPP untuk semua mahasiswa aktif pada semester baru
    (Teknik 5jt, Ekonomi 4jt, jatuh tempo 14 hari setelah semester_start).
    """
    created = service.generate_billing(
        semester=payload.semester,
        semester_start=payload.semester_start,
    )
    return [_to_billing_out(b) for b in created]


@router.post("/{billing_id}/pay")
def record_manual_payment(
    billing_id: int,
    payload: ManualPaymentInput,
    service: BillingService = Depends(get_billing_service),
) -> dict[str, Any]:
    """Step 2: Mencatat pembayaran manual dalam satu transaksi atomik."""
    billing, payment, is_dup = service.process_payment(
        billing_id=billing_id,
        amount=payload.amount,
        method_code=payload.method_code,
        transaction_id=payload.transaction_id,
        source="manual",
        note=payload.note,
    )
    return {
        "duplicate": is_dup,
        "billing": _to_billing_out(billing),
        "payment": PaymentOut(
            id=payment.id,
            billing_id=payment.billing_id,
            transaction_id=payment.transaction_id,
            method_code=payment.method.code if payment.method else payload.method_code,
            amount=payment.amount,
            status=payment.status,
            source=payment.source,
            paid_at=payment.paid_at,
            note=payment.note,
        ),
    }


@router.post("/webhook/payment")
async def payment_gateway_webhook(
    request: Request,
    x_webhook_signature: str = Header(default="", alias="X-Webhook-Signature"),
    service: BillingService = Depends(get_billing_service),
) -> dict[str, Any]:
    """Deliverable 4: Endpoint Webhook Payment Gateway (simulasi).
    Memverifikasi HMAC-SHA256 `X-Webhook-Signature`, mencatat pembayaran secara
    atomik (`unpaid -> partial/paid`), mengirim receipt via email, dan return 200 OK.
    """
    raw_body = await request.body()
    payload = json.loads(raw_body.decode("utf-8"))
    return service.handle_webhook(
        raw_body=raw_body,
        payload=payload,
        signature=x_webhook_signature,
    )


@router.post("/webhook/simulate")
def simulate_gateway_webhook(
    payload: WebhookPaymentPayload,
    service: BillingService = Depends(get_billing_service),
) -> dict[str, Any]:
    """Helper simulasi gateway untuk tombol di Dashboard Keuangan (otomatis
    menghitung signature HMAC-SHA256 valid lalu memanggil `handle_webhook`).
    """
    body_dict = payload.model_dump(mode="json")
    raw_body = json.dumps(body_dict).encode("utf-8")
    sig = compute_webhook_signature(raw_body)
    return service.handle_webhook(raw_body=raw_body, payload=body_dict, signature=sig)


@router.post("/reminders/run")
def run_overdue_reminders(
    service: BillingService = Depends(get_billing_service),
) -> dict[str, Any]:
    """Menjalankan pengecekan tunggakan (update overdue + hitung denda) dan
    mengirim reminder email otomatis ke mahasiswa menunggak.
    """
    sent = service.send_overdue_reminders()
    return {"total_reminders": len(sent), "reminders": sent}


@router.get("/dashboard")
def get_finance_dashboard(
    service: BillingService = Depends(get_billing_service),
) -> dict[str, Any]:
    """Deliverable 3: Data real-time Dashboard Keuangan (per mahasiswa, per prodi,
    grafik pembayaran per bulan).
    """
    return service.get_dashboard_summary()


@router.get("/ai-insights")
def get_ai_financial_insights(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Deliverable 5: AI Financial Report (otomatis mengekspor CSV dari DB dan
    menghasilkan JSON insights untuk dashboard frontend).
    """
    csv_text = export_payment_csv_from_db(db)
    return generate_financial_insights_from_csv(csv_text)


@router.post("/ai-insights/csv")
def analyze_csv_financial_insights(
    payload: CSVInsightsInput,
) -> dict[str, Any]:
    """Deliverable 5: Menganalisis input CSV (`nim,jumlah,tanggal,status`) menjadi
    laporan ringkas JSON (Total revenue bulan ini, collection rate, Top 10 tunggakan, rekomendasi).
    """
    return generate_financial_insights_from_csv(
        payload.csv_data,
        reference_date=payload.reference_date,
    )

import hashlib
import hmac
import logging
import math
import os
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.exceptions import (
    BillingNotFoundError,
    InvalidPaymentError,
    InvalidWebhookSignatureError,
)
from app.models.billing import Billing, BillingStatus, Payment, PaymentMethod
from app.models.mahasiswa import Mahasiswa
from app.observers.channels import LogChannel

logger = logging.getLogger("simak.billing")

DEFAULT_WEBHOOK_SECRET = "simak-webhook-secret-2025"
LATE_FEE_PER_WEEK = Decimal("50000.00")
MAX_LATE_FEE_RATIO = Decimal("0.20")
TWO_PLACES = Decimal("0.01")


def get_webhook_secret() -> str:
    return os.getenv("PAYMENT_WEBHOOK_SECRET", DEFAULT_WEBHOOK_SECRET)


def compute_webhook_signature(raw_body: bytes, secret: str | None = None) -> str:
    """Menghitung signature HMAC-SHA256 hex untuk verifikasi keamanan webhook gateway."""
    key = (secret if secret is not None else get_webhook_secret()).encode("utf-8")
    return hmac.new(key, raw_body, hashlib.sha256).hexdigest()


def verify_webhook_signature(
    raw_body: bytes,
    provided_signature: str,
    secret: str | None = None,
) -> bool:
    expected = compute_webhook_signature(raw_body, secret=secret)
    provided = provided_signature.strip()
    if provided.startswith("sha256="):
        provided = provided[7:]
    return hmac.compare_digest(expected, provided)


def spp_amount_for_prodi(prodi: str) -> Decimal:
    """Tarif SPP per semester sesuai Step 1:
    - Teknik  : Rp 5.000.000
    - Ekonomi : Rp 4.000.000
    - Lainnya : Rp 4.500.000
    """
    p = prodi.lower()
    if "teknik" in p or "informatika" in p or "komputer" in p:
        return Decimal("5000000.00")
    if "ekonomi" in p or "akuntansi" in p or "manajemen" in p:
        return Decimal("4000000.00")
    return Decimal("4500000.00")


def has_unpaid_arrears(session: Session, nim: str, *, as_of_date: date | None = None) -> bool:
    """Memeriksa apakah mahasiswa memiliki tunggakan SPP (status `overdue`, atau
    `unpaid`/`partial` yang sudah melewati `due_date`).

    Dipakai oleh `KRSManager` untuk menegakkan aturan:
    'Mahasiswa dengan tunggakan tidak bisa isi KRS'.
    """
    today = as_of_date or date.today()
    stmt = (
        select(Billing.id)
        .where(
            Billing.nim == nim,
            or_(
                Billing.status == BillingStatus.OVERDUE,
                (
                    Billing.status.in_([BillingStatus.UNPAID, BillingStatus.PARTIAL])
                    & (Billing.due_date < today)
                ),
            ),
        )
        .limit(1)
    )
    return session.scalars(stmt).first() is not None


class BillingService:
    """Service layer Modul Keuangan / SPP (Minggu 11).

    Menangani:
    - Generate tagihan SPP per semester berdasarkan program studi.
    - Perhitungan denda keterlambatan & pembaruan status `overdue`.
    - Pencatatan pembayaran (manual maupun webhook) dalam 1 transaksi atomik.
    - Verifikasi signature webhook + pengiriman receipt email via `LogChannel`.
    - Agregasi data Dashboard Keuangan real-time.
    """

    def __init__(
        self,
        session: Session,
        email_channel: Optional[LogChannel] = None,
    ) -> None:
        self._session = session
        self._email_channel = email_channel if email_channel is not None else LogChannel("email")

    def generate_billing(
        self,
        semester: str,
        semester_start: date,
    ) -> list[Billing]:
        """Step 1: Generate tagihan SPP untuk seluruh mahasiswa aktif yang belum
        memiliki tagihan pada `semester` tersebut (idempoten).
        Due date = 2 minggu (14 hari) setelah `semester_start`, status awal `unpaid`.
        """
        due_date = semester_start + timedelta(days=14)
        students = list(
            self._session.scalars(select(Mahasiswa).order_by(Mahasiswa.nim)).all()
        )
        existing_nims = set(
            self._session.scalars(
                select(Billing.nim).where(Billing.semester == semester)
            ).all()
        )

        created: list[Billing] = []
        try:
            for mhs in students:
                if mhs.nim in existing_nims:
                    continue
                bill = Billing(
                    nim=mhs.nim,
                    semester=semester,
                    amount=spp_amount_for_prodi(mhs.prodi),
                    denda=Decimal("0.00"),
                    paid_amount=Decimal("0.00"),
                    due_date=due_date,
                    status=BillingStatus.UNPAID,
                )
                self._session.add(bill)
                created.append(bill)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        for bill in created:
            self._session.refresh(bill)
        return created

    def calculate_late_fee(
        self,
        billing: Billing,
        *,
        as_of_date: date | None = None,
    ) -> Decimal:
        """Menghitung denda keterlambatan: Rp 50.000 per minggu terlambat (dibulatkan
        ke atas per minggu), maksimal 20% dari pokok tagihan.
        """
        if billing.status == BillingStatus.PAID:
            return Decimal("0.00")
        today = as_of_date or date.today()
        if today <= billing.due_date:
            return Decimal("0.00")
        days_late = (today - billing.due_date).days
        weeks_late = math.ceil(days_late / 7)
        raw_fee = LATE_FEE_PER_WEEK * Decimal(weeks_late)
        max_fee = (Decimal(str(billing.amount)) * MAX_LATE_FEE_RATIO).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        return min(raw_fee, max_fee)

    def mark_overdue_and_calculate_fees(
        self,
        *,
        as_of_date: date | None = None,
    ) -> list[Billing]:
        """Menandai tagihan yang melewati jatuh tempo menjadi `overdue` dan
        memperbarui nilai denda keterlambatannya dalam satu transaksi.
        """
        today = as_of_date or date.today()
        stmt = select(Billing).where(
            Billing.status != BillingStatus.PAID,
            Billing.due_date < today,
        )
        overdue_bills = list(self._session.scalars(stmt).all())
        try:
            for bill in overdue_bills:
                bill.denda = self.calculate_late_fee(bill, as_of_date=today)
                bill.status = BillingStatus.OVERDUE
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return overdue_bills

    def send_overdue_reminders(
        self,
        *,
        as_of_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Scheduled job reminder: update status overdue + denda lalu kirim email
        pengingat otomatis ke setiap mahasiswa yang menunggak.
        """
        today = as_of_date or date.today()
        overdue_bills = self.mark_overdue_and_calculate_fees(as_of_date=today)
        sent: list[dict[str, Any]] = []
        for bill in overdue_bills:
            recipient = f"mahasiswa:{bill.nim}"
            subject = f"Reminder Tunggakan SPP Semester {bill.semester}"
            message = (
                f"Tagihan SPP Semester {bill.semester} jatuh tempo {bill.due_date.isoformat()} "
                f"berstatus OVERDUE. Sisa tagihan (termasuk denda Rp {bill.denda:,.0f}): "
                f"Rp {bill.sisa:,.0f}. Harap segera melunasi agar pengisian KRS tidak terblokir."
            )
            key = f"reminder:{bill.id}:{today.isoformat()}"
            delivered = self._email_channel.send(
                recipient=recipient,
                subject=subject,
                message=message,
                key=key,
            )
            sent.append(
                {
                    "billing_id": bill.id,
                    "nim": bill.nim,
                    "sisa": float(bill.sisa),
                    "denda": float(bill.denda),
                    "delivered": delivered,
                }
            )
        return sent

    def _send_payment_receipt(self, billing: Billing, payment: Payment) -> bool:
        """Mengirim kuitansi pembayaran via email (LogChannel) secara idempoten."""
        recipient = f"mahasiswa:{billing.nim}"
        subject = f"Kuitansi Pembayaran SPP ({payment.transaction_id})"
        message = (
            f"Pembayaran sebesar Rp {Decimal(str(payment.amount)):,.0f} melalui "
            f"{payment.method.name if payment.method else 'Gateway'} untuk SPP Semester "
            f"{billing.semester} telah diterima. Status tagihan kini: {billing.status.value.upper()} "
            f"(sisa: Rp {billing.sisa:,.0f})."
        )
        return self._email_channel.send(
            recipient=recipient,
            subject=subject,
            message=message,
            key=f"receipt:{payment.transaction_id}",
        )

    def process_payment(
        self,
        *,
        billing_id: int,
        amount: Decimal,
        method_code: str,
        transaction_id: Optional[str] = None,
        source: str = "manual",
        note: Optional[str] = None,
        paid_at: Optional[datetime] = None,
    ) -> tuple[Billing, Payment, bool]:
        """Step 2: Mencatat pembayaran dalam SATU transaksi database atomik.

        - Jika `transaction_id` sudah pernah diproses -> idempoten (tidak double-charge).
        - Jika `paid_amount < billing.total` -> status `partial`.
        - Jika `paid_amount >= billing.total` -> status `paid`.
        - Mengembalikan `(billing, payment, is_duplicate)`.
        """
        pay_amount = Decimal(str(amount))
        if pay_amount <= Decimal("0.00"):
            raise InvalidPaymentError("Nominal pembayaran harus lebih besar dari 0.")

        trx_id = (transaction_id or f"TRX-{uuid.uuid4().hex[:12].upper()}").strip()

        # Idempotensi webhook / retry: jika transaction_id sudah tercatat, kembalikan langsung
        existing_payment = self._session.scalars(
            select(Payment).where(Payment.transaction_id == trx_id)
        ).first()
        if existing_payment is not None:
            bill = self._session.get(Billing, existing_payment.billing_id)
            assert bill is not None
            return bill, existing_payment, True

        try:
            billing = self._session.scalars(
                select(Billing).where(Billing.id == billing_id).with_for_update()
            ).first()
            if billing is None:
                raise BillingNotFoundError(f"Tagihan dengan ID '{billing_id}' tidak ditemukan.")

            if billing.status == BillingStatus.PAID:
                raise InvalidPaymentError(
                    f"Tagihan #{billing_id} (NIM {billing.nim}, sem {billing.semester}) sudah LUNAS."
                )

            method = self._session.scalars(
                select(PaymentMethod).where(PaymentMethod.code == method_code.strip().upper())
            ).first()
            if method is None:
                raise BillingNotFoundError(
                    f"Metode pembayaran '{method_code}' tidak ditemukan."
                )

            payment = Payment(
                billing_id=billing.id,
                payment_method_id=method.id,
                transaction_id=trx_id,
                amount=pay_amount,
                status="paid",
                source=source,
                paid_at=paid_at or datetime.now(timezone.utc),
                note=note,
            )
            self._session.add(payment)

            new_paid = Decimal(str(billing.paid_amount)) + pay_amount
            billing.paid_amount = new_paid
            if new_paid >= billing.total:
                billing.status = BillingStatus.PAID
            else:
                billing.status = BillingStatus.PARTIAL

            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        self._session.refresh(billing)
        self._session.refresh(payment)

        # Kirim receipt email SETELAH transaksi commit
        self._send_payment_receipt(billing, payment)
        return billing, payment, False

    def handle_webhook(
        self,
        *,
        raw_body: bytes,
        payload: dict[str, Any],
        signature: str,
    ) -> dict[str, Any]:
        """Step 2: Menangani webhook konfirmasi pembayaran dari payment gateway (simulasi):
        1. Verify HMAC-SHA256 signature.
        2. Extract `billing_id`, `transaction_id`, `amount`, `status`, `method`.
        3. Call `process_payment` (transaksi atomik + kirim receipt email).
        4. Return ringkasan 200 OK.
        """
        if not verify_webhook_signature(raw_body, signature):
            raise InvalidWebhookSignatureError(
                "Signature webhook tidak valid (X-Webhook-Signature gagal diverifikasi)."
            )

        status_str = str(payload.get("status", "")).lower()
        trx_id = str(payload.get("transaction_id", "")).strip()
        if not trx_id:
            raise InvalidPaymentError("Field `transaction_id` wajib ada pada payload webhook.")

        if status_str not in {"paid", "settlement", "success"}:
            return {
                "ok": True,
                "ignored": True,
                "transaction_id": trx_id,
                "message": f"Status webhook '{status_str}' tidak memicu pelunasan.",
            }

        billing_id = int(payload["billing_id"])
        amount = Decimal(str(payload["amount"]))
        method_code = str(payload.get("method", "VA_BCA"))

        billing, payment, is_dup = self.process_payment(
            billing_id=billing_id,
            amount=amount,
            method_code=method_code,
            transaction_id=trx_id,
            source="webhook",
            note="Konfirmasi otomatis via Payment Gateway Webhook",
        )
        return {
            "ok": True,
            "duplicate": is_dup,
            "transaction_id": payment.transaction_id,
            "billing_id": billing.id,
            "nim": billing.nim,
            "billing_status": billing.status.value,
            "paid_amount": float(billing.paid_amount),
            "sisa": float(billing.sisa),
            "receipt_sent": True,
        }

    def list_billings(
        self,
        *,
        nim: Optional[str] = None,
        semester: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[Billing]:
        stmt = select(Billing)
        if nim:
            stmt = stmt.where(Billing.nim == nim)
        if semester:
            stmt = stmt.where(Billing.semester == semester)
        if status:
            stmt = stmt.where(Billing.status == BillingStatus(status))
        stmt = stmt.order_by(Billing.semester.desc(), Billing.nim)
        return list(self._session.scalars(stmt).all())

    def get_dashboard_summary(self) -> dict[str, Any]:
        """Deliverable 3: Dashboard Keuangan real-time:
        - Per mahasiswa: total tagihan, sudah bayar, sisa, status
        - Per program studi: collection rate (%)
        - Grafik pembayaran per bulan (YYYY-MM)
        """
        billings = list(self._session.scalars(select(Billing).order_by(Billing.nim)).all())
        payments = list(self._session.scalars(select(Payment).order_by(Payment.paid_at)).all())

        # Agregasi per mahasiswa
        by_student: dict[str, dict[str, Any]] = {}
        by_prodi: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "prodi": "",
                "total_tagihan": Decimal("0.00"),
                "sudah_bayar": Decimal("0.00"),
                "jumlah_tagihan": 0,
                "jumlah_lunas": 0,
            }
        )

        total_billed = Decimal("0.00")
        total_collected = Decimal("0.00")
        total_overdue_students: set[str] = set()

        for b in billings:
            mhs_nama = b.mahasiswa.nama if b.mahasiswa else b.nim
            prodi = b.mahasiswa.prodi if b.mahasiswa else "Lainnya"
            entry = by_student.setdefault(
                b.nim,
                {
                    "nim": b.nim,
                    "nama": mhs_nama,
                    "prodi": prodi,
                    "total_tagihan": Decimal("0.00"),
                    "sudah_bayar": Decimal("0.00"),
                    "sisa": Decimal("0.00"),
                    "has_overdue": False,
                },
            )
            entry["total_tagihan"] += b.total
            entry["sudah_bayar"] += Decimal(str(b.paid_amount))
            entry["sisa"] += b.sisa
            if b.status == BillingStatus.OVERDUE:
                entry["has_overdue"] = True
                total_overdue_students.add(b.nim)

            p_entry = by_prodi[prodi]
            p_entry["prodi"] = prodi
            p_entry["total_tagihan"] += b.total
            p_entry["sudah_bayar"] += Decimal(str(b.paid_amount))
            p_entry["jumlah_tagihan"] += 1
            if b.status == BillingStatus.PAID:
                p_entry["jumlah_lunas"] += 1

            total_billed += b.total
            total_collected += Decimal(str(b.paid_amount))

        per_mahasiswa = [
            {
                "nim": v["nim"],
                "nama": v["nama"],
                "prodi": v["prodi"],
                "total_tagihan": float(v["total_tagihan"]),
                "sudah_bayar": float(v["sudah_bayar"]),
                "sisa": float(v["sisa"]),
                "status": (
                    "overdue"
                    if v["has_overdue"]
                    else "paid"
                    if v["sisa"] <= Decimal("0.00")
                    else "partial"
                    if v["sudah_bayar"] > Decimal("0.00")
                    else "unpaid"
                ),
            }
            for v in by_student.values()
        ]

        per_prodi = []
        for p in sorted(by_prodi.values(), key=lambda x: x["prodi"]):
            rate = (
                float((p["sudah_bayar"] / p["total_tagihan"] * Decimal("100")).quantize(TWO_PLACES))
                if p["total_tagihan"] > 0
                else 0.0
            )
            per_prodi.append(
                {
                    "prodi": p["prodi"],
                    "total_tagihan": float(p["total_tagihan"]),
                    "sudah_bayar": float(p["sudah_bayar"]),
                    "jumlah_tagihan": p["jumlah_tagihan"],
                    "jumlah_lunas": p["jumlah_lunas"],
                    "collection_rate": rate,
                }
            )

        # Grafik pembayaran per bulan
        monthly_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for pay in payments:
            if pay.status == "paid":
                ym = pay.paid_at.strftime("%Y-%m")
                monthly_totals[ym] += Decimal(str(pay.amount))

        grafik_per_bulan = [
            {"bulan": ym, "total": float(monthly_totals[ym])}
            for ym in sorted(monthly_totals.keys())
        ]

        overall_rate = (
            float((total_collected / total_billed * Decimal("100")).quantize(TWO_PLACES))
            if total_billed > 0
            else 0.0
        )
        return {
            "summary": {
                "total_tagihan": float(total_billed),
                "total_terbayar": float(total_collected),
                "total_tunggakan": float(max(Decimal("0.00"), total_billed - total_collected)),
                "collection_rate": overall_rate,
                "jumlah_mahasiswa_overdue": len(total_overdue_students),
            },
            "per_mahasiswa": per_mahasiswa,
            "per_prodi": per_prodi,
            "grafik_per_bulan": grafik_per_bulan,
        }

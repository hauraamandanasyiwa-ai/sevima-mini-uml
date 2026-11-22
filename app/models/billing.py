import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BillingStatus(str, enum.Enum):
    """Empat status resmi tagihan SPP (Payment State Management)."""

    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"


class PaymentMethod(Base):
    """Tabel 1 Keuangan: Metode pembayaran yang didukung (VA, QRIS, Transfer, Tunai)."""

    __tablename__ = "payment_method"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<PaymentMethod {self.code} ({self.name})>"


class Billing(Base):
    """Tabel 2 Keuangan: Tagihan SPP per mahasiswa per semester.

    Menyimpan pokok tagihan (`amount`), denda keterlambatan (`denda`),
    total terbayar (`paid_amount`), tanggal jatuh tempo (`due_date`), dan `status`.
    """

    __tablename__ = "billing"
    __table_args__ = (
        UniqueConstraint("nim", "semester", name="uq_billing_nim_semester"),
        CheckConstraint("LENGTH(semester) = 5", name="ck_billing_semester_len"),
        CheckConstraint("amount >= 0", name="ck_billing_amount_nonneg"),
        CheckConstraint("denda >= 0", name="ck_billing_denda_nonneg"),
        CheckConstraint("paid_amount >= 0", name="ck_billing_paid_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nim: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("mahasiswa.nim", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    semester: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    denda: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[BillingStatus] = mapped_column(
        Enum(BillingStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=BillingStatus.UNPAID,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    mahasiswa = relationship("Mahasiswa", lazy="joined")
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="billing",
        cascade="all, delete-orphan",
        order_by="Payment.paid_at.desc()",
        lazy="selectin",
    )

    @property
    def total(self) -> Decimal:
        """Total tagihan yang harus dibayar (pokok + denda)."""
        return Decimal(str(self.amount)) + Decimal(str(self.denda))

    @property
    def sisa(self) -> Decimal:
        """Sisa tunggakan yang belum dibayar (minimal 0)."""
        rem = self.total - Decimal(str(self.paid_amount))
        return rem if rem > Decimal("0.00") else Decimal("0.00")

    def __repr__(self) -> str:
        return (
            f"<Billing id={self.id} nim={self.nim} sem={self.semester} "
            f"total={self.total} paid={self.paid_amount} status={self.status.value}>"
        )


class Payment(Base):
    """Tabel 3 Keuangan: Catatan transaksi pembayaran (manual maupun via webhook)."""

    __tablename__ = "payment"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payment_amount_pos"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    billing_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("billing.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_method_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("payment_method.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="paid")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    billing: Mapped["Billing"] = relationship("Billing", back_populates="payments")
    method: Mapped["PaymentMethod"] = relationship("PaymentMethod", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} trx={self.transaction_id} "
            f"billing={self.billing_id} amount={self.amount} source={self.source}>"
        )

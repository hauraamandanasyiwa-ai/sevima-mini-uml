from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class GenerateBillingInput(BaseModel):
    semester: str = Field(..., min_length=5, max_length=5, examples=["20251"])
    semester_start: date = Field(..., examples=["2025-09-01"])


class ManualPaymentInput(BaseModel):
    amount: Decimal = Field(..., gt=0, examples=[2500000])
    method_code: str = Field(default="VA_BCA", min_length=2, max_length=24, examples=["VA_BCA"])
    transaction_id: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=255)


class WebhookPaymentPayload(BaseModel):
    billing_id: int = Field(..., ge=1)
    transaction_id: str = Field(..., min_length=3, max_length=64)
    amount: Decimal = Field(..., gt=0)
    status: str = Field(default="paid", examples=["paid"])
    method: str = Field(default="VA_BCA", examples=["VA_BCA"])


class PaymentOut(BaseModel):
    id: int
    billing_id: int
    transaction_id: str
    method_code: str
    amount: Decimal
    status: str
    source: str
    paid_at: datetime
    note: Optional[str] = None


class BillingOut(BaseModel):
    id: int
    nim: str
    nama: str
    prodi: str
    semester: str
    amount: Decimal
    denda: Decimal
    total: Decimal
    paid_amount: Decimal
    sisa: Decimal
    due_date: date
    status: str


class CSVInsightsInput(BaseModel):
    csv_data: str = Field(..., min_length=10)
    reference_date: Optional[date] = None

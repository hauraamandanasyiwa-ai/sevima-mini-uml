import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.billing import Billing, BillingStatus, Payment

TWO_PLACES = Decimal("0.01")


def export_payment_csv_from_db(session: Session) -> str:
    """Mengekspor data pembayaran & tunggakan dari database ke format CSV standar
    Step 3 (`nim,jumlah,tanggal,status`) sebagai input `generate_financial_insights_from_csv`.
    """
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["nim", "jumlah", "tanggal", "status"])

    payments = list(session.scalars(select(Payment).order_by(Payment.paid_at)).all())
    for p in payments:
        nim = p.billing.nim if p.billing else "-"
        writer.writerow([nim, f"{Decimal(str(p.amount)):.2f}", p.paid_at.date().isoformat(), "paid"])

    billings = list(session.scalars(select(Billing).order_by(Billing.due_date)).all())
    for b in billings:
        if b.status != BillingStatus.PAID and b.sisa > Decimal("0.00"):
            writer.writerow([b.nim, f"{b.sisa:.2f}", b.due_date.isoformat(), b.status.value])

    return output.getvalue()


def generate_financial_insights_from_csv(
    csv_text: str,
    *,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """Step 3: AI Financial Insights.

    Menerima `payment_data` (CSV dengan kolom: `nim, jumlah, tanggal, status`)
    dan menghasilkan laporan ringkas JSON untuk dashboard frontend:
    - Total revenue bulan ini (Rp X)
    - Collection rate (Y% mahasiswa sudah bayar)
    - Top 10 mahasiswa dengan tunggakan terbesar
    - Rekomendasi: 'Kirim reminder ke Z mahasiswa dengan tunggakan >2 bulan'
    """
    ref = reference_date or date.today()
    reader = csv.DictReader(StringIO(csv_text.strip()))

    revenue_this_month = Decimal("0.00")
    total_revenue_all = Decimal("0.00")
    all_students: set[str] = set()
    paid_students: set[str] = set()
    arrears_by_nim: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    overdue_over_2_months: set[str] = set()

    for row in reader:
        nim = (row.get("nim") or "").strip()
        if not nim:
            continue
        status = (row.get("status") or "").strip().lower()
        try:
            jumlah = Decimal(str(row.get("jumlah", "0")).strip())
        except Exception:
            continue
        tanggal_raw = (row.get("tanggal") or "").strip()
        try:
            tgl = date.fromisoformat(tanggal_raw[:10])
        except ValueError:
            tgl = ref

        all_students.add(nim)
        if status in {"paid", "lunas", "settled"}:
            paid_students.add(nim)
            total_revenue_all += jumlah
            if tgl.year == ref.year and tgl.month == ref.month:
                revenue_this_month += jumlah
        else:
            arrears_by_nim[nim] += jumlah
            if (ref - tgl).days > 60:
                overdue_over_2_months.add(nim)

    collection_rate = (
        float(
            (Decimal(len(paid_students)) / Decimal(len(all_students)) * Decimal("100")).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
        )
        if all_students
        else 0.0
    )

    top_10 = [
        {"nim": nim, "tunggakan": float(amount)}
        for nim, amount in sorted(
            arrears_by_nim.items(), key=lambda kv: (-kv[1], kv[0])
        )[:10]
    ]

    z_count = len(overdue_over_2_months)
    rekomendasi = (
        f"Kirim reminder ke {z_count} mahasiswa dengan tunggakan >2 bulan"
        if z_count > 0
        else "Tidak ada mahasiswa dengan tunggakan >2 bulan; pertahankan reminder rutin sebelum jatuh tempo."
    )

    return {
        "periode_bulan": ref.strftime("%Y-%m"),
        "total_revenue_bulan_ini": float(revenue_this_month),
        "total_revenue_bulan_ini_formatted": f"Rp {revenue_this_month:,.0f}",
        "total_revenue_keseluruhan": float(total_revenue_all),
        "collection_rate_persen": collection_rate,
        "ringkasan_collection_rate": f"{collection_rate:.2f}% mahasiswa sudah bayar",
        "top_10_tunggakan": top_10,
        "jumlah_tunggakan_lebih_2_bulan": z_count,
        "rekomendasi": rekomendasi,
    }

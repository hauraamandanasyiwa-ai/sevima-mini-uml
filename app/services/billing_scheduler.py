import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.services.billing_service import BillingService

logger = logging.getLogger("simak.billing_scheduler")

_scheduler: BackgroundScheduler | None = None


def _current_semester_code(today: date) -> str:
    """Menentukan kode semester aktif (Feb–Jul = Genap '2', Agu–Jan = Ganjil '1')."""
    if 2 <= today.month <= 7:
        return f"{today.year - 1}2"
    return f"{today.year}1"


def scheduled_semester_billing_job() -> None:
    """Cron job awal semester: otomatis generate tagihan SPP untuk semua mahasiswa aktif."""
    today = date.today()
    semester = _current_semester_code(today)
    with SessionLocal() as session:
        service = BillingService(session=session)
        created = service.generate_billing(semester=semester, semester_start=today)
        logger.info(
            "[CRON] generate_billing semester=%s selesai: %d tagihan baru dibuat.",
            semester,
            len(created),
        )


def scheduled_overdue_reminder_job() -> None:
    """Cron job harian: update status overdue + denda lalu kirim reminder email otomatis."""
    with SessionLocal() as session:
        service = BillingService(session=session)
        sent = service.send_overdue_reminders()
        logger.info(
            "[CRON] overdue_reminder_job selesai: %d reminder diproses.",
            len(sent),
        )


def build_billing_scheduler() -> BackgroundScheduler:
    """Menyusun APScheduler dengan 2 cron job sesuai Step 1 & Tujuan Pembelajaran:
    1. `semester_billing_generator`: jalan otomatis tiap awal semester (1 Feb & 1 Agu 00:05).
    2. `daily_overdue_reminder`: jalan harian pukul 07:00 untuk denda & reminder tunggakan.
    """
    scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
    scheduler.add_job(
        scheduled_semester_billing_job,
        trigger=CronTrigger(month="2,8", day=1, hour=0, minute=5),
        id="semester_billing_generator",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_overdue_reminder_job,
        trigger=CronTrigger(hour=7, minute=0),
        id="daily_overdue_reminder",
        replace_existing=True,
    )
    return scheduler


def start_billing_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = build_billing_scheduler()
    if not _scheduler.running:
        _scheduler.start()
        logger.info("APScheduler Billing Jobs aktif (%d jobs).", len(_scheduler.get_jobs()))
    return _scheduler


def stop_billing_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler Billing Jobs dihentikan.")

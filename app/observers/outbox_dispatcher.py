from contextvars import ContextVar
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.outbox import OutboxEvent, OutboxStatus
from app.observers.subject import ScheduleSubject

logger = logging.getLogger("simak.outbox")

MAX_OUTBOX_ATTEMPTS = 5

# Menyimpan session aktif selama `OutboxDispatcher.run()` agar repository observer
# (mis. StudentObserver) membaca database yang sama termasuk pada SQLite in-memory test.
current_dispatch_session: ContextVar[Session | None] = ContextVar(
    "current_dispatch_session", default=None
)


class OutboxDispatcher:
    """Membaca baris `notification_outbox` berstatus `pending` SETELAH transaksi
    utama di-commit, lalu meneruskannya ke `ScheduleSubject.notify()`.

    - Memakai `with_for_update(skip_locked=True)` agar dua dispatcher paralel
      tidak memproses baris yang sama.
    - Jika semua observer sukses -> status menjadi `sent`.
    - Jika ada observer gagal -> `attempts` naik dan baris tetap `pending` untuk
      dicoba ulang (sampai `MAX_OUTBOX_ATTEMPTS = 5`, lalu ditandai `failed`).
    - Pengulangan aman dari pesan ganda karena setiap kanal memeriksa kunci
      idempotensi (`event_id:recipient:channel`).
    """

    def __init__(
        self,
        subject: ScheduleSubject,
        max_attempts: int = MAX_OUTBOX_ATTEMPTS,
    ) -> None:
        self._subject = subject
        self._max_attempts = max_attempts

    @property
    def subject(self) -> ScheduleSubject:
        return self._subject

    def run(self, session: Session, *, limit: int = 50) -> dict[str, int]:
        """Memproses antrean outbox pending dan mengembalikan ringkasan jumlah."""
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatus.PENDING.value)
            .order_by(OutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = list(session.scalars(stmt).all())
        stats = {"processed": 0, "sent": 0, "retried": 0, "failed": 0}

        token = current_dispatch_session.set(session)
        try:
            for row in rows:
                stats["processed"] += 1
                event = row.to_event()
                failed_observers = self._subject.notify(event)

                if not failed_observers:
                    row.status = OutboxStatus.SENT.value
                    row.sent_at = datetime.now(timezone.utc)
                    row.last_error = None
                    stats["sent"] += 1
                else:
                    row.attempts += 1
                    row.last_error = f"Observer gagal: {', '.join(failed_observers)}"
                    if row.attempts >= self._max_attempts:
                        row.status = OutboxStatus.FAILED.value
                        stats["failed"] += 1
                        logger.error(
                            "OutboxEvent id=%s gagal permanen setelah %d percobaan: %s",
                            row.id,
                            row.attempts,
                            row.last_error,
                        )
                    else:
                        stats["retried"] += 1
        finally:
            current_dispatch_session.reset(token)

        if rows:
            session.commit()
        return stats

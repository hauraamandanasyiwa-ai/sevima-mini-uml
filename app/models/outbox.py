import enum
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OutboxStatus(str, enum.Enum):
    """Status pengiriman baris event pada tabel Transactional Outbox."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class OutboxEvent(Base):
    """Tabel Transactional Outbox untuk menjamin konsistensi antara perubahan jadwal
    dan pengiriman notifikasi.

    Prinsip utama:
    - Baris event ditulis dalam TRANSAKSI YANG SAMA dengan perubahan jadwal & invalidasi KRS.
    - Jika commit gagal, jadwal dan event outbox sama-sama ter-rollback.
    - Pengiriman sesungguhnya ke observer dilakukan SETELAH commit oleh `OutboxDispatcher`.
    - Kolom `event_id` unik agar event yang sama tidak bisa tercatat dua kali.
    """

    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=OutboxStatus.PENDING.value, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @classmethod
    def from_event(cls, event: Any) -> "OutboxEvent":
        """Mengubah objek immutable `ScheduleEvent` menjadi baris ORM `OutboxEvent`."""
        return cls(
            event_id=event.event_id,
            event_type=event.event_type.value,
            payload={
                "event_type": event.event_type.value,
                "before": event.before,
                "after": event.after,
                "occurred_at": event.occurred_at.isoformat(),
            },
            status=OutboxStatus.PENDING.value,
            attempts=0,
        )

    def to_event(self) -> Any:
        """Membangun kembali objek immutable `ScheduleEvent` dari baris outbox."""
        from app.observers.events import EventType, ScheduleEvent

        occurred_raw = self.payload.get("occurred_at")
        occurred_at = (
            datetime.fromisoformat(occurred_raw)
            if isinstance(occurred_raw, str)
            else self.created_at
        )
        return ScheduleEvent(
            event_id=self.event_id,
            event_type=EventType(self.event_type),
            before=self.payload.get("before"),
            after=self.payload.get("after"),
            occurred_at=occurred_at,
        )

    def __repr__(self) -> str:
        return (
            f"<OutboxEvent id={self.id} event_id={self.event_id[:8]} "
            f"type={self.event_type} status={self.status} attempts={self.attempts}>"
        )

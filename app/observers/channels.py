import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

logger = logging.getLogger("simak.notifications")


@dataclass(frozen=True)
class NotificationLogEntry:
    """Catatan satu pengiriman notifikasi yang tersimpan untuk inspeksi demo & test."""

    channel: str
    recipient: str
    subject: str
    message: str
    idempotency_key: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationChannel(Protocol):
    """Kontrak kanal notifikasi (mirip Strategy Pattern).

    Observer tidak peduli apakah pesan dikirim lewat Email, SMS, Push, atau
    provider sungguhan di masa depan — observer cukup memanggil `send()`.
    """

    @property
    def name(self) -> str: ...

    def send(self, recipient: str, subject: str, message: str, key: str) -> bool: ...


class LogChannel:
    """Implementasi kanal notifikasi yang disimulasikan lewat logger Python
    dengan perlindungan **kunci idempotensi** (*at-least-once delivery + deduplication*).

    Satu `key` hanya akan dikirim tepat sekali. Jika OutboxDispatcher mengulang
    pengiriman setelah kegagalan parsial, kunci yang sama otomatis diabaikan.
    """

    def __init__(
        self,
        channel_name: str,
        *,
        shared_history: list[NotificationLogEntry] | None = None,
    ) -> None:
        self._name = channel_name.lower()
        self._sent_keys: set[str] = set()
        self._history: list[NotificationLogEntry] = (
            shared_history if shared_history is not None else []
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def sent_keys(self) -> frozenset[str]:
        return frozenset(self._sent_keys)

    @property
    def history(self) -> list[NotificationLogEntry]:
        return list(self._history)

    def clear(self) -> None:
        """Mengosongkan state in-memory (berguna untuk isolasi pengujian)."""
        self._sent_keys.clear()
        self._history.clear()

    def send(self, recipient: str, subject: str, message: str, key: str) -> bool:
        """Mengirim notifikasi melalui log. Mengembalikan `False` jika kunci
        idempotensi sudah pernah terkirim (deduplikasi), `True` jika baru dikirim.
        """
        if key in self._sent_keys:
            logger.debug(
                "[%s] Skip duplikat key=%s untuk recipient=%s",
                self._name.upper(),
                key,
                recipient,
            )
            return False

        self._sent_keys.add(key)
        entry = NotificationLogEntry(
            channel=self._name,
            recipient=recipient,
            subject=subject,
            message=message,
            idempotency_key=key,
        )
        self._history.append(entry)
        logger.info(
            "[%s] To=%s | Subject=%s | Key=%s | %s",
            self._name.upper(),
            recipient,
            subject,
            key,
            message,
        )
        return True

import logging
from collections.abc import Callable, Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.krs import KRS, KRSDetail
from app.observers.channels import NotificationChannel
from app.observers.events import EventType, ScheduleEvent, format_slot_label

logger = logging.getLogger("simak.observers")


class ScheduleObserver(Protocol):
    """Kontrak Observer memakai `typing.Protocol` (structural subtyping).

    Berbeda dengan ABC, kelas apa pun yang menyediakan method `update(event)`
    otomatis memenuhi kontrak tanpa wajib mewarisi kelas dasar tertentu.
    """

    def update(self, event: ScheduleEvent) -> None: ...


class EnrollmentRepository(Protocol):
    """Abstraksi query peserta kelas agar `StudentObserver` mudah diuji tanpa DB."""

    def get_enrolled_nims(self, kelas_id: int) -> list[str]: ...


class SQLAlchemyEnrollmentRepository:
    """Implementasi repository peserta kelas yang membaca tabel `krs_detail` -> `krs`."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def get_enrolled_nims(self, kelas_id: int) -> list[str]:
        from app.observers.outbox_dispatcher import current_dispatch_session

        active_session = current_dispatch_session.get()
        stmt = (
            select(KRS.nim)
            .join(KRSDetail, KRSDetail.krs_id == KRS.id)
            .where(KRSDetail.kelas_id == kelas_id)
            .distinct()
            .order_by(KRS.nim)
        )
        if active_session is not None:
            return list(active_session.scalars(stmt).all())

        session = self._session_factory()
        try:
            return list(session.scalars(stmt).all())
        finally:
            session.close()


class ScheduleSubject:
    """Subject (Notification Manager) pada Observer Pattern.

    Menjamin tiga properti penting:
    1. `attach()` bersifat idempoten — menolak observer yang sudah terdaftar agar
       tidak terjadi notifikasi ganda.
    2. `notify()` mengiterasi salinan daftar (`list(self._observers)`) sehingga
       observer yang melakukan `detach()` di tengah jalan tidak merusak loop.
    3. Setiap `observer.update(event)` dibungkus `try/except` terpisah agar satu
       observer yang rusak tidak membungkam observer lainnya.
    """

    def __init__(self) -> None:
        self._observers: list[ScheduleObserver] = []

    @property
    def observers(self) -> list[ScheduleObserver]:
        return list(self._observers)

    def attach(self, observer: ScheduleObserver) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: ScheduleObserver) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event: ScheduleEvent) -> list[str]:
        """Memberi tahu seluruh observer terdaftar dan mengembalikan daftar nama
        observer yang gagal (kosong jika semua berhasil).
        """
        failed_observers: list[str] = []
        for observer in list(self._observers):
            try:
                observer.update(event)
            except Exception:
                obs_name = getattr(observer, "name", type(observer).__name__)
                logger.exception(
                    "Observer '%s' gagal memproses event %s (%s)",
                    obs_name,
                    event.event_id,
                    event.event_type.value,
                )
                failed_observers.append(obs_name)
        return failed_observers


def _compose_message(event: ScheduleEvent) -> tuple[str, str]:
    """Menyusun (subject, message) yang informatif dari data `before` dan `after`."""
    ref = event.after or event.before or {}
    kode_mk = ref.get("kode_mk") or f"Kelas#{ref.get('kelas_id')}"
    nama_mk = ref.get("nama_mk") or ""
    nama_kelas = ref.get("nama_kelas") or ""
    label_mk = f"{kode_mk} {nama_mk} ({nama_kelas})".strip()

    if event.event_type == EventType.SCHEDULE_DELETED:
        before_slot = format_slot_label(event.before) if event.before else "-"
        return (
            f"Jadwal Dihapus: {label_mk}",
            f"Jadwal {label_mk} pada {before_slot} telah dihapus. "
            "Silakan periksa kembali KRS Anda.",
        )

    before_slot = format_slot_label(event.before) if event.before else "-"
    after_slot = format_slot_label(event.after) if event.after else "-"
    return (
        f"Perubahan Jadwal: {label_mk}",
        f"Jadwal {label_mk} dipindah dari {before_slot} ke {after_slot}. "
        "KRS terkait dikembalikan ke status revisi untuk diperiksa ulang.",
    )


class StudentObserver:
    """Observer 1: Memberi tahu semua mahasiswa yang mengambil kelas terdampak."""

    name = "StudentObserver"

    def __init__(
        self,
        enrollment_repo: EnrollmentRepository,
        channels: Sequence[NotificationChannel],
    ) -> None:
        self._enrollment_repo = enrollment_repo
        self._channels = list(channels)

    def update(self, event: ScheduleEvent) -> None:
        data = event.after or event.before
        if not data or data.get("kelas_id") is None:
            return
        nims = self._enrollment_repo.get_enrolled_nims(int(data["kelas_id"]))
        subject, message = _compose_message(event)
        for nim in nims:
            recipient = f"mahasiswa:{nim}"
            for channel in self._channels:
                idem_key = f"{event.event_id}:{recipient}:{channel.name}"
                channel.send(recipient=recipient, subject=subject, message=message, key=idem_key)


class LecturerObserver:
    """Observer 2: Memberi tahu dosen pengampu, termasuk dosen LAMA jika dosen diganti."""

    name = "LecturerObserver"

    def __init__(self, channels: Sequence[NotificationChannel]) -> None:
        self._channels = list(channels)

    def update(self, event: ScheduleEvent) -> None:
        dosen_ids: list[int] = []
        if event.after and event.after.get("dosen_id") is not None:
            dosen_ids.append(int(event.after["dosen_id"]))
        if event.before and event.before.get("dosen_id") is not None:
            old_id = int(event.before["dosen_id"])
            if old_id not in dosen_ids:
                dosen_ids.append(old_id)

        subject, message = _compose_message(event)
        for dosen_id in dosen_ids:
            recipient = f"dosen:{dosen_id}"
            for channel in self._channels:
                idem_key = f"{event.event_id}:{recipient}:{channel.name}"
                channel.send(recipient=recipient, subject=subject, message=message, key=idem_key)


class AdminObserver:
    """Observer 3: Mengirim ringkasan jejak perubahan/penghapusan ke admin akademik."""

    name = "AdminObserver"

    def __init__(
        self,
        channels: Sequence[NotificationChannel],
        admin_recipient: str = "admin:akademik",
    ) -> None:
        self._channels = list(channels)
        self._admin_recipient = admin_recipient

    def update(self, event: ScheduleEvent) -> None:
        subject, message = _compose_message(event)
        summary = f"[AUDIT] event={event.event_id[:8]} | {message}"
        for channel in self._channels:
            idem_key = f"{event.event_id}:{self._admin_recipient}:{channel.name}"
            channel.send(
                recipient=self._admin_recipient,
                subject=subject,
                message=summary,
                key=idem_key,
            )

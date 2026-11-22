from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.observers.channels import LogChannel, NotificationChannel, NotificationLogEntry
from app.observers.events import EventType, ScheduleEvent, build_schedule_snapshot
from app.observers.outbox_dispatcher import MAX_OUTBOX_ATTEMPTS, OutboxDispatcher
from app.observers.subject import (
    AdminObserver,
    EnrollmentRepository,
    LecturerObserver,
    SQLAlchemyEnrollmentRepository,
    ScheduleObserver,
    ScheduleSubject,
    StudentObserver,
)


@dataclass
class NotificationRuntime:
    """Bundel runtime Observer + 3 Kanal + OutboxDispatcher yang dirangkai SEKALI
    saat aplikasi mulai berjalan (bukan di dalam endpoint request) untuk mencegah
    kebocoran memori dan notifikasi ganda.
    """

    subject: ScheduleSubject
    dispatcher: OutboxDispatcher
    channels: list[LogChannel]
    history: list[NotificationLogEntry]


def build_notification_runtime(
    session_factory: Callable[[], Session],
) -> NotificationRuntime:
    """Merangkai ScheduleSubject dengan 3 observer konkret (Student, Lecturer, Admin)
    dan 3 kanal simulasi log (email, sms, push).
    """
    shared_history: list[NotificationLogEntry] = []
    channels = [
        LogChannel("email", shared_history=shared_history),
        LogChannel("sms", shared_history=shared_history),
        LogChannel("push", shared_history=shared_history),
    ]
    enrollment_repo = SQLAlchemyEnrollmentRepository(session_factory)

    subject = ScheduleSubject()
    subject.attach(StudentObserver(enrollment_repo=enrollment_repo, channels=channels))
    subject.attach(LecturerObserver(channels=channels))
    subject.attach(AdminObserver(channels=channels))

    dispatcher = OutboxDispatcher(subject=subject)
    return NotificationRuntime(
        subject=subject,
        dispatcher=dispatcher,
        channels=channels,
        history=shared_history,
    )


__all__ = [
    "EventType",
    "ScheduleEvent",
    "build_schedule_snapshot",
    "NotificationChannel",
    "NotificationLogEntry",
    "LogChannel",
    "ScheduleObserver",
    "ScheduleSubject",
    "EnrollmentRepository",
    "SQLAlchemyEnrollmentRepository",
    "StudentObserver",
    "LecturerObserver",
    "AdminObserver",
    "OutboxDispatcher",
    "MAX_OUTBOX_ATTEMPTS",
    "NotificationRuntime",
    "build_notification_runtime",
]

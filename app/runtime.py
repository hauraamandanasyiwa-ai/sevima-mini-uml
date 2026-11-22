from app.database import SessionLocal
from app.observers import NotificationRuntime, build_notification_runtime

_runtime: NotificationRuntime | None = None


def init_notification_runtime() -> NotificationRuntime:
    """Merangkai ScheduleSubject, 3 Observer, 3 Kanal Log, dan OutboxDispatcher
    SEKALI saat aplikasi mulai (mencegah memory leak akibat attach di endpoint).
    """
    global _runtime
    if _runtime is None:
        _runtime = build_notification_runtime(SessionLocal)
    return _runtime


def get_notification_runtime() -> NotificationRuntime:
    if _runtime is None:
        return init_notification_runtime()
    return _runtime

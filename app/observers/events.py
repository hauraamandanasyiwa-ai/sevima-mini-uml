import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.schedule import Jadwal

HARI_LABEL: dict[int, str] = {
    1: "Senin",
    2: "Selasa",
    3: "Rabu",
    4: "Kamis",
    5: "Jumat",
    6: "Sabtu",
}


class EventType(str, enum.Enum):
    """Jenis event perubahan jadwal yang dipublikasikan ke observer."""

    SCHEDULE_CHANGED = "schedule_changed"
    SCHEDULE_DELETED = "schedule_deleted"


@dataclass(frozen=True)
class ScheduleEvent:
    """Event immutable (frozen) yang membawa snapshot sebelum dan sesudah perubahan jadwal.

    `frozen=True` menjamin tidak ada observer yang diam-diam memutasi data event
    yang juga dibaca oleh observer lain.
    """

    event_type: EventType
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def build_schedule_snapshot(jadwal: Jadwal) -> dict[str, Any]:
    """Mengubah objek ORM `Jadwal` menjadi dictionary JSON-serializable.

    Waktu ditulis sebagai string HH:MM agar aman disimpan ke kolom JSON outbox.
    """
    kode_mk = jadwal.kelas.kode_mk if jadwal.kelas else None
    nama_kelas = jadwal.kelas.nama_kelas if jadwal.kelas else None
    nama_mk = (
        jadwal.kelas.mata_kuliah.nama
        if jadwal.kelas and jadwal.kelas.mata_kuliah
        else None
    )
    nama_dosen = jadwal.dosen.nama if jadwal.dosen else None
    return {
        "jadwal_id": jadwal.id,
        "kelas_id": jadwal.kelas_id,
        "kode_mk": kode_mk,
        "nama_mk": nama_mk,
        "nama_kelas": nama_kelas,
        "ruangan_kode": jadwal.ruangan_kode,
        "dosen_id": jadwal.dosen_id,
        "dosen_nama": nama_dosen,
        "hari": jadwal.hari,
        "hari_nama": HARI_LABEL.get(jadwal.hari, f"Hari-{jadwal.hari}"),
        "jam_mulai": jadwal.jam_mulai.strftime("%H:%M"),
        "jam_selesai": jadwal.jam_selesai.strftime("%H:%M"),
        "sequence": getattr(jadwal, "sequence", 0),
    }


def format_slot_label(snapshot: dict[str, Any]) -> str:
    """Format ringkas slot jadwal untuk isi pesan notifikasi."""
    hari_nama = snapshot.get("hari_nama") or HARI_LABEL.get(snapshot.get("hari", 0), "?")
    return (
        f"{hari_nama} {snapshot.get('jam_mulai')}-{snapshot.get('jam_selesai')} "
        f"di Ruang {snapshot.get('ruangan_kode')}"
    )

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.krs import (
    KRS,
    KRSAktor,
    KRSApprovalLog,
    KRSDetail,
    KRSStatus,
)


class KRSInvalidator:
    """Mengembalikan KRS berstatus `submitted` atau `approved` yang terdampak
    perubahan/penghapusan jadwal kelas ke status `revision`.

    Prinsip desain:
    - KRS `draft` dan `revision` tidak disentuh karena mahasiswa masih bisa
      mengubahnya dan validator bentrok akan memeriksanya lagi saat submit.
    - Perubahan status WAJIB lewat pintu tunggal `krs.transition(KRSStatus.REVISION, KRSAktor.SYSTEM)`
      — tidak pernah menulis `krs.status = ...` secara langsung.
    - TIDAK melakukan `session.commit()` sendiri karena ikut transaksi milik
      `SchedulingService` (atomik: jadwal berubah + KRS revisi + outbox ditulis).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def invalidate_for_kelas(self, kelas_id: int, reason: str) -> list[int]:
        """Mengembalikan daftar `krs.id` yang diinvalidasi ke `revision`."""
        stmt = (
            select(KRS)
            .join(KRSDetail, KRSDetail.krs_id == KRS.id)
            .where(
                KRSDetail.kelas_id == kelas_id,
                KRS.status.in_([KRSStatus.SUBMITTED, KRSStatus.APPROVED]),
            )
            .distinct()
            .order_by(KRS.id)
        )
        affected_krs = list(self._session.scalars(stmt).all())
        invalidated_ids: list[int] = []

        for krs in affected_krs:
            krs.transition(KRSStatus.REVISION, KRSAktor.SYSTEM)
            krs.revision_note = reason
            self._session.add(
                KRSApprovalLog(
                    krs_id=krs.id,
                    action="system_invalidate",
                    actor_id=KRSAktor.SYSTEM.value,
                    note=reason,
                )
            )
            invalidated_ids.append(krs.id)

        return invalidated_ids

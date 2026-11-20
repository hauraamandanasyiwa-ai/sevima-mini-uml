from dataclasses import dataclass
from datetime import time
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.exceptions import (
    CapacityExceededError,
    ScheduleConflictError,
    ScheduleNotFoundError,
)
from app.models.krs import KRSDetail
from app.models.schedule import Dosen, Jadwal, Kelas, Ruangan
from app.services.conflict_detector import Conflict, detect_schedule_conflicts


@dataclass(frozen=True)
class ScheduleData:
    """Data tervalidasi untuk membuat atau memperbarui satu pertemuan jadwal."""

    kelas_id: int
    ruangan_kode: str
    dosen_id: int
    hari: int
    jam_mulai: time
    jam_selesai: time


class SchedulingService:
    """Service layer pintu tunggal untuk manajemen Jadwal & Ruang (Minggu 7).

    Prinsip desain:
    - Single Responsibility: bebas detail HTTP, menerima `Session`.
    - `create_jadwal` dan `update_jadwal` berbagi satu method `_simpan()`.
    - Pessimistic locking dengan urutan tetap (`Ruangan` dulu, lalu `Dosen`)
      untuk mencegah race condition sekaligus mencegah deadlock.
    - Objek jadwal baru ditambahkan ke session PALING AKHIR setelah semua
      pemeriksaan lulus agar autoflush SQLAlchemy tidak membuat jadwal baru
      terdeteksi bentrok dengan dirinya sendiri.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def _kunci_ruangan_dan_dosen(
        self,
        ruangan_kode: str,
        dosen_id: int,
    ) -> tuple[Ruangan, Dosen]:
        """Mengunci baris Ruangan lebih dulu lalu baris Dosen dengan `FOR UPDATE`.

        Urutan tetap (Ruangan -> Dosen) menjamin dua transaksi paralel tidak
        saling menunggu selamanya (deadlock-free).
        """
        ruangan = self._session.scalars(
            select(Ruangan).where(Ruangan.kode == ruangan_kode).with_for_update()
        ).first()
        if ruangan is None:
            raise ScheduleNotFoundError(f"Ruangan dengan kode '{ruangan_kode}' tidak ditemukan.")

        dosen = self._session.scalars(
            select(Dosen).where(Dosen.id == dosen_id).with_for_update()
        ).first()
        if dosen is None:
            raise ScheduleNotFoundError(f"Dosen dengan ID '{dosen_id}' tidak ditemukan.")

        return ruangan, dosen

    def _cari_bentrok_db(
        self,
        data: ScheduleData,
        *,
        exclude_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Mencari jadwal yang beririsan langsung di SQL memakai indeks gabungan
        `(hari, ruangan_kode)` dan `(hari, dosen_id)` serta aturan interval
        setengah terbuka: `jam_mulai < data.jam_selesai AND jam_selesai > data.jam_mulai`.

        Saat `update`, `exclude_id` mengecualikan jadwal itu sendiri agar
        menggeser waktu kuliah tidak dianggap bentrok dengan dirinya sendiri.
        """
        conditions = [
            Jadwal.hari == data.hari,
            Jadwal.jam_mulai < data.jam_selesai,
            Jadwal.jam_selesai > data.jam_mulai,
            or_(
                Jadwal.ruangan_kode == data.ruangan_kode,
                Jadwal.dosen_id == data.dosen_id,
            ),
        ]
        if exclude_id is not None:
            conditions.append(Jadwal.id != exclude_id)

        overlapping = self._session.scalars(
            select(Jadwal).where(and_(*conditions)).order_by(Jadwal.id)
        ).all()

        conflicts: list[dict[str, Any]] = []
        for existing in overlapping:
            affected = (
                sorted([exclude_id, existing.id])
                if exclude_id is not None
                else [existing.id]
            )
            if existing.ruangan_kode == data.ruangan_kode:
                conflicts.append(
                    {
                        "type": "room_conflict",
                        "affected": affected,
                        "message": (
                            f"Ruangan {data.ruangan_kode} sudah dipakai jadwal #{existing.id} "
                            f"({existing.jam_mulai.strftime('%H:%M')}-{existing.jam_selesai.strftime('%H:%M')})."
                        ),
                    }
                )
            if existing.dosen_id == data.dosen_id:
                conflicts.append(
                    {
                        "type": "lecturer_conflict",
                        "affected": affected,
                        "message": (
                            f"Dosen #{data.dosen_id} sudah mengajar pada jadwal #{existing.id} "
                            f"({existing.jam_mulai.strftime('%H:%M')}-{existing.jam_selesai.strftime('%H:%M')})."
                        ),
                    }
                )
        return conflicts

    def check_capacity(self, ruangan: Ruangan, kelas: Kelas) -> None:
        """Hard Constraint ke-3: kebutuhan kursi <= kapasitas ruangan.

        Memakai `max(kelas.kuota, jumlah_terdaftar)` karena saat jadwal dibuat
        di awal semester jumlah peserta terdaftar di `krs_detail` masih 0,
        tetapi kelas berkuota 50 tetap tidak boleh ditaruh di ruang berkapasitas 40.
        """
        terdaftar = self._session.scalar(
            select(func.count(KRSDetail.id)).where(KRSDetail.kelas_id == kelas.id)
        ) or 0
        kebutuhan = max(kelas.kuota, int(terdaftar))

        if kebutuhan > ruangan.kapasitas:
            raise CapacityExceededError(
                f"Kapasitas ruangan {ruangan.kode} ({ruangan.kapasitas} kursi) tidak mencukupi "
                f"untuk kelas {kelas.kode_mk}-{kelas.nama_kelas} yang membutuhkan {kebutuhan} kursi "
                f"(kuota={kelas.kuota}, terdaftar={terdaftar})."
            )

    def _simpan(self, jadwal: Jadwal, data: ScheduleData, *, is_new: bool) -> Jadwal:
        try:
            kelas = self._session.get(Kelas, data.kelas_id)
            if kelas is None:
                raise ScheduleNotFoundError(f"Kelas dengan ID '{data.kelas_id}' tidak ditemukan.")

            # 1. Kunci ruangan lalu dosen (urutan tetap anti-deadlock)
            ruangan, _dosen = self._kunci_ruangan_dan_dosen(data.ruangan_kode, data.dosen_id)

            # 2. Cari bentrok di DB (kecualikan diri sendiri saat update)
            exclude_id = None if is_new else jadwal.id
            conflicts = self._cari_bentrok_db(data, exclude_id=exclude_id)
            if conflicts:
                raise ScheduleConflictError(
                    message=f"Jadwal ditolak karena ditemukan {len(conflicts)} konflik.",
                    conflicts=conflicts,
                )

            # 3. Cek kapasitas (max(kuota, terdaftar) <= kapasitas ruangan)
            self.check_capacity(ruangan, kelas)

            # 4. Baru setelah semua lolos, salin field, tambahkan objek (jika baru), lalu commit
            jadwal.kelas_id = data.kelas_id
            jadwal.ruangan_kode = data.ruangan_kode
            jadwal.dosen_id = data.dosen_id
            jadwal.hari = data.hari
            jadwal.jam_mulai = data.jam_mulai
            jadwal.jam_selesai = data.jam_selesai

            if is_new:
                self._session.add(jadwal)

            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        self._session.refresh(jadwal)
        return jadwal

    def create_jadwal(self, data: ScheduleData) -> Jadwal:
        """Membuat jadwal baru setelah lolos pemeriksaan bentrok 3D dan kapasitas."""
        return self._simpan(Jadwal(), data, is_new=True)

    def update_jadwal(self, jadwal_id: int, data: ScheduleData) -> Jadwal:
        """Memperbarui jadwal yang ada (mengecualikan dirinya sendiri dari cek bentrok)."""
        jadwal = self._session.get(Jadwal, jadwal_id)
        if jadwal is None:
            raise ScheduleNotFoundError(f"Jadwal dengan ID '{jadwal_id}' tidak ditemukan.")
        return self._simpan(jadwal, data, is_new=False)

    def delete_jadwal(self, jadwal_id: int) -> None:
        """Menghapus jadwal dalam satu transaksi (titik kait Observer Minggu 8)."""
        try:
            jadwal = self._session.get(Jadwal, jadwal_id)
            if jadwal is None:
                raise ScheduleNotFoundError(f"Jadwal dengan ID '{jadwal_id}' tidak ditemukan.")
            self._session.delete(jadwal)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def list_jadwals(self) -> list[Jadwal]:
        """Mengambil seluruh jadwal terurut berdasarkan hari dan jam mulai."""
        stmt = select(Jadwal).order_by(Jadwal.hari, Jadwal.jam_mulai, Jadwal.id)
        return list(self._session.scalars(stmt).all())

    def get_all_conflicts(self) -> list[Conflict]:
        """Mendeteksi seluruh bentrok yang terlanjur ada di database (mis. hasil impor
        data lama) menggunakan algoritma teroptimasi Grouping + Sort-and-Sweep.
        """
        jadwals = self.list_jadwals()
        return detect_schedule_conflicts(jadwals)

from decimal import Decimal

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session

from app.models.krs import KRS, KRSDetail, MataKuliah, SkalaNilai, prerequisites

# Nilai minimal lulus prasyarat adalah C (bobot = 2.00)
MIN_PASSING_BOBOT = Decimal("2.00")


def prasyarat_belum_lulus(
    session: Session,
    nim: str,
    kode_mk: str,
    semester_aktif: str,
) -> list[str]:
    """Mengembalikan daftar nama mata kuliah prasyarat dari `kode_mk` yang BELUM
    diluluskan mahasiswa `nim` pada semester sebelumnya (< `semester_aktif`)
    dengan bobot nilai minimal C (2.00).

    Menggunakan pola SQL `NOT EXISTS` dalam satu query (bebas N+1) dan
    memetakan huruf ke bobot melalui tabel `skala_nilai` sehingga terhindar dari
    jebakan perbandingan string (`nilai >= 'C'` yang justru meloloskan D/E dan
    menolak A/B).

    Setara dengan SQL murni:
        SELECT mk.nama
        FROM prerequisites p
        JOIN mata_kuliah mk ON mk.kode_mk = p.kode_prasyarat
        WHERE p.kode_mk = :kode_mk
          AND NOT EXISTS (
              SELECT 1
              FROM krs_detail kd
              JOIN krs k ON k.id = kd.krs_id
              JOIN skala_nilai sn ON sn.huruf = kd.nilai
              WHERE k.nim = :nim
                AND k.semester < :semester_aktif
                AND kd.kode_mk = p.kode_prasyarat
                AND sn.bobot >= 2.00
          )
        ORDER BY mk.kode_mk;
    """
    bukti_kelulusan = (
        select(KRSDetail.id)
        .join(KRS, KRS.id == KRSDetail.krs_id)
        .join(SkalaNilai, SkalaNilai.huruf == KRSDetail.nilai)
        .where(
            and_(
                KRS.nim == nim,
                KRS.semester < semester_aktif,
                KRSDetail.kode_mk == prerequisites.c.kode_prasyarat,
                SkalaNilai.bobot >= MIN_PASSING_BOBOT,
            )
        )
    )

    stmt = (
        select(MataKuliah.nama)
        .select_from(prerequisites)
        .join(MataKuliah, MataKuliah.kode_mk == prerequisites.c.kode_prasyarat)
        .where(
            and_(
                prerequisites.c.kode_mk == kode_mk,
                ~exists(bukti_kelulusan),
            )
        )
        .order_by(MataKuliah.kode_mk)
    )

    return list(session.scalars(stmt).all())

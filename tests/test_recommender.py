from sqlalchemy.orm import Session

from app.services.krs_recommender import KRSRecommender


def test_recommender_prioritizes_wajib_and_respects_validators(db_session: Session) -> None:
    """Challenge Opsional:
    - IF202 (Basis Data, WAJIB, Senin 08:00-10:30) bentrok dengan IF203 (Statistika, PILIHAN, Senin 09:00-11:00)
      -> WAJIB memilih IF202, bukan IF203.
    - IF204 (Jaringan Komputer, WAJIB, Senin 10:30-13:00) bersambung -> ikut dipilih.
    - IF201 (Struktur Data) prasyarat IF101 belum lulus -> disaring dengan alasan jelas.
    """
    recommender = KRSRecommender(session=db_session)
    result = recommender.recommend(
        nim="20240001",
        semester="20251",
        desired_kode_mk=["IF203", "IF202", "IF204", "IF201"],
    )

    selected_codes = {m.kode_mk for m in result.selected_courses}
    assert "IF202" in selected_codes
    assert "IF204" in selected_codes
    assert "IF203" not in selected_codes
    assert "IF201" not in selected_codes
    assert "IF201" in result.skipped_reasons
    assert "Prasyarat" in result.skipped_reasons["IF201"]
    assert result.total_sks == 6

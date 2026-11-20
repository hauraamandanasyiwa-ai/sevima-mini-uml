from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.krs import MataKuliah
from app.validators import (
    ConflictValidator,
    DuplicateValidator,
    KRSContext,
    MAX_SKS,
    PrerequisiteValidator,
    SKSValidator,
    build_validation_chain,
)


@dataclass(frozen=True)
class RecommendationResult:
    """Hasil rekomendasi kombinasi jadwal KRS bebas bentrok dan lolos seluruh validator."""

    selected_courses: list[MataKuliah]
    skipped_reasons: dict[str, str]
    total_sks: int


class KRSRecommender:
    """Challenge Opsional (+10% Bonus): Rekomendasi KRS berbasis Constraint
    Satisfaction Problem (CSP) dengan algoritma Backtracking.

    Aturan guardrail (tidak bisa ditawar):
    - Mata kuliah WAJIB (`is_wajib=True`) selalu diprioritaskan di atas PILIHAN.
    - Total SKS maksimal `target_sks` (<= `MAX_SKS` = 24).
    - Tidak ada jadwal yang saling bentrok dan seluruh prasyarat wajib terpenuhi.
    - Setiap kandidat yang dipertimbangkan & hasil akhir WAJIB diverifikasi oleh
      rantai validator KRS yang sama — algoritma hanya menyarankan, validator
      yang memutuskan.
    """

    def __init__(self, session: Session, max_sks: int = MAX_SKS) -> None:
        self._session = session
        self._max_sks = min(max_sks, MAX_SKS)
        self._prereq_validator = PrerequisiteValidator()
        self._full_chain = build_validation_chain(
            [
                DuplicateValidator(),
                SKSValidator(max_sks=self._max_sks),
                ConflictValidator(),
                PrerequisiteValidator(),
            ]
        )

    def recommend(
        self,
        nim: str,
        semester: str,
        desired_kode_mk: list[str],
        *,
        target_sks: int = MAX_SKS,
    ) -> RecommendationResult:
        cap_sks = min(target_sks, self._max_sks)
        stmt = select(MataKuliah).where(MataKuliah.kode_mk.in_(desired_kode_mk))
        found_map = {mk.kode_mk: mk for mk in self._session.scalars(stmt).all()}

        skipped_reasons: dict[str, str] = {}
        eligible: list[MataKuliah] = []

        # Langkah 1: Saring kode tidak ditemukan & prasyarat yang belum lulus lewat PrerequisiteValidator
        for kode in dict.fromkeys(desired_kode_mk):
            mk = found_map.get(kode)
            if mk is None:
                skipped_reasons[kode] = f"Mata kuliah '{kode}' tidak ditemukan."
                continue

            prereq_res = self._prereq_validator.check(
                KRSContext(
                    nim=nim,
                    semester=semester,
                    existing_courses=[],
                    new_course=mk,
                    session=self._session,
                )
            )
            if not prereq_res.ok:
                skipped_reasons[kode] = prereq_res.message
                continue

            eligible.append(mk)

        # Urutkan: wajib dulu, lalu SKS lebih besar agar pencarian cepat menemukan solusi optimal
        eligible.sort(key=lambda m: (not m.is_wajib, -m.sks, m.kode_mk))

        best_combo: list[MataKuliah] = []
        best_score: tuple[int, int, int] = (0, 0, 0)  # (jumlah_wajib, total_sks, jumlah_mk)
        conflict_validator = ConflictValidator()

        def backtrack(idx: int, chosen: list[MataKuliah], current_sks: int, wajib_count: int) -> None:
            nonlocal best_combo, best_score

            score = (wajib_count, current_sks, len(chosen))
            if score > best_score:
                best_score = score
                best_combo = list(chosen)

            if idx >= len(eligible) or current_sks == cap_sks:
                return

            # Pruning sederhana: hitung batas atas maksimum wajib & SKS tersisa
            remaining = eligible[idx:]
            max_possible_wajib = wajib_count + sum(1 for m in remaining if m.is_wajib)
            max_possible_sks = min(cap_sks, current_sks + sum(m.sks for m in remaining))
            if (max_possible_wajib, max_possible_sks, len(chosen) + len(remaining)) <= best_score:
                return

            candidate = eligible[idx]

            # Cabang 1: Coba ambil kandidat jika lolos batas SKS & ConflictValidator
            if current_sks + candidate.sks <= cap_sks:
                res = conflict_validator.check(
                    KRSContext(
                        nim=nim,
                        semester=semester,
                        existing_courses=chosen,
                        new_course=candidate,
                        session=self._session,
                    )
                )
                if res.ok:
                    chosen.append(candidate)
                    backtrack(
                        idx + 1,
                        chosen,
                        current_sks + candidate.sks,
                        wajib_count + (1 if candidate.is_wajib else 0),
                    )
                    chosen.pop()

            # Cabang 2: Lewati kandidat
            backtrack(idx + 1, chosen, current_sks, wajib_count)

        backtrack(0, [], 0, 0)

        # Langkah 2 (Guardrail akhir): verifikasi ulang setiap MK terpilih memakai rantai validator utuh
        verified: list[MataKuliah] = []
        assert self._full_chain is not None
        for mk in best_combo:
            res = self._full_chain.validate(
                KRSContext(
                    nim=nim,
                    semester=semester,
                    existing_courses=verified,
                    new_course=mk,
                    session=self._session,
                )
            )
            if res.ok:
                verified.append(mk)
            else:
                skipped_reasons[mk.kode_mk] = res.message

        verified_codes = {m.kode_mk for m in verified}
        for mk in eligible:
            if mk.kode_mk not in verified_codes and mk.kode_mk not in skipped_reasons:
                skipped_reasons[mk.kode_mk] = (
                    "Tidak dipilih karena bentrok jadwal atau melebihi target SKS."
                )

        return RecommendationResult(
            selected_courses=verified,
            skipped_reasons=skipped_reasons,
            total_sks=sum(m.sks for m in verified),
        )

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import time
from typing import Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import ScheduleNotFoundError
from app.models.krs import KRSDetail
from app.models.schedule import Jadwal, Kelas, Ruangan
from app.observers.events import HARI_LABEL
from app.services.conflict_detector import JadwalSlot, detect_schedule_conflicts

logger = logging.getLogger("simak.ai_rescheduler")

# Blok waktu kuliah standar (prioritas pagi lalu siang sesuai dokumen tugas)
STANDARD_TIME_BLOCKS: tuple[tuple[time, time], ...] = (
    (time(8, 0), time(9, 40)),
    (time(9, 40), time(11, 20)),
    (time(11, 20), time(13, 0)),
    (time(13, 0), time(14, 40)),
    (time(14, 40), time(16, 20)),
)


class LLMClient(Protocol):
    """Interface tunggal untuk pemanggilan LLM agar mudah diganti `FakeLLMClient` saat testing."""

    def complete(self, prompt: str) -> str: ...


class RescheduleSuggestion(BaseModel):
    """Saringan ke-2: Skema Pydantic untuk satu saran jadwal alternatif dari AI."""

    hari: int = Field(..., ge=1, le=6)
    jam_mulai: time
    jam_selesai: time
    ruangan_kode: str = Field(..., min_length=1, max_length=16)
    alasan: str = Field(..., min_length=1, max_length=400)

    @model_validator(mode="after")
    def _validate_time_range(self) -> "RescheduleSuggestion":
        if self.jam_selesai <= self.jam_mulai:
            raise ValueError("jam_selesai harus lebih lambat dari jam_mulai.")
        return self


@dataclass(frozen=True)
class AvailableSlot:
    """Satu slot kosong yang dihitung oleh KODE KITA SENDIRI (bukan dikarang AI)."""

    hari: int
    jam_mulai: time
    jam_selesai: time
    ruangan_kode: str
    ruangan_kapasitas: int


def _kebutuhan_kursi(session: Session, kelas: Kelas) -> int:
    terdaftar = session.scalar(
        select(func.count(KRSDetail.id)).where(KRSDetail.kelas_id == kelas.id)
    ) or 0
    return max(kelas.kuota, int(terdaftar))


def _durasi_menit(mulai: time, selesai: time) -> int:
    return (selesai.hour * 60 + selesai.minute) - (mulai.hour * 60 + mulai.minute)


def compute_available_slots(
    session: Session,
    jadwal: Jadwal,
    *,
    max_candidates: int = 24,
) -> list[AvailableSlot]:
    """Menghitung daftar slot tersedia secara deterministik dari database menggunakan
    `detect_schedule_conflicts` (Minggu 7). AI HANYA boleh memilih dari daftar ini
    dan memberi alasan; AI tidak pernah dipercaya mengarang slot sendiri.
    """
    kelas = jadwal.kelas or session.get(Kelas, jadwal.kelas_id)
    if kelas is None:
        return []

    kebutuhan = _kebutuhan_kursi(session, kelas)
    rooms = list(
        session.scalars(
            select(Ruangan)
            .where(Ruangan.kapasitas >= kebutuhan)
            .order_by(Ruangan.kapasitas, Ruangan.kode)
        ).all()
    )
    existing_jadwals = list(
        session.scalars(select(Jadwal).where(Jadwal.id != jadwal.id)).all()
    )

    # Susun blok waktu kandidat: pertahankan durasi kuliah asli bila berbeda
    durasi_asli = _durasi_menit(jadwal.jam_mulai, jadwal.jam_selesai)
    blocks: list[tuple[time, time]] = []
    for mulai, selesai in STANDARD_TIME_BLOCKS:
        if durasi_asli > 0 and durasi_asli != _durasi_menit(mulai, selesai):
            total_end = mulai.hour * 60 + mulai.minute + durasi_asli
            if total_end <= 17 * 60:
                selesai = time(total_end // 60, total_end % 60)
        blocks.append((mulai, selesai))

    available: list[AvailableSlot] = []
    for hari in range(1, 7):
        for jam_mulai, jam_selesai in blocks:
            for room in rooms:
                candidate = JadwalSlot(
                    id=-1,
                    hari=hari,
                    jam_mulai=jam_mulai,
                    jam_selesai=jam_selesai,
                    ruangan_kode=room.kode,
                    dosen_id=jadwal.dosen_id,
                )
                conflicts = detect_schedule_conflicts([*existing_jadwals, candidate])
                if not any(-1 in c.affected for c in conflicts):
                    available.append(
                        AvailableSlot(
                            hari=hari,
                            jam_mulai=jam_mulai,
                            jam_selesai=jam_selesai,
                            ruangan_kode=room.kode,
                            ruangan_kapasitas=room.kapasitas,
                        )
                    )
                    if len(available) >= max_candidates:
                        return available
    return available


def build_reschedule_prompt(
    jadwal: Jadwal,
    available_slots: list[AvailableSlot],
) -> str:
    """Menyusun prompt terstruktur untuk AI Scheduling Assistant (Langkah 3)."""
    kelas = jadwal.kelas
    mk_label = (
        f"{kelas.kode_mk} - {kelas.mata_kuliah.nama} (Kelas {kelas.nama_kelas})"
        if kelas and kelas.mata_kuliah
        else f"Kelas #{jadwal.kelas_id}"
    )
    dosen_nama = jadwal.dosen.nama if jadwal.dosen else f"Dosen #{jadwal.dosen_id}"

    slot_lines = [
        f"- hari={s.hari} ({HARI_LABEL.get(s.hari, s.hari)}), "
        f"jam_mulai={s.jam_mulai.strftime('%H:%M')}, "
        f"jam_selesai={s.jam_selesai.strftime('%H:%M')}, "
        f"ruangan_kode={s.ruangan_kode} (kapasitas={s.ruangan_kapasitas})"
        for s in available_slots
    ]
    slots_text = "\n".join(slot_lines) if slot_lines else "(tidak ada slot tersedia)"

    return (
        "Anda adalah Scheduling Assistant akademik untuk SIMAK Mini.\n"
        "Tugas Anda: rekomendasikan tepat 3 slot pengganti terbaik untuk jadwal yang bentrok.\n"
        "Syarat:\n"
        "1. Pilih HANYA dari daftar slot tersedia di bawah.\n"
        "2. Kapasitas ruangan mencukupi dan tidak bentrok dengan dosen.\n"
        "3. Prioritaskan jam pagi atau siang dengan gangguan minimal bagi mahasiswa.\n\n"
        "Jadwal yang bentrok:\n"
        f"- jadwal_id: {jadwal.id}\n"
        f"- mata_kuliah: {mk_label}\n"
        f"- dosen: {dosen_nama} (id={jadwal.dosen_id})\n"
        f"- slot_saat_ini: hari={jadwal.hari} ({HARI_LABEL.get(jadwal.hari, jadwal.hari)}), "
        f"{jadwal.jam_mulai.strftime('%H:%M')}-{jadwal.jam_selesai.strftime('%H:%M')}, "
        f"ruangan={jadwal.ruangan_kode}\n\n"
        "Daftar slot tersedia (sudah diverifikasi bebas bentrok oleh sistem):\n"
        f"{slots_text}\n\n"
        "Balas HANYA JSON array valid tanpa teks tambahan, dengan skema:\n"
        '[{"hari": 2, "jam_mulai": "08:00", "jam_selesai": "09:40", '
        '"ruangan_kode": "A101", "alasan": "Slot pagi bebas bentrok dengan kapasitas memadai."}]'
    )


def _extract_json_array(raw_text: str) -> list[object]:
    """Saringan 1 (Parsing): ambil bagian di antara `[` pertama dan `]` terakhir.
    Jika bukan JSON list valid, kembalikan `[]` (tidak pernah crash).
    """
    if not raw_text:
        return []
    start = raw_text.find("[")
    end = raw_text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        parsed = json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def validate_ai_suggestions(
    raw_text: str,
    session: Session,
    jadwal: Jadwal,
    *,
    max_results: int = 3,
) -> list[RescheduleSuggestion]:
    """Empat saringan ketat untuk keluaran AI:
    1. Parsing JSON aman (di antara `[` dan `]`, rusak -> `[]`).
    2. Validasi skema Pydantic per item (rusak dibuang satu per satu).
    3. Validasi ruangan ada di DB & kapasitas >= max(kuota, terdaftar).
    4. Validasi bentrok memakai `detect_schedule_conflicts` (calon diberi `id=-1`;
       jika ada konflik yang `affected`-nya memuat `-1`, saran dibuang).

    AI boleh menyarankan, tetapi validator KITA yang memutuskan.
    """
    raw_items = _extract_json_array(raw_text)
    if not raw_items:
        return []

    kelas = jadwal.kelas or session.get(Kelas, jadwal.kelas_id)
    if kelas is None:
        return []
    kebutuhan = _kebutuhan_kursi(session, kelas)

    existing_jadwals = list(
        session.scalars(select(Jadwal).where(Jadwal.id != jadwal.id)).all()
    )

    valid_suggestions: list[RescheduleSuggestion] = []
    seen_keys: set[tuple[int, time, time, str]] = set()

    for raw_item in raw_items:
        # Saringan 2: Skema Pydantic per item
        if not isinstance(raw_item, dict):
            continue
        try:
            suggestion = RescheduleSuggestion.model_validate(raw_item)
        except ValidationError:
            continue

        # Hindari duplikat slot yang identik
        dedup_key = (
            suggestion.hari,
            suggestion.jam_mulai,
            suggestion.jam_selesai,
            suggestion.ruangan_kode,
        )
        if dedup_key in seen_keys:
            continue

        # Saringan 3: Ruangan ada di DB & kapasitas mencukupi
        ruangan = session.get(Ruangan, suggestion.ruangan_kode)
        if ruangan is None or ruangan.kapasitas < kebutuhan:
            continue

        # Saringan 4: Deteksi bentrok 3 dimensi dengan detect_schedule_conflicts
        candidate = JadwalSlot(
            id=-1,
            hari=suggestion.hari,
            jam_mulai=suggestion.jam_mulai,
            jam_selesai=suggestion.jam_selesai,
            ruangan_kode=suggestion.ruangan_kode,
            dosen_id=jadwal.dosen_id,
        )
        conflicts = detect_schedule_conflicts([*existing_jadwals, candidate])
        if any(-1 in c.affected for c in conflicts):
            continue

        seen_keys.add(dedup_key)
        valid_suggestions.append(suggestion)
        if len(valid_suggestions) >= max_results:
            break

    return valid_suggestions


class GeminiLLMClient:
    """Klien LLM gratis menggunakan Gemini Flash (Google AI Studio) dengan
    temperature rendah dan JSON mode.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def complete(self, prompt: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={self._api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        response = httpx.post(url, json=payload, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


class HeuristicFallbackLLMClient:
    """Klien fallback lokal (tanpa API key) yang membaca daftar slot tersedia dari prompt
    dan memprioritaskan jam pagi/siang agar dashboard tetap dapat didemokan offline.
    """

    _SLOT_RE = re.compile(
        r"hari=(\d+).*?jam_mulai=(\d{2}:\d{2}),\s*jam_selesai=(\d{2}:\d{2}),\s*ruangan_kode=([A-Za-z0-9_-]+)"
    )

    def complete(self, prompt: str) -> str:
        matches = self._SLOT_RE.findall(prompt)
        # Prioritaskan slot pagi (jam < 12:00) lalu siang
        ordered = sorted(matches, key=lambda m: (0 if m[1] < "12:00" else 1, int(m[0]), m[1]))
        suggestions = []
        for hari_str, jam_mulai, jam_selesai, ruangan_kode in ordered[:3]:
            sesi = "pagi" if jam_mulai < "12:00" else "siang"
            hari_int = int(hari_str)
            hari_nama = HARI_LABEL.get(hari_int, f"Hari {hari_int}")
            suggestions.append(
                {
                    "hari": hari_int,
                    "jam_mulai": jam_mulai,
                    "jam_selesai": jam_selesai,
                    "ruangan_kode": ruangan_kode,
                    "alasan": (
                        f"Slot {sesi} ({hari_nama} {jam_mulai}-{jam_selesai} di {ruangan_kode}) "
                        "bebas bentrok ruangan & dosen serta kapasitas ruangan mencukupi."
                    ),
                }
            )
        return json.dumps(suggestions, ensure_ascii=False)


def build_default_llm_client() -> LLMClient:
    """Memilih Gemini Flash jika `GEMINI_API_KEY` tersedia di environment,
    atau fallback lokal jika dijalankan offline tanpa API key.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        return GeminiLLMClient(api_key=api_key)
    return HeuristicFallbackLLMClient()


class AIReschedulerService:
    """Orkestrator penjadwalan ulang berbasis AI dengan 4-stage validator."""

    def __init__(
        self,
        session: Session,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._session = session
        self._llm = llm_client if llm_client is not None else build_default_llm_client()

    def suggest_alternatives(
        self,
        jadwal_id: int,
        *,
        max_results: int = 3,
    ) -> list[RescheduleSuggestion]:
        jadwal = self._session.get(Jadwal, jadwal_id)
        if jadwal is None:
            raise ScheduleNotFoundError(f"Jadwal dengan ID '{jadwal_id}' tidak ditemukan.")

        available_slots = compute_available_slots(self._session, jadwal)
        prompt = build_reschedule_prompt(jadwal, available_slots)

        try:
            raw_output = self._llm.complete(prompt)
        except Exception:
            logger.exception("Pemanggilan LLM gagal; memakai fallback lokal.")
            raw_output = HeuristicFallbackLLMClient().complete(prompt)

        return validate_ai_suggestions(
            raw_output,
            self._session,
            jadwal,
            max_results=max_results,
        )

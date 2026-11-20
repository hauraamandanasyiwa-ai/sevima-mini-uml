from fastapi.testclient import TestClient


def test_api_polymorphic_status_codes_403_409_400_201_200(api_client: TestClient) -> None:
    """Puncak piramida testing: memastikan kode HTTP 201, 200, 400, 403, 409
    benar-benar keluar dari FastAPI melalui single exception handler polimorfik.
    """
    # 1. Tambah Basis Data -> 201
    r1 = api_client.post("/krs/20240001/20251/courses", json={"kode_mk": "IF202"})
    assert r1.status_code == 201

    # 2. Tambah Statistika (bentrok) -> 400 Bad Request
    r2 = api_client.post("/krs/20240001/20251/courses", json={"kode_mk": "IF203"})
    assert r2.status_code == 400
    assert "bentrok" in r2.json()["detail"].lower()

    # 3. Coba approve langsung dari DRAFT -> 409 Conflict (TransitionError)
    r3 = api_client.post("/krs/20240001/20251/approve", json={"dosen_pa_id": "PA001"})
    assert r3.status_code == 409
    assert "Transisi tidak diizinkan" in r3.json()["detail"]

    # 4. Submit KRS oleh Budi -> 200 OK
    r4 = api_client.post("/krs/20240001/20251/submit", json={"actor_nim": "20240001"})
    assert r4.status_code == 200
    assert r4.json()["status"] == "submitted"
    current_version = r4.json()["version"]

    # 5. Tambah MK saat SUBMITTED -> 409 Conflict (KRSLockedError)
    r5 = api_client.post("/krs/20240001/20251/courses", json={"kode_mk": "IF204"})
    assert r5.status_code == 409

    # 6. Approve oleh dosen PA yang salah -> 403 Forbidden (ForbiddenError)
    r6 = api_client.post(
        "/krs/20240001/20251/approve",
        json={"dosen_pa_id": "PA999", "version": current_version},
    )
    assert r6.status_code == 403

    # 7. Approve oleh Dosen PA sah dengan versi benar -> 200 OK
    r7 = api_client.post(
        "/krs/20240001/20251/approve",
        json={"dosen_pa_id": "PA001", "version": current_version},
    )
    assert r7.status_code == 200
    assert r7.json()["status"] == "approved"
    assert r7.json()["approved_at"] is not None

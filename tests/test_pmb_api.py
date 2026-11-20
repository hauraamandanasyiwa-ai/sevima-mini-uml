import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JalurMasuk, ProgramStudi
from tests.conftest import daftar


def test_health_root(client: TestClient) -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert "Swagger UI" in res.json()["message"]


def test_register_success(
    client: TestClient,
    prodi_ti: ProgramStudi,
    jalur_snbp: JalurMasuk,
) -> None:
    # Act
    res = daftar(
        client,
        nama_lengkap="Sinta Dewi",
        email="sinta.dewi@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    )

    # Assert
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "sinta.dewi@example.com"
    assert body["status"] == "pending"
    assert body["nim"] is None
    assert body["approved_at"] is None


def test_register_duplicate_email(
    client: TestClient,
    prodi_ti: ProgramStudi,
    jalur_snbp: JalurMasuk,
) -> None:
    # Arrange
    first = daftar(
        client,
        email="duplikat@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    )
    assert first.status_code == 201

    # Act
    second = daftar(
        client,
        nama_lengkap="Orang Lain",
        email="DUPLIKAT@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    )

    # Assert
    assert second.status_code == 409
    assert "Email sudah terdaftar" in second.json()["detail"]


def test_register_invalid_reference(
    client: TestClient,
    prodi_ti: ProgramStudi,
    jalur_snbp: JalurMasuk,
) -> None:
    res_bad_prodi = daftar(
        client,
        email="badprodi@example.com",
        program_studi_id=999,
        jalur_masuk_id=jalur_snbp.id,
    )
    assert res_bad_prodi.status_code == 400

    res_bad_jalur = daftar(
        client,
        email="badjalur@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=999,
    )
    assert res_bad_jalur.status_code == 400


def test_invalid_phone_format(
    client: TestClient,
    prodi_ti: ProgramStudi,
    jalur_snbp: JalurMasuk,
) -> None:
    """Sesuai keputusan ADR-001, error validasi Pydantic dikembalikan sebagai 400 Bad Request."""
    res = daftar(
        client,
        email="badphone@example.com",
        phone="021123456",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    )
    assert res.status_code == 400
    body = res.json()
    assert body["detail"] == "Validasi input gagal"
    assert any(err["field"] == "phone" for err in body["errors"])


def test_approve_generate_nim(
    client: TestClient,
    prodi_ti: ProgramStudi,
    jalur_snbp: JalurMasuk,
) -> None:
    """Approve dua pendaftar prodi TI harus menghasilkan NIM 11 digit yang berurutan."""
    # Arrange
    sinta = daftar(
        client,
        nama_lengkap="Sinta Dewi",
        email="sinta@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()
    budi = daftar(
        client,
        nama_lengkap="Budi Santoso",
        email="budi@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()

    # Act
    res_sinta = client.put(f"/api/pmb/approve/{sinta['id']}")
    res_budi = client.put(f"/api/pmb/approve/{budi['id']}")

    # Assert
    assert res_sinta.status_code == 200
    assert res_budi.status_code == 200

    data_sinta = res_sinta.json()
    data_budi = res_budi.json()

    assert data_sinta["status"] == "approved"
    assert data_sinta["approved_at"] is not None
    assert re.fullmatch(r"\d{4}001\d{4}", data_sinta["nim"]) is not None
    assert re.fullmatch(r"\d{4}001\d{4}", data_budi["nim"]) is not None

    seq_sinta = int(data_sinta["nim"][-4:])
    seq_budi = int(data_budi["nim"][-4:])
    assert seq_budi == seq_sinta + 1


def test_approve_idempotent(
    client: TestClient,
    prodi_ti: ProgramStudi,
    jalur_snbp: JalurMasuk,
) -> None:
    """Approve 2x pada pendaftar sama harus mengembalikan NIM identik tanpa menaikkan counter."""
    # Arrange
    sinta = daftar(
        client,
        nama_lengkap="Sinta Dewi",
        email="sinta.idem@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()
    budi = daftar(
        client,
        nama_lengkap="Budi Santoso",
        email="budi.idem@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()

    # Act: approve Sinta dua kali, lalu approve Budi
    first = client.put(f"/api/pmb/approve/{sinta['id']}")
    second = client.put(f"/api/pmb/approve/{sinta['id']}")
    next_applicant = client.put(f"/api/pmb/approve/{budi['id']}")

    # Assert
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["nim"] == second.json()["nim"]
    assert first.json()["approved_at"] == second.json()["approved_at"]

    # Buktikan counter tidak ikut naik saat approve ulang (Budi mendapat 0002, bukan 0003)
    assert next_applicant.status_code == 200
    assert int(next_applicant.json()["nim"][-4:]) == int(first.json()["nim"][-4:]) + 1


def test_approve_not_found(client: TestClient) -> None:
    res = client.put("/api/pmb/approve/9999")
    assert res.status_code == 404


def test_approve_rejected_returns_409(
    client: TestClient,
    prodi_ti: ProgramStudi,
    jalur_snbp: JalurMasuk,
) -> None:
    # Arrange
    pendaftar = daftar(
        client,
        email="ditolak@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()
    reject_res = client.put(f"/api/pmb/reject/{pendaftar['id']}")
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"

    # Act
    approve_res = client.put(f"/api/pmb/approve/{pendaftar['id']}")

    # Assert
    assert approve_res.status_code == 409


def test_approve_invalid_kode_prodi_returns_400(
    client: TestClient,
    db: Session,
    jalur_snbp: JalurMasuk,
) -> None:
    """Jika kode prodi tidak berupa 3 digit angka, approve harus mengembalikan 400 Bad Request."""
    # Arrange: sisipkan prodi dengan kode non-digit langsung di DB untuk menyimulasikan data kotor
    bad_prodi = ProgramStudi(kode="TI", nama="Prodi Rusak", fakultas="Fakultas Uji")
    db.add(bad_prodi)
    db.commit()
    db.refresh(bad_prodi)

    pendaftar = daftar(
        client,
        email="badkode@example.com",
        program_studi_id=bad_prodi.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()

    # Act
    res = client.put(f"/api/pmb/approve/{pendaftar['id']}")

    # Assert
    assert res.status_code == 400


def test_reject_idempotent_and_guards(
    client: TestClient,
    prodi_ti: ProgramStudi,
    jalur_snbp: JalurMasuk,
) -> None:
    # Not found -> 404
    assert client.put("/api/pmb/reject/9999").status_code == 404

    # Reject 2x -> 200 (idempotent)
    p1 = daftar(
        client,
        email="reject1@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()
    assert client.put(f"/api/pmb/reject/{p1['id']}").status_code == 200
    assert client.put(f"/api/pmb/reject/{p1['id']}").status_code == 200

    # Reject pendaftar yang sudah approved -> 409
    p2 = daftar(
        client,
        email="approved.first@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()
    assert client.put(f"/api/pmb/approve/{p2['id']}").status_code == 200
    assert client.put(f"/api/pmb/reject/{p2['id']}").status_code == 409


def test_get_status_success_and_not_found(
    client: TestClient,
    prodi_ti: ProgramStudi,
    jalur_snbp: JalurMasuk,
) -> None:
    # 404 jika tidak ditemukan
    assert client.get("/api/pmb/status/9999").status_code == 404

    # Arrange
    pendaftar = daftar(
        client,
        nama_lengkap="Ayu Lestari",
        email="ayu@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()
    client.put(f"/api/pmb/approve/{pendaftar['id']}")

    # Act
    res = client.get(f"/api/pmb/status/{pendaftar['id']}")

    # Assert
    assert res.status_code == 200
    body = res.json()
    assert body["nama_lengkap"] == "Ayu Lestari"
    assert body["program_studi"] == "Teknik Informatika"
    assert body["jalur_masuk"] == "SNBP"
    assert body["status"] == "approved"
    assert body["nim"] is not None
    # Pastikan data pribadi sensitif tidak ikut terekspos
    assert "alamat" not in body
    assert "tanggal_lahir" not in body
    assert "phone" not in body
    assert "email" not in body


def test_get_stats_aggregation_and_zero_counts(
    client: TestClient,
    prodi_ti: ProgramStudi,
    prodi_si: ProgramStudi,
    jalur_snbp: JalurMasuk,
    jalur_snbt: JalurMasuk,
    jalur_mandiri: JalurMasuk,
) -> None:
    """Statistik harus menggunakan GROUP BY + OUTER JOIN sehingga prodi/jalur 0 pendaftar tetap tampil."""
    # Arrange: 2 pendaftar di TI (1 approved, 1 rejected), 1 pendaftar pending di TI jalur SNBT
    # Prodi SI dan Jalur Mandiri sengaja dibiarkan 0 pendaftar.
    p1 = daftar(
        client,
        email="stat1@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()
    p2 = daftar(
        client,
        email="stat2@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbp.id,
    ).json()
    daftar(
        client,
        email="stat3@example.com",
        program_studi_id=prodi_ti.id,
        jalur_masuk_id=jalur_snbt.id,
    )

    client.put(f"/api/pmb/approve/{p1['id']}")
    client.put(f"/api/pmb/reject/{p2['id']}")

    # Act
    res = client.get("/api/pmb/stats")

    # Assert
    assert res.status_code == 200
    stats = res.json()
    assert stats["total_pendaftar"] == 3
    assert stats["per_status"] == {"pending": 1, "approved": 1, "rejected": 1}

    prodi_map = {item["kode"]: item["jumlah"] for item in stats["per_program_studi"]}
    assert prodi_map == {"001": 3, "002": 0}

    jalur_map = {item["nama"]: item["jumlah"] for item in stats["per_jalur_masuk"]}
    assert jalur_map == {"SNBP": 2, "SNBT": 1, "Mandiri": 0}

"""Login, papéis e visibilidade dos documentos por área."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from conftest import MANUAL, POLICY, SALARIES, SAMPLES, login
from sqlalchemy import inspect, text

from app.security import create_token, decode_token, hash_password, verify_password

SALARY_QUESTION = "Qual a faixa salarial do engenheiro de automação pleno?"


@pytest.fixture
def company(client):
    """Empresa de exemplo: benefícios global, manual para Engenharia e Estoque, salários só para o RH."""
    areas = {
        name: client.post("/api/areas", json={"name": name}).json()["id"] for name in ("Engenharia", "Estoque", "RH")
    }

    def user(username, area_names):
        body = {
            "username": username,
            "name": username.title(),
            "password": "senha123",
            "area_ids": [areas[a] for a in area_names],
        }
        assert client.post("/api/users", json=body).status_code == 201
        return login(client, username, "senha123")

    def upload(path, is_global, area_names=()):
        data = {"is_global": str(is_global).lower(), "area_ids": [areas[a] for a in area_names]}
        response = client.post(
            "/api/documents", files=[("files", (path.name, path.read_bytes(), "application/pdf"))], data=data
        )
        assert response.status_code == 201, response.text
        return response.json()["documents"][0]["id"]

    docs = {
        "policy": upload(POLICY, True),
        "manual": upload(MANUAL, False, ["Engenharia", "Estoque"]),
        "salaries": upload(SALARIES, False, ["RH"]),
    }
    return {
        "areas": areas,
        "docs": docs,
        "eng": user("ana.eng", ["Engenharia"]),
        "est": user("bruno.est", ["Estoque"]),
        "rh": user("carla.rh", ["RH"]),
        "none": user("sem.area", []),
    }


def visible(client, headers) -> set[str]:
    response = client.get("/api/documents", headers=headers)
    assert response.status_code == 200
    return {d["filename"] for d in response.json()}


class TestLogin:
    def test_wrong_password_and_unknown_user_get_the_same_answer(self, client):
        wrong = client.post("/api/auth/login", data={"username": "admin", "password": "errada"})
        unknown = client.post("/api/auth/login", data={"username": "ninguem", "password": "errada"})
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json()

    def test_me_returns_user_and_areas(self, client, company):
        me = client.get("/api/auth/me", headers=company["eng"]).json()
        assert me["username"] == "ana.eng"
        assert me["is_admin"] is False
        assert [a["name"] for a in me["areas"]] == ["Engenharia"]

    @pytest.mark.parametrize("path", ["/api/documents", "/api/auth/me", "/api/areas"])
    def test_routes_require_a_token(self, client, path):
        assert client.get(path, headers={"Authorization": ""}).status_code == 401

    def test_invalid_token_is_rejected(self, client):
        assert client.get("/api/documents", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401

    def test_health_stays_public(self, client):
        assert client.get("/api/health", headers={"Authorization": ""}).status_code == 200


class TestVisibility:
    def test_each_user_sees_global_documents_plus_their_areas(self, client, company):
        assert visible(client, company["eng"]) == {POLICY.name, MANUAL.name}
        assert visible(client, company["est"]) == {POLICY.name, MANUAL.name}
        assert visible(client, company["rh"]) == {POLICY.name, SALARIES.name}
        assert visible(client, company["none"]) == {POLICY.name}
        assert visible(client, {}) == {POLICY.name, MANUAL.name, SALARIES.name}  # admin

    def test_chat_never_retrieves_chunks_the_user_cannot_see(self, client, company):
        for who in ("eng", "est", "none"):
            body = client.post("/api/chat", json={"question": SALARY_QUESTION}, headers=company[who]).json()
            assert SALARIES.name not in {s["filename"] for s in body["sources"]}
            assert "9.500" not in body["answer"]

    def test_authorized_area_gets_the_restricted_answer(self, client, company):
        body = client.post("/api/chat", json={"question": SALARY_QUESTION}, headers=company["rh"]).json()
        cited = [s for s in body["sources"] if s["cited"]]
        assert cited[0]["filename"] == SALARIES.name
        assert "9.500" in body["answer"]

    def test_document_filter_cannot_be_used_to_bypass_access(self, client, company):
        body = client.post(
            "/api/chat",
            json={"question": SALARY_QUESTION, "document_ids": [company["docs"]["salaries"]]},
            headers=company["eng"],
        ).json()
        assert body["sources"] == []

    def test_shared_document_serves_both_areas(self, client, company):
        for who in ("eng", "est"):
            body = client.post("/api/chat", json={"question": "Qual a potência do motor?"}, headers=company[who]).json()
            assert MANUAL.name in {s["filename"] for s in body["sources"]}

    def test_hidden_file_returns_404_as_if_it_did_not_exist(self, client, company):
        response = client.get(f"/api/documents/{company['docs']['salaries']}/file", headers=company["eng"])
        assert response.status_code == 404

    def test_file_link_accepts_token_in_query_string(self, client, company):
        token = company["rh"]["Authorization"].split()[1]
        response = client.get(
            f"/api/documents/{company['docs']['salaries']}/file?access_token={token}", headers={"Authorization": ""}
        )
        assert response.status_code == 200
        assert response.content == SALARIES.read_bytes()

    def test_changing_access_takes_effect_immediately(self, client, company):
        doc = company["docs"]["salaries"]
        response = client.put(
            f"/api/documents/{doc}/access", json={"is_global": False, "area_ids": [company["areas"]["Engenharia"]]}
        )
        assert [a["name"] for a in response.json()["areas"]] == ["Engenharia"]
        assert SALARIES.name in visible(client, company["eng"])
        assert SALARIES.name not in visible(client, company["rh"])

    def test_restricted_document_needs_at_least_one_area(self, client, company):
        doc = company["docs"]["manual"]
        assert client.put(f"/api/documents/{doc}/access", json={"is_global": False, "area_ids": []}).status_code == 422
        upload = client.post(
            "/api/documents",
            files=[("files", (POLICY.name, POLICY.read_bytes(), "application/pdf"))],
            data={"is_global": "false"},
        )
        assert upload.status_code == 422

    def test_deleting_an_area_unlinks_documents_and_users(self, client, company):
        assert client.delete(f"/api/areas/{company['areas']['RH']}").status_code == 204
        assert visible(client, company["rh"]) == {POLICY.name}
        salaries = next(d for d in client.get("/api/documents").json() if d["filename"] == SALARIES.name)
        assert salaries["areas"] == []  # só o administrador continua vendo


class TestAdminOnly:
    @pytest.mark.parametrize(
        ("method", "path", "kwargs"),
        [
            ("post", "/api/documents", {"files": [("files", ("a.pdf", b"x", "application/pdf"))]}),
            ("delete", "/api/documents/1", {}),
            ("put", "/api/documents/1/access", {"json": {"is_global": True}}),
            ("get", "/api/users", {}),
            ("post", "/api/areas", {"json": {"name": "Nova"}}),
            ("get", "/api/eval/cases", {}),
            ("post", "/api/eval/runs", {"json": {}}),
        ],
    )
    def test_regular_user_gets_403(self, client, company, method, path, kwargs):
        response = getattr(client, method)(path, headers=company["eng"], **kwargs)
        assert response.status_code == 403

    def test_admin_cannot_lock_themselves_out(self, client):
        me = client.get("/api/auth/me").json()
        demote = client.put(f"/api/users/{me['id']}", json={"name": "Admin", "is_admin": False})
        assert demote.status_code == 422
        assert client.delete(f"/api/users/{me['id']}").status_code == 422

    def test_duplicates_are_rejected(self, client, company):
        assert client.post("/api/areas", json={"name": "RH"}).status_code == 409
        body = {"username": "ana.eng", "name": "Outra Ana", "password": "senha123"}
        assert client.post("/api/users", json=body).status_code == 409

    def test_admin_can_reset_password_and_move_user_between_areas(self, client, company):
        users = {u["username"]: u for u in client.get("/api/users").json()}
        body = {"name": "Ana", "is_admin": False, "area_ids": [company["areas"]["RH"]], "password": "nova-senha"}
        assert client.put(f"/api/users/{users['ana.eng']['id']}", json=body).status_code == 200
        headers = login(client, "ana.eng", "nova-senha")
        assert visible(client, headers) == {POLICY.name, SALARIES.name}


class TestSecurityHelpers:
    def test_password_hash_is_salted_and_verifiable(self):
        first, second = hash_password("segredo"), hash_password("segredo")
        assert first != second
        assert verify_password("segredo", first)
        assert not verify_password("outra", first)
        assert not verify_password("segredo", "formato-invalido")

    def test_token_round_trip_and_expiry(self):
        assert decode_token(create_token(42)) == 42
        expired = jwt.encode(
            {"sub": "42", "exp": datetime.now(UTC) - timedelta(minutes=1)}, "dev-secret-troque-em-producao", "HS256"
        )
        assert decode_token(expired) is None
        assert decode_token("lixo") is None


def test_existing_database_gains_the_access_column(database):
    """Bancos criados antes desta versão não tinham is_global; init_db acrescenta a coluna."""
    from app.db import init_db

    with database.begin() as conn:
        conn.execute(text("ALTER TABLE documents DROP COLUMN is_global"))
    init_db()
    columns = {c["name"] for c in inspect(database).get_columns("documents")}
    assert "is_global" in columns


def test_seed_creates_demo_company(client):
    from app.seed import seed

    seed(SAMPLES)
    assert visible(client, login(client, "estoque", "demo1234")) == {POLICY.name, MANUAL.name}
    assert visible(client, login(client, "rh", "demo1234")) == {POLICY.name, SALARIES.name}
    seed(SAMPLES)  # rodar de novo não duplica nada
    assert len(client.get("/api/documents").json()) == 3

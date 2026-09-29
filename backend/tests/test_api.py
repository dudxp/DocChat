"""Testes de ponta a ponta pela API, com PostgreSQL + pgvector reais e o provedor fake."""

import io
import json

from conftest import MANUAL, SAMPLES


def test_health_reports_provider(client):
    body = client.get("/api/health").json()
    assert body["provider"] == "fake"
    assert body["search_mode"] == "hybrid"


class TestDocuments:
    def test_upload_indexes_pages_and_chunks(self, client, uploaded):
        docs = {d["filename"]: d for d in client.get("/api/documents").json()}
        manual = docs["manual-esteira-et200.pdf"]
        assert manual["num_units"] == 6
        assert manual["kind"] == "pdf"
        assert manual["chunk_count"] >= 6

    def test_accepts_formats_other_than_pdf(self, client):
        files = [("files", ("notas.txt", "manutenção preventiva".encode(), "text/plain"))]
        created = client.post("/api/documents", files=files).json()["documents"]
        assert created[0]["kind"] == "text"
        assert created[0]["chunk_count"] == 1

    def test_rejects_unsupported_format(self, client):
        response = client.post("/api/documents", files=[("files", ("foto.jpg", b"\xff\xd8\xff", "image/jpeg"))])
        assert response.status_code == 422
        assert "Formato não suportado" in response.json()["detail"][0]["error"]

    def test_rejects_corrupted_pdf(self, client):
        response = client.post("/api/documents", files=[("files", ("x.pdf", b"%PDF-1.4 lixo", "application/pdf"))])
        assert response.status_code == 422

    def test_partial_upload_returns_created_and_errors(self, client):
        files = [
            ("files", (MANUAL.name, MANUAL.read_bytes(), "application/pdf")),
            ("files", ("foto.jpg", b"\xff\xd8\xff", "image/jpeg")),
        ]
        body = client.post("/api/documents", files=files).json()
        assert len(body["documents"]) == 1
        assert body["errors"][0]["filename"] == "foto.jpg"

    def test_serves_original_pdf(self, client, uploaded):
        response = client.get(f"/api/documents/{uploaded[MANUAL.name]}/file")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "inline" in response.headers["content-disposition"]
        assert response.content == MANUAL.read_bytes()

    def test_serves_other_formats_as_download_with_their_own_type(self, client):
        """O navegador não abre .xlsx; servir como application/pdf faria ele salvar um arquivo quebrado."""
        from openpyxl import Workbook

        workbook = Workbook()
        workbook.active.title = "Custos"
        workbook.active.append(["Item", "Valor"])
        workbook.active.append(["Motor", 1500])
        buffer = io.BytesIO()
        workbook.save(buffer)

        created = client.post("/api/documents", files=[("files", ("custos.xlsx", buffer.getvalue()))]).json()
        response = client.get(f"/api/documents/{created['documents'][0]['id']}/file")
        assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
        assert "attachment" in response.headers["content-disposition"]

    def test_delete_removes_document_and_chunks(self, client, uploaded):
        assert client.delete(f"/api/documents/{uploaded[MANUAL.name]}").status_code == 204
        names = [d["filename"] for d in client.get("/api/documents").json()]
        assert MANUAL.name not in names
        assert client.delete(f"/api/documents/{uploaded[MANUAL.name]}").status_code == 404


class TestChat:
    def test_answer_cites_the_page_where_the_information_is(self, client, uploaded):
        body = client.post("/api/chat", json={"question": "Qual o valor do vale-refeição?"}).json()
        cited = [s for s in body["sources"] if s["cited"]]
        assert "900" in body["answer"]
        assert cited and cited[0]["unit"] == 3
        assert cited[0]["location"] == "página 3"
        assert cited[0]["filename"] == "politica-ferias-beneficios.pdf"

    def test_filter_restricts_search_to_selected_documents(self, client, uploaded):
        body = client.post(
            "/api/chat",
            json={"question": "Qual o valor do vale-refeição?", "document_ids": [uploaded[MANUAL.name]]},
        ).json()
        assert {s["filename"] for s in body["sources"]} == {MANUAL.name}

    def test_top_k_limits_sources(self, client, uploaded):
        body = client.post("/api/chat", json={"question": "garantia", "top_k": 2}).json()
        assert len(body["sources"]) == 2

    def test_without_documents_says_it_did_not_find(self, client):
        body = client.post("/api/chat", json={"question": "Qual a garantia?"}).json()
        assert body["sources"] == []
        assert "Não encontrei" in body["answer"]

    def test_vector_only_mode_also_works(self, client, uploaded):
        body = client.post("/api/chat", json={"question": "óleo do redutor", "search_mode": "vector"}).json()
        assert body["sources"]


class TestEvaluation:
    def import_gabarito(self, client):
        items = json.loads((SAMPLES / "gabarito.json").read_text(encoding="utf-8"))
        return client.post("/api/eval/cases/import", json=items).json()

    def test_import_links_cases_to_documents_by_filename(self, client, uploaded):
        assert self.import_gabarito(client) == {"imported": 12, "skipped": []}
        cases = client.get("/api/eval/cases").json()
        assert cases[0]["document_filename"] == "manual-esteira-et200.pdf"

    def test_import_skips_cases_of_missing_documents(self, client):
        result = self.import_gabarito(client)
        assert result["imported"] == 0
        assert len(result["skipped"]) == 12

    def test_export_round_trips_the_import(self, client, uploaded):
        self.import_gabarito(client)
        exported = client.get("/api/eval/cases/export").json()
        original = json.loads((SAMPLES / "gabarito.json").read_text(encoding="utf-8"))
        assert exported == original

    def test_import_accepts_the_old_expected_page_key(self, client, uploaded):
        """Gabaritos exportados antes de `page` virar `unit` continuam importáveis."""
        legacy = [
            {
                "question": "Q?",
                "expected_answer": "R",
                "document": MANUAL.name,
                "expected_page": 4,
            }
        ]
        assert client.post("/api/eval/cases/import", json=legacy).json() == {"imported": 1, "skipped": []}
        assert client.get("/api/eval/cases").json()[0]["expected_unit"] == 4

    def test_case_crud(self, client, uploaded):
        created = client.post(
            "/api/eval/cases",
            json={"question": "Q?", "expected_answer": "R", "document_id": uploaded[MANUAL.name], "expected_unit": 2},
        ).json()
        updated = client.put(
            f"/api/eval/cases/{created['id']}",
            json={"question": "Q2?", "expected_answer": "R2", "document_id": None, "expected_unit": None},
        ).json()
        assert updated["question"] == "Q2?"
        assert client.delete(f"/api/eval/cases/{created['id']}").status_code == 204
        assert client.get("/api/eval/cases").json() == []

    def test_case_with_unknown_document_is_rejected(self, client):
        response = client.post("/api/eval/cases", json={"question": "Q", "expected_answer": "R", "document_id": 999})
        assert response.status_code == 422

    def test_run_measures_retrieval_and_answers(self, client, uploaded):
        self.import_gabarito(client)
        run = client.post("/api/eval/runs", json={"top_k": 3, "search_mode": "hybrid"}).json()

        assert run["config"]["top_k"] == 3
        assert run["config"]["judge"] is False  # provedor fake não tem juiz
        assert len(run["results"]) == 12
        summary = run["summary"]
        assert summary["cases"] == 12
        assert summary["hit_rate"] >= 0.75
        assert 0 < summary["mrr"] <= summary["hit_rate"]
        assert summary["judge_score"] is None

        listed = client.get("/api/eval/runs").json()
        assert listed[0]["id"] == run["id"]
        detail = client.get(f"/api/eval/runs/{run['id']}").json()
        assert len(detail["results"][0]["retrieved"]) == 3

    def test_run_without_cases_is_rejected(self, client):
        assert client.post("/api/eval/runs", json={}).status_code == 422

    def test_deleting_a_document_keeps_cases_but_unlinks_them(self, client, uploaded):
        self.import_gabarito(client)
        client.delete(f"/api/documents/{uploaded[MANUAL.name]}")
        cases = client.get("/api/eval/cases").json()
        assert len(cases) == 12
        assert all(c["document_filename"] != MANUAL.name for c in cases)

import json

import pytest
from fastapi.testclient import TestClient


def _make_app(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_CONFIG__API_KEY", "sk-test-key")
    monkeypatch.setenv("ASYNC_INGESTION", "false")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("API_KEYS", json.dumps({
        "sk-query-key": ["query"],
        "sk-ingest-key": ["ingest"],
        "sk-admin-key": ["query", "ingest"],
    }))
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    monkeypatch.setenv("MEMORY_BACKEND", "memory")
    from ragframework.api.main import create_app
    return TestClient(create_app())


def _pdf_bytes():
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.add_font("Noto", "", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")
        pdf.set_font("Noto", size=12)
    except Exception:
        pdf.set_font("Helvetica", size=12)
    pdf.cell(text="test")
    r = pdf.output(dest="S")
    return bytes(r) if isinstance(r, bytearray) else r.encode("latin-1") if isinstance(r, str) else r


class TestAuthQuery:
    def test_without_auth_returns_401(self, monkeypatch, tmp_path):
        client = _make_app(monkeypatch, tmp_path)
        response = client.post("/v1/query", json={"query": "hello", "session_id": "s"})
        assert response.status_code == 401

    def test_with_correct_scope_returns_200(self, monkeypatch, tmp_path):
        client = _make_app(monkeypatch, tmp_path)
        response = client.post(
            "/v1/query",
            json={"query": "hello", "session_id": "s"},
            headers={"Authorization": "Bearer sk-query-key"},
        )
        assert response.status_code == 200

    def test_with_ingest_only_key_returns_403(self, monkeypatch, tmp_path):
        client = _make_app(monkeypatch, tmp_path)
        response = client.post(
            "/v1/query",
            json={"query": "hello", "session_id": "s"},
            headers={"Authorization": "Bearer sk-ingest-key"},
        )
        assert response.status_code == 403

    def test_with_invalid_key_returns_401(self, monkeypatch, tmp_path):
        client = _make_app(monkeypatch, tmp_path)
        response = client.post(
            "/v1/query",
            json={"query": "hello", "session_id": "s"},
            headers={"Authorization": "Bearer sk-nonexistent"},
        )
        assert response.status_code == 401


class TestAuthIngestion:
    def test_upload_without_auth_returns_401(self, monkeypatch, tmp_path):
        client = _make_app(monkeypatch, tmp_path)
        response = client.post("/v1/documents", files={"file": ("test.pdf", _pdf_bytes(), "application/pdf")})
        assert response.status_code == 401

    def test_upload_with_wrong_scope_returns_403(self, monkeypatch, tmp_path):
        client = _make_app(monkeypatch, tmp_path)
        response = client.post(
            "/v1/documents",
            files={"file": ("test.pdf", _pdf_bytes(), "application/pdf")},
            headers={"Authorization": "Bearer sk-query-key"},
        )
        assert response.status_code == 403

    def test_upload_with_correct_scope_returns_200(self, monkeypatch, tmp_path):
        client = _make_app(monkeypatch, tmp_path)
        response = client.post(
            "/v1/documents",
            files={"file": ("test.pdf", _pdf_bytes(), "application/pdf")},
            headers={"Authorization": "Bearer sk-ingest-key"},
        )
        assert response.status_code == 200

    def test_get_status_with_correct_scope(self, monkeypatch, tmp_path):
        client = _make_app(monkeypatch, tmp_path)
        response = client.get(
            "/v1/documents/some-job",
            headers={"Authorization": "Bearer sk-ingest-key"},
        )
        assert response.status_code == 200

    def test_delete_with_correct_scope(self, monkeypatch, tmp_path):
        client = _make_app(monkeypatch, tmp_path)
        response = client.delete(
            "/v1/documents/some-id",
            headers={"Authorization": "Bearer sk-ingest-key"},
        )
        assert response.status_code == 200

    def test_admin_key_can_access_both(self, monkeypatch, tmp_path):
        client = _make_app(monkeypatch, tmp_path)
        r1 = client.post(
            "/v1/query", json={"query": "hello", "session_id": "s"},
            headers={"Authorization": "Bearer sk-admin-key"},
        )
        r2 = client.post(
            "/v1/documents", files={"file": ("t.pdf", _pdf_bytes(), "application/pdf")},
            headers={"Authorization": "Bearer sk-admin-key"},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200

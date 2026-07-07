from fastapi.testclient import TestClient
import pytest


def _app_with_cors(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_CONFIG__API_KEY", "sk-test-key")
    monkeypatch.setenv("ASYNC_INGESTION", "false")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    monkeypatch.setenv("MEMORY_BACKEND", "memory")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://example.com"]')
    from ragframework.api.main import create_app
    return TestClient(create_app())


def _app_no_cors(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_CONFIG__API_KEY", "sk-test-key")
    monkeypatch.setenv("ASYNC_INGESTION", "false")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    monkeypatch.setenv("MEMORY_BACKEND", "memory")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "[]")
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
    pdf.cell(text="test content")
    r = pdf.output(dest="S")
    return bytes(r) if isinstance(r, bytearray) else r.encode("latin-1") if isinstance(r, str) else r


class TestCORS:
    def test_cors_headers_present_when_configured(self, monkeypatch, tmp_path):
        client = _app_with_cors(monkeypatch, tmp_path)
        response = client.options(
            "/v1/health",
            headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"},
        )
        allow_origin = response.headers.get("access-control-allow-origin")
        assert allow_origin == "https://example.com"

    def test_cors_not_allowed_for_other_origin(self, monkeypatch, tmp_path):
        client = _app_with_cors(monkeypatch, tmp_path)
        response = client.options(
            "/v1/health",
            headers={"Origin": "https://evil.com", "Access-Control-Request-Method": "GET"},
        )
        allow_origin = response.headers.get("access-control-allow-origin")
        assert allow_origin != "https://evil.com"

    def test_no_cors_when_empty_origins(self, monkeypatch, tmp_path):
        client = _app_no_cors(monkeypatch, tmp_path)
        response = client.options(
            "/v1/health",
            headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"},
        )
        allow_origin = response.headers.get("access-control-allow-origin")
        assert not allow_origin or allow_origin == ""


class TestUploadValidation:
    def test_rejects_non_pdf_extension(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.setenv("CACHE_BACKEND", "memory")
        monkeypatch.setenv("MEMORY_BACKEND", "memory")
        from ragframework.api.main import create_app
        client = TestClient(create_app())
        response = client.post(
            "/v1/documents",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400
        assert "Only PDF files" in response.json()["detail"]

    def test_rejects_invalid_file_signature(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.setenv("CACHE_BACKEND", "memory")
        monkeypatch.setenv("MEMORY_BACKEND", "memory")
        from ragframework.api.main import create_app
        client = TestClient(create_app())
        response = client.post(
            "/v1/documents",
            files={"file": ("fake.pdf", b"not a pdf signature", "application/pdf")},
        )
        assert response.status_code == 400
        assert "file signature" in response.json()["detail"].lower()

    def test_rejects_large_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.setenv("CACHE_BACKEND", "memory")
        monkeypatch.setenv("MEMORY_BACKEND", "memory")
        monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "100")
        from ragframework.api.main import create_app
        client = TestClient(create_app())
        response = client.post(
            "/v1/documents",
            files={"file": ("big.pdf", b"%PDF" + b"x" * 200, "application/pdf")},
        )
        assert response.status_code == 413

    def test_upload_cleanup_after_sync(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.setenv("CACHE_BACKEND", "memory")
        monkeypatch.setenv("MEMORY_BACKEND", "memory")
        storage = tmp_path / "uploads"
        storage.mkdir()
        monkeypatch.setenv("OBJECT_STORAGE_PATH", str(storage))
        from ragframework.api.main import create_app
        client = TestClient(create_app())
        client.post(
            "/v1/documents",
            files={"file": ("test.pdf", _pdf_bytes(), "application/pdf")},
        )
        files_after = list(storage.iterdir())
        assert len(files_after) == 0, "Temp file should be cleaned up after sync ingestion"

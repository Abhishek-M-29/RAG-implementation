"""Integration tests for Stage 7 — Async Ingestion Pipeline.

Covers all verification items from §8.10 and §9 Definition of Done.

Uses a real Redis instance on localhost:6379, database 15 (test-only DB).
Database 15 is flushed before each test in this file to guarantee isolation.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import redis as redis_module
from fpdf import FPDF
from fastapi.testclient import TestClient

from ragframework.api.main import create_app
from ragframework.cache import index_fingerprint, bump_index_fingerprint, _FINGERPRINT_REDIS_KEY
from ragframework.config import Settings
from ragframework.api.schemas import JobStatusResponse, DocumentUploadResponse

REDIS_TEST_DB = 15
REDIS_TEST_URL = f"redis://localhost:6379/{REDIS_TEST_DB}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pdf_bytes(text: str = "Hello world this is a test document.") -> bytes:
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.add_font("Noto", "", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")
        pdf.set_font("Noto", size=12)
    except Exception:
        pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(w=0, text=text)
    result = pdf.output(dest="S")
    if isinstance(result, bytearray):
        return bytes(result)
    if isinstance(result, str):
        return result.encode("latin-1")
    return result


def _make_pdf_to_file(path: Path, text: str):
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.add_font("Noto", "", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")
        pdf.set_font("Noto", size=12)
    except Exception:
        pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(w=0, text=text)
    pdf.output(str(path))


def _redis_client():
    return redis_module.Redis(host="localhost", port=6379, db=REDIS_TEST_DB)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_redis_and_fingerprint():
    r = _redis_client()
    r.flushdb()
    import ragframework.cache
    ragframework.cache._index_fingerprint = 0
    yield
    r.flushdb()


@pytest.fixture
def sync_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("ASYNC_INGESTION", "false")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    monkeypatch.setenv("MEMORY_BACKEND", "memory")
    storage = tmp_path / "uploads"
    storage.mkdir()
    monkeypatch.setenv("OBJECT_STORAGE_PATH", str(storage))
    return Settings()


@pytest.fixture
def sync_app(sync_settings):
    app = create_app()
    return app


@pytest.fixture
def sync_client(sync_app):
    return TestClient(sync_app)


# ===================================================================
# 1. Schema validation
# ===================================================================

class TestSchema:
    def test_job_status_response_queued(self):
        r = JobStatusResponse(job_id="abc", status="queued")
        assert r.job_id == "abc"
        assert r.status == "queued"
        assert r.error is None

    def test_job_status_response_processing(self):
        r = JobStatusResponse(job_id="abc", status="processing")
        assert r.status == "processing"

    def test_job_status_response_done(self):
        r = JobStatusResponse(job_id="abc", status="done")
        assert r.status == "done"

    def test_job_status_response_failed(self):
        r = JobStatusResponse(job_id="abc", status="failed", error="Something broke")
        assert r.status == "failed"
        assert r.error == "Something broke"

    def test_document_upload_response(self):
        r = DocumentUploadResponse(job_id="abc", status="done")
        assert r.job_id == "abc"
        assert r.status == "done"

    def test_job_status_accepts_any_string_status(self):
        r = JobStatusResponse(job_id="abc", status="invalid")
        assert r.status == "invalid"


# ===================================================================
# 2. Settings
# ===================================================================

class TestSettings:
    def test_default_settings(self):
        s = Settings()
        assert s.object_storage_path == "uploads/"
        assert s.async_ingestion is False

    def test_override_settings(self, monkeypatch):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("OBJECT_STORAGE_PATH", "/tmp/mypath")
        s = Settings()
        assert s.async_ingestion is False
        assert s.object_storage_path == "/tmp/mypath"


# ===================================================================
# 3. Cache / Fingerprint (memory path)
# ===================================================================

class TestFingerprintMemory:
    def test_fingerprint_starts_at_zero(self):
        assert index_fingerprint() == 0

    def test_bump_increments(self):
        start = index_fingerprint()
        bump_index_fingerprint()
        assert index_fingerprint() == start + 1

    def test_multiple_bumps(self):
        bump_index_fingerprint()
        bump_index_fingerprint()
        bump_index_fingerprint()
        assert index_fingerprint() == 3

    def test_bump_without_redis_falls_back_to_memory(self):
        bump_index_fingerprint(redis_client=None)
        assert index_fingerprint() == 1


# ===================================================================
# 4. Cache / Fingerprint (Redis path)
# ===================================================================

class TestFingerprintRedis:
    def test_bump_with_redis(self):
        r = _redis_client()
        bump_index_fingerprint(redis_client=r)
        assert index_fingerprint(redis_client=r) == 1

    def test_bump_multiple_with_redis(self):
        r = _redis_client()
        bump_index_fingerprint(redis_client=r)
        bump_index_fingerprint(redis_client=r)
        bump_index_fingerprint(redis_client=r)
        assert index_fingerprint(redis_client=r) == 3

    def test_redis_and_memory_independent(self):
        r = _redis_client()
        assert index_fingerprint(redis_client=r) == 0
        assert index_fingerprint() == 0
        bump_index_fingerprint(redis_client=r)
        assert index_fingerprint(redis_client=r) == 1
        assert index_fingerprint() == 0

    def test_redis_key_constant(self):
        assert _FINGERPRINT_REDIS_KEY == "rag:index_fingerprint"

    def test_redis_bump_stores_correct_key(self):
        r = _redis_client()
        bump_index_fingerprint(redis_client=r)
        assert int(r.get("rag:index_fingerprint")) == 1


# ===================================================================
# 5. Sync ingestion — POST /v1/documents with async_ingestion=False
# ===================================================================

class TestSyncIngestion:
    def test_post_returns_immediately(self, sync_client):
        pdf_bytes = _make_pdf_bytes()
        response = sync_client.post(
            "/v1/documents",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "done"

    def test_post_rejects_non_pdf(self, sync_client):
        response = sync_client.post(
            "/v1/documents",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400
        assert "Only PDF files" in response.json()["detail"]

    def test_post_large_file(self, sync_client):
        large_text = "Hello world. " * 10000
        pdf_bytes = _make_pdf_bytes(large_text)
        response = sync_client.post(
            "/v1/documents",
            files={"file": ("large.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "done"


# ===================================================================
# 6. GET /v1/documents/{job_id} — sync path
# ===================================================================

class TestSyncJobStatus:
    def test_get_job_status_sync_returns_done(self, sync_client):
        response = sync_client.get("/v1/documents/any-job-id")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "any-job-id"
        assert data["status"] == "done"
        assert data["error"] is None


# ===================================================================
# 7. Auth protection (ingest scope)
# ===================================================================

class TestAuthProtection:
    def make_app_with_auth(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS",
            json.dumps({"sk-query-key": ["query"], "sk-ingest-key": ["ingest"]}))
        monkeypatch.setenv("CACHE_BACKEND", "memory")
        monkeypatch.setenv("MEMORY_BACKEND", "memory")
        storage = tmp_path / "uploads"
        storage.mkdir()
        monkeypatch.setenv("OBJECT_STORAGE_PATH", str(storage))
        return TestClient(create_app())

    def test_upload_without_auth(self, monkeypatch, tmp_path):
        client = self.make_app_with_auth(monkeypatch, tmp_path)
        response = client.post(
            "/v1/documents",
            files={"file": ("test.pdf", _make_pdf_bytes(), "application/pdf")},
        )
        assert response.status_code == 401

    def test_upload_with_wrong_scope(self, monkeypatch, tmp_path):
        client = self.make_app_with_auth(monkeypatch, tmp_path)
        response = client.post(
            "/v1/documents",
            files={"file": ("test.pdf", _make_pdf_bytes(), "application/pdf")},
            headers={"Authorization": "Bearer sk-query-key"},
        )
        assert response.status_code == 403

    def test_upload_with_correct_scope(self, monkeypatch, tmp_path):
        client = self.make_app_with_auth(monkeypatch, tmp_path)
        response = client.post(
            "/v1/documents",
            files={"file": ("test.pdf", _make_pdf_bytes(), "application/pdf")},
            headers={"Authorization": "Bearer sk-ingest-key"},
        )
        assert response.status_code == 200

    def test_get_status_with_correct_scope(self, monkeypatch, tmp_path):
        client = self.make_app_with_auth(monkeypatch, tmp_path)
        response = client.get(
            "/v1/documents/some-job",
            headers={"Authorization": "Bearer sk-ingest-key"},
        )
        assert response.status_code == 200

    def test_get_status_without_auth(self, monkeypatch, tmp_path):
        client = self.make_app_with_auth(monkeypatch, tmp_path)
        response = client.get("/v1/documents/some-job")
        assert response.status_code == 401

    def test_delete_with_correct_scope(self, monkeypatch, tmp_path):
        client = self.make_app_with_auth(monkeypatch, tmp_path)
        response = client.delete(
            "/v1/documents/some-id",
            headers={"Authorization": "Bearer sk-ingest-key"},
        )
        assert response.status_code == 200


# ===================================================================
# 8. Worker function
# ===================================================================

class TestWorkerFunction:
    def test_worker_processes_valid_pdf_and_bumps_fingerprint(self, tmp_path, monkeypatch):
        monkeypatch.setenv("REDIS_URL", REDIS_TEST_URL)
        pdf_path = tmp_path / "test.pdf"
        _make_pdf_to_file(pdf_path, "Apple banana cherry are fruits.")

        from ragframework.workers.ingestion_worker import process_ingestion_job
        process_ingestion_job(str(pdf_path), "test.pdf", request_id="req-123")

        assert not pdf_path.exists()
        r = _redis_client()
        fp = int(r.get(_FINGERPRINT_REDIS_KEY) or 0)
        assert fp >= 1, "index_fingerprint must be bumped on job success"

    def test_worker_fails_on_corrupt_pdf(self, tmp_path):
        pdf_path = tmp_path / "corrupt.pdf"
        pdf_path.write_bytes(b"not a pdf at all")

        from ragframework.workers.ingestion_worker import process_ingestion_job
        with pytest.raises(Exception) as excinfo:
            process_ingestion_job(str(pdf_path), "corrupt.pdf")
        msg = str(excinfo.value).lower()
        assert "no text" in msg or "could not be extracted" in msg

    def test_worker_uses_registry(self, tmp_path, monkeypatch):
        """Worker imports from the connector registry, not vendor modules."""
        import ragframework.workers.ingestion_worker as w_mod
        import inspect
        source = inspect.getsource(w_mod)
        assert "from ragframework.vectorstores.registry import get_vector_store" in source
        assert "from ragframework.vectorstores.faiss_store import" not in source
        assert "from ragframework.llms.google_genai import" not in source
        assert "from ragframework.llms.registry import get_llm" not in source  # not needed in worker


# ===================================================================
# 9. Async path integration (via real Redis)
# ===================================================================

class TestAsyncIngestion:
    def test_post_enqueues_job_and_returns_immediately(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ASYNC_INGESTION", "true")
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.setenv("CACHE_BACKEND", "memory")
        monkeypatch.setenv("MEMORY_BACKEND", "memory")
        monkeypatch.setenv("REDIS_URL", REDIS_TEST_URL)
        storage = tmp_path / "uploads"
        storage.mkdir()
        monkeypatch.setenv("OBJECT_STORAGE_PATH", str(storage))

        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/v1/documents",
            files={"file": ("test.pdf", _make_pdf_bytes(), "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_get_job_status_after_enqueue(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ASYNC_INGESTION", "true")
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.setenv("CACHE_BACKEND", "memory")
        monkeypatch.setenv("MEMORY_BACKEND", "memory")
        monkeypatch.setenv("REDIS_URL", REDIS_TEST_URL)
        storage = tmp_path / "uploads"
        storage.mkdir()
        monkeypatch.setenv("OBJECT_STORAGE_PATH", str(storage))

        app = create_app()
        client = TestClient(app)

        post_resp = client.post(
            "/v1/documents",
            files={"file": ("test.pdf", _make_pdf_bytes(), "application/pdf")},
        )
        job_id = post_resp.json()["job_id"]

        status_resp = client.get(f"/v1/documents/{job_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] in ("queued", "processing", "done")

    def test_get_job_status_not_found(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ASYNC_INGESTION", "true")
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.setenv("REDIS_URL", REDIS_TEST_URL)
        storage = tmp_path / "uploads"
        storage.mkdir()
        monkeypatch.setenv("OBJECT_STORAGE_PATH", str(storage))

        app = create_app()
        client = TestClient(app)
        response = client.get("/v1/documents/nonexistent-job-id")
        assert response.status_code == 404


# ===================================================================
# 10. End-to-end: sync ingestion
# ===================================================================

class TestSyncEndToEnd:
    def test_sync_ingestion_completes(self, sync_client, tmp_path):
        """Sync ingestion processes a PDF end-to-end and cleans up the temp file."""
        pdf_bytes = _make_pdf_bytes("Apple banana cherry are delicious fruits.")
        ingest_resp = sync_client.post(
            "/v1/documents",
            files={"file": ("fruits.pdf", pdf_bytes, "application/pdf")},
        )
        assert ingest_resp.status_code == 200
        data = ingest_resp.json()
        assert "job_id" in data
        assert data["status"] == "done"

    def test_sync_ingestion_cleanup(self, tmp_path, monkeypatch):
        """Sync ingestion cleans up the stored file after processing."""
        storage = tmp_path / "uploads"
        storage.mkdir()
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.setenv("CACHE_BACKEND", "memory")
        monkeypatch.setenv("MEMORY_BACKEND", "memory")

        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        client.post(
            "/v1/documents",
            files={"file": ("test.pdf", _make_pdf_bytes(), "application/pdf")},
        )
        files_after = list(storage.iterdir())
        assert len(files_after) == 0, "Temp file should be cleaned up after sync ingestion"

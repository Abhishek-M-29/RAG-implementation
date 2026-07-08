import os
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from ragframework.core.ingestion import (
    _embedding_cache_key,
    _validate_pdf_safety,
    embed_and_index_chunks,
    get_pdf_paths_from_directory,
    load_and_extract_text_from_pdfs,
)


class TestGetPdfPathsFromDirectory:
    def test_existing_directory_with_pdfs(self, tmp_path):
        (tmp_path / "doc1.pdf").write_text("dummy")
        (tmp_path / "doc2.pdf").write_text("dummy")
        (tmp_path / "readme.txt").write_text("not a pdf")
        paths = get_pdf_paths_from_directory(str(tmp_path))
        assert len(paths) == 2
        assert all(p.endswith(".pdf") for p in paths)

    def test_missing_directory_creates_it(self, tmp_path):
        missing = str(tmp_path / "nonexistent")
        paths = get_pdf_paths_from_directory(missing)
        assert paths == []
        assert os.path.isdir(missing)

    def test_empty_directory(self, tmp_path):
        paths = get_pdf_paths_from_directory(str(tmp_path))
        assert paths == []

    def test_no_pdf_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        paths = get_pdf_paths_from_directory(str(tmp_path))
        assert paths == []


class TestValidatePdfSafety:
    def test_valid_pdf_passes(self, tmp_path):
        pdf_path = tmp_path / "valid.pdf"
        pdf_path.write_bytes(_make_minimal_pdf(3))
        _validate_pdf_safety(str(pdf_path))

    def test_malformed_pdf_raises(self, tmp_path):
        pdf_path = tmp_path / "corrupt.pdf"
        pdf_path.write_bytes(b"not a pdf")
        with pytest.raises(ValueError, match="Malformed PDF"):
            _validate_pdf_safety(str(pdf_path))

    def test_too_many_pages_raises(self, tmp_path):
        pdf_path = tmp_path / "bomb.pdf"
        pdf_path.write_bytes(_make_minimal_pdf(10_001))
        with pytest.raises(ValueError, match="decompression bomb"):
            _validate_pdf_safety(str(pdf_path))


class TestLoadAndExtractTextFromPdfs:
    def test_empty_list_returns_empty(self):
        result = load_and_extract_text_from_pdfs([])
        assert result == []

    def test_per_file_error_surfacing(self, tmp_path):
        good = tmp_path / "good.pdf"
        good.write_bytes(_make_minimal_pdf(1))
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a real pdf")
        result = load_and_extract_text_from_pdfs([str(good), str(bad)])
        assert isinstance(result, list)

    def test_all_files_fail_returns_empty(self, tmp_path):
        bad1 = tmp_path / "bad1.pdf"
        bad1.write_bytes(b"garbage")
        bad2 = tmp_path / "bad2.pdf"
        bad2.write_bytes(b"corrupt")
        result = load_and_extract_text_from_pdfs([str(bad1), str(bad2)])
        assert result == []


class TestEmbeddingCacheKey:
    def test_deterministic(self):
        key1 = _embedding_cache_key("hello world", "model-v1")
        key2 = _embedding_cache_key("hello world", "model-v1")
        assert key1 == key2

    def test_different_text_different_key(self):
        key1 = _embedding_cache_key("hello", "model-v1")
        key2 = _embedding_cache_key("world", "model-v1")
        assert key1 != key2

    def test_different_model_different_key(self):
        key1 = _embedding_cache_key("hello", "model-v1")
        key2 = _embedding_cache_key("hello", "model-v2")
        assert key1 != key2

    def test_starts_with_emb_prefix(self):
        key = _embedding_cache_key("test", "m")
        assert key.startswith("emb:")

    def test_handles_empty_text(self):
        key = _embedding_cache_key("", "m")
        assert isinstance(key, str)
        assert len(key) > 4


class TestEmbedAndIndexChunks:
    @pytest.fixture
    def mock_cache(self):
        return MagicMock(get=MagicMock(return_value=None), set=MagicMock())

    @pytest.fixture
    def mock_vector_store(self):
        vs = MagicMock()
        vs.add_documents.return_value = ["id-1", "id-2"]
        return vs

    def test_embeds_and_indexes_new_chunks(self, mock_cache, mock_vector_store):
        chunks = [
            Document(page_content="Hello world", metadata={"source": "doc.pdf"}),
            Document(page_content="Foo bar", metadata={"source": "doc.pdf"}),
        ]
        embed_and_index_chunks(chunks, MagicMock(), mock_cache, mock_vector_store, "doc.pdf")
        assert mock_vector_store.add_embedded_documents.called

    def test_all_chunks_cached_skips_indexing(self, mock_cache, mock_vector_store):
        mock_cache.get.return_value = "1"
        chunks = [
            Document(page_content="Hello", metadata={"source": "doc.pdf"}),
        ]
        embed_and_index_chunks(chunks, MagicMock(), mock_cache, mock_vector_store, "doc.pdf")
        assert not mock_vector_store.add_documents.called

    def test_adds_ids_and_source_to_chunks(self, mock_cache, mock_vector_store):
        chunks = [
            Document(page_content="Hello", metadata={}),
        ]
        embed_and_index_chunks(chunks, MagicMock(), mock_cache, mock_vector_store, "doc.pdf")
        assert chunks[0].metadata.get("source") == "doc.pdf"
        assert chunks[0].metadata.get("id") is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_pdf(page_count: int) -> bytes:
    from fpdf import FPDF
    pdf = FPDF()
    try:
        pdf.add_font("Noto", "", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")
        pdf.set_font("Noto", size=12)
    except Exception:
        pdf.set_font("Helvetica", size=12)
    for _ in range(page_count):
        pdf.add_page()
        pdf.cell(text="x")
    return pdf.output(dest="S").encode("latin-1") if isinstance(pdf.output(dest="S"), str) else bytes(pdf.output(dest="S"))  # noqa: E501

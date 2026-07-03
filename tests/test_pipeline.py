import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import (
    collect_pdf_paths,
    process_documents,
    run_indexing,
    run_clear,
    run_info,
    run_reindex,
    INDEX_PATH,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)
from src.embedding import (
    build_and_save_faiss_index,
    add_to_faiss_index,
    load_faiss_index,
    clear_faiss_index,
)


# ---------------------------------------------------------------------------
# collect_pdf_paths
# ---------------------------------------------------------------------------

class TestCollectPdfPaths:
    def test_collect_from_directory(self, sample_pdfs):
        files = collect_pdf_paths(dirs=[str(sample_pdfs)], files=None)
        assert len(files) == 3
        assert all(f.endswith(".pdf") for f in files)

    def test_collect_from_specific_files(self, sample_pdfs, pdf_factory):
        extra = pdf_factory(sample_pdfs, "hello world", "extra.pdf")
        files = collect_pdf_paths(
            dirs=None,
            files=[str(sample_pdfs / "doc1.pdf"), str(extra)],
        )
        assert len(files) == 2

    def test_collect_from_both(self, temp_dir, pdf_factory):
        (temp_dir / "a").mkdir()
        (temp_dir / "b").mkdir()
        pdf_factory(temp_dir / "a", "from dir", "x.pdf")
        pdf_factory(temp_dir / "b", "another", "y.pdf")
        files = collect_pdf_paths(
            dirs=[str(temp_dir / "a")],
            files=[str(temp_dir / "b" / "y.pdf")],
        )
        assert len(files) == 2

    def test_skip_missing_directory(self, capsys):
        files = collect_pdf_paths(dirs=["/nonexistent/path"], files=None)
        assert files == []
        captured = capsys.readouterr()
        assert "Warning" in captured.out

    def test_skip_missing_file(self, capsys):
        files = collect_pdf_paths(dirs=None, files=["/nonexistent.pdf"])
        assert files == []
        captured = capsys.readouterr()
        assert "Warning" in captured.out

    def test_skip_non_pdf_file(self, temp_dir):
        txt = temp_dir / "readme.txt"
        txt.write_text("not a pdf")
        files = collect_pdf_paths(dirs=None, files=[str(txt)])
        assert files == []

    def test_empty_directory(self, temp_dir):
        files = collect_pdf_paths(dirs=[str(temp_dir)], files=None)
        assert files == []


# ---------------------------------------------------------------------------
# process_documents
# ---------------------------------------------------------------------------

class TestProcessDocuments:
    def test_returns_chunks(self, sample_pdfs):
        files = collect_pdf_paths(dirs=[str(sample_pdfs)], files=None)
        chunks = process_documents(files, CHUNK_SIZE, CHUNK_OVERLAP)
        assert chunks is not None
        assert len(chunks) >= 1
        assert all(hasattr(c, "page_content") for c in chunks)
        assert all(hasattr(c, "metadata") for c in chunks)

    def test_empty_files_returns_none(self):
        assert process_documents([], CHUNK_SIZE, CHUNK_OVERLAP) is None


# ---------------------------------------------------------------------------
# Index lifecycle: build → load → append → clear
# ---------------------------------------------------------------------------

class TestIndexLifecycle:
    def test_build_and_load(self, sample_pdfs, temp_dir):
        idx = str(temp_dir / "faiss_test")
        files = collect_pdf_paths(dirs=[str(sample_pdfs)], files=None)
        chunks = process_documents(files, CHUNK_SIZE, CHUNK_OVERLAP)

        v1 = build_and_save_faiss_index(chunks, idx)
        assert v1 is not None
        assert v1.index.ntotal == len(chunks)

        v2 = load_faiss_index(idx)
        assert v2 is not None
        assert v2.index.ntotal == len(chunks)

        clear_faiss_index(idx)

    def test_append_adds_vectors(self, sample_pdfs, pdf_factory, temp_dir, capsys):
        idx = str(temp_dir / "faiss_append")
        files = collect_pdf_paths(dirs=[str(sample_pdfs)], files=None)
        chunks = process_documents(files, CHUNK_SIZE, CHUNK_OVERLAP)
        build_and_save_faiss_index(chunks, idx)

        # Create one extra doc and append
        extra_pdf = pdf_factory(temp_dir, "Extra document with unique text content", "extra.pdf")
        extra_chunks = process_documents([str(extra_pdf)], CHUNK_SIZE, CHUNK_OVERLAP)
        v = add_to_faiss_index(extra_chunks, idx)
        assert v is not None
        assert v.index.ntotal == len(chunks) + len(extra_chunks)

        # Reload and verify
        v2 = load_faiss_index(idx)
        assert v2.index.ntotal == len(chunks) + len(extra_chunks)

        # New content is searchable
        results = v2.similarity_search("Extra document", k=3)
        assert any("Extra document" in r.page_content for r in results)

        clear_faiss_index(idx)

    def test_append_to_nonexistent_index_creates_new(self, sample_pdfs, temp_dir):
        idx = str(temp_dir / "faiss_new")
        files = collect_pdf_paths(dirs=[str(sample_pdfs)], files=None)
        chunks = process_documents(files, CHUNK_SIZE, CHUNK_OVERLAP)
        v = add_to_faiss_index(chunks, idx)
        assert v is not None
        assert v.index.ntotal == len(chunks)
        clear_faiss_index(idx)

    def test_clear_removes_index(self, sample_pdfs, temp_dir):
        idx = str(temp_dir / "faiss_clear")
        files = collect_pdf_paths(dirs=[str(sample_pdfs)], files=None)
        chunks = process_documents(files, CHUNK_SIZE, CHUNK_OVERLAP)
        build_and_save_faiss_index(chunks, idx)
        assert os.path.exists(idx)
        clear_faiss_index(idx)
        assert not os.path.exists(idx)


# ---------------------------------------------------------------------------
# High-level CLI workflow: index → info → append → reindex → clear
# ---------------------------------------------------------------------------

class TestCliWorkflow:
    def test_full_index_cycle(self, sample_pdfs, capsys):
        run_indexing(dirs=[str(sample_pdfs)], files=None, append=False,
                     chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        out = capsys.readouterr().out
        assert "Indexing completed" in out
        assert os.path.exists(INDEX_PATH)

        # info
        run_info()
        out = capsys.readouterr().out
        assert "Number of vectors" in out

        # clear
        run_clear()
        assert not os.path.exists(INDEX_PATH)

    def test_reindex_clears_and_rebuilds(self, sample_pdfs, capsys):
        run_reindex(dirs=[str(sample_pdfs)], files=None,
                    chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        out = capsys.readouterr().out
        assert "Indexing completed" in out
        assert os.path.exists(INDEX_PATH)

    def test_append_via_index_command(self, sample_pdfs, pdf_factory, capsys):
        run_indexing(dirs=[str(sample_pdfs)], files=None, append=False,
                     chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        capsys.readouterr()

        extra_pdf = pdf_factory(sample_pdfs.parent, "New appended content for testing", "extra.pdf")
        run_indexing(dirs=[str(sample_pdfs.parent)], files=None, append=True,
                     chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        out = capsys.readouterr().out
        assert "Appending to existing index" in out
        assert "Indexing completed" in out

        # Verify both old and new docs are searchable
        v = load_faiss_index(INDEX_PATH)
        results = v.similarity_search("appended", k=5)
        assert any("appended" in r.page_content for r in results)
        results = v.similarity_search("fruit", k=5)
        assert any("fruit" in r.page_content for r in results)

    def test_info_when_no_index(self, capsys):
        from src.embedding import clear_faiss_index
        if os.path.exists(INDEX_PATH):
            clear_faiss_index(INDEX_PATH)
        run_info()
        out = capsys.readouterr().out
        assert "No index found" in out

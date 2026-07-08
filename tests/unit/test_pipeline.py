from langchain_core.documents import Document

from ragframework.core.chunking import chunk_text
from ragframework.core.ingestion import get_pdf_paths_from_directory
from ragframework.vectorstores.faiss_store import FaissStore


class TestCollectPdfPaths:
    def test_collect_from_directory(self, sample_pdfs):
        files = get_pdf_paths_from_directory(str(sample_pdfs))
        assert len(files) == 3
        assert all(f.endswith(".pdf") for f in files)

    def test_skip_missing_directory(self, tmp_path):
        files = get_pdf_paths_from_directory(str(tmp_path / "nonexistent"))
        assert files == []

    def test_empty_directory(self, tmp_path):
        files = get_pdf_paths_from_directory(str(tmp_path))
        assert files == []


class TestProcessDocuments:
    def test_chunking_returns_chunks(self, sample_pdfs):
        pdf_files = get_pdf_paths_from_directory(str(sample_pdfs))
        assert len(pdf_files) == 3

    def test_empty_files_returns_empty(self):
        assert chunk_text([], chunk_size=1000, chunk_overlap=100) == []


class TestIndexLifecycle:
    def test_build_and_load(self, tmp_path):
        from langchain_huggingface import HuggingFaceEmbeddings

        index_path = str(tmp_path / "faiss_test")

        docs = [
            Document(page_content="Apple banana fruit.", metadata={"id": "p1", "source": "test.pdf"}),  # noqa: E501
            Document(page_content="Dog cat animal.", metadata={"id": "p2", "source": "test.pdf"}),
        ]

        emb = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        store = FaissStore(index_path, embedding_model=emb)
        store._load_or_init()

        ids = store.add_documents(docs)
        assert ids == ["p1", "p2"]

        results = store.similarity_search("fruit", k=3)
        assert len(results) > 0

        store2 = FaissStore(index_path, embedding_model=emb)
        store2._load_or_init()
        results2 = store2.similarity_search("fruit", k=3)
        assert len(results2) > 0

        store2.delete(["p1", "p2"])

    def test_append_adds_vectors(self, tmp_path):
        from langchain_huggingface import HuggingFaceEmbeddings

        index_path = str(tmp_path / "faiss_append")
        emb = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        docs_a = [
            Document(page_content="First set of documents.", metadata={"id": "a1", "source": "a.pdf"}),  # noqa: E501
        ]
        store = FaissStore(index_path, embedding_model=emb)
        store._load_or_init()
        store.add_documents(docs_a)

        docs_b = [
            Document(page_content="Second set appended.", metadata={"id": "b1", "source": "b.pdf"}),
        ]
        store.add_documents(docs_b)

        from langchain_community.vectorstores import FAISS
        loaded = FAISS.load_local(index_path, emb, allow_dangerous_deserialization=True)
        assert loaded.index.ntotal == 2

        store.delete(["a1", "b1"])

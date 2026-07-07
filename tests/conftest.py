import pytest
import os
import shutil
import tempfile

os.environ["INGESTION_RATE_LIMIT"] = "10000/minute"
os.environ["QUERY_RATE_LIMIT"] = "10000/minute"
from pathlib import Path
from fpdf import FPDF
from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.messages import AIMessage


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        orig = os.getcwd()
        os.chdir(tmp)
        yield Path(tmp)
        os.chdir(orig)


def make_pdf(path: Path, text: str):
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.add_font("Noto", "", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")
        pdf.set_font("Noto", size=12)
    except Exception:
        pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(w=0, text=text)
    pdf.output(str(path))
    return path


@pytest.fixture
def pdf_factory():
    created = []

    def _make(dir_path: Path, text: str, name: str = "test.pdf"):
        path = dir_path / name
        make_pdf(path, text)
        created.append(path)
        return path

    yield _make
    for p in created:
        if p.exists():
            p.unlink()


@pytest.fixture
def sample_pdfs(pdf_factory, temp_dir):
    src = temp_dir / "pdfs"
    src.mkdir()
    pdf_factory(src, "Apple banana fruit are delicious and healthy.", "doc1.pdf")
    pdf_factory(src, "Dog cat animal are popular pets in households.", "doc2.pdf")
    pdf_factory(src, "Machine learning artificial intelligence is transforming technology.", "doc3.pdf")
    return src


# ---------------------------------------------------------------------------
# Shared contract/unit test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_docs():
    return [
        Document(
            page_content="Apple banana fruit are delicious and healthy.",
            metadata={"id": "id-1", "source": "test"},
        ),
        Document(
            page_content="Dog cat animal are popular pets in households.",
            metadata={"id": "id-2", "source": "test"},
        ),
        Document(
            page_content="Machine learning artificial intelligence is transforming technology.",
            metadata={"id": "id-3", "source": "test"},
        ),
    ]


# ---------------------------------------------------------------------------
# Mock connectors for integration tests
# ---------------------------------------------------------------------------

class MockVectorStore:
    def __init__(self):
        self._docs = {}
        self._healthy = True

    def add_documents(self, documents):
        ids = []
        for doc in documents:
            doc_id = doc.metadata.get("id", str(id(doc)))
            self._docs[doc_id] = doc
            ids.append(doc_id)
        return ids

    def add_embedded_documents(self, text_vector_pairs, metadatas):
        for (text, _vec), meta in zip(text_vector_pairs, metadatas):
            doc_id = meta.get("id", str(id((text, meta))))
            self._docs[doc_id] = Document(page_content=text, metadata=meta)
        return [m.get("id") for m in metadatas]

    def similarity_search(self, query, k=5):
        return list(self._docs.values())[:k]

    def delete(self, ids):
        for doc_id in ids:
            self._docs.pop(doc_id, None)

    def list_documents(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for doc in self._docs.values():
            source = doc.metadata.get("source", "unknown")
            counts[source] = counts.get(source, 0) + 1
        return counts

    def health_check(self):
        return self._healthy


class MockChatModel(BaseChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="Mock answer"))]
        )

    @property
    def _llm_type(self):
        return "mock"


class MockChain:
    def stream(self, input, config=None):
        yield {"answer": "Mock "}
        yield {"answer": "answer "}
        yield {"answer": "response"}


@pytest.fixture
def mock_connectors(monkeypatch):
    env_settings = {
        "ASYNC_INGESTION": "false",
        "AUTH_ENABLED": "false",
        "CACHE_BACKEND": "memory",
        "MEMORY_BACKEND": "memory",
    }
    for k, v in env_settings.items():
        monkeypatch.setenv(k, v)

    import ragframework.api.routers.query
    import ragframework.api.routers.ingestion
    import ragframework.api.routers.health

    mock_vs = MockVectorStore()
    mock_llm = MockChatModel()
    mock_chain = MockChain()

    monkeypatch.setattr(ragframework.api.routers.query, "get_vector_store", lambda s: mock_vs)
    monkeypatch.setattr(ragframework.api.routers.query, "get_llm", lambda s: mock_llm)
    monkeypatch.setattr(ragframework.api.routers.query, "build_rag_chain", lambda *a, **kw: mock_chain)
    monkeypatch.setattr(ragframework.api.routers.ingestion, "get_vector_store", lambda s: mock_vs)
    monkeypatch.setattr(ragframework.api.routers.health, "get_vector_store", lambda s: mock_vs)
    monkeypatch.setattr(ragframework.api.routers.health, "get_llm", lambda s: mock_llm)

    return mock_vs, mock_llm


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from ragframework.config import get_settings
    get_settings.cache_clear()
    yield

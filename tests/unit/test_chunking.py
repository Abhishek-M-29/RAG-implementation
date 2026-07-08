from langchain_core.documents import Document

from ragframework.core.chunking import chunk_text


class TestChunkText:
    def test_single_document_splits_into_chunks(self):
        text = "hello world " * 500
        docs = [Document(page_content=text)]
        chunks = chunk_text(docs, chunk_size=200, chunk_overlap=20)
        assert len(chunks) > 1
        assert all(isinstance(c, Document) for c in chunks)

    def test_empty_input_returns_empty_list(self):
        assert chunk_text([], chunk_size=200, chunk_overlap=20) == []

    def test_chunk_size_respected(self):
        text = "A " * 1000
        docs = [Document(page_content=text)]
        chunks = chunk_text(docs, chunk_size=100, chunk_overlap=0)
        for c in chunks:
            assert len(c.page_content) <= 100

    def test_chunk_overlap_adds_overlap(self):
        text = "word " * 500
        docs = [Document(page_content=text)]
        chunks_no_overlap = chunk_text(docs, chunk_size=200, chunk_overlap=0)
        chunks_with_overlap = chunk_text(docs, chunk_size=200, chunk_overlap=50)
        assert len(chunks_with_overlap) >= len(chunks_no_overlap)

    def test_preserves_metadata(self):
        docs = [Document(page_content="Hello world.", metadata={"source": "test.pdf", "page": 1})]
        chunks = chunk_text(docs, chunk_size=50, chunk_overlap=0)
        for c in chunks:
            assert c.metadata.get("source") == "test.pdf"

    def test_very_short_text_stays_as_single_chunk(self):
        docs = [Document(page_content="Short.")]
        chunks = chunk_text(docs, chunk_size=200, chunk_overlap=20)
        assert len(chunks) == 1

    def test_multiple_documents_combined(self):
        docs = [
            Document(page_content="hello world " * 100, metadata={"source": "a.pdf"}),
            Document(page_content="foo bar " * 100, metadata={"source": "b.pdf"}),
        ]
        chunks = chunk_text(docs, chunk_size=100, chunk_overlap=10)
        assert len(chunks) >= 2

    def test_whitespace_only_input(self):
        docs = [Document(page_content="   \n   \t   ")]
        chunks = chunk_text(docs, chunk_size=100, chunk_overlap=10)
        assert isinstance(chunks, list)

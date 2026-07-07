import logging

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


def chunk_text(
    documents_to_split: list[Document],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    if not documents_to_split:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )

    split_chunks_docs = text_splitter.split_documents(documents_to_split)
    logger.info(
        "Split %d documents into %d chunks",
        len(documents_to_split), len(split_chunks_docs),
        extra={
            "input_docs": len(documents_to_split),
            "output_chunks": len(split_chunks_docs),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        },
    )

    return split_chunks_docs

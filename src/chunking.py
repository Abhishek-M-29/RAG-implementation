# src/chunking.py

# Using LangChain's RecursiveCharacterTextSplitter for semantic chunking.

import json
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from src.log_utils import get_logger

logger = get_logger(__name__)


def chunk_text(documents_to_split: list[Document], chunk_size: int = 1000, chunk_overlap: int = 100) -> list[Document]:
    """
    Splits a list of LangChain Document objects into smaller chunks.

    Args:
        documents_to_split (list[Document]): The list of Document objects to be chunked.
                                            Each Document should have page_content and metadata.
        chunk_size (int): The target size of each chunk.
        chunk_overlap (int): The number of characters to overlap between chunks.

    Returns:
        list[Document]: A list of chunked Document objects, preserving metadata.
    """
    if not documents_to_split:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        # add_start_index is not directly used by split_documents in the same way as create_documents
        # Metadata from original documents is preserved and handled by split_documents.
    )

    split_chunks_docs = text_splitter.split_documents(documents_to_split)
    logger.info("Split %d documents into %d chunks", len(documents_to_split), len(split_chunks_docs))

    return split_chunks_docs
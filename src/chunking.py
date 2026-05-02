# src/chunking.py

# Using LangChain's RecursiveCharacterTextSplitter for semantic chunking.

import json
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document # Import Document

# def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]: # Old signature
def chunk_text(documents_to_split: list[Document], chunk_size: int = 2500, chunk_overlap: int = 250) -> list[Document]: # New signature
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
    
    # Use split_documents for list[Document] input
    split_chunks_docs = text_splitter.split_documents(documents_to_split)
    
    # Original logging was for create_documents, adjust if necessary or rely on main.py logging
    # For example:
    # print(f"Processed {len(documents_to_split)} original documents.")
    # print(f"Number of chunks created: {len(split_chunks_docs)}")
    # if split_chunks_docs:
        # print(f"Example chunk (first 50 chars): '{split_chunks_docs[0].page_content[:50]}...'")
        # print(f"Metadata of first chunk: {split_chunks_docs[0].metadata}") # Useful for debugging
        
    return split_chunks_docs

def save_chunks_to_json(chunked_documents: list[Document], file_path: str):
    """
    Saves the list of chunked Document objects (content and metadata) to a JSON file.

    Args:
        chunked_documents (list[Document]): A list of chunked Document objects.
        file_path (str): The path to the JSON file where chunks will be saved.
    """
    data_to_save = [
        {"page_content": doc.page_content, "metadata": doc.metadata}
        for doc in chunked_documents
    ]
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data_to_save, f, indent=4)
    print(f"Chunked documents (with metadata) saved to {file_path}")

def load_chunks_from_json(file_path: str) -> list[dict]:
    """
    Loads chunked data (page_content and metadata) from a JSON file.

    Args:
        file_path (str): The path to the JSON file.

    Returns:
        list[dict]: A list of dictionaries, where each dict has "page_content" and "metadata".
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        print(f"Chunked data (with metadata) loaded from {file_path}")
        return loaded_data
    except FileNotFoundError:
        print(f"Error: Chunk file not found at {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}. File might be empty or corrupted.")
        return []

if __name__ == '__main__':
    # Example Usage (for testing chunking.py directly)
    # This section needs to be updated to use Document objects for testing.
    # For now, it's commented out to avoid errors due to the signature change.
    pass
    # sample_doc_content = """This is a long sample text to demonstrate the chunking functionality.
    # It has multiple sentences and paragraphs. The purpose of chunking is to break down
    # large documents into smaller, manageable pieces for processing by language models.
    # This is particularly important for models with context window limitations.
    # Semantic chunking, which tries to keep related concepts together, is often preferred
    # over simple fixed-size chunking. LangChain provides useful tools for this.
    # Let's see how the RecursiveCharacterTextSplitter handles this.
    # It should be able to split based on common separators like newlines and sentence endings.
    # The overlap helps in maintaining context between chunks.
    # This is the end of the sample text. We hope the chunking works as expected.
    # Another sentence to make it a bit longer. And one more for good measure.
    # Final sentence here.
    # """
    # sample_metadata = {"source": "test_document.txt", "doc_id": 1}
    # sample_document = Document(page_content=sample_doc_content, metadata=sample_metadata)
    
    # print(f"Testing with RecursiveCharacterTextSplitter on Document objects:")
    # chunked_docs = chunk_text([sample_document], chunk_size=150, chunk_overlap=30)
    
    # if chunked_docs:
    #     for i, doc_chunk in enumerate(chunked_docs):
    #         print(f"Chunk {i+1} (length {len(doc_chunk.page_content)}):")
    #         print(f"Content: '{doc_chunk.page_content}'")
    #         print(f"Metadata: {doc_chunk.metadata}")
    #         print("---")
            
    #     # Test saving and loading
    #     # save_chunks_to_json(chunked_docs, "test_chunks_with_metadata.json")
    #     # loaded_chunk_data = load_chunks_from_json("test_chunks_with_metadata.json")
    #     # print("\\nLoaded chunk data (first item):", loaded_chunk_data[0] if loaded_chunk_data else "None")
    #     # import os
    #     # if os.path.exists("test_chunks_with_metadata.json"):
    #     #     os.remove("test_chunks_with_metadata.json")
    # else:
    #     print("No chunks were created.")

# Main script to run the RAG pipeline

from src.ingestion import load_and_extract_text_from_pdfs, get_pdf_paths_from_directory
from src.chunking import chunk_text # chunk_text now expects list[Document] and returns list[Document]
from src.embedding import create_embeddings, build_and_save_faiss_index, load_faiss_index, embed_query
from src.retrieval import search_faiss_index
from src.generation import generate_llm_response
# utils.py uses save_chunks_to_json and load_chunks_from_json from chunking.py
from src.utils import save_text_chunks, load_text_chunks 
from langchain_core.documents import Document # Import Document

import os
import json # If saving/loading chunks as json

# --- Configuration ---
# Paths
INDEX_PATH = "index_store/faiss_index.idx"
TEXT_CHUNKS_PATH = "index_store/text_chunks.json" # Path to store/load text chunks

# Models (using placeholders, replace with actual model identifiers)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL_NAME = "gemini-2.0-flash" # Updated to reflect Gemini usage and specific model path

# Chunking parameters
CHUNK_SIZE = 1000 # Characters or tokens, depending on your chunking strategy
CHUNK_OVERLAP = 100

# Retrieval parameters
TOP_K_RESULTS = 5 # Increased from 3 to 5

def ensure_directories_exist():
    """Ensures that necessary output directories exist."""
    os.makedirs("index_store", exist_ok=True)
    # No longer printing PDF_DIRECTORY guidance here

def run_indexing_pipeline(): # Removed source_directory parameter
    """Runs the data ingestion, chunking, embedding, and indexing part of the pipeline."""
    
    source_directory = input("Please enter the path to the directory containing your PDF files: ").strip()
    if not source_directory:
        print("No source directory provided. Exiting indexing pipeline.")
        return

    print(f"Starting indexing pipeline for source directory: {source_directory}...")
    ensure_directories_exist() # Ensures index_store exists

    if not os.path.isdir(source_directory):
        print(f"Error: Source directory '{source_directory}' not found or is not a directory.")
        return

    pdf_files = get_pdf_paths_from_directory(source_directory) # Use the passed argument
    if not pdf_files:
        print(f"No PDF files found in {source_directory}. Please add some PDFs and try again.")
        return

    print(f"Found {len(pdf_files)} PDF(s) to process.")
    # all_texts_with_sources is a list of dicts: [{'text': ..., 'source': ..., 'page': ...}, ...]
    all_texts_with_sources = load_and_extract_text_from_pdfs(pdf_files)

    if not all_texts_with_sources:
        print("No text could be extracted from the PDFs.")
        return

    # Convert list of dicts to list of Langchain Document objects
    documents_to_chunk = [
        Document(page_content=item['text'], metadata={'source': item['source'], 'page': item.get('page', 'N/A')})
        for item in all_texts_with_sources
    ]

    if not documents_to_chunk:
        print("No documents could be prepared for chunking.")
        return

    # chunk_text now expects list[Document] and returns list[Document]
    chunked_documents = chunk_text(documents_to_chunk, CHUNK_SIZE, CHUNK_OVERLAP)

    if not chunked_documents:
        print("No chunks were created from the text.")
        return

    print(f"Created {len(chunked_documents)} chunks.")

    # Extract page_content for embedding from the list of Document objects
    actual_text_chunks = [doc.page_content for doc in chunked_documents]

    embeddings = create_embeddings(actual_text_chunks, EMBEDDING_MODEL_NAME)
    if embeddings is None or len(embeddings) == 0:
        print("Failed to create embeddings.")
        return

    print(f"Generated {len(embeddings)} embeddings.")

    build_and_save_faiss_index(embeddings, INDEX_PATH)
    # save_text_chunks now handles list[Document] via chunking.py's save_chunks_to_json
    save_text_chunks(chunked_documents, TEXT_CHUNKS_PATH) 

    print(f"FAISS index built and saved to {INDEX_PATH}")
    print(f"Text chunks saved to {TEXT_CHUNKS_PATH}")
    print("Indexing pipeline completed.")

def run_query_pipeline():
    """Runs the query processing part of the pipeline."""
    print("Starting query pipeline...")
    if not os.path.exists(INDEX_PATH) or not os.path.exists(TEXT_CHUNKS_PATH):
        print("Index or text chunks not found. Please run the indexing pipeline first.") # Removed 'python main.py index'
        return

    faiss_index = load_faiss_index(INDEX_PATH)
    # load_text_chunks (via chunking.py's load_chunks_from_json) returns list[dict]
    # where each dict is {'page_content': ..., 'metadata': ...}
    loaded_chunk_data = load_text_chunks(TEXT_CHUNKS_PATH)

    if faiss_index is None or not loaded_chunk_data: # Check if loaded_chunk_data is empty
        print("Failed to load FAISS index or text chunks.")
        return

    user_query = input("Please enter your question: ")
    if not user_query:
        print("No query entered.")
        return

    query_embedding = embed_query(user_query, EMBEDDING_MODEL_NAME)
    if query_embedding is None:
        print("Failed to embed query.")
        return

    retrieved_indices, _ = search_faiss_index(query_embedding, faiss_index, top_k=TOP_K_RESULTS)

    # relevant_chunk_data will be a list of dicts from loaded_chunk_data
    relevant_chunk_data = [loaded_chunk_data[i] for i in retrieved_indices]
    
    # Extract page_content from the dictionaries
    relevant_texts = [chunk['page_content'] for chunk in relevant_chunk_data]

    if not relevant_texts:
        print("No relevant documents found for your query.")
        return

    print(f"\\nRetrieved {len(relevant_texts)} relevant chunks for your query.")

    answer = generate_llm_response(user_query, relevant_texts, LLM_MODEL_NAME)

    print("\\n--- Answer ---")
    print(answer)
    print("\\n--- Sources ---")
    for i, chunk_data in enumerate(relevant_chunk_data):
        source = chunk_data['metadata'].get('source', 'N/A')
        page = chunk_data['metadata'].get('page', 'N/A')
        print(f"[{i+1}] Source: {source}, Page: {page}")

if __name__ == "__main__":
    action = input("Do you want to 'index' new documents or 'query' the existing knowledge base? (index/query): ").strip().lower()

    if action == 'index':
        run_indexing_pipeline()
    elif action == 'query':
        run_query_pipeline()
    else:
        print("Invalid action. Please type 'index' or 'query'.")

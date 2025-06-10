# Main script to run the RAG pipeline

from src.ingestion import load_and_extract_text_from_pdfs, get_pdf_paths_from_directory
from src.chunking import chunk_text
from src.embedding import create_embeddings, build_and_save_faiss_index, load_faiss_index, embed_query
from src.retrieval import search_faiss_index
from src.generation import generate_llm_response
from src.utils import save_text_chunks, load_text_chunks # For saving/loading the text chunks

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
    all_texts_with_sources = load_and_extract_text_from_pdfs(pdf_files)

    if not all_texts_with_sources:
        print("No text could be extracted from the PDFs.")
        return

    # The 'all_texts_with_sources' variable should be a list of dictionaries,
    # each containing 'text', 'source', and 'page'. This is what chunk_text expects.
    # texts_to_chunk = [item['text'] for item in all_texts_with_sources] # No longer needed
    # source_metadata = [{ "source": item['source'], "page": item.get('page') } for item in all_texts_with_sources] # No longer needed

    text_chunks_with_metadata = chunk_text(all_texts_with_sources, CHUNK_SIZE, CHUNK_OVERLAP)

    if not text_chunks_with_metadata:
        print("No chunks were created from the text.")
        return

    print(f"Created {len(text_chunks_with_metadata)} chunks.")

    # Separate actual text for embedding and metadata for storage
    actual_text_chunks = [chunk['text'] for chunk in text_chunks_with_metadata]

    embeddings = create_embeddings(actual_text_chunks, EMBEDDING_MODEL_NAME)
    if embeddings is None or len(embeddings) == 0:
        print("Failed to create embeddings.")
        return

    print(f"Generated {len(embeddings)} embeddings.")

    build_and_save_faiss_index(embeddings, INDEX_PATH)
    save_text_chunks(text_chunks_with_metadata, TEXT_CHUNKS_PATH) # Save chunks with metadata

    print(f"FAISS index built and saved to {INDEX_PATH}")
    print(f"Text chunks saved to {TEXT_CHUNKS_PATH}")
    print("Indexing pipeline completed.")

def run_query_pipeline():
    """Runs the query processing part of the pipeline."""
    print("Starting query pipeline...")
    if not os.path.exists(INDEX_PATH) or not os.path.exists(TEXT_CHUNKS_PATH):
        print("Index or text chunks not found. Please run the indexing pipeline first using 'python main.py index'.")
        return

    faiss_index = load_faiss_index(INDEX_PATH)
    # Load the text_chunks_with_metadata that were saved during indexing
    text_chunks_with_metadata = load_text_chunks(TEXT_CHUNKS_PATH)

    if faiss_index is None or text_chunks_with_metadata is None:
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

    # The search_faiss_index should return indices, which we then use to get chunks from text_chunks_with_metadata
    retrieved_indices, _ = search_faiss_index(query_embedding, faiss_index, top_k=TOP_K_RESULTS)

    relevant_chunks_with_metadata = [text_chunks_with_metadata[i] for i in retrieved_indices]
    # Extract just the text for the LLM, but keep metadata if you want to show sources
    relevant_texts = [chunk['text'] for chunk in relevant_chunks_with_metadata]

    if not relevant_texts:
        print("No relevant documents found for your query.")
        return

    print(f"\nRetrieved {len(relevant_texts)} relevant chunks for your query.")

    answer = generate_llm_response(user_query, relevant_texts, LLM_MODEL_NAME)

    print("\n--- Answer ---")
    print(answer)
    print("\n--- Sources ---")
    for i, chunk_meta in enumerate(relevant_chunks_with_metadata):
        print(f"[{i+1}] Source: {chunk_meta.get('source', 'N/A')}, Page: {chunk_meta.get('page', 'N/A')}")

if __name__ == "__main__":
    action = input("Do you want to 'index' new documents or 'query' the existing knowledge base? (index/query): ").strip().lower()

    if action == 'index':
        run_indexing_pipeline()
    elif action == 'query':
        run_query_pipeline()
    else:
        print("Invalid action. Please type 'index' or 'query'.")

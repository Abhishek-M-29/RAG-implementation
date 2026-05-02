# Main script to run the RAG pipeline

import os

# --- Configuration ---
# Paths
INDEX_PATH = "index_store/faiss_index"

# Models
LLM_MODEL_NAME = "gemini-3-flash-preview"

# Chunking parameters
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

# Retrieval parameters
TOP_K_RESULTS = 5

def ensure_directories_exist():
    """Ensures that necessary output directories exist."""
    os.makedirs("index_store", exist_ok=True)

def run_indexing_pipeline():
    """Runs the data ingestion, chunking, embedding, and indexing part of the pipeline."""
    from src.ingestion import load_and_extract_text_from_pdfs, get_pdf_paths_from_directory
    from src.chunking import chunk_text
    from src.embedding import build_and_save_faiss_index
    from langchain_core.documents import Document
    
    source_directory = input("Please enter the path to the directory containing your PDF files: ").strip()
    if not source_directory:
        print("No source directory provided. Exiting indexing pipeline.")
        return

    print(f"Starting indexing pipeline for source directory: {source_directory}...")
    ensure_directories_exist()

    if not os.path.isdir(source_directory):
        print(f"Error: Source directory '{source_directory}' not found or is not a directory.")
        return

    pdf_files = get_pdf_paths_from_directory(source_directory)
    if not pdf_files:
        print(f"No PDF files found in {source_directory}. Please add some PDFs and try again.")
        return

    print(f"Found {len(pdf_files)} PDF(s) to process.")
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

    chunked_documents = chunk_text(documents_to_chunk, CHUNK_SIZE, CHUNK_OVERLAP)

    if not chunked_documents:
        print("No chunks were created from the text.")
        return

    print(f"Created {len(chunked_documents)} chunks.")

    vectorstore = build_and_save_faiss_index(chunked_documents, INDEX_PATH)
    
    if vectorstore is None:
        print("Failed to create and save index.")
        return

    print("Indexing pipeline completed.")

def run_query_pipeline():
    """Runs the query processing part of the pipeline."""
    print("Starting query pipeline...")
    from src.embedding import load_faiss_index
    from src.retrieval import search_faiss_index
    from src.generation import generate_llm_response
    
    vectorstore = load_faiss_index(INDEX_PATH)
    
    if vectorstore is None:
        print("Failed to load FAISS index. Please run the indexing pipeline first.")
        return

    user_query = input("Please enter your question: ")
    if not user_query:
        print("No query entered.")
        return

    relevant_docs = search_faiss_index(user_query, vectorstore, top_k=TOP_K_RESULTS)

    if not relevant_docs:
        print("No relevant documents found for your query.")
        return

    print(f"\nRetrieved {len(relevant_docs)} relevant chunks for your query.")

    desired_marks_str = input("How many marks is this question worth (e.g., 2, 5, 10)? Press Enter for default detail: ").strip()
    desired_marks = None
    if desired_marks_str:
        try:
            desired_marks = int(desired_marks_str)
            if desired_marks <= 0:
                print("Marks should be a positive number. Using default detail.")
                desired_marks = None
        except ValueError:
            print("Invalid input for marks. Using default detail.")
            desired_marks = None

    answer = generate_llm_response(user_query, relevant_docs, LLM_MODEL_NAME, desired_marks=desired_marks)

    print("\n--- Answer ---")
    print(answer)
    print("\n--- Sources ---")
    for i, doc in enumerate(relevant_docs):
        source = doc.metadata.get('source', 'N/A')
        page = doc.metadata.get('page', 'N/A')
        print(f"[{i+1}] Source: {source}, Page: {page}")

if __name__ == "__main__":
    action = input("Do you want to 'index' new documents or 'query' the existing knowledge base? (index/query): ").strip().lower()

    if action == 'index':
        run_indexing_pipeline()
    elif action == 'query':
        run_query_pipeline()
    else:
        print("Invalid action. Please type 'index' or 'query'.")
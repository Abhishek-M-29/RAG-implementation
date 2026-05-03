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
    all_documents = load_and_extract_text_from_pdfs(pdf_files)

    if not all_documents:
        print("No text could be extracted from the PDFs.")
        return

    chunked_documents = chunk_text(all_documents, CHUNK_SIZE, CHUNK_OVERLAP)

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
    print("Starting CLI query pipeline...")
    from src.embedding import load_faiss_index
    from src.generation import get_rag_chain
    from langchain_community.chat_message_histories import ChatMessageHistory
    
    vectorstore = load_faiss_index(INDEX_PATH)
    
    if vectorstore is None:
        print("Failed to load FAISS index. Please run the indexing pipeline first.")
        return

    # Prepare an in-memory session history for the CLI
    cli_history = ChatMessageHistory()
    def get_session_history(session_id: str):
        return cli_history

    try:
        rag_chain = get_rag_chain(vectorstore, top_k=TOP_K_RESULTS, llm_model_name=LLM_MODEL_NAME, get_session_history=get_session_history)
    except Exception as e:
        print(f"Error initializing RAG chain: {e}")
        return

    while True:
        user_query = input("\nPlease enter your question (or type 'exit' to quit): ").strip()
        if user_query.lower() in ['exit', 'quit']:
            break
            
        if not user_query:
            continue

        print("\nThinking...")
        try:
            result = rag_chain.invoke(
                {"input": user_query},
                config={"configurable": {"session_id": "cli_session"}}
            )
            answer = result["answer"]

            print("\n--- Answer ---")
            print(answer)
        except Exception as e:
            print(f"Error generating answer: {e}")

if __name__ == "__main__":
    action = input("Do you want to 'index' new documents or 'query' the existing knowledge base? (index/query): ").strip().lower()

    if action == 'index':
        run_indexing_pipeline()
    elif action == 'query':
        run_query_pipeline()
    else:
        print("Invalid action. Please type 'index' or 'query'.")
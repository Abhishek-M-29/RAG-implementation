import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()

INDEX_PATH = "index_store/faiss_index"
LLM_MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
TOP_K_RESULTS = 5


def ensure_directories_exist():
    os.makedirs("index_store", exist_ok=True)


def collect_pdf_paths(dirs=None, files=None):
    from src.ingestion import get_pdf_paths_from_directory

    pdf_files = []
    if dirs:
        for d in dirs:
            if not os.path.isdir(d):
                print(f"Warning: Directory '{d}' not found, skipping.")
                continue
            pdf_files.extend(get_pdf_paths_from_directory(d))
    if files:
        for f in files:
            if os.path.isfile(f) and f.lower().endswith(".pdf"):
                pdf_files.append(os.path.abspath(f))
            else:
                print(f"Warning: File '{f}' not found or not a PDF, skipping.")
    return pdf_files


def process_documents(pdf_files, chunk_size, chunk_overlap):
    from src.ingestion import load_and_extract_text_from_pdfs
    from src.chunking import chunk_text

    if not pdf_files:
        return None

    print(f"Processing {len(pdf_files)} PDF(s)...")
    all_documents = load_and_extract_text_from_pdfs(pdf_files)
    if not all_documents:
        print("No text could be extracted from the PDFs.")
        return None

    chunked_documents = chunk_text(all_documents, chunk_size, chunk_overlap)
    if not chunked_documents:
        print("No chunks were created from the text.")
        return None

    print(f"Created {len(chunked_documents)} chunks.")
    return chunked_documents


def prompt_for_pdf_source():
    source_directory = input("Please enter the path to the directory containing your PDF files: ").strip()
    if not source_directory:
        print("No source directory provided.")
        return None
    if not os.path.isdir(source_directory):
        print(f"Error: Source directory '{source_directory}' not found.")
        return None
    files = collect_pdf_paths(dirs=[source_directory], files=None)
    if not files:
        print(f"No PDF files found in {source_directory}.")
        return None
    return files


def run_indexing(dirs, files, append, chunk_size, chunk_overlap):
    from src.embedding import build_and_save_faiss_index, add_to_faiss_index

    ensure_directories_exist()

    pdf_files = collect_pdf_paths(dirs, files)
    if not pdf_files:
        pdf_files = prompt_for_pdf_source()
        if not pdf_files:
            return

    chunked = process_documents(pdf_files, chunk_size, chunk_overlap)
    if chunked is None:
        return

    if append:
        print("Appending to existing index...")
        vectorstore = add_to_faiss_index(chunked, INDEX_PATH)
    else:
        print("Building new index...")
        vectorstore = build_and_save_faiss_index(chunked, INDEX_PATH)

    if vectorstore is None:
        print("Failed to create and save index.")
        return

    print("Indexing completed.")


def run_clear():
    from src.embedding import clear_faiss_index
    clear_faiss_index(INDEX_PATH)


def run_reindex(dirs, files, chunk_size, chunk_overlap):
    run_clear()
    run_indexing(dirs, files, append=False, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def run_info():
    from src.embedding import load_faiss_index

    path = INDEX_PATH
    if not os.path.exists(path):
        print(f"No index found at {path}")
        return

    index_file = os.path.join(path, "index.faiss")
    pkl_file = os.path.join(path, "index.pkl")
    index_size = os.path.getsize(index_file) if os.path.exists(index_file) else 0
    pkl_size = os.path.getsize(pkl_file) if os.path.exists(pkl_file) else 0

    vectorstore = load_faiss_index(path)
    if vectorstore is None:
        print("Could not load index.")
        return

    num_docs = vectorstore.index.ntotal if hasattr(vectorstore, "index") else "unknown"

    print(f"Index location: {os.path.abspath(path)}")
    print(f"Number of vectors: {num_docs}")
    print(f"Index file size: {index_size / 1024:.1f} KB")
    print(f"Document store size: {pkl_size / 1024:.1f} KB")
    print(f"Total size: {(index_size + pkl_size) / 1024:.1f} KB")


def run_query(top_k):
    from src.embedding import load_faiss_index
    from src.generation import get_rag_chain
    from langchain_community.chat_message_histories import ChatMessageHistory

    print("Starting CLI query pipeline...")
    vectorstore = load_faiss_index(INDEX_PATH)
    if vectorstore is None:
        print("Failed to load FAISS index. Please run the indexing pipeline first.")
        return

    cli_history = ChatMessageHistory()

    def get_session_history(session_id: str):
        return cli_history

    try:
        rag_chain = get_rag_chain(
            vectorstore,
            top_k=top_k,
            llm_model_name=LLM_MODEL_NAME,
            get_session_history=get_session_history,
        )
    except Exception as e:
        print(f"Error initializing RAG chain: {e}")
        return

    while True:
        user_query = input("\nPlease enter your question (or type 'exit' to quit): ").strip()
        if user_query.lower() in ["exit", "quit"]:
            break
        if not user_query:
            continue

        print("\nThinking...")
        try:
            result = rag_chain.invoke(
                {"input": user_query},
                config={"configurable": {"session_id": "cli_session"}},
            )
            print("\n--- Answer ---")
            print(result["answer"])
        except Exception as e:
            print(f"Error generating answer: {e}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="RAG CLI - Index and query documents using a local knowledge base"
    )
    subparsers = parser.add_subparsers(dest="command")

    p_index = subparsers.add_parser("index", help="Index documents into the knowledge base")
    p_index.add_argument("-d", "--dir", action="append", dest="dirs", help="Directory containing PDF files (repeatable)")
    p_index.add_argument("-f", "--file", action="append", dest="files", help="Specific PDF file to index (repeatable)")
    p_index.add_argument("-a", "--append", action="store_true", help="Append to existing index instead of overwriting")
    p_index.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help=f"Chunk size in characters (default: {CHUNK_SIZE})")
    p_index.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP, help=f"Chunk overlap in characters (default: {CHUNK_OVERLAP})")

    p_reindex = subparsers.add_parser("reindex", help="Clear and reindex all documents from scratch")
    p_reindex.add_argument("-d", "--dir", action="append", dest="dirs", help="Directory containing PDF files (repeatable)")
    p_reindex.add_argument("-f", "--file", action="append", dest="files", help="Specific PDF file to index (repeatable)")
    p_reindex.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help=f"Chunk size in characters (default: {CHUNK_SIZE})")
    p_reindex.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP, help=f"Chunk overlap in characters (default: {CHUNK_OVERLAP})")

    subparsers.add_parser("clear", help="Clear/delete the FAISS index")

    p_query = subparsers.add_parser("query", help="Query the knowledge base interactively")
    p_query.add_argument("--top-k", type=int, default=TOP_K_RESULTS, help=f"Number of results to retrieve (default: {TOP_K_RESULTS})")

    subparsers.add_parser("info", help="Show information about the current index")

    return parser


def run_interactive():
    prompt = "index/query/clear/reindex/info"
    action = input(f"Do you want to '{prompt}'? ").strip().lower()

    if action == "index":
        append = input("Append to existing index? (y/N): ").strip().lower() == "y"
        run_indexing(None, None, append, CHUNK_SIZE, CHUNK_OVERLAP)
    elif action == "query":
        run_query(TOP_K_RESULTS)
    elif action == "clear":
        run_clear()
    elif action == "reindex":
        run_reindex(None, None, CHUNK_SIZE, CHUNK_OVERLAP)
    elif action == "info":
        run_info()
    else:
        print(f"Invalid action. Choose from: {prompt}")


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        run_interactive()
    elif args.command == "index":
        run_indexing(args.dirs, args.files, args.append, args.chunk_size, args.chunk_overlap)
    elif args.command == "clear":
        run_clear()
    elif args.command == "reindex":
        run_reindex(args.dirs, args.files, args.chunk_size, args.chunk_overlap)
    elif args.command == "info":
        run_info()
    elif args.command == "query":
        run_query(args.top_k)

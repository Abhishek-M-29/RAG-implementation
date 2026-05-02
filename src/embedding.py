# src/embedding.py

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import os

_embedding_model = None

def _get_embedding_model(model_name="sentence-transformers/all-MiniLM-L6-v2"):
    global _embedding_model
    if _embedding_model is None:
        # print(f"Loading embedding model: {model_name}...")
        _embedding_model = HuggingFaceEmbeddings(model_name=model_name)
        # print("Embedding model loaded successfully.")
    return _embedding_model

def build_and_save_faiss_index(documents, index_path="index_store/faiss_index"):
    """
    Builds a FAISS vector store from LangChain Documents and saves it.
    This overwrites the existing index as requested (destructive indexing).
    """
    if not documents:
        # print("No documents provided to build FAISS index.")
        return None
    try:
        model = _get_embedding_model()
        # print(f"Building FAISS index with {len(documents)} documents...")
        vectorstore = FAISS.from_documents(documents, model)
        
        # Save the vector store directly (this saves index and document store)
        # Note: We save to a directory, not a .idx file directly.
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        vectorstore.save_local(index_path)
        # print(f"FAISS index and document store saved to {index_path}")
        return vectorstore
    except Exception as e:
        # print(f"Error building or saving FAISS index: {e}")
        return None

def load_faiss_index(index_path="index_store/faiss_index"):
    """
    Loads a FAISS vector store from disk.
    """
    if not os.path.exists(index_path):
        # print(f"FAISS index directory not found at {index_path}")
        return None
    try:
        # print(f"Loading FAISS index from {index_path}...")
        model = _get_embedding_model()
        vectorstore = FAISS.load_local(index_path, model, allow_dangerous_deserialization=True)
        # print("FAISS index loaded successfully.")
        return vectorstore
    except Exception as e:
        # print(f"Error loading FAISS index: {e}")
        return None
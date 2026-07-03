# src/embedding.py

import os
import shutil
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

_embedding_model = None

def _get_embedding_model(model_name="sentence-transformers/all-MiniLM-L6-v2"):
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = HuggingFaceEmbeddings(model_name=model_name)
    return _embedding_model

def build_and_save_faiss_index(documents, index_path="index_store/faiss_index"):
    """
    Builds a FAISS vector store from LangChain Documents and saves it.
    Overwrites any existing index.
    """
    if not documents:
        return None
    try:
        model = _get_embedding_model()
        vectorstore = FAISS.from_documents(documents, model)
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        vectorstore.save_local(index_path)
        return vectorstore
    except Exception as e:
        print(f"Error building FAISS index: {e}")
        return None

def add_to_faiss_index(documents, index_path="index_store/faiss_index"):
    """
    Adds documents to an existing FAISS index.
    If no index exists, creates a new one.
    """
    if not documents:
        return None
    existing = load_faiss_index(index_path)
    if existing is None:
        return build_and_save_faiss_index(documents, index_path)
    try:
        existing.add_documents(documents)
        existing.save_local(index_path)
        return existing
    except Exception as e:
        print(f"Error during add_documents: {e}")
        print("Falling back to merge approach...")
        try:
            all_docs = []
            for doc_id in existing.index_to_docstore_id.values():
                doc = existing.docstore.search(doc_id)
                if doc is not None:
                    all_docs.append(doc)
            all_docs.extend(documents)
            print(f"Merging {len(all_docs)} total documents into new index...")
            return build_and_save_faiss_index(all_docs, index_path)
        except Exception as e2:
            print(f"Merge also failed: {e2}")
            return None

def load_faiss_index(index_path="index_store/faiss_index"):
    """
    Loads a FAISS vector store from disk.
    """
    if not os.path.exists(index_path):
        return None
    try:
        model = _get_embedding_model()
        vectorstore = FAISS.load_local(index_path, model, allow_dangerous_deserialization=True)
        return vectorstore
    except Exception as e:
        print(f"Error loading FAISS index: {e}")
        return None

def clear_faiss_index(index_path="index_store/faiss_index"):
    """
    Removes the FAISS index directory from disk.
    """
    if os.path.exists(index_path):
        shutil.rmtree(index_path)
        print(f"Index cleared from {index_path}")
    else:
        print(f"No index found at {index_path}")
# src/embedding.py

from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import os

# Global variable to hold the embedding model
# This is to avoid loading the model multiple times if functions are called repeatedly.
_embedding_model = None

def _get_embedding_model(model_name="sentence-transformers/all-MiniLM-L6-v2"):
    """Loads the sentence transformer model. Uses a global variable to ensure it's loaded only once."""
    global _embedding_model
    if _embedding_model is None:
        try:
            print(f"Loading embedding model: {model_name}...")
            _embedding_model = SentenceTransformer(model_name)
            print("Embedding model loaded successfully.")
        except Exception as e:
            print(f"Error loading sentence transformer model {model_name}: {e}")
            # Potentially fall back to a default or raise an error
            raise
    return _embedding_model

def create_embeddings(text_chunks, embedding_model_name="sentence-transformers/all-MiniLM-L6-v2"):
    """
    Generates vector embeddings for a list of text chunks.
    Args:
        text_chunks (list of str): List of text chunks.
        embedding_model_name (str): Name or path of the pre-trained embedding model.
    Returns:
        numpy.ndarray: An array of embeddings, or None if an error occurs.
    """
    if not text_chunks:
        print("No text chunks provided for embedding.")
        return np.array([])
    try:
        model = _get_embedding_model(embedding_model_name)
        print(f"Generating embeddings for {len(text_chunks)} chunks...")
        embeddings = model.encode(text_chunks, show_progress_bar=True)
        print("Embeddings generated.")
        return np.array(embeddings).astype('float32') # FAISS expects float32
    except Exception as e:
        print(f"Error creating embeddings: {e}")
        return None

def build_and_save_faiss_index(embeddings, index_path="faiss_index.idx"):
    """
    Builds a FAISS index from embeddings and saves it.
    Args:
        embeddings (numpy.ndarray): The vector embeddings to index.
        index_path (str): Path to save the FAISS index.
    Returns:
        faiss.Index: The created FAISS index, or None if an error occurs.
    """
    if embeddings is None or embeddings.shape[0] == 0:
        print("No embeddings provided to build FAISS index.")
        return None
    try:
        dimension = embeddings.shape[1]
        # Using IndexFlatL2, which is a simple L2 distance search.
        # For larger datasets, more complex indices like IndexIVFFlat might be better.
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)
        print(f"FAISS index built with {index.ntotal} vectors.")
        faiss.write_index(index, index_path)
        print(f"FAISS index saved to {index_path}")
        return index
    except Exception as e:
        print(f"Error building or saving FAISS index: {e}")
        return None

def load_faiss_index(index_path="faiss_index.idx"):
    """
    Loads a FAISS index from disk.
    Args:
        index_path (str): Path to the FAISS index file.
    Returns:
        faiss.Index: The loaded FAISS index, or None if not found or error.
    """
    if not os.path.exists(index_path):
        print(f"FAISS index file not found at {index_path}")
        return None
    try:
        print(f"Loading FAISS index from {index_path}...")
        index = faiss.read_index(index_path)
        print(f"FAISS index loaded with {index.ntotal} vectors.")
        return index
    except Exception as e:
        print(f"Error loading FAISS index: {e}")
        return None

def embed_query(query_text, embedding_model_name="sentence-transformers/all-MiniLM-L6-v2"):
    """
    Generates a vector embedding for the user's query.
    Args:
        query_text (str): The user's query.
        embedding_model_name (str): Name or path of the pre-trained embedding model.
    Returns:
        numpy.ndarray: The embedding for the query (as a 2D array for FAISS), or None if error.
    """
    if not query_text:
        print("No query text provided for embedding.")
        return None
    try:
        model = _get_embedding_model(embedding_model_name)
        embedding = model.encode([query_text]) # Encode expects a list
        return np.array(embedding).astype('float32')
    except Exception as e:
        print(f"Error embedding query: {e}")
        return None

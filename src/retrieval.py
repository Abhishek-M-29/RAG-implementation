# src/retrieval.py
import numpy as np

def search_faiss_index(query_embedding, faiss_index, top_k=5):
    """
    Searches the FAISS index for the most similar embeddings to the query embedding.
    Args:
        query_embedding (numpy.ndarray): The embedding of the user's query (should be 2D array).
        faiss_index (faiss.Index): The FAISS index.
        top_k (int): The number of top similar chunks to retrieve.
    Returns:
        tuple: (indices, distances) of the top_k results or (None, None) if error.
    """
    if query_embedding is None or faiss_index is None:
        print("Error: Query embedding or FAISS index is None.")
        return None, None
    try:
        if query_embedding.ndim == 1:
            query_embedding = np.expand_dims(query_embedding, axis=0) # Ensure 2D for FAISS
        
        print(f"Searching FAISS index for top {top_k} results...")
        distances, indices = faiss_index.search(query_embedding, top_k)
        print(f"Search completed. Found indices: {indices}, Distances: {distances}")
        return indices[0], distances[0] # Return 1D arrays for easier handling
    except Exception as e:
        print(f"Error during FAISS search: {e}")
        return None, None

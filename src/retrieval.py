# src/retrieval.py

def search_faiss_index(query_text, vectorstore, top_k=5):
    """
    Searches the LangChain FAISS vectorstore for the most similar chunks.
    Args:
        query_text (str): The user's query text.
        vectorstore (FAISS): The LangChain FAISS vectorstore.
        top_k (int): The number of top similar chunks to retrieve.
    Returns:
        list[Document]: The retrieved documents, or empty list if error.
    """
    if not query_text or vectorstore is None:
        print("Error: Query text or vectorstore is None.")
        return []
    try:
        print(f"Searching for top {top_k} results...")
        docs = vectorstore.similarity_search(query_text, k=top_k)
        print(f"Search completed. Found {len(docs)} documents.")
        return docs
    except Exception as e:
        print(f"Error during search: {e}")
        return []
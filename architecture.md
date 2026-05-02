# RAG System Architecture

This document outlines the architecture for a Retrieval Augmented Generation (RAG) system.

## Core Pipeline Steps

The system follows these main steps:

1.  **PDF Reading:**
    *   **Tool/Library:** `pypdf` (or similar Python PDF processing library).
    *   **Process:** Load PDF documents provided by the user. Extract raw text content from these PDFs.
    *   **Output:** Plain text extracted from the PDFs.

2.  **Chunk the Data:**
    *   **Process:** Take the extracted plain text and divide it into smaller, manageable, and semantically coherent chunks. This is important for effective embedding and for fitting within the context window of LLMs.
    *   **Considerations:** Chunk size, overlap between chunks.
    *   **Output:** A list of text chunks.

3.  **Make Vector Embeddings and Store in Vector Database:**
    *   **Embedding Model:** A sentence transformer model (e.g., from Hugging Face like `all-MiniLM-L6-v2`) or an API-based model (e.g., OpenAI's `text-embedding-ada-002`).
    *   **Vector Database:** FAISS (Facebook AI Similarity Search).
    *   **Process:**
        *   For each text chunk, generate a numerical vector representation (embedding) using the chosen embedding model.
        *   Store these embeddings in a FAISS index. This index will allow for efficient similarity searches.
        *   It's also crucial to store the original text chunks in a way that they can be retrieved using the results from the FAISS index (e.g., by storing them in a list or a simple key-value store where the index in FAISS corresponds to the index/key of the text chunk).
    *   **Output:** A FAISS index containing the embeddings and a corresponding store of the text chunks.

4.  **Get Query from User:**
    *   **Process:** Provide an interface (e.g., command-line input, web UI) for the user to submit their question or query.
    *   **Output:** The user's query as a string.

5.  **Embed the Query:**
    *   **Process:** Take the user's query and convert it into a vector embedding using the *exact same embedding model* that was used in Step 3 for the documents.
    *   **Output:** A query vector.

6.  **Find Cosine Similarity (or other distance metric) in Vector DB:**
    *   **Process:** Use the query vector to search the FAISS index. FAISS will calculate the similarity (e.g., cosine similarity, L2 distance) between the query embedding and all the chunk embeddings stored in the index.
    *   **Output:** A list of similarities/distances and the indices of the corresponding chunks in the FAISS index.

7.  **Pick the Top Few Embeddings (Most Relevant Chunks):**
    *   **Process:** Based on the similarity scores from Step 6, select the top-k most relevant/similar chunks.
    *   Retrieve the actual text of these top-k chunks using the indices obtained from FAISS and the stored text chunks.
    *   **Output:** A list of the most relevant text chunks (the context).

8.  **Feed to LLM and Generate Response:**
    *   **LLM:** A Large Language Model, specifically Google's **Gemini 3 Flash Preview** (`gemini-3-flash-preview`).
    *   **Process:**
        *   Construct a prompt for the LLM. This prompt should include:
            *   The retrieved relevant text chunks (the context).
            *   The original user query.
            *   Clear instructions for the LLM to answer the query *based only on the provided context* and output in formatted Markdown.
        *   Send this augmented prompt to the LLM.
        *   Receive the generated text from the LLM.
    *   **Output:** The final answer to the user's query.

## Data Flow Summary

**Indexing Phase (Offline):**
`PDFs` -> `Text Extraction (pypdf)` -> `Raw Text` -> `Chunking` -> `Text Chunks` -> `Embedding Model` -> `Vector Embeddings` -> `FAISS Index`

**Querying Phase (Online):**
`User Query` -> `Embedding Model` -> `Query Embedding` -> `FAISS Search (with Index)` -> `Top-k Relevant Chunk Indices` -> `Retrieve Text Chunks` -> `Context + Query` -> `LLM` -> `Answer`

# RAG Implementation with Gemini

This project implements a Retrieval Augmented Generation (RAG) system that uses PDF documents as a knowledge base and the Gemini API (gemini-1.0-flash or similar) for generating answers.

## Features

*   PDF text extraction and chunking.
*   Vector embeddings using Sentence Transformers.
*   FAISS for efficient similarity search (vector database).
*   Answer generation using Google's Gemini API.
*   CLI for indexing new documents and querying the knowledge base.

## Project Structure

```
.RAG-implementation/
├── .git/                     # Git repository files
├── data/                     # (Recommended) Store your source PDF files here
│   └── (empty by default)
├── index_store/              # Stores the FAISS index and text chunks
│   ├── faiss_index.idx
│   └── text_chunks.json
├── src/                      # Source code for the RAG pipeline
│   ├── chunking.py
│   ├── embedding.py
│   ├── generation.py
│   ├── ingestion.py
│   ├── retrieval.py
│   └── utils.py
├── main.py                   # Main script to run indexing or querying
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── architecture.md           # System architecture overview
```

## Setup

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone https://github.com/Abhishek-M-29/RAG-implementation.git
    cd RAG-implementation
    ```

2.  **Create a Python virtual environment (recommended):**
    ```bash
    python -m venv venv
    ```
    Activate it:
    *   Windows (PowerShell):
        ```powershell
        .\venv\Scripts\Activate.ps1
        ```
    *   macOS/Linux:
        ```bash
        source venv/bin/activate
        ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure API Key:**
    The Gemini API key is currently hardcoded in `src/generation.py`:
    ```python
    # src/generation.py
    # ...
    api_key = "AIzaSyBXzi17iCVtVcqAz4QaI6lITij1udpx_GA" # Your hardcoded key
    # ...
    ```
    Replace `"AIzaSyBXzi17iCVtVcqAz4QaI6lITij1udpx_GA"` with your actual Google Gemini API key.
    **Security Note:** For production or shared environments, it is strongly recommended to use environment variables or a secrets manager instead of hardcoding API keys.

## Usage

The `main.py` script provides a command-line interface to interact with the RAG system.

### 1. Indexing Documents

Before you can query, you need to index your PDF documents.

1.  Place your PDF files into a directory (e.g., create a `data/pdfs` directory within the project and put them there).
2.  Run the indexing pipeline:
    ```bash
    python main.py
    ```
3.  When prompted, enter `index`.
4.  Enter the full path to the directory containing your PDF files (e.g., `c:\Users\abhis\Programs\RAG-implementation\data\pdfs` or `./data/pdfs` if you created it inside the project).

    This will:
    *   Extract text from the PDFs.
    *   Chunk the text.
    *   Generate embeddings for each chunk.
    *   Build a FAISS index and save it to `index_store/faiss_index.idx`.
    *   Save the text chunks metadata to `index_store/text_chunks.json`.

### 2. Querying the Knowledge Base

Once your documents are indexed, you can ask questions.

1.  Run the query pipeline:
    ```bash
    python main.py
    ```
2.  When prompted, enter `query`.
3.  Enter your question.

The system will retrieve relevant chunks from your documents and use the Gemini API to generate an answer based *only* on that context. The answer and the sources (document name and page number) will be displayed.

## Configuration Parameters (in `main.py`)

*   `INDEX_PATH`: Path to the FAISS index file.
*   `TEXT_CHUNKS_PATH`: Path to the JSON file storing text chunks.
*   `EMBEDDING_MODEL_NAME`: Sentence Transformer model for embeddings (default: `"sentence-transformers/all-MiniLM-L6-v2"`).
*   `LLM_MODEL_NAME`: Gemini model for generation (e.g., `"models/gemini-pro"`, `"gemini-1.0-flash"`). Currently set to `"gemini-2.0-flash"` (Note: this model name might need adjustment based on availability, the code in `src/generation.py` will attempt to list models if the specified one fails).
*   `CHUNK_SIZE`: Target size of text chunks (in characters).
*   `CHUNK_OVERLAP`: Character overlap between chunks.
*   `TOP_K_RESULTS`: Number of relevant chunks to retrieve and pass to the LLM.

## To Do / Potential Improvements

*   Implement more robust API key management (e.g., `.env` file, environment variables).
*   Add a `.gitignore` file to exclude `index_store/`, `data/` (if PDFs are large/private), and `__pycache__/`.
*   Explore different chunking strategies.
*   Experiment with various embedding and LLM models.
*   Refine prompt engineering for better answer quality.
*   Add more comprehensive error handling and logging.
*   Consider a web interface instead of a CLI.

## Contributing

Feel free to fork the repository and submit pull requests.

## License

This project is open-source (specify a license if you wish, e.g., MIT License).

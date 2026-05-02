# RAG Implementation with Gemini

This project implements a Retrieval Augmented Generation (RAG) system that uses PDF documents as a knowledge base and the Gemini API (gemini-3-flash-preview) for generating formatted Markdown answers.

## Features

*   **LangChain LCEL Pipeline:** Clean, unified generation orchestration relying efficiently on standard LangChain abstractions.
*   **Native Document Ingestion:** Built-in PDF parsing mapping directly into `Document` schemas using `PyPDFLoader`.
*   **Conversational Memory:** Context-aware `RunnableWithMessageHistory` to seamlessly facilitate follow-up questions contextually instead of generic stateless interaction.
*   **Semantic Text Splitters:** Configurable text chunking (`RecursiveCharacterTextSplitter`) explicitly balancing semantic continuity vs context bloat.
*   **Vector embeddings:** Leveraging open-source `sentence-transformers` embedded into a scalable FAISS vector store database index system.
*   **Answer generation:** Utilizing Google's Gemini API (`gemini-3-flash-preview`).
*   **Streamlit UI:** Centralized WebUI interface enabling intuitive PDF file-uploads via an expandable interface directly embedded in chat workflows (removing legacy sidebar-dependency).

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
    import os
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY") # Load from .env
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

## Configuration Parameters

Both `main.py` and `app.py` support the following primary configuration behaviors adjusting vector searches and model utilization explicitly:

*   `INDEX_PATH`: Default destination for storing/querying FAISS (`index_store/faiss_index.idx`).
*   `CHUNK_SIZE = 1000`: How long individual snippet breakdowns of PDF pages should functionally be in absolute character volume. (Lower ensures tighter embeddings, higher avoids context-starvation).
*   `CHUNK_OVERLAP = 100`: The sliding window overlapping value explicitly stitching text concepts together traversing arbitrary line breaks. 
*   `TOP_K_RESULTS = 5`: Limits explicit vector similarity matching context directly down to appending the top 5 matches into the generation pipeline explicitly dynamically.
*   `LLM_MODEL_NAME = "gemini-3-flash-preview"`: Google API integration parameter declaring runtime.

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

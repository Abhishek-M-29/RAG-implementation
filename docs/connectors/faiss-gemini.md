# FAISS + Google Gemini connector guide

This guide covers the shipped default connector pairing: **FAISS** for the vector
store and **Google Gemini** for the LLM. It follows a template structure that a
future "pgvector + OpenAI" page (or any other pairing) can reuse verbatim with
different values.

---

## 1. Connector selection

Set these environment variables (in `.env` or in your shell) to select the
FAISS vector store and Google Gemini LLM:

```env
VECTOR_STORE=faiss
LLM_PROVIDER=google_genai
```

These are the defaults — if you omit them, the framework uses FAISS + Gemini.

---

## 2. Connector-specific configuration

### FAISS (`VECTOR_STORE=faiss`)

| Variable | Default | Description |
|---|---|---|
| `VECTOR_STORE_CONFIG__INDEX_PATH` | `index_store/faiss_index` | On-disk path for the FAISS index directory |
| `VECTOR_STORE_CONFIG__MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace embedding model for vectorisation |
| `VECTOR_STORE_TIMEOUT_SECONDS` | `30.0` | Timeout for vector store operations |

The embedding model is loaded via `langchain_huggingface.HuggingFaceEmbeddings`
and downloads on first use. The model is cached in `~/.cache/huggingface/`.

### Google Gemini (`LLM_PROVIDER=google_genai`)

| Variable | Default | Description |
|---|---|---|
| `LLM_CONFIG__API_KEY` | — | **Required.** Your Google Gemini API key |
| `LLM_CONFIG__MODEL` | `gemini-3.1-flash-lite` | Gemini model identifier |
| `LLM_TIMEOUT_SECONDS` | `30.0` | Timeout for LLM calls |

The API key is read from `LLM_CONFIG__API_KEY` only — there is no fallback to
`GOOGLE_API_KEY` or `GEMINI_API_KEY`. This is intentional: the adopter's
configuration is the single source of truth.

---

## 3. Known limitations

Both limitations below are properties of the **FAISS connector specifically**.
They are not framework-wide issues, and they are the primary reasons the
"next" connectors to implement would be networked vector stores (pgvector,
Qdrant, Pinecone).

### 3.1 `allow_dangerous_deserialization=True`

FAISS persists its index to disk using Python's `pickle` module. When the
framework loads an existing index on startup, it must call:

```python
FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
```

**What this means:** Loading a FAISS index from disk executes arbitrary pickle
data. If an attacker can replace your index files on disk, they could achieve
code execution when the framework starts.

**Why this is accepted:** There is no safe-load path for FAISS indexes saved
by a prior session — the `allow_dangerous_deserialization` flag is a FAISS API
requirement, not a framework choice. The risk is mitigated by:

- The index files are local to the machine running the framework
- Only the framework process writes to the index directory
- In containerised deployments, the index lives on a Docker volume, not a
  shared filesystem

**Future connectors (pgvector, Qdrant, etc.) do not share this risk.** They
communicate with a remote index over a wire protocol and never deserialise
user-supplied pickle data. The presence of this flag on the FAISS connector
alone is not a reason to avoid the framework; it is a reason to prefer a
networked vector store for deployments with stricter security requirements.

### 3.2 O(n) `delete()` cost

When you delete a document from the FAISS index, the framework:

1. Loads every document currently in the index
2. Filters out the deleted document IDs
3. Rebuilds the entire FAISS index from the remaining documents
4. Persists the rebuilt index to disk

This is an **O(n)** operation where `n` is the total number of indexed chunks.
For small indexes (thousands of chunks) the rebuild is nearly instantaneous.
For large indexes (hundreds of thousands of chunks) the delay becomes
noticeable.

**Why this matters for connector choice:** Networked vector stores typically
support O(1) or O(log n) deletion by removing individual vectors without
rebuilding the index. If your application requires frequent or low-latency
deletions, consider replacing FAISS with a networked vector store.

---

## 4. Worked example

This walks through a complete session from a fresh environment to a working
RAG query.

### Prerequisites

- Python 3.10+
- A Google Gemini API key (get one at https://aistudio.google.com/apikey)

### Step 1: Install

```bash
pip install ragframework
```

### Step 2: Configure

```bash
cat > .env << 'EOF'
LLM_CONFIG__API_KEY=your-gemini-api-key
VECTOR_STORE=faiss
VECTOR_STORE_CONFIG__INDEX_PATH=index_store/faiss_index
LLM_PROVIDER=google_genai
LLM_CONFIG__MODEL=gemini-3.1-flash-lite
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
TOP_K=5
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CACHE_BACKEND=memory
MEMORY_BACKEND=memory
ASYNC_INGESTION=false
EOF
```

Replace `your-gemini-api-key` with your actual key.

### Step 3: Start the server

```bash
ragframework serve
```

The API starts on `http://localhost:8000`. Verify it's alive:

```bash
curl http://localhost:8000/v1/health
# {"status":"ok"}
```

### Step 4: Index a PDF

```bash
curl -X POST http://localhost:8000/v1/documents \
  -F "file=@/path/to/your-document.pdf"
```

For synchronous ingestion (`ASYNC_INGESTION=false`), the response returns
immediately with `"status": "queued"` once ingestion completes.

### Step 5: Query

```bash
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What does this document say?", "top_k": 5, "session_id": "demo"}'
```

The response is an SSE stream:

```
data: {"type": "token", "content": "Based on the document, ..."}
data: {"type": "token", "content": " it explains that ..."}
data: {"type": "metadata", "sources": [{"text": "...", "source": "your-document.pdf", "page": 1}], "cached": false}
```

### Step 6: (Optional) Run with Docker

See [`docker/README.md`](../../docker/README.md) for the full docker-compose
stack including Redis, async ingestion, and the frontend.

---

## 5. Template structure for future connector guides

This page follows a reusable template. A future "pgvector + OpenAI" guide (or
any other pairing) should use the same sections:

1. **Connector selection** — the env vars that activate this pairing
2. **Connector-specific configuration** — a table of env vars scoped to each
   connector, with defaults and descriptions
3. **Known limitations** — honest documentation of tradeoffs specific to each
   connector, framed as reasons to prefer other connectors for certain use
   cases (not as defects)
4. **Worked example** — a complete, copy-pasteable walkthrough from `pip install`
   to a working query
5. **Template structure note** — this section, so the pattern propagates

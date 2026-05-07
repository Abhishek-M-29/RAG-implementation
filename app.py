import streamlit as st
import os
import tempfile

from src.ingestion import load_and_extract_text_from_pdfs
from src.chunking import chunk_text
from src.embedding import build_and_save_faiss_index, load_faiss_index
from src.generation import get_rag_chain
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

# --- Configuration ---
INDEX_PATH = "index_store/faiss_index"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
TOP_K_RESULTS = 5
LLM_MODEL_NAME = "gemini-3-flash-preview"
MAX_FILE_SIZE = 50 * 1024 * 1024
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CONTEXT_WINDOW = 128000  # Gemini Flash context window

st.set_page_config(
    page_title="RAG Implementation",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, p, span, div, input, textarea, button, label, h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
}
/* Preserve Streamlit icon font */
[data-testid="stIconMaterial"],
.material-symbols-rounded,
[class*="Icon"] span,
[data-testid="stExpanderToggleIcon"] span {
    font-family: 'Material Symbols Rounded' !important;
}

:root {
    --accent: #6C63FF;
    --accent-glow: rgba(108, 99, 255, 0.25);
    --surface: #1A1D29;
    --surface-light: #232738;
    --text-primary: #E8E8ED;
    --text-muted: #8B8FA3;
    --success: #2ECC71;
    --warning: #F39C12;
    --danger: #E74C3C;
}

/* Sidebar — flat bg, wider, no scroll */
section[data-testid="stSidebar"] {
    background: #12141E;
    border-right: 1px solid rgba(108, 99, 255, 0.15);
    min-width: 340px !important;
    max-width: 340px !important;
    width: 340px !important;
}
section[data-testid="stSidebar"] > div:first-child {
    overflow: hidden !important;
    padding-top: 1rem;
    padding-bottom: 0.5rem;
}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-muted) !important;
    margin-bottom: 0.2rem !important;
    margin-top: 0 !important;
    font-weight: 600 !important;
}
/* Remove default spacing from sidebar markdown dividers */
section[data-testid="stSidebar"] hr {
    margin-top: 0.4rem !important;
    margin-bottom: 0.4rem !important;
}

/* Sidebar card — flat, no blur, no glass */
.sb-card {
    background: var(--surface-light);
    border: 1px solid rgba(108, 99, 255, 0.1);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 6px;
}

/* Metric mini card — compact */
.metric-row { display: flex; gap: 8px; margin-bottom: 6px; }
.metric-card {
    flex: 1;
    background: var(--surface-light);
    border: 1px solid rgba(108, 99, 255, 0.1);
    border-radius: 8px;
    padding: 8px 6px;
    text-align: center;
}
.metric-card .val {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--accent);
    line-height: 1.2;
}
.metric-card .lbl {
    font-size: 0.58rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 1px;
}

/* Pipeline bar */
.pipeline-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    padding: 10px 20px;
    background: var(--surface);
    border: 1px solid rgba(108, 99, 255, 0.1);
    border-radius: 14px;
    margin-bottom: 18px;
}
.pipe-stage {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.3px;
    color: var(--text-muted);
    transition: all 0.3s ease;
}
.pipe-stage.active {
    color: var(--accent);
    background: var(--accent-glow);
}
.pipe-stage.done {
    color: var(--success);
}
.pipe-arrow {
    color: rgba(108,99,255,0.25);
    font-size: 0.75rem;
    margin: 0 2px;
}

/* Status dot */
.status-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
}
.status-dot.green { background: var(--success); box-shadow: 0 0 6px rgba(46,204,113,0.5); }
.status-dot.red { background: var(--danger); box-shadow: 0 0 6px rgba(231,76,60,0.4); }

/* Chunk card */
.chunk-card {
    background: var(--surface-light);
    border: 1px solid rgba(108, 99, 255, 0.08);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    font-size: 0.8rem;
    line-height: 1.5;
}
.chunk-card .chunk-meta {
    font-size: 0.68rem;
    color: var(--text-muted);
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
}
.chunk-card .chunk-text {
    color: var(--text-primary);
    opacity: 0.85;
}

/* Token / context bar (sidebar) */
.bar-container { margin-top: 4px; margin-bottom: 2px; }
.bar-bg {
    background: var(--surface);
    border-radius: 5px;
    height: 7px;
    overflow: hidden;
}
.bar-fill {
    height: 100%;
    border-radius: 5px;
    background: var(--accent);
    transition: width 0.6s ease;
}
.bar-labels {
    font-size: 0.6rem;
    color: var(--text-muted);
    display: flex;
    justify-content: space-between;
    margin-top: 2px;
}

/* Chat area prominence */
[data-testid="stChatMessage"] {
    border-radius: 12px !important;
    margin-bottom: 6px;
}

/* VDB info row — compact */
.vdb-row {
    display: flex;
    justify-content: space-between;
    padding: 2px 0;
    font-size: 0.73rem;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.vdb-row .vdb-k { color: var(--text-muted); }
.vdb-row .vdb-v { color: var(--text-primary); font-weight: 500; }

/* Hide default streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stHeader"] { visibility: hidden; }

/* Main title */
.main-title {
    text-align: center;
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 2px;
}
.main-subtitle {
    text-align: center;
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-bottom: 16px;
}

/* Fix file uploader alignment inside expander */
[data-testid="stExpander"] [data-testid="stFileUploader"] {
    width: 100% !important;
}
[data-testid="stExpander"] [data-testid="stFileUploader"] > section {
    width: 100% !important;
}
[data-testid="stExpander"] [data-testid="stFileUploader"] label {
    width: 100% !important;
}
[data-testid="stExpander"] .stFileUploader {
    width: 100% !important;
}
</style>
""", unsafe_allow_html=True)


# ── Session State Initialization ──
defaults = {
    "messages": [],
    "chat_history": ChatMessageHistory(),
    "total_tokens_in": 0,
    "total_tokens_out": 0,
    "query_count": 0,
    "token_history": [],
    "pipeline_stage": "idle",
    "last_context_pct": 0.0,
    "index_vectors": 0,
    "index_dims": 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def get_session_history(session_id: str) -> ChatMessageHistory:
    return st.session_state.chat_history


def get_vectorstore_info():
    """Get vector count and dimensions from FAISS index if available."""
    vs = load_faiss_index(INDEX_PATH)
    if vs is not None:
        try:
            n = vs.index.ntotal
            d = vs.index.d
            st.session_state.index_vectors = n
            st.session_state.index_dims = d
            return vs, n, d
        except Exception:
            return vs, 0, 0
    return None, 0, 0


# ── SIDEBAR (single-page, no scrolling) ──
with st.sidebar:
    # Branding — compact
    st.markdown("""
    <div style="text-align:center; padding: 8px 0 4px 0;">
        <div style="font-size:1rem; font-weight:700; color:#E8E8ED;">RAG Implementation</div>
        <div style="font-size:0.6rem; color:#8B8FA3; letter-spacing:2px; text-transform:uppercase;">LangChain Workflow</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Session Metrics — 4 compact cards in 2 rows
    st.markdown("### Session Metrics")
    qc = st.session_state.query_count
    ti = st.session_state.total_tokens_in
    to_ = st.session_state.total_tokens_out
    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-card">
            <div class="val">{qc}</div>
            <div class="lbl">Queries</div>
        </div>
        <div class="metric-card">
            <div class="val">{ti + to_:,}</div>
            <div class="lbl">Tokens</div>
        </div>
        <div class="metric-card">
            <div class="val">{ti:,}</div>
            <div class="lbl">Input</div>
        </div>
        <div class="metric-card">
            <div class="val">{to_:,}</div>
            <div class="lbl">Output</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Context window bar — in sidebar
    ctx_pct = st.session_state.last_context_pct
    st.markdown(f"""
    <div class="bar-container">
        <div style="font-size:0.65rem; color:var(--text-muted); margin-bottom:3px;">
            Context Window  —  <strong style="color:var(--accent);">{ctx_pct:.1f}%</strong> used
        </div>
        <div class="bar-bg">
            <div class="bar-fill" style="width:{min(ctx_pct, 100):.1f}%"></div>
        </div>
        <div class="bar-labels">
            <span>~{ti:,} in</span>
            <span>~{to_:,} out</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Vector DB Status — compact
    st.markdown("### Vector Database")
    index_exists = os.path.exists(INDEX_PATH)
    dot_class = "green" if index_exists else "red"
    status_text = "Active" if index_exists else "No Index"
    nv = st.session_state.index_vectors
    nd = st.session_state.index_dims

    st.markdown(f"""
    <div class="sb-card">
        <div class="vdb-row">
            <span class="vdb-k">Status</span>
            <span class="vdb-v"><span class="status-dot {dot_class}"></span>{status_text}</span>
        </div>
        <div class="vdb-row">
            <span class="vdb-k">Vectors</span>
            <span class="vdb-v">{nv:,}</span>
        </div>
        <div class="vdb-row">
            <span class="vdb-k">Dimensions</span>
            <span class="vdb-v">{nd}</span>
        </div>
        <div class="vdb-row">
            <span class="vdb-k">Engine</span>
            <span class="vdb-v">FAISS</span>
        </div>
        <div class="vdb-row" style="border:none;">
            <span class="vdb-k">Embeddings</span>
            <span class="vdb-v">{EMBEDDING_MODEL}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Pipeline Config — compact
    st.markdown("### Pipeline Config")
    st.markdown(f"""
    <div class="sb-card">
        <div class="vdb-row">
            <span class="vdb-k">Chunk Size</span>
            <span class="vdb-v">{CHUNK_SIZE}</span>
        </div>
        <div class="vdb-row">
            <span class="vdb-k">Overlap</span>
            <span class="vdb-v">{CHUNK_OVERLAP}</span>
        </div>
        <div class="vdb-row">
            <span class="vdb-k">Top-K</span>
            <span class="vdb-v">{TOP_K_RESULTS}</span>
        </div>
        <div class="vdb-row" style="border:none;">
            <span class="vdb-k">LLM</span>
            <span class="vdb-v">{LLM_MODEL_NAME}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── MAIN AREA ──

# Title
st.markdown('<div class="main-title">RAG Implementation for docs with LangChain Workflow</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">Upload your PDF document to start querying intelligently using a LangChain-powered RAG pipeline.</div>', unsafe_allow_html=True)

# Pipeline Status Bar
stage = st.session_state.pipeline_stage
stages_def = [
    ("Ingest", "ingesting"),
    ("Chunk", "chunking"),
    ("Embed", "embedding"),
    ("Retrieve", "retrieving"),
    ("Generate", "generating"),
]
stage_order = ["ingesting", "chunking", "embedding", "retrieving", "generating"]

pipe_html = '<div class="pipeline-bar">'
for i, (label, skey) in enumerate(stages_def):
    cls = ""
    if stage == skey:
        cls = "active"
    elif stage in stage_order:
        si = stage_order.index(stage)
        ci = stage_order.index(skey)
        if ci < si:
            cls = "done"
    pipe_html += f'<div class="pipe-stage {cls}">{label}</div>'
    if i < len(stages_def) - 1:
        pipe_html += '<span class="pipe-arrow">&rsaquo;</span>'
pipe_html += '</div>'
st.markdown(pipe_html, unsafe_allow_html=True)


# Document Upload — compact expander
with st.expander("Document Management", expanded=not os.path.exists(INDEX_PATH)):
    uploaded_files = st.file_uploader(
        "Upload PDF documents (Max 50MB each)",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    if st.button("Process & Index Documents", use_container_width=True) and uploaded_files:
        with st.status("Processing Documents into Vector Store...", expanded=True) as status:
            try:
                st.session_state.pipeline_stage = "ingesting"
                st.write("Initializing file ingestion...")
                temp_dir = tempfile.mkdtemp()
                temp_file_paths = []

                for uploaded_file in uploaded_files:
                    if uploaded_file.size > MAX_FILE_SIZE:
                        st.error(f"File '{uploaded_file.name}' exceeds 50MB limit. Skipping.")
                        continue
                    temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(temp_file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    temp_file_paths.append(temp_file_path)

                if not temp_file_paths:
                    status.update(label="No valid files to process", state="error")
                    st.session_state.pipeline_stage = "idle"
                else:
                    st.session_state.pipeline_stage = "ingesting"
                    st.write(f"Extracting content from {len(temp_file_paths)} PDF(s)...")
                    extracted_documents = load_and_extract_text_from_pdfs(temp_file_paths)

                    if not extracted_documents:
                        status.update(label="No text extracted", state="error")
                        st.session_state.pipeline_stage = "idle"
                    else:
                        st.session_state.pipeline_stage = "chunking"
                        st.write(f"Chunking {len(extracted_documents)} documents...")
                        chunked_documents = chunk_text(extracted_documents, CHUNK_SIZE, CHUNK_OVERLAP)

                        st.session_state.pipeline_stage = "embedding"
                        st.write("Building FAISS Vector Index...")
                        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
                        vectorstore = build_and_save_faiss_index(chunked_documents, INDEX_PATH)

                        if vectorstore:
                            try:
                                st.session_state.index_vectors = vectorstore.index.ntotal
                                st.session_state.index_dims = vectorstore.index.d
                            except Exception:
                                pass
                            st.session_state.pipeline_stage = "idle"
                            status.update(
                                label=f"Indexed {len(temp_file_paths)} doc(s) -- {len(chunked_documents)} chunks created.",
                                state="complete"
                            )
                        else:
                            status.update(label="Failed to build index.", state="error")
                            st.session_state.pipeline_stage = "idle"

            except Exception as e:
                status.update(label=f"Error: {e}", state="error")
                st.session_state.pipeline_stage = "idle"

st.markdown("")

# ── Chat Interface (CENTER STAGE) ──

# Display chat messages from history
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Show ONLY chunk details for assistant messages
        if message["role"] == "assistant" and "chunks" in message and message["chunks"]:
            chunks = message["chunks"]
            with st.expander(f"Retrieved Chunks  ({len(chunks)})", expanded=False):
                for j, chunk in enumerate(chunks):
                    src = chunk.get("source", "Unknown")
                    page = chunk.get("page", "?")
                    text_preview = chunk.get("text", "")[:250]
                    char_len = chunk.get("length", 0)

                    st.markdown(f"""
                    <div class="chunk-card">
                        <div class="chunk-meta">
                            <span>{os.path.basename(str(src))}  |  Page {page}</span>
                            <span>{char_len:,} chars</span>
                        </div>
                        <div class="chunk-text">{text_preview}{'...' if len(chunk.get("text","")) > 250 else ''}</div>
                    </div>
                    """, unsafe_allow_html=True)


# Accept user input
if prompt := st.chat_input("Ask a question about your documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()

        with st.spinner("Searching index and generating response..."):
            # Load index and get info
            vs, nv, nd = get_vectorstore_info()

            if vs is None:
                response = "Please upload and index a document first using the Document Management panel above."
                chunks_data = []
            else:
                try:
                    st.session_state.pipeline_stage = "retrieving"

                    rag_chain = get_rag_chain(
                        vs,
                        top_k=TOP_K_RESULTS,
                        llm_model_name=LLM_MODEL_NAME,
                        get_session_history=get_session_history
                    )

                    st.session_state.pipeline_stage = "generating"

                    result = rag_chain.invoke(
                        {"input": prompt},
                        config={"configurable": {"session_id": "default_streamlit_session"}}
                    )
                    response = result["answer"]

                    # Extract chunk details from retrieved context
                    context_docs = result.get("context", [])
                    chunks_data = []
                    total_context_text = ""
                    for doc in context_docs:
                        txt = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                        meta = doc.metadata if hasattr(doc, 'metadata') else {}
                        total_context_text += txt
                        chunks_data.append({
                            "source": meta.get("source", "Unknown"),
                            "page": meta.get("page", "?"),
                            "text": txt,
                            "length": len(txt),
                        })

                    # Token estimates — update sidebar-level stats
                    tokens_in = estimate_tokens(total_context_text + prompt)
                    tokens_out = estimate_tokens(response)
                    ctx_pct = (tokens_in / CONTEXT_WINDOW) * 100

                    st.session_state.query_count += 1
                    st.session_state.total_tokens_in += tokens_in
                    st.session_state.total_tokens_out += tokens_out
                    st.session_state.last_context_pct = ctx_pct

                    st.session_state.pipeline_stage = "idle"

                except Exception as e:
                    response = f"Error during generation: {e}"
                    chunks_data = []
                    st.session_state.pipeline_stage = "idle"

        message_placeholder.markdown(response)

        # Show ONLY chunk details inline
        if chunks_data:
            with st.expander(f"Retrieved Chunks  ({len(chunks_data)})", expanded=False):
                for j, chunk in enumerate(chunks_data):
                    src = chunk.get("source", "Unknown")
                    page = chunk.get("page", "?")
                    text_preview = chunk.get("text", "")[:250]
                    char_len = chunk.get("length", 0)
                    st.markdown(f"""
                    <div class="chunk-card">
                        <div class="chunk-meta">
                            <span>{os.path.basename(str(src))}  |  Page {page}</span>
                            <span>{char_len:,} chars</span>
                        </div>
                        <div class="chunk-text">{text_preview}{'...' if len(chunk.get("text","")) > 250 else ''}</div>
                    </div>
                    """, unsafe_allow_html=True)

        # Save message with metadata
        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "chunks": chunks_data,
        })
        
        st.rerun()

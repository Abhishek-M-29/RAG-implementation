import streamlit as st
import os
import tempfile

from src.ingestion import load_and_extract_text_from_pdfs
from src.chunking import chunk_text
from src.embedding import build_and_save_faiss_index, load_faiss_index
from src.retrieval import search_faiss_index
from src.generation import generate_llm_response
from langchain_core.documents import Document

# --- Configuration ---
INDEX_PATH = "index_store/faiss_index"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
TOP_K_RESULTS = 5
LLM_MODEL_NAME = "gemini-3-flash-preview"

st.set_page_config(page_title="Minimal RAG App", layout="centered")
st.title("Minimal RAG System")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for file upload
with st.sidebar:
    st.header("Document Upload")
    uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])
    
    if st.button("Index Document") and uploaded_file is not None:
        with st.status("Processing Document...", expanded=True) as status:
            try:
                # 1. Save uploaded file to temp dir
                st.write("Saving file...")
                temp_dir = tempfile.mkdtemp()
                temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 2. Extract Text
                st.write("Extracting text...")
                extracted_data = load_and_extract_text_from_pdfs([temp_file_path])
                
                if not extracted_data:
                    status.update(label="No text extracted", state="error")
                else:
                    # 3. Chunking
                    st.write("Chunking text...")
                    documents_to_chunk = [
                        Document(page_content=item['text'], metadata={'source': item['source'], 'page': item.get('page', 'N/A')})
                        for item in extracted_data
                    ]
                    chunked_documents = chunk_text(documents_to_chunk, CHUNK_SIZE, CHUNK_OVERLAP)
                    
                    # 4. Building Index
                    st.write("Building FAISS index...")
                    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
                    vectorstore = build_and_save_faiss_index(chunked_documents, INDEX_PATH)
                    
                    if vectorstore:
                        status.update(label="Indexing complete!", state="complete")
                    else:
                        status.update(label="Failed to build index", state="error")
                        
            except Exception as e:
                status.update(label=f"Error: {e}", state="error")

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Ask a question about the document..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        with st.spinner("Searching index and generating response..."):
            vectorstore = load_faiss_index(INDEX_PATH)
            if vectorstore is None:
                response = "Please upload and index a document first."
            else:
                relevant_docs = search_faiss_index(prompt, vectorstore, top_k=TOP_K_RESULTS)
                if not relevant_docs:
                    response = "No relevant information found in the document."
                else:
                    response = generate_llm_response(prompt, relevant_docs, LLM_MODEL_NAME)
        
        message_placeholder.markdown(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})

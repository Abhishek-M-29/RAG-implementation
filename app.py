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
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file

st.set_page_config(page_title="IntelliRAG Agent", layout="centered")

st.title("RAG Implementation for docs with LangChain Workflow")
st.markdown("Upload your PDF document to start querying intelligently using a LangChain-powered RAG pipeline.")

# Initialize chat history and mapping
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = ChatMessageHistory()

def get_session_history(session_id: str) -> ChatMessageHistory:
    return st.session_state.chat_history

# Expandable section for document upload replacing the sidebar
with st.expander("📄 Document Management", expanded=not os.path.exists(INDEX_PATH)):
    uploaded_files = st.file_uploader(
        "Upload PDF documents to the internal knowledge base (Max 50MB per file)", 
        type=["pdf"], 
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    if st.button("Process & Index Documents", use_container_width=True) and uploaded_files:
        with st.status("Processing Documents into Vector Store...", expanded=True) as status:
            try:
                st.write("Initializing file ingestion...")
                temp_dir = tempfile.mkdtemp()
                temp_file_paths = []
                
                # Validate and save all uploaded files
                for uploaded_file in uploaded_files:
                    file_size = uploaded_file.size
                    if file_size > MAX_FILE_SIZE:
                        st.error(f"File '{uploaded_file.name}' exceeds 50MB limit ({file_size / (1024*1024):.2f}MB). Skipping.")
                        continue
                    
                    temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(temp_file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    temp_file_paths.append(temp_file_path)
                
                if not temp_file_paths:
                    status.update(label="No valid files to process", state="error")
                else:
                    # 2. Extract Text via PyPDFLoader
                    st.write(f"Extracting content from {len(temp_file_paths)} PDF(s) with LangChain PyPDFLoader...")
                    extracted_documents = load_and_extract_text_from_pdfs(temp_file_paths)
                    
                    if not extracted_documents:
                        status.update(label="No text extracted", state="error")
                    else:
                        # 3. Chunking
                        st.write(f"Chunking {len(extracted_documents)} documents into semantic sequences...")
                        chunked_documents = chunk_text(extracted_documents, CHUNK_SIZE, CHUNK_OVERLAP)
                        
                        # 4. Building Index
                        st.write("Building and persisting FAISS Vector Index...")
                        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
                        vectorstore = build_and_save_faiss_index(chunked_documents, INDEX_PATH)
                        
                        if vectorstore:
                            status.update(label=f"Successfully indexed {len(temp_file_paths)} document(s) and ready for querying!", state="complete")
                        else:
                            status.update(label="Failed to build index.", state="error")
                        
            except Exception as e:
                status.update(label=f"Processing Request Error: {e}", state="error")

st.divider()

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Ask a question about the document..."):
    # Add user message to chat history UI sync
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
                try:
                    # Use the entire pipeline through standard invocation structure
                    rag_chain = get_rag_chain(
                        vectorstore, 
                        top_k=TOP_K_RESULTS, 
                        llm_model_name=LLM_MODEL_NAME, 
                        get_session_history=get_session_history
                    )
                    
                    # Execute LCEL RunnableWithMessageHistory wrapper
                    result = rag_chain.invoke(
                        {"input": prompt},
                        config={"configurable": {"session_id": "default_streamlit_session"}}
                    )
                    response = result["answer"]
                except Exception as e:
                    response = f"Error during generation: {e}"
        
        message_placeholder.markdown(response)
        
        # Add assistant response to chat history UI sync 
        # (Internal ChatMessageHistory is updated automatically by runnable)
        st.session_state.messages.append({"role": "assistant", "content": response})

# src/generation.py

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.runnables.history import RunnableWithMessageHistory

load_dotenv()

_llm = None
_current_model_name = None

def _get_llm(model_name=None):
    global _llm, _current_model_name

    if model_name is None:
        model_name = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite")
    
    if _llm is not None and _current_model_name == model_name:
        return _llm
        
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: The API key is missing. Please set GOOGLE_API_KEY in .env")
        return None
        
    try:
        _llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
        _current_model_name = model_name
        return _llm
    except Exception as e:
        print(f"Error configuring Google Generative AI: {e}")
        return None

def get_rag_chain(vectorstore, top_k=5, llm_model_name=None, get_session_history=None):
    """
    Constructs a unified LangChain RAG pipeline using LCEL and memory.
    
    Args:
        vectorstore (FAISS): The loaded LangChain FAISS vectorstore.
        top_k (int): Number of documents to retrieve.
        llm_model_name (str): Name of the Gemini model to use. Defaults to MODEL_NAME from .env.
        get_session_history (callable): A factory function that returns the chat history for a given session_id.
    
    Returns:
        RunnableWithMessageHistory: The complete executable RAG chain with built-in memory and retrieval.
    """
    llm = _get_llm(llm_model_name)
    if not llm:
        raise ValueError("Could not initialize LLM. Check API key.")

    # 1. Convert vectorstore to retriever
    retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})

    # 2. Define the ChatPromptTemplate using generic system/human messages + chat history
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant answering based ONLY on the provided context.\n\nContext:\n{context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])

    # 3. Create the compound chains
    document_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)

    # 4. Wrap with message history abstraction
    if get_session_history is None:
        raise ValueError("A get_session_history function must be provided for RunnableWithMessageHistory.")

    conversational_rag_chain = RunnableWithMessageHistory(
        retrieval_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer"
    )

    return conversational_rag_chain
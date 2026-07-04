import os
import threading
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.runnables.history import RunnableWithMessageHistory
from src.log_utils import get_logger

load_dotenv()

logger = get_logger(__name__)

_llm = None
_current_model_name = None
_llm_lock = threading.Lock()


def _get_llm(model_name=None):
    global _llm, _current_model_name

    if model_name is None:
        model_name = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite")

    if _llm is not None and _current_model_name == model_name:
        return _llm

    with _llm_lock:
        if _llm is not None and _current_model_name == model_name:
            return _llm
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("API key missing. Set GOOGLE_API_KEY or GEMINI_API_KEY in .env")
            return None

        try:
            _llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
            _current_model_name = model_name
            logger.info("Initialized LLM: %s", model_name)
            return _llm
        except Exception as e:
            logger.error("Error configuring Google Generative AI: %s", e)
            return None


def get_rag_chain(vectorstore, top_k=5, llm_model_name=None, get_session_history=None):
    llm = _get_llm(llm_model_name)
    if not llm:
        raise ValueError("Could not initialize LLM. Check API key.")

    retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant answering based ONLY on the provided context.\n\nContext:\n{context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])

    document_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)

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

import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.runnables.history import RunnableWithMessageHistory

logger = logging.getLogger(__name__)


def build_rag_chain(
    llm: BaseChatModel,
    retriever,
    *,
    get_session_history=None,
    system_prompt: str | None = None,
):
    if system_prompt is None:
        system_prompt = (
            "You are a helpful assistant answering based ONLY on the provided context.\n\n"
            "Context:\n{context}"
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
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
        output_messages_key="answer",
    )

    logger.info(
        "Built RAG chain",
        extra={"model": getattr(llm, "model", "unknown")},
    )

    return conversational_rag_chain

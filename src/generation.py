# src/generation.py

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

load_dotenv()

_llm = None
_current_model_name = None

def _get_llm(model_name="gemini-3-flash-preview"):
    global _llm, _current_model_name
    
    if _llm is not None and _current_model_name == model_name:
        return _llm
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: The API key is missing. Please set GEMINI_API_KEY in .env")
        return None
        
    try:
        _llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.7, google_api_key=api_key)
        _current_model_name = model_name
        return _llm
    except Exception as e:
        print(f"Error configuring Google Generative AI: {e}")
        return None

def generate_llm_response(query, relevant_docs, llm_model_name="gemini-3-flash-preview", desired_marks=None):
    """
    Generates a response from the Gemini API using LangChain.
    Args:
        query (str): The user's original query.
        relevant_docs (list[Document]): List of relevant LangChain Document objects.
        llm_model_name (str): Name of the Gemini model to use.
        desired_marks (int, optional): Guides the LLM to answer with detail appropriate for the marks.
    Returns:
        str: The LLM-generated answer, or an error message.
    """
    llm = _get_llm(llm_model_name)
    if not llm:
        return "Error: Could not initialize LLM. Check your API key and setup."

    if not relevant_docs:
        return "I could not find any relevant information in the provided documents to answer your question."

    context = "\n\n---\n".join([doc.page_content for doc in relevant_docs])

    print("\n--- Context Sent to LLM ---")
    for i, doc in enumerate(relevant_docs):
        print(f"Chunk {i+1}:\n{doc.page_content}\n---")
    print("--- End of Context Sent to LLM ---\n")

    detail_instruction = " Provide a detailed and thorough answer."
    if desired_marks is not None:
        if desired_marks >= 10:
            detail_instruction = f" Provide a comprehensive, in-depth answer suitable for a {desired_marks}-mark question. Use bullet points or numbered lists where appropriate."
        elif desired_marks >= 5:
            detail_instruction = f" Provide a detailed answer suitable for a {desired_marks}-mark question."
        else:
            detail_instruction = f" Provide a concise answer suitable for a {desired_marks}-mark question."

    template = """You are a helpful assistant. Based *only* on the following context from study materials, please answer the question.{detail_instruction}
Please format your answer in well-structured Markdown, using headings, bullet points, and bold text for clarity where appropriate.
If the answer is not found in the context, say 'I could not find the answer in the provided materials.'
Do not use any information outside of the provided context.

Context:
{context}

Question: {query}

Answer:"""

    prompt = PromptTemplate(
        input_variables=["context", "query", "detail_instruction"],
        template=template
    )

    print("\n--- Prompt for Gemini API ---")
    print(prompt.format(context=context, query=query, detail_instruction=detail_instruction))
    print("--- End of Prompt ---\n")

    try:
        chain = prompt | llm
        response = chain.invoke({
            "context": context, 
            "query": query, 
            "detail_instruction": detail_instruction
        })
        return response.content
    except Exception as e:
        print(f"Error generating response from Gemini: {e}")
        return f"Error generating response from Gemini: {e}"
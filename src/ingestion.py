# src/ingestion.py

import os
from langchain_community.document_loaders import PyPDFLoader

def get_pdf_paths_from_directory(directory_path):
    """Gets all PDF file paths from a given directory."""
    pdf_files = []
    try:
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(directory_path, filename))
    except FileNotFoundError:
        print(f"Error: Directory not found at {directory_path}")
        # Create the directory if it doesn't exist, or handle as preferred
        os.makedirs(directory_path, exist_ok=True)
        print(f"Created directory: {directory_path}. Please add PDF files there.")
    return pdf_files

def load_and_extract_text_from_pdfs(pdf_file_paths):
    """
    Loads PDF files and extracts them into LangChain Document objects.
    Args:
        pdf_file_paths (list): A list of paths to PDF files.
    Returns:
        list[Document]: A list of LangChain Document objects containing the text and metadata.
    """
    extracted_docs = []
    if not pdf_file_paths:
        print("No PDF file paths provided.")
        return extracted_docs

    for pdf_path in pdf_file_paths:
        try:
            # print(f"Processing PDF: {pdf_path}")
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            extracted_docs.extend(docs)
            # print(f"Successfully extracted {len(docs)} documents from {os.path.basename(pdf_path)}.")
        except Exception as e:
            pass # Suppressing standard CLI print outputs for the Streamlit UI flow
            # print(f"Error processing PDF {pdf_path}: {e}")
    return extracted_docs

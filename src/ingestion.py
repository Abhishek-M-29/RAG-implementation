import os
from langchain_community.document_loaders import PyPDFLoader
from src.log_utils import get_logger

logger = get_logger(__name__)


def get_pdf_paths_from_directory(directory_path):
    pdf_files = []
    try:
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(directory_path, filename))
    except FileNotFoundError:
        logger.error("Directory not found at %s", directory_path)
        os.makedirs(directory_path, exist_ok=True)
        logger.info("Created directory: %s. Please add PDF files there.", directory_path)
    return pdf_files


def load_and_extract_text_from_pdfs(pdf_file_paths):
    extracted_docs = []
    if not pdf_file_paths:
        logger.warning("No PDF file paths provided.")
        return extracted_docs

    for pdf_path in pdf_file_paths:
        try:
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            extracted_docs.extend(docs)
            logger.info("Extracted %d pages from %s", len(docs), os.path.basename(pdf_path))
        except Exception as e:
            logger.error("Failed to process PDF %s: %s", pdf_path, e)
    return extracted_docs

# src/ingestion.py

import os
from pypdf import PdfReader

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
    Loads PDF files and extracts text content from each page.
    Args:
        pdf_file_paths (list): A list of paths to PDF files.
    Returns:
        list: A list of dictionaries, where each dictionary contains:
              {'source': str, 'text': str, 'page': int}
    """
    extracted_data = []
    if not pdf_file_paths:
        print("No PDF file paths provided.")
        return extracted_data

    for pdf_path in pdf_file_paths:
        try:
            print(f"Processing PDF: {pdf_path}")
            reader = PdfReader(pdf_path)
            num_pages = len(reader.pages)
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                text = page.extract_text()
                if text: # Only add if text was extracted
                    extracted_data.append({
                        "source": os.path.basename(pdf_path),
                        "text": text,
                        "page": page_num + 1
                    })
            print(f"Successfully extracted text from {num_pages} pages in {os.path.basename(pdf_path)}.")
        except Exception as e:
            print(f"Error processing PDF {pdf_path}: {e}")
    return extracted_data

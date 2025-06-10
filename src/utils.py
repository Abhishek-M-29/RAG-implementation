# src/utils.py
import json
import os
# from langchain_core.documents import Document # Not strictly needed here if we only expect dicts or convert Documents

def save_text_chunks(chunked_data, file_path):
    """
    Saves the list of text chunks to a JSON file.
    If chunked_data contains Langchain Document objects, they are converted to dicts.
    Args:
        chunked_data (list): The chunks to save. Can be list of dicts or list of Document objects.
        file_path (str): The path to the JSON file.
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        data_to_save = []
        # Check if the first item has page_content and metadata attributes, common for Document objects
        if chunked_data and hasattr(chunked_data[0], 'page_content') and hasattr(chunked_data[0], 'metadata'):
            # Convert list of Document objects to list of dicts
            data_to_save = [
                {"page_content": doc.page_content, "metadata": doc.metadata}
                for doc in chunked_data
            ]
            print(f"Converted {len(chunked_data)} Document objects to dicts for saving in utils.save_text_chunks.")
        else:
            # Assume it's already a list of dicts
            data_to_save = chunked_data
            # print(f"Data in utils.save_text_chunks is already a list of dicts or not recognized as Documents.")

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4)
        print(f"Text chunks successfully saved to {file_path}")
    except Exception as e:
        print(f"Error saving text chunks to {file_path}: {e}")

def load_text_chunks(file_path):
    """
    Loads text chunks (which are dicts with metadata) from a JSON file.
    Args:
        file_path (str): The path to the JSON file.
    Returns:
        list of dict: The loaded text chunks, or None if an error occurs.
    """
    if not os.path.exists(file_path):
        print(f"Text chunks file not found at {file_path}")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Text chunks successfully loaded from {file_path}")
        return data
    except Exception as e:
        print(f"Error loading text chunks from {file_path}: {e}")
        return None

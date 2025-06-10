# src/utils.py
import json
import os

def save_text_chunks(text_chunks_with_metadata, file_path):
    """
    Saves the list of text chunks (which are dicts with metadata) to a JSON file.
    Args:
        text_chunks_with_metadata (list of dict): The chunks to save.
        file_path (str): The path to the JSON file.
    """
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(text_chunks_with_metadata, f, indent=4)
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

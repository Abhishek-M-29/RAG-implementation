# src/chunking.py

# Using a simple character-based splitter for now.
# Consider LangChain's RecursiveCharacterTextSplitter for more advanced strategies.

def chunk_text(texts_with_metadata, chunk_size, chunk_overlap):
    """
    Splits a list of texts (with their source metadata) into smaller chunks.

    Args:
        texts_with_metadata (list of dict):
            List of dictionaries, where each dict has at least a 'text' key and a 'source' key.
            Example: [{'source': 'doc1.pdf', 'text': '...', 'page': 1}, ...]
        chunk_size (int): The maximum size of each chunk (in characters).
        chunk_overlap (int): The number of characters to overlap between chunks.

    Returns:
        list: A list of dictionaries, where each dictionary is a chunk with its original metadata.
              Example: [{'source': 'doc1.pdf', 'text': 'chunk1_text', 'page': 1, 'chunk_id': 0}, ...]
    """
    all_chunks_with_metadata = []
    chunk_id_counter = 0

    for item in texts_with_metadata:
        original_text = item['text']
        metadata = {k: v for k, v in item.items() if k != 'text'} # Keep all other metadata

        if not original_text:
            continue

        start_index = 0
        while start_index < len(original_text):
            end_index = start_index + chunk_size
            chunk_text_content = original_text[start_index:end_index]

            chunk_metadata = metadata.copy() # Copy metadata for this chunk
            chunk_metadata['text'] = chunk_text_content
            chunk_metadata['chunk_id'] = chunk_id_counter # Unique ID for the chunk
            all_chunks_with_metadata.append(chunk_metadata)

            chunk_id_counter += 1
            start_index += chunk_size - chunk_overlap
            if start_index >= len(original_text):
                break

    return all_chunks_with_metadata


# More sophisticated chunking (example using LangChain, if you install it)
"""
from langchain.text_splitter import RecursiveCharacterTextSplitter

def chunk_text_langchain(texts_with_metadata, chunk_size, chunk_overlap):
    all_chunks_with_metadata = []
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )

    for item in texts_with_metadata:
        original_text = item['text']
        metadata = {k: v for k, v in item.items() if k != 'text'}

        if not original_text:
            continue
        
        # Langchain splitters work on pure text and then you re-associate metadata.
        # This is a simplified way; more robust solutions might involve splitting and then
        # carefully mapping back to original document parts if very fine-grained source tracking is needed.
        split_texts = text_splitter.split_text(original_text)
        
        for i, chunk_text_content in enumerate(split_texts):
            chunk_meta = metadata.copy()
            chunk_meta['text'] = chunk_text_content
            # You might want a more sophisticated chunk_id or way to link back if needed
            chunk_meta['chunk_part'] = i 
            all_chunks_with_metadata.append(chunk_meta)
            
    return all_chunks_with_metadata
"""

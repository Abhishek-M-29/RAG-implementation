# src/generation.py

import os
import google.generativeai as genai

# The API key is hardcoded in this file.
# For production, consider using environment variables or a secrets manager.
# API_KEY = "YOUR_API_KEY_HERE" # Replace with your actual key if different

_gemini_model = None
_current_model_name = None # Keep track of the currently configured model

def _configure_gemini(model_name_to_load):
    global _gemini_model, _current_model_name
    # If model is already loaded and it's the same one requested, do nothing
    if _gemini_model is not None and _current_model_name == model_name_to_load:
        return True
    
    # If a different model is requested or no model is loaded, (re)configure
    try:
        # API key is hardcoded here.
        api_key = "AIzaSyBXzi17iCVtVcqAz4QaI6lITij1udpx_GA" 

        if not api_key:
            print("Error: The hardcoded API key is empty.")
            print("Please provide a valid Google API Key in src/generation.py.")
            return False
        
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel(model_name_to_load)
        _current_model_name = model_name_to_load
        print(f"Gemini API configured with hardcoded key and model loaded successfully ({model_name_to_load}).")
        return True
    except Exception as e:
        print(f"Error configuring Gemini API or loading model '{model_name_to_load}' with hardcoded key: {e}")
        _gemini_model = None
        _current_model_name = None
        # If model loading fails, let's list available models
        try:
            print("\\nAttempting to list available models...") # Corrected: single backslash for newline
            models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if models:
                print("Available models supporting 'generateContent':")
                for m in models:
                    print(f"- {m.name}")
            else:
                print("No models found supporting 'generateContent'.")
        except Exception as list_e:
            print(f"Could not list models: {list_e}")
        return False

def generate_llm_response(query, relevant_chunks, llm_model_name="gemini-pro"):
    """
    Generates a response from the Gemini API using the query and relevant chunks.
    Args:
        query (str): The user's original query.
        relevant_chunks (list of str): List of relevant text chunks from the vector store.
        llm_model_name (str): Name of the Gemini model to use (e.g., "gemini-pro").
    Returns:
        str: The LLM-generated answer, or an error message.
    """
    if not _configure_gemini(llm_model_name): # Pass the model name to configure
        return f"Error: Gemini API not configured for model {llm_model_name}. Please check your API key and setup."

    if not relevant_chunks:
        # Optionally, you could still ask Gemini without context, but for RAG, context is key.
        # response = _gemini_model.generate_content(query)
        # return response.text
        return "I could not find any relevant information in the provided documents to answer your question."

    context = "\\n\\n---\\n".join(relevant_chunks)
    
    # --- Log the context being sent to the LLM ---
    print("\\n--- Context Sent to LLM ---")
    for i, chunk_text in enumerate(relevant_chunks):
        print(f"Chunk {i+1}:\\n{chunk_text}\\n---")
    print("--- End of Context Sent to LLM ---\\n")
    # --- End of logging ---

    # Constructing a prompt suitable for Gemini
    # Gemini chat models often work well with a more conversational or direct instruction format.
    prompt = f"""You are a helpful assistant. Based *only* on the following context from study materials, please answer the question.
If the answer is not found in the context, say 'I could not find the answer in the provided materials.'
Do not use any information outside of the provided context.

Context:
{context}

Question: {query}

Answer:"""

    print("\\n--- Prompt for Gemini API ---")
    print(prompt)
    print("--- End of Prompt ---\\n")

    try:
        # Configure generation parameters
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=2000, # Increased max output tokens
            temperature=0.7 # You can adjust temperature if needed
        )

        response = _gemini_model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        # Accessing the text part of the response
        # The structure of the response object might vary slightly based on the exact Gemini model and SDK version.
        # Check the Google AI SDK documentation for the most up-to-date way to access parts.
        if response.parts:
            # Assuming the first part contains the text response
            # Sometimes, safety ratings or other metadata might be present.
            # Filter for text parts if necessary, or directly access if simple.
            answer_text = ' '.join(part.text for part in response.parts if hasattr(part, 'text'))
            if not answer_text and response.candidates and response.candidates[0].content.parts:
                 answer_text = ' '.join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
            
            if not answer_text:
                # Check for finish_reason if the text is empty
                if response.candidates and response.candidates[0].finish_reason:
                    finish_reason = response.candidates[0].finish_reason
                    if finish_reason != "STOP": # Other reasons: MAX_TOKENS, SAFETY, RECITATION, OTHER
                        return f"Gemini could not generate a complete answer. Finish Reason: {finish_reason.name}"
                return "Gemini returned an empty response."
            return answer_text.strip()
        elif hasattr(response, 'text'): # Older or simpler response objects might have a direct .text attribute
            return response.text.strip()
        else:
            # Log the full response if the structure is unexpected
            print(f"Unexpected Gemini response structure: {response}")
            return "Could not parse the response from Gemini."

    except Exception as e:
        print(f"Error during Gemini API call with model {_current_model_name}: {e}")
        # You might want to inspect the type of exception for more specific error handling
        # e.g., if it's a google.api_core.exceptions.PermissionDenied, your API key might be wrong.
        return f"Error generating response from Gemini (model: {_current_model_name}): {e}"

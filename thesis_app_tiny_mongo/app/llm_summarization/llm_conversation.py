import ollama
import requests
import os
import config

# define constants from config file
MISTRAL_KEY = config.MISTRAL_KEY  
MISTRAL_MODEL = config.MISTRAL_MODEL
MISTRAL_BASE_URL = config.MISTRAL_API_URL

# Function to ask a local Ollama model or a remote LLM API
def ask_llm(
    prompt,
    ollama_model='tinydolphin',
    mistral_model=MISTRAL_MODEL,
    temperature=0.7,
    max_tokens=1000,
    provider='mistral',
    api_key=MISTRAL_KEY, 
    base_url=MISTRAL_BASE_URL,
    previous_messages=None
):
    """
    Unified function to call either a local Ollama model or a remote LLM API (e.g., Mistral).
    
    Args:
        prompt: The current user prompt string.
        ollama_model: Model name for Ollama.
        mistral_model: Model name for Mistral.
        temperature: Sampling temperature.
        max_tokens: Max tokens to generate.
        provider: 'ollama' for local, 'mistral' for remote.
        api_key: Required for remote providers like Mistral.
        base_url: Endpoint for remote API.
        previous_messages: List of prior messages for conversation context.
    
    Returns:
        The model's text response.
    """

    if provider == 'ollama':
        # Local Ollama call
        messages = previous_messages if previous_messages else []
        messages.append({"role": "user", "content": prompt})
        response = ollama.chat(
            model=ollama_model,
            messages=messages,
            options={"temperature": temperature}
        )
        return response['message']['content']

    elif provider == 'mistral':
        if not api_key or not base_url:
            raise ValueError("For Mistral provider, both api_key and base_url must be provided.")
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {api_key}"
        }

        messages = previous_messages if previous_messages else []
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": mistral_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        response = requests.post(base_url, headers=headers, json=payload)

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            raise RuntimeError(f"API request failed: {response.status_code} - {response.text}")
    
    else:
        raise ValueError(f"Unknown provider: {provider}")
    


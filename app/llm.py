import httpx
import os
import logging

logger = logging.getLogger(__name__)

# Default to Ollama Cloud OpenAI-compatible endpoint
DEFAULT_URL = "https://ollama.com/v1/chat/completions"
DEFAULT_MODEL = "llama3.1:8b"

# Read from environment (set on Render dashboard)
OLLAMA_URL = os.getenv("OLLAMA_API_BASE", DEFAULT_URL)
MODEL = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
API_KEY = os.getenv("OLLAMA_API_KEY", "")

logger.info(f"LLM config: url={OLLAMA_URL} model={MODEL} key_set={'yes' if API_KEY else 'no'}")

async def call_ollama(prompt: str, temperature: float = 0.2) -> str:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "stream": False
    }
    
    logger.info(f"Sending request to {OLLAMA_URL} with model {MODEL}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(OLLAMA_URL, json=payload, headers=headers)
        logger.info(f"Response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        # Support both Ollama native format and OpenAI-compatible format
        if "message" in data:
            content = data["message"]["content"]
        elif "choices" in data:
            content = data["choices"][0]["message"]["content"]
        else:
            raise ValueError(f"Unexpected response format: {data}")
        logger.info(f"Response length: {len(content)} chars")
        return content

__all__ = ["call_ollama"]
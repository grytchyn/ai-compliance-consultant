import httpx
import asyncio
import os

# Use environment variables for Render deployment, fallback to local Ollama
OLLAMA_URL = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434/api/chat")
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
API_KEY = os.getenv("OLLAMA_API_KEY", "")  # For services that require auth

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
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(OLLAMA_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        # Support both Ollama native format and OpenAI-compatible format
        if "message" in data:
            return data["message"]["content"]
        elif "choices" in data:
            return data["choices"][0]["message"]["content"]
        else:
            raise ValueError(f"Unexpected response format: {data}")

def sync_call_ollama(prompt: str, temperature: float = 0.2) -> str:
    return asyncio.run(call_ollama(prompt, temperature))

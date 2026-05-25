<<<<<<< HEAD
import httpx
import asyncio

def sync_search_web(query: str, limit: int = 3):
    """
    Simple wrapper around DuckDuckGo Instant Answer API.
    Returns list of dicts with keys: title, url, snippet.
    """
    # Use httpx in a sync way via asyncio.run
    return asyncio.run(_async_search_web(query, limit))

async def _async_search_web(query: str, limit: int):
=======
import requests
from typing import List, Dict

def duckduckgo_instant_answer(query: str) -> List[Dict]:
    """
    Simple wrapper around DuckDuckGo Instant Answer API.
    Returns list of results with 'content'.
    """
>>>>>>> 7721fb9 (Add full project: database, models, llm, search, prompts, utils, frontend, requirements, Dockerfile)
    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1
    }
<<<<<<< HEAD
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    results = []
    # RelatedTopics may contain nested structures; we'll extract simple ones.
    for topic in data.get("RelatedTopics", []):
        if isinstance(topic, dict) and topic.get("FirstURL") and topic.get("Text"):
            results.append({
                "title": topic.get("Text")[:100],
                "url": topic.get("FirstURL"),
                "snippet": topic.get("Text")[:200]
            })
        if len(results) >= limit:
            break
    # If not enough, fallback to Abstract
    if not results and data.get("Abstract"):
        results.append({
            "title": data.get("Heading") or query,
            "url": data.get("AbstractURL") or "",
            "snippet": data.get("Abstract")[:300]
        })
    return results[:limit]
=======
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = []
        # Abstract
        if data.get("Abstract"):
            results.append({"content": data["Abstract"]})
        # RelatedTopics
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({"content": topic["Text"]})
        return results
    except Exception as e:
        # Return empty list on failure
        return []
>>>>>>> 7721fb9 (Add full project: database, models, llm, search, prompts, utils, frontend, requirements, Dockerfile)

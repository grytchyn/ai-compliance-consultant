import httpx
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def duckduckgo_instant_answer(query: str) -> List[Dict]:
    """
    Synchronous DuckDuckGo Instant Answer API call.
    Returns list of results with 'content' key.
    """
    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
        results = []
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("FirstURL") and topic.get("Text"):
                results.append({
                    "content": f"{topic.get('Text', '')[:200]}"
                })
            if len(results) >= 3:
                break
                
        if not results and data.get("Abstract"):
            results.append({
                "content": f"{data.get('Heading') or query}. {data.get('Abstract')[:300]}"
            })
            
        return results[:3]
    except Exception as e:
        logger.warning(f"Search failed for '{query}': {type(e).__name__}: {e}")
        return []

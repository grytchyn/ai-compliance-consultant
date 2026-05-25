import httpx
from typing import List, Dict, Any

async def duckduckgo_instant_answer(query: str) -> List[Dict]:
    """
    Async wrapper around DuckDuckGo Instant Answer API.
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
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
        results = []
        # RelatedTopics may contain nested structures; we'll extract simple ones.
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("FirstURL") and topic.get("Text"):
                results.append({
                    "content": f"{topic.get('Text', '')[:200]}"
                })
            if len(results) >= 3:
                break
                
        # If not enough, fallback to Abstract
        if not results and data.get("Abstract"):
            results.append({
                "content": f"{data.get('Heading') or query}. {data.get('Abstract')[:300]}"
            })
            
        return results[:3]
    except Exception as e:
        # Return empty list on failure
        print(f"Search error: {e}")
        return []

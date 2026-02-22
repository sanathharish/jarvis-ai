from tavily import TavilyClient
import httpx
from config import TAVILY_API_KEY

client = TavilyClient(api_key=TAVILY_API_KEY)
TAVILY_URL = "https://api.tavily.com/search"

def web_search(query: str) -> str:
    response = client.search(
        query=query,
        search_depth="basic",
        max_results=5
    )
    results = response.get("results", [])
    if not results:
        return "No results found."
    
    formatted = []
    for r in results[:3]:
        formatted.append(f"**{r['title']}**\n{r['content']}\nSource: {r['url']}")
    
    return "\n\n".join(formatted)

async def async_web_search(query: str, max_results: int = 5) -> dict:
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
    }
    async with httpx.AsyncClient(timeout=5) as client_http:
        response = await client_http.post(TAVILY_URL, json=payload)
        response.raise_for_status()
        return response.json()

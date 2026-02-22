from tavily import TavilyClient
from config import TAVILY_API_KEY

client = TavilyClient(api_key=TAVILY_API_KEY)

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
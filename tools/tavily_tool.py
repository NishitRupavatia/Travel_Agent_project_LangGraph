import os
import certifi
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

API_KEY = os.getenv("TAVILY_API_KEY")

# Built lazily so a missing key produces a readable message instead of
# crashing the whole app at import time.
client = TavilyClient(api_key=API_KEY) if API_KEY else None


def tavily_search(query, max_results=5):
    if client is None:
        return (
            "Hotel search error: TAVILY_API_KEY is missing.\n"
            "Please add this in your .env file:\n"
            "TAVILY_API_KEY=your_api_key_here"
        )

    try:
        response = client.search(
            query=query,
            max_results=max_results
        )
    except Exception as e:
        return f"Hotel search failed: {e}"

    results = []

    for i, r in enumerate(response.get("results", []), 1):
        title   = r.get("title", "Unknown")
        url     = r.get("url", "")
        snippet = (r.get("content") or "").strip()
        # Keep only the first 300 characters to avoid wall-of-text
        if len(snippet) > 300:
            snippet = snippet[:300].rsplit(" ", 1)[0] + "..."

        results.append(f"{i}. **{title}**\n   {url}\n   {snippet}")

    if not results:
        return f"No hotel information found for: {query}"

    return "\n\n".join(results)

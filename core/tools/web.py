"""Shared web tools available to any agent or app."""
import warnings
import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

warnings.filterwarnings("ignore", message=".*duckduckgo_search.*renamed.*ddgs.*")


@tool
def fetch_page(url: str, max_chars: int = 8000) -> str:
    """Fetch a web page and return its main text content (strips HTML/JS/CSS)."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        content = "\n".join(lines)
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n[...truncated at {max_chars} chars]"
        return content or "(no readable content)"
    except Exception as e:
        return f"Error fetching page: {e}"


@tool
def web_search(query: str, max_results: int = 8) -> str:
    """Search the web using DuckDuckGo and return titles, URLs, and snippets."""
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    f"Title: {r.get('title', '')}\n"
                    f"URL: {r.get('href', '')}\n"
                    f"Snippet: {r.get('body', '')}\n"
                )
        return "\n---\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {e}"

"""
City of Safety Harbor procurement scraper.
Endpoint: https://www.cityofsafetyharbor.com/607/Solicitations
Plain HTML page — no JavaScript execution required.
"""
import json
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

_URL    = "https://www.cityofsafetyharbor.com/607/Solicitations"
_OUTPUT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output")
_AGENCY = "City of Safety Harbor"
_SOURCE = "safety_harbor"

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}


def _scrape(keyword: str = "") -> list[dict]:
    """Scrape open solicitations. Optionally filter by keyword in title."""
    resp = requests.get(_URL, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    bids = []

    # Find the "Open Solicitations" section header
    open_header = None
    for tag in soup.find_all(["h2", "h3", "h4", "strong", "b"]):
        if "open" in tag.get_text(strip=True).lower() and "solicit" in tag.get_text(strip=True).lower():
            open_header = tag
            break

    if not open_header:
        # Try looking for any links near "open" text
        for tag in soup.find_all(["h2", "h3", "h4"]):
            if "solicit" in tag.get_text(strip=True).lower():
                open_header = tag
                break

    if not open_header:
        return []

    # Walk siblings after the header to find bid links
    for sibling in open_header.find_next_siblings():
        text = sibling.get_text(strip=True).lower()
        # Stop if we hit a "closed" section
        if "closed" in text and "solicit" in text:
            break
        if "no open" in text or "no current" in text:
            break

        for a in sibling.find_all("a", href=True):
            title = a.get_text(strip=True)
            if not title:
                continue
            href = a["href"]
            if not href.startswith("http"):
                href = "https://www.cityofsafetyharbor.com" + href

            # Extract solicitation number from title (e.g. "RFP NO. 2024-01")
            sol_match = re.search(r"(RFP|RFQ|ITB|IFB|BID)[^\d]*(\d{4}[-/]\d+)", title, re.I)
            sol_number = f"{sol_match.group(1)}-{sol_match.group(2)}" if sol_match else ""

            bid = {
                "notice_id":           f"{_SOURCE}_{sol_number or hash(title) & 0xFFFFFF}",
                "title":               title,
                "solicitation_number": sol_number,
                "agency":              _AGENCY,
                "notice_type":         sol_match.group(1).upper() if sol_match else "BID",
                "status":              "OPEN",
                "response_deadline":   "",
                "posted_date":         "",
                "description":         "",
                "ui_link":             href,
                "state_code":          "FL",
                "state_name":          "Florida",
                "naics_code":          "",
                "type_of_set_aside":   "",
            }
            if keyword and keyword.lower() not in title.lower():
                continue
            bids.append(bid)

    return bids


@tool
def search_safety_harbor_bids(keywords: str = "") -> str:
    """Search City of Safety Harbor open solicitations.
    No API key required — scrapes the public procurement page directly.

    Args:
        keywords: Optional keyword filter on bid title. Leave blank to return all open bids.

    Returns:
        JSON string with list of open bids.
    """
    try:
        results = _scrape(keyword=keywords)
        if not results:
            return f"No open Safety Harbor bids found{' for: ' + keywords if keywords else ''}."
        return json.dumps(results, default=str)
    except Exception as e:
        return f"Error: {e}"


@tool
def save_safety_harbor_bids_to_json(keywords: str = "") -> str:
    """Search City of Safety Harbor open solicitations and save details to a JSON file in output/.

    Args:
        keywords: Optional keyword filter. Leave blank to save all open bids.

    Returns:
        Path to saved JSON file and summary.
    """
    try:
        results = _scrape(keyword=keywords)
        if not results:
            return f"No open Safety Harbor bids found{' for: ' + keywords if keywords else ''}."

        os.makedirs(_OUTPUT, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        safe_kw  = (keywords or "all").replace(" ", "_")[:40]
        filename = os.path.join(_OUTPUT, f"safety_harbor_{safe_kw}_{date_str}.json")

        payload = {
            "source":      _AGENCY,
            "search_term": keywords or "(all open)",
            "fetched_at":  datetime.now(timezone.utc).isoformat() + "Z",
            "total_found": len(results),
            "bids":        results,
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

        size_kb = os.path.getsize(filename) / 1024
        return (
            f"Saved {len(results)} Safety Harbor bid(s) to: {filename} ({size_kb:.1f} KB)\n"
            f"Titles: {', '.join(r['title'][:50] for r in results)}"
        )
    except Exception as e:
        return f"Error: {e}"

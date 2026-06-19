"""
Florida MyFloridaMarketPlace Vendor Bid System (VBS) API tools.
Endpoint: https://vendor.myfloridamarketplace.com/mfmp/pub/search/bids
No API key required — public endpoint.
"""
import json
import os
import warnings
from datetime import datetime, timezone

import requests
from langchain_core.tools import tool

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

_BASE     = "https://vendor.myfloridamarketplace.com/mfmp"
_SEARCH   = f"{_BASE}/pub/search/bids"
_OUTPUT   = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output")

_HEADERS  = {
    "User-Agent":   "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept":       "application/json",
    "Referer":      "https://vendor.myfloridamarketplace.com/search/bids",
}

# Ad type IDs from /mfmp/bids/AdTypes
AD_TYPES = {
    "1":  "Agency Decision",
    "2":  "Grant Opportunities",
    "3":  "Informational Notice",
    "4":  "Invitation to Bid",
    "5":  "Invitation to Negotiate",
    "6":  "Request for Proposals",
    "7":  "Public Meeting Notice",
    "8":  "Request for Information",
    "9":  "Request for Statement of Qualifications",
    "10": "Single Source",
}


def _search_vbs(title: str = "", organization_id: str = "",
                ad_type_id: str = "", max_results: int = 100) -> list[dict]:
    """Raw search call — returns list of bid dicts."""
    payload: dict = {"maxResults": max_results}
    if title.strip():
        payload["title"] = title.strip()
    if organization_id.strip():
        payload["organizationId"] = organization_id.strip()
    if ad_type_id.strip():
        payload["adTypeId"] = ad_type_id.strip()

    resp = requests.post(_SEARCH, json=payload, headers=_HEADERS, timeout=20, verify=False)
    resp.raise_for_status()
    return resp.json() if isinstance(resp.json(), list) else []


@tool
def search_florida_bids(
    keywords: str,
    max_results: int = 100,
    ad_type: str = "",
) -> str:
    """Search the Florida MyFloridaMarketPlace Vendor Bid System for state contracts.
    No API key required. Covers state agencies, universities, colleges,
    water management districts, and some local municipalities.

    Args:
        keywords: Title keyword to search, e.g. 'lawn maintenance' or 'landscaping'
        max_results: Maximum results to return (default 100)
        ad_type: Filter by type. Options: 'ITB' (Invitation to Bid),
                 'RFP' (Request for Proposals), 'ITN' (Invitation to Negotiate),
                 'RFI' (Request for Information), or leave blank for all.

    Returns:
        JSON string with list of matching bids including all available fields.
    """
    try:
        # Map friendly type names to IDs
        type_map = {"ITB": "4", "RFP": "6", "ITN": "5", "RFI": "8", "SSQ": "9"}
        ad_type_id = type_map.get(ad_type.upper().strip(), "")

        results = _search_vbs(
            title=keywords,
            ad_type_id=ad_type_id,
            max_results=max_results,
        )
        return json.dumps(results, default=str)
    except Exception as e:
        return f"Error: {e}"


@tool
def save_florida_bids_to_json(keywords: str, max_results: int = 100) -> str:
    """Search Florida VBS for contracts matching keywords and save ALL details
    to a JSON file in the output/ folder.

    Args:
        keywords: Search keywords, e.g. 'lawn maintenance'
        max_results: Maximum records to fetch (default 100)

    Returns:
        Path to the saved JSON file and summary of what was found.
    """
    try:
        results = _search_vbs(title=keywords, max_results=max_results)

        if not results:
            return f"No Florida VBS contracts found for '{keywords}'."

        os.makedirs(_OUTPUT, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        safe_kw  = keywords.replace(" ", "_").replace("/", "-")[:40]
        filename = os.path.join(_OUTPUT, f"florida_vbs_{safe_kw}_{date_str}.json")

        payload = {
            "source":       "Florida MyFloridaMarketPlace VBS",
            "search_term":  keywords,
            "fetched_at":   datetime.now(timezone.utc).isoformat() + "Z",
            "total_found":  len(results),
            "bids":         results,
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

        size_kb = os.path.getsize(filename) / 1024
        statuses = {}
        for r in results:
            s = r.get("status", "UNKNOWN")
            statuses[s] = statuses.get(s, 0) + 1

        status_str = ", ".join(f"{v} {k}" for k, v in sorted(statuses.items()))
        return (
            f"Saved {len(results)} Florida VBS contracts to: {filename} ({size_kb:.1f} KB)\n"
            f"Statuses: {status_str}\n"
            f"Fields per record: {', '.join(results[0].keys()) if results else 'none'}"
        )
    except Exception as e:
        return f"Error: {e}"


@tool
def list_florida_organizations() -> str:
    """List all Florida state agencies and organizations available in the VBS,
    with their IDs for use in filtered searches."""
    try:
        resp = requests.get(
            f"{_BASE}/pub/search/picklistOrg",
            headers=_HEADERS, timeout=15, verify=False
        )
        resp.raise_for_status()
        orgs = resp.json()
        lines = [f"{o['id']:>12}  {o['value']}" for o in orgs]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"

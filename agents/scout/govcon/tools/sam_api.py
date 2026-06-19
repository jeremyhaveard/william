"""
SAM.gov Opportunities API tools.
All network I/O against api.sam.gov lives here.
Requires SAM_API_KEY environment variable (free key from api.data.gov).
"""
import json
import os
from datetime import datetime, timedelta

import requests
from langchain_core.tools import tool

_SAM_BASE = "https://api.sam.gov/opportunities/v2/search"


def _api_key() -> str:
    key = os.getenv("SAM_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "SAM_API_KEY is not set. Get a free key at https://api.data.gov/signup "
            "and add SAM_API_KEY=your_key to your .env file."
        )
    return key


def _default_date_range(days_back: int = 30) -> tuple[str, str]:
    """Return (posted_from, posted_to) in MM/dd/yyyy format."""
    today = datetime.utcnow()
    start = today - timedelta(days=days_back)
    return start.strftime("%m/%d/%Y"), today.strftime("%m/%d/%Y")


@tool
def search_opportunities(
    keywords: str,
    naics_codes: str = "",
    set_aside: str = "",
    days_back: int = 30,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """Search SAM.gov for active federal contract opportunities.

    Args:
        keywords: Search terms, e.g. 'cloud infrastructure DevSecOps'
        naics_codes: Comma-separated NAICS codes, e.g. '541511,541512'
        set_aside: Set-aside type code. Options: SBA, 8A, HZC, SDVOSBC, WOSB, EDWOSB
        days_back: How many days back to search (default 30)
        limit: Results per page (default 100, max 1000)
        offset: Pagination offset — increment by limit to get next page

    Returns:
        JSON string with keys: total_records (int), opportunities (list of dicts),
        or an error string starting with 'Error:'.
    """
    try:
        posted_from, posted_to = _default_date_range(days_back)
        params: dict = {
            "api_key":     _api_key(),
            "limit":       limit,
            "offset":      offset,
            "postedFrom":  posted_from,
            "postedTo":    posted_to,
            "active":      "true",
        }
        if keywords.strip():
            params["keywords"] = keywords.strip()
        if naics_codes.strip():
            params["naics"] = naics_codes.strip()
        if set_aside.strip():
            params["typeOfSetAside"] = set_aside.strip()

        resp = requests.get(_SAM_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        total = data.get("totalRecords", 0)
        raw_opps = data.get("opportunitiesData", [])

        opportunities = []
        for o in raw_opps:
            pop = o.get("placeOfPerformance") or {}
            state = pop.get("state") or {}
            opportunities.append({
                "notice_id":              o.get("noticeId", ""),
                "title":                  o.get("title", ""),
                "solicitation_number":    o.get("solicitationNumber", ""),
                "agency":                 o.get("fullParentPathName", ""),
                "naics_code":             o.get("naicsCode", ""),
                "type_of_set_aside":      o.get("typeOfSetAside", ""),
                "type_of_set_aside_desc": o.get("typeOfSetAsideDescription", ""),
                "response_deadline":      o.get("responseDeadLine", ""),
                "posted_date":            o.get("postedDate", ""),
                "notice_type":            o.get("type", ""),
                "ui_link":                o.get("uiLink", ""),
                "description":            o.get("description", ""),
                "state_code":             state.get("code", ""),
                "state_name":             state.get("name", ""),
            })

        return json.dumps({"total_records": total, "opportunities": opportunities})

    except EnvironmentError as e:
        return f"Error: {e}"
    except requests.HTTPError as e:
        return f"Error: SAM.gov API returned {e.response.status_code} — {e.response.text[:300]}"
    except Exception as e:
        return f"Error: {e}"


@tool
def get_opportunity_detail(notice_id: str) -> str:
    """Fetch full details for a single SAM.gov opportunity by its notice ID.

    Args:
        notice_id: The SAM.gov noticeId, e.g. 'a1b2c3d4e5f6...'

    Returns:
        JSON string of the full opportunity record, or an error string.
    """
    try:
        params = {
            "api_key":  _api_key(),
            "noticeid": notice_id,
            "limit":    1,
        }
        resp = requests.get(_SAM_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        opps = data.get("opportunitiesData", [])
        if not opps:
            return f"Error: No opportunity found for notice_id={notice_id}"
        return json.dumps(opps[0])
    except EnvironmentError as e:
        return f"Error: {e}"
    except requests.HTTPError as e:
        return f"Error: SAM.gov API returned {e.response.status_code} — {e.response.text[:300]}"
    except Exception as e:
        return f"Error: {e}"

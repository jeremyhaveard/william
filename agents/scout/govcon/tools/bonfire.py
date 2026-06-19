"""
Bonfire/Euna Procurement platform scraper.
Covers: Hillsborough County, City of Tarpon Springs (and any future Bonfire agencies).
Portal pattern: https://{agency_subdomain}.bonfirehub.com/opportunities

No API key required — public portal. Uses Playwright to handle AJAX-loaded tables.
"""
import asyncio
import json
import os
from datetime import datetime, timezone

from langchain_core.tools import tool

from apps.govcon.tools._browser import get_page, run_sync

_OUTPUT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output")

# Known agencies: subdomain -> human label
_AGENCIES = {
    "hillsboroughcounty": "Hillsborough County",
    "ctsfl":              "City of Tarpon Springs",
}


async def _scrape_bonfire(agency_subdomain: str, keyword: str = "") -> list[dict]:
    """Scrape open opportunities from a Bonfire portal."""
    url = f"https://{agency_subdomain}.bonfirehub.com/opportunities?tab=openOpportunities"
    agency_label = _AGENCIES.get(agency_subdomain, agency_subdomain)

    # Intercept the API response if available, else fall back to DOM scraping
    api_results: list[dict] = []
    dom_results: list[dict] = []

    async def handle_response(response):
        if "opportunities" in response.url and response.status == 200:
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    data = await response.json()
                    items = data if isinstance(data, list) else data.get("data", data.get("opportunities", []))
                    if isinstance(items, list):
                        api_results.extend(items)
            except Exception:
                pass

    async with get_page(url, timeout=40000) as page:
        page.on("response", handle_response)

        # Wait for either the table to populate or "no opportunities" message
        try:
            await page.wait_for_selector(
                "table tbody tr, .no-opportunities, .empty-state, [class*='no-result'], [class*='empty']",
                timeout=20000,
            )
        except Exception:
            pass

        # Give AJAX a moment to finish
        await asyncio.sleep(2)

        # DOM scrape — works regardless of whether API interception succeeded
        rows = await page.query_selector_all("table tbody tr")
        for row in rows:
            cells = await row.query_selector_all("td")
            if len(cells) < 2:
                continue
            texts = [await c.inner_text() for c in cells]

            # Try to get the detail link
            link_el = await row.query_selector("a")
            href = ""
            if link_el:
                href = await link_el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = f"https://{agency_subdomain}.bonfirehub.com{href}"

            # Bonfire column order: Status | Ref# | Project | Close Date | Days Left | Action
            status = texts[0].strip() if texts else "OPEN"
            ref    = texts[1].strip() if len(texts) > 1 else ""
            title  = texts[2].strip() if len(texts) > 2 else ""
            close  = texts[3].strip() if len(texts) > 3 else ""

            # Derive type from ref number prefix (e.g. ITB-26-00234 -> ITB)
            type_match = __import__("re").match(r"([A-Z]+)", ref)
            btype = type_match.group(1) if type_match else ""

            if not title or title.lower() in ("title", "name", "project"):
                continue

            dom_results.append({
                "notice_id":           f"bonfire_{agency_subdomain}_{ref or hash(title) & 0xFFFFFF}",
                "title":               title,
                "solicitation_number": ref,
                "agency":              agency_label,
                "notice_type":         btype,
                "status":              status,
                "response_deadline":   close,
                "posted_date":         "",
                "description":         "",
                "ui_link":             href,
                "state_code":          "FL",
                "state_name":          "Florida",
                "naics_code":          "",
                "type_of_set_aside":   "",
            })

    # Prefer DOM results (more reliable); fall back to API results if DOM empty
    results = dom_results if dom_results else _normalize_api(api_results, agency_subdomain, agency_label)

    if keyword:
        results = [r for r in results if keyword.lower() in r["title"].lower()]

    return results


def _normalize_api(items: list, subdomain: str, label: str) -> list[dict]:
    """Normalize raw Bonfire API records to our schema."""
    out = []
    for item in items:
        ref = item.get("referenceNumber", item.get("number", ""))
        out.append({
            "notice_id":           f"bonfire_{subdomain}_{ref or item.get('id', '')}",
            "title":               item.get("name", item.get("title", "")),
            "solicitation_number": ref,
            "agency":              label,
            "notice_type":         item.get("type", item.get("opportunityType", "")),
            "status":              "OPEN",
            "response_deadline":   item.get("closingDate", item.get("deadline", "")),
            "posted_date":         item.get("publishedDate", ""),
            "description":         item.get("description", "")[:1000],
            "ui_link":             item.get("url", f"https://{subdomain}.bonfirehub.com/opportunities"),
            "state_code":          "FL",
            "state_name":          "Florida",
            "naics_code":          "",
            "type_of_set_aside":   "",
        })
    return out


@tool
def search_bonfire_bids(agency_subdomain: str, keywords: str = "") -> str:
    """Search a Bonfire procurement portal for open bid opportunities.

    Args:
        agency_subdomain: Bonfire subdomain, e.g. 'hillsboroughcounty' or 'ctsfl'
        keywords: Optional keyword filter on bid title. Leave blank for all open bids.

    Returns:
        JSON string with list of open bids.
    """
    try:
        results = run_sync(_scrape_bonfire(agency_subdomain, keyword=keywords))
        if not results:
            return f"No open Bonfire bids found for '{agency_subdomain}'" + (f" matching '{keywords}'" if keywords else "") + "."
        return json.dumps(results, default=str)
    except Exception as e:
        return f"Error scraping {agency_subdomain}: {e}"


@tool
def save_bonfire_bids_to_json(agency_subdomain: str, keywords: str = "") -> str:
    """Search a Bonfire procurement portal and save open bids to a JSON file in output/.

    Args:
        agency_subdomain: Bonfire subdomain, e.g. 'hillsboroughcounty' or 'ctsfl'
        keywords: Optional keyword filter. Leave blank to save all open bids.

    Returns:
        Path to the saved JSON file and a summary.
    """
    try:
        results = run_sync(_scrape_bonfire(agency_subdomain, keyword=keywords))
        agency_label = _AGENCIES.get(agency_subdomain, agency_subdomain)

        if not results:
            return f"No open bids found for {agency_label}" + (f" matching '{keywords}'" if keywords else "") + "."

        os.makedirs(_OUTPUT, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        safe_kw  = (keywords or "all").replace(" ", "_")[:30]
        filename = os.path.join(_OUTPUT, f"bonfire_{agency_subdomain}_{safe_kw}_{date_str}.json")

        payload = {
            "source":      f"Bonfire — {agency_label}",
            "agency_slug": agency_subdomain,
            "search_term": keywords or "(all open)",
            "fetched_at":  datetime.now(timezone.utc).isoformat() + "Z",
            "total_found": len(results),
            "bids":        results,
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

        size_kb = os.path.getsize(filename) / 1024
        return (
            f"Saved {len(results)} bid(s) from {agency_label} to: {filename} ({size_kb:.1f} KB)\n"
            f"Titles: {chr(10).join('  - ' + r['title'][:70] for r in results[:10])}"
        )
    except Exception as e:
        return f"Error: {e}"

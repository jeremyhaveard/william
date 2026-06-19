"""
OpenGov Procurement platform scraper.
Covers: Pinellas County, City of Clearwater, City of St. Petersburg,
        City of Tampa, Pinellas County Schools (and any future OpenGov agencies).
Portal pattern: https://procurement.opengov.com/portal/{agency_slug}

No API key required — public portal. Uses Playwright (React SPA).
"""
import asyncio
import json
import os
import re
from datetime import datetime, timezone

from langchain_core.tools import tool

from agents.scout.tools._browser import get_page, run_sync

_OUTPUT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output")
_BASE   = "https://procurement.opengov.com/portal"

_AGENCIES = {
    "pinellasfl":  "Pinellas County",
    "myclearwater": "City of Clearwater",
    "stpete":      "City of St. Petersburg",
    "cityoftampa": "City of Tampa",
    "PCSB":        "Pinellas County Schools",
}


async def _scrape_opengov(agency_slug: str, keyword: str = "") -> list[dict]:
    """NOTE: procurement.opengov.com is behind Cloudflare enterprise protection.
    Automated scraping is currently blocked. Returns empty list with a warning."""
    raise RuntimeError(
        f"OpenGov portal '{agency_slug}' is protected by Cloudflare and cannot be scraped automatically. "
        "To enable: log into the portal in Chrome, copy the 'cf_clearance' cookie value to "
        "OPENGOV_CF_CLEARANCE in .env, then re-run."
    )

async def _scrape_opengov_impl(agency_slug: str, keyword: str = "") -> list[dict]:
    """Scrape open projects from an OpenGov portal."""
    url = f"{_BASE}/{agency_slug}"
    agency_label = _AGENCIES.get(agency_slug, agency_slug)

    api_results: list[dict] = []

    async def handle_response(response):
        url_lower = response.url.lower()
        if ("project" in url_lower or "solicitation" in url_lower or "opportunit" in url_lower) \
                and response.status == 200:
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    data = await response.json()
                    # OpenGov wraps results in various keys
                    for key in ("projects", "solicitations", "opportunities", "data", "results"):
                        if isinstance(data, dict) and key in data:
                            items = data[key]
                            if isinstance(items, list):
                                api_results.extend(items)
                                return
                    if isinstance(data, list):
                        api_results.extend(data)
            except Exception:
                pass

    bids: list[dict] = []

    async with get_page(url, timeout=45000) as page:
        page.on("response", handle_response)

        # Wait for project cards or list to appear
        selectors = [
            "[data-testid='project-list-item']",
            "[class*='ProjectCard']",
            "[class*='project-card']",
            "[class*='solicitation']",
            ".project-list",
            "article",
        ]
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=12000)
                break
            except Exception:
                continue

        await asyncio.sleep(2)

        # If keyword provided, try typing it into the search box
        if keyword:
            try:
                search_sel = "input[type='search'], input[placeholder*='Search'], input[placeholder*='search']"
                search_box = await page.query_selector(search_sel)
                if search_box:
                    await search_box.fill(keyword)
                    await search_box.press("Enter")
                    await asyncio.sleep(2)
            except Exception:
                pass

        # DOM scrape — extract card/row data
        cards = await page.query_selector_all(
            "[data-testid='project-list-item'], [class*='ProjectCard'], [class*='project-card'], article"
        )
        for card in cards:
            text = (await card.inner_text()).strip()
            if not text:
                continue

            link_el = await card.query_selector("a")
            href = ""
            if link_el:
                href = await link_el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = "https://procurement.opengov.com" + href

            # Parse title — first non-empty line
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            title = lines[0] if lines else text[:100]

            # Extract dates (looks like "Closes MM/DD/YYYY" or "Due MM/DD/YYYY")
            deadline = ""
            date_match = re.search(r"(?:clos|due|deadline|open)[^\d]*(\d{1,2}/\d{1,2}/\d{4})", text, re.I)
            if date_match:
                deadline = date_match.group(1)

            # Extract solicitation number
            sol_match = re.search(r"(RFP|RFQ|ITB|IFB|BID|RFSO|RFI)[^\d]*(\d[\w-]+)", text, re.I)
            sol_number = f"{sol_match.group(1)}-{sol_match.group(2)}" if sol_match else ""

            bids.append({
                "notice_id":           f"opengov_{agency_slug}_{sol_number or hash(title) & 0xFFFFFF}",
                "title":               title,
                "solicitation_number": sol_number,
                "agency":              agency_label,
                "notice_type":         sol_match.group(1).upper() if sol_match else "",
                "status":              "OPEN",
                "response_deadline":   deadline,
                "posted_date":         "",
                "description":         text[:500],
                "ui_link":             href or url,
                "state_code":          "FL",
                "state_name":          "Florida",
                "naics_code":          "",
                "type_of_set_aside":   "",
            })

    # Prefer DOM results; fall back to intercepted API results if DOM scrape empty
    results = bids if bids else _normalize_api(api_results, agency_slug, agency_label)

    if keyword and results:
        results = [r for r in results if keyword.lower() in r["title"].lower()]

    return results


def _normalize_api(items: list, slug: str, label: str) -> list[dict]:
    out = []
    for item in items:
        ref = item.get("referenceNumber", item.get("number", item.get("id", "")))
        title = item.get("name", item.get("title", ""))
        out.append({
            "notice_id":           f"opengov_{slug}_{ref}",
            "title":               title,
            "solicitation_number": str(ref),
            "agency":              label,
            "notice_type":         item.get("type", item.get("projectType", "")),
            "status":              item.get("status", "OPEN"),
            "response_deadline":   item.get("closingDate", item.get("dueDate", "")),
            "posted_date":         item.get("publishedDate", item.get("postedDate", "")),
            "description":         str(item.get("description", ""))[:1000],
            "ui_link":             item.get("url", f"https://procurement.opengov.com/portal/{slug}"),
            "state_code":          "FL",
            "state_name":          "Florida",
            "naics_code":          "",
            "type_of_set_aside":   "",
        })
    return out


@tool
def search_opengov_bids(agency_slug: str, keywords: str = "") -> str:
    """Search an OpenGov procurement portal for open bid opportunities.

    Args:
        agency_slug: OpenGov agency slug, e.g. 'pinellasfl', 'myclearwater', 'stpete',
                     'cityoftampa', 'PCSB'
        keywords: Optional keyword filter on bid title. Leave blank for all open bids.

    Returns:
        JSON string with list of open bids.
    """
    try:
        results = run_sync(_scrape_opengov(agency_slug, keyword=keywords))
        if not results:
            return f"No open OpenGov bids found for '{agency_slug}'" + (f" matching '{keywords}'" if keywords else "") + "."
        return json.dumps(results, default=str)
    except Exception as e:
        return f"Error scraping {agency_slug}: {e}"


@tool
def save_opengov_bids_to_json(agency_slug: str, keywords: str = "") -> str:
    """Search an OpenGov procurement portal and save open bids to a JSON file in output/.

    Args:
        agency_slug: OpenGov agency slug, e.g. 'pinellasfl', 'myclearwater', 'stpete',
                     'cityoftampa', 'PCSB'
        keywords: Optional keyword filter. Leave blank to save all open bids.

    Returns:
        Path to saved JSON file and summary.
    """
    try:
        results = run_sync(_scrape_opengov(agency_slug, keyword=keywords))
        agency_label = _AGENCIES.get(agency_slug, agency_slug)

        if not results:
            return f"No open bids found for {agency_label}" + (f" matching '{keywords}'" if keywords else "") + "."

        os.makedirs(_OUTPUT, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        safe_kw  = (keywords or "all").replace(" ", "_")[:30]
        safe_slug = agency_slug.replace("/", "-")
        filename = os.path.join(_OUTPUT, f"opengov_{safe_slug}_{safe_kw}_{date_str}.json")

        payload = {
            "source":      f"OpenGov — {agency_label}",
            "agency_slug": agency_slug,
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
            f"Titles:\n{chr(10).join('  - ' + r['title'][:70] for r in results[:10])}"
        )
    except Exception as e:
        return f"Error: {e}"

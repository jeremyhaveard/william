"""
SQLite tool wrappers for the GovCon app.
All tools use get_db("govcon.db") from core.db.
"""
import os
from datetime import datetime
from langchain_core.tools import tool
from core.db import get_db

_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output")

# NAICS sector codes → human-readable function labels
_NAICS_SECTORS = {
    "11": "Agriculture / Forestry / Fishing",
    "21": "Mining / Oil & Gas",
    "22": "Utilities",
    "23": "Construction",
    "31": "Manufacturing",
    "32": "Manufacturing",
    "33": "Manufacturing",
    "42": "Wholesale Trade",
    "44": "Retail Trade",
    "45": "Retail Trade",
    "48": "Transportation / Warehousing",
    "49": "Transportation / Warehousing",
    "51": "Information Technology",
    "52": "Finance / Insurance",
    "53": "Real Estate",
    "54": "Professional / Scientific / Technical",
    "55": "Management of Companies",
    "56": "Administrative / Support Services",
    "61": "Education",
    "62": "Health Care / Social Assistance",
    "71": "Arts / Entertainment / Recreation",
    "72": "Accommodation / Food Services",
    "81": "Other Services",
    "92": "Public Administration / Defense",
}


@tool
def get_company_profile() -> str:
    """Read the company targeting profile (NAICS codes, keywords, set-aside types).
    Always call this first before searching so you know what to look for.
    """
    try:
        with get_db("govcon.db") as conn:
            rows = conn.execute(
                "SELECT key, value FROM company_profile ORDER BY key"
            ).fetchall()
        if not rows:
            return "Company profile is empty. No targeting parameters configured."
        return "\n".join(f"{row['key']}: {row['value']}" for row in rows)
    except Exception as e:
        return f"Error reading company profile: {e}"


@tool
def save_opportunity(
    notice_id: str,
    title: str,
    solicitation_number: str,
    agency: str,
    naics_code: str,
    type_of_set_aside: str,
    type_of_set_aside_desc: str,
    response_deadline: str,
    posted_date: str,
    notice_type: str,
    ui_link: str,
    description: str,
    state_code: str = "",
    state_name: str = "",
) -> str:
    """Save a contract opportunity to the database. Skips duplicates by notice_id.

    Returns: 'saved', 'duplicate', or an error string.
    """
    try:
        with get_db("govcon.db") as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO opportunities (
                    notice_id, title, solicitation_number, agency,
                    naics_code, type_of_set_aside, type_of_set_aside_desc,
                    response_deadline, posted_date, notice_type, ui_link, description,
                    state_code, state_name
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    notice_id, title, solicitation_number, agency,
                    naics_code, type_of_set_aside, type_of_set_aside_desc,
                    response_deadline, posted_date, notice_type, ui_link, description,
                    state_code, state_name,
                ),
            )
        return "saved" if cursor.rowcount else "duplicate"
    except Exception as e:
        return f"Error saving opportunity: {e}"


@tool
def list_opportunities(status: str = "new", limit: int = 50) -> str:
    """List contract opportunities by status.

    Args:
        status: Filter by workflow status: new, reviewing, bid, no_bid, archived
        limit: Max rows to return (default 50)

    Returns:
        Formatted table of opportunities or a message if none found.
    """
    try:
        with get_db("govcon.db") as conn:
            rows = conn.execute(
                """
                SELECT notice_id, title, agency, naics_code,
                       response_deadline, posted_date, ui_link
                FROM opportunities
                WHERE status = ?
                ORDER BY response_deadline ASC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()

        if not rows:
            return f"No opportunities with status='{status}'."

        lines = [f"{'TITLE':<50} {'AGENCY':<35} {'NAICS':<8} {'DEADLINE':<12}"]
        lines.append("-" * 110)
        for r in rows:
            title   = (r["title"] or "")[:48]
            agency  = (r["agency"] or "")[:33]
            naics   = (r["naics_code"] or "")[:7]
            deadline = (r["response_deadline"] or "")[:10]
            lines.append(f"{title:<50} {agency:<35} {naics:<8} {deadline:<12}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing opportunities: {e}"


@tool
def get_opportunity(notice_id: str) -> str:
    """Get full details for a single opportunity by notice_id."""
    try:
        with get_db("govcon.db") as conn:
            row = conn.execute(
                "SELECT * FROM opportunities WHERE notice_id = ?", (notice_id,)
            ).fetchone()
        if not row:
            return f"No opportunity found with notice_id={notice_id}"
        return "\n".join(f"{k}: {v}" for k, v in dict(row).items())
    except Exception as e:
        return f"Error: {e}"


@tool
def update_opportunity_status(notice_id: str, status: str, notes: str = "") -> str:
    """Update the workflow status of an opportunity.

    Args:
        notice_id: The SAM.gov notice ID
        status: One of: new, reviewing, bid, no_bid, archived
        notes: Optional notes to attach

    Returns: 'updated', 'not_found', or an error string.
    """
    valid = {"new", "reviewing", "bid", "no_bid", "archived"}
    if status not in valid:
        return f"Error: status must be one of {sorted(valid)}"
    try:
        with get_db("govcon.db") as conn:
            cursor = conn.execute(
                """
                UPDATE opportunities
                SET status = ?, notes = ?, updated_at = datetime('now')
                WHERE notice_id = ?
                """,
                (status, notes, notice_id),
            )
        return "updated" if cursor.rowcount else "not_found"
    except Exception as e:
        return f"Error: {e}"


@tool
def generate_breakdown_report(status: str = "new") -> str:
    """Generate a Markdown report breaking down opportunities by state and function (NAICS sector).
    Saves the report to the output/ folder and returns the file path.

    Args:
        status: Which opportunities to include: new, reviewing, bid, no_bid, archived, or 'all'
    """
    try:
        os.makedirs(_OUTPUT_DIR, exist_ok=True)

        with get_db("govcon.db") as conn:
            query = "SELECT * FROM opportunities"
            params: tuple = ()
            if status != "all":
                query += " WHERE status = ?"
                params = (status,)
            rows = conn.execute(query + " ORDER BY response_deadline ASC", params).fetchall()

        if not rows:
            return f"No opportunities found with status='{status}'. Run a search first."

        total = len(rows)

        # ── By State ──────────────────────────────────────────────────────────
        state_counts: dict[str, list] = {}
        for r in rows:
            key = (r["state_code"] or "Unknown") + (f" — {r['state_name']}" if r["state_name"] else "")
            state_counts.setdefault(key, []).append(r)

        state_lines = ["| State | Count | Upcoming Deadline |",
                       "|-------|-------|-------------------|"]
        for state, opps in sorted(state_counts.items(), key=lambda x: -len(x[1])):
            deadlines = sorted(o["response_deadline"] or "" for o in opps if o["response_deadline"])
            next_dl = deadlines[0][:10] if deadlines else "—"
            state_lines.append(f"| {state} | {len(opps)} | {next_dl} |")

        # ── By Function (NAICS sector) ─────────────────────────────────────
        sector_counts: dict[str, list] = {}
        for r in rows:
            code = (r["naics_code"] or "")[:2]
            label = _NAICS_SECTORS.get(code, f"Other ({code or 'unknown'})")
            sector_counts.setdefault(label, []).append(r)

        sector_lines = ["| Function | NAICS Sector | Count |",
                        "|----------|-------------|-------|"]
        for sector, opps in sorted(sector_counts.items(), key=lambda x: -len(x[1])):
            code = (opps[0]["naics_code"] or "")[:2]
            sector_lines.append(f"| {sector} | {code}xxxx | {len(opps)} |")

        # ── Urgent deadlines (within 14 days) ─────────────────────────────
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        urgent = [
            r for r in rows
            if r["response_deadline"] and r["response_deadline"][:10] >= today_str
            and r["response_deadline"][:10] <= datetime.utcnow().strftime("%Y-%m-%") + "22"
        ]
        # Simpler: just grab those with earliest deadlines
        with_deadline = sorted(
            [r for r in rows if r["response_deadline"]],
            key=lambda r: r["response_deadline"]
        )[:10]

        urgent_lines = ["| Title | Agency | State | Deadline | Link |",
                        "|-------|--------|-------|----------|------|"]
        for r in with_deadline:
            title  = (r["title"] or "")[:50]
            agency = (r["agency"] or "").split("::")[-1][:30]
            state  = r["state_code"] or "—"
            dl     = (r["response_deadline"] or "")[:10]
            link   = r["ui_link"] or "—"
            urgent_lines.append(f"| {title} | {agency} | {state} | {dl} | {link} |")

        # ── Assemble report ────────────────────────────────────────────────
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        report = f"""# Government Contract Opportunities Report
**Generated:** {date_str}  **Status filter:** {status}  **Total opportunities:** {total}

---

## Breakdown by State

{chr(10).join(state_lines)}

---

## Breakdown by Function (NAICS Sector)

{chr(10).join(sector_lines)}

---

## Earliest Deadlines (Next 10)

{chr(10).join(urgent_lines)}
"""
        filename = f"contracts_report_{date_str}.md"
        path = os.path.join(_OUTPUT_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)

        return f"Report saved: {path} ({total} opportunities)"

    except Exception as e:
        return f"Error generating report: {e}"


@tool
def update_company_profile(key: str, value: str) -> str:
    """Update or add a key in the company profile.

    Common keys: company_name, naics_codes (JSON array), keywords (JSON array),
                 set_aside_types (JSON array), min_value, max_value
    """
    try:
        with get_db("govcon.db") as conn:
            conn.execute(
                """
                INSERT INTO company_profile (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value),
            )
        return f"Profile updated: {key} = {value}"
    except Exception as e:
        return f"Error: {e}"

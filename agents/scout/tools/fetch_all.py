"""
Fetch all active contracts from SAM.gov and save raw JSON to output/.

Usage:
    python -m agents.scout.tools.fetch_all
    python -m agents.scout.tools.fetch_all --days 90
    python -m agents.scout.tools.fetch_all --resume   (continue a previous run)

SAM.gov rate limits are strict. This script paces at 15s per page and uses
a checkpoint file so it can resume if interrupted or rate-limited.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
load_dotenv()

_SAM_BASE    = "https://api.sam.gov/opportunities/v2/search"
_PAGE_SIZE   = 1000
_MAX_OFFSET  = 9000        # SAM.gov hard cap per query window
_PAGE_DELAY  = 15          # seconds between pages — conservative for rate limits
_WINDOW_DELAY = 10         # seconds between date windows
_OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output")
_CHECKPOINT  = os.path.join(_OUTPUT_DIR, "_fetch_checkpoint.json")


def _api_key() -> str:
    key = os.getenv("SAM_API_KEY", "").strip()
    if not key:
        raise EnvironmentError("SAM_API_KEY not set in .env")
    return key


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_page(params: dict, max_retries: int = 6) -> dict:
    """GET one page with exponential backoff on 429. Raises after max_retries."""
    delay = 60  # start with 60s wait on first 429
    for attempt in range(max_retries):
        resp = requests.get(_SAM_BASE, params=params, timeout=30)
        if resp.status_code == 429:
            wait = delay * (2 ** attempt)
            print(f"\n  Rate limited. Waiting {wait}s "
                  f"(attempt {attempt + 1}/{max_retries})...")
            sys.stdout.flush()
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("Max retries exceeded — run again later with --resume")


def _load_checkpoint() -> dict:
    if os.path.exists(_CHECKPOINT):
        with open(_CHECKPOINT, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_checkpoint(data: dict) -> None:
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    with open(_CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _load_partial(filename: str) -> list:
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f).get("contracts", [])
    return []


def _save_partial(filename: str, records: list, days_back: int) -> None:
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at":    _now().isoformat() + "Z",
            "days_back":     days_back,
            "total_fetched": len(records),
            "status":        "in_progress",
            "contracts":     records,
        }, f, indent=2)


def fetch_all(days_back: int = 90, resume: bool = False) -> str:
    """
    Fetch all active SAM.gov contracts posted in the last `days_back` days.
    Uses 30-day sliding windows to stay under the 10,000-record API cap.
    Checkpoints progress so --resume can continue after interruption.
    Returns the path to the saved JSON file.
    """
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    date_str = _now().strftime("%Y-%m-%d")
    out_file = os.path.join(_OUTPUT_DIR, f"all_contracts_{date_str}.json")

    # Load checkpoint if resuming
    checkpoint = _load_checkpoint() if resume else {}
    start_from = checkpoint.get("next_window_start")

    today      = _now()
    start_date = today - timedelta(days=days_back)

    # All records seen so far (from partial file if resuming)
    all_records: list[dict] = _load_partial(out_file) if resume else []
    seen_ids:    set[str]   = {r.get("noticeId", "") for r in all_records}

    print(f"Fetching SAM.gov contracts — last {days_back} days")
    print(f"Pacing: {_PAGE_DELAY}s between pages, {_WINDOW_DELAY}s between windows")
    if resume and start_from:
        print(f"Resuming from window starting {start_from}")
    print(f"Output: {out_file}\n")
    sys.stdout.flush()

    window_start = datetime.strptime(start_from, "%Y-%m-%d") if start_from else start_date

    while window_start < today:
        window_end = min(window_start + timedelta(days=30), today)
        pf = window_start.strftime("%m/%d/%Y")
        pt = window_end.strftime("%m/%d/%Y")

        print(f"Window {pf} -> {pt}")
        sys.stdout.flush()

        # Fetch all pages in this window
        window_records: list[dict] = []
        offset = 0

        while True:
            params = {
                "api_key":    _api_key(),
                "limit":      _PAGE_SIZE,
                "offset":     offset,
                "postedFrom": pf,
                "postedTo":   pt,
                "active":     "true",
            }

            data  = _get_page(params)
            total = data.get("totalRecords", 0)
            page  = data.get("opportunitiesData", [])
            window_records += page

            fetched = offset + len(page)
            print(f"  Page offset={offset}: {len(page)} records "
                  f"({fetched:,}/{total:,} in window)", flush=True)

            if not page or fetched >= total or offset + _PAGE_SIZE > _MAX_OFFSET:
                break

            offset += _PAGE_SIZE
            time.sleep(_PAGE_DELAY)

        # Deduplicate and add to master list
        new = [r for r in window_records if r.get("noticeId") not in seen_ids]
        seen_ids.update(r.get("noticeId", "") for r in new)
        all_records += new

        print(f"  -> {len(new):,} new records  (total so far: {len(all_records):,})\n",
              flush=True)

        # Save partial results and checkpoint after every window
        _save_partial(out_file, all_records, days_back)
        next_start = window_end.strftime("%Y-%m-%d")
        _save_checkpoint({"next_window_start": next_start, "out_file": out_file})

        window_start = window_end
        time.sleep(_WINDOW_DELAY)

    # Finalize
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at":    _now().isoformat() + "Z",
            "days_back":     days_back,
            "total_fetched": len(all_records),
            "status":        "complete",
            "contracts":     all_records,
        }, f, indent=2)

    # Clean up checkpoint
    if os.path.exists(_CHECKPOINT):
        os.remove(_CHECKPOINT)

    size_mb = os.path.getsize(out_file) / 1_048_576
    print(f"Done. Saved {len(all_records):,} contracts -> {out_file}  ({size_mb:.1f} MB)")
    return out_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch all active SAM.gov contracts")
    parser.add_argument("--days",   type=int,  default=90,
                        help="Days back to fetch (default: 90)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume a previous interrupted run")
    args = parser.parse_args()
    fetch_all(days_back=args.days, resume=args.resume)

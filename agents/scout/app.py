"""
Scout agent entry point for William.
Exposes: DESCRIPTION (str) and graph (compiled StateGraph).
"""
from agents.scout.db import init_db
from agents.scout.graphs.discovery import graph

# Create tables and seed default profile on first import — idempotent.
init_db()

DESCRIPTION = (
    "Government contracts bidding platform. Route here when the user wants to search "
    "SAM.gov for federal contract opportunities, find RFPs or solicitations by keyword "
    "or NAICS code, save contract leads to the pipeline, review the opportunity list, "
    "check upcoming deadlines, or update the company targeting profile (keywords, NAICS "
    "codes, set-aside certifications). Maintains a persistent SQLite pipeline with "
    "workflow status tracking (new, reviewing, bid, no_bid, archived)."
)

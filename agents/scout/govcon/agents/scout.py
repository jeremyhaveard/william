from langgraph.prebuilt import create_react_agent
from core.llm import get_llm
from apps.govcon.config import is_enabled, enabled_by_platform
from apps.govcon.prompts.scout import SCOUT_PROMPT
from apps.govcon.tools.db_tools import (
    get_company_profile,
    save_opportunity,
    list_opportunities,
    get_opportunity,
    update_opportunity_status,
    update_company_profile,
    generate_breakdown_report,
)

tools = [
    get_company_profile,
    save_opportunity,
    list_opportunities,
    get_opportunity,
    update_opportunity_status,
    update_company_profile,
    generate_breakdown_report,
]

# Federal
if is_enabled("federal"):
    from apps.govcon.tools.sam_api import search_opportunities, get_opportunity_detail
    tools += [search_opportunities, get_opportunity_detail]

# Florida state
if is_enabled("florida_state"):
    from apps.govcon.tools.florida_vbs import (
        search_florida_bids,
        save_florida_bids_to_json,
        list_florida_organizations,
    )
    tools += [search_florida_bids, save_florida_bids_to_json, list_florida_organizations]

# OpenGov platform (Pinellas County, Clearwater, St. Pete, Tampa, PCSB)
if enabled_by_platform("opengov"):
    from apps.govcon.tools.opengov import search_opengov_bids, save_opengov_bids_to_json
    tools += [search_opengov_bids, save_opengov_bids_to_json]

# Bonfire platform (Hillsborough County, Tarpon Springs)
if enabled_by_platform("bonfire"):
    from apps.govcon.tools.bonfire import search_bonfire_bids, save_bonfire_bids_to_json
    tools += [search_bonfire_bids, save_bonfire_bids_to_json]

# Simple HTML scrapers
if enabled_by_platform("simple"):
    from apps.govcon.tools.safety_harbor import (
        search_safety_harbor_bids,
        save_safety_harbor_bids_to_json,
    )
    tools += [search_safety_harbor_bids, save_safety_harbor_bids_to_json]

scout_agent = create_react_agent(
    model=get_llm(),
    tools=tools,
    prompt=SCOUT_PROMPT,
)

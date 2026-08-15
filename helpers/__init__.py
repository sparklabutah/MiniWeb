"""Generic, project-agnostic utilities.

Everything here is standalone and reusable — no Flask blueprints, no site or
macro domain logic — so the rest of the project can be restructured around it
freely. Import the specific module you need:

    from helpers.llm import LLMClient, call_llm
    from helpers.geo import haversine
    from helpers.security import safe_next
    from helpers.auth import current_user, browsing_user
"""

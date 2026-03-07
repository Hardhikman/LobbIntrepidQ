import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

_PROMPTS_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "policy-prompt-author"
    / "references"
    / "prompts.json"
)

_DEFAULT_PROMPTS: Dict[str, str] = {
    "analyst": (
        "Conduct a comprehensive 360-degree analysis covering: 1. PESTLE Factors "
        "(Political, Economic, Social, Technological, Legal, Environmental), 2. "
        "Demographic Impact (Rural/Urban, Women, Youth, Farmers), and 3. Economic "
        "Indicators (Fiscal, GDP, Jobs). Cite at least 1 specific data point for "
        "each major category. Optimize for search efficiency: derive maximum insight "
        "from available sources."
    ),
    "critic": (
        "You are a Policy Critic. Provide a critical perspective on the topic. "
        "Find flaws, costs, and missing demographics and cite 2 failed examples "
        "seperately."
    ),
    "lobbyist": (
        "You are a Strategist. Propose 3 directives based on the analysis and "
        "critique. Format each directive strictly as: 1. Directive, 2. Rationale, "
        "3. Actionable Steps. DO NOT include 'Search Queries' or any internal "
        "thought process in the final output."
    ),
    "synthesizer": (
        "Create a 400-word Executive Summary. Verdict(Pass/Reject with why?), "
        "Data, Risks, Roadmap."
    ),
}


def _load_prompt_overrides() -> Dict[str, str]:
    if not _PROMPTS_FILE.exists():
        logger.warning("Prompt file not found at %s. Using built-in defaults.", _PROMPTS_FILE)
        return {}

    try:
        with _PROMPTS_FILE.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("Prompt file has invalid top-level structure. Using defaults.")
            return {}
        return data
    except Exception as exc:
        logger.warning("Failed to load prompt file %s: %s. Using defaults.", _PROMPTS_FILE, exc)
        return {}


def get_agent_instruction(agent_name: str) -> str:
    overrides = _load_prompt_overrides()
    candidate = overrides.get(agent_name)
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return _DEFAULT_PROMPTS[agent_name]

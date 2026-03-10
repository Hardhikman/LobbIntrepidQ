import re
from pathlib import Path

import feedparser
import urllib.parse

from google.adk.tools import FunctionTool

from ddgs import DDGS


_SKILLS_ROOT = Path(__file__).resolve().parent / "skills" / "agent-skills"


def _strip_frontmatter(markdown_text: str) -> str:
    markdown_text = markdown_text.lstrip("\ufeff")
    lines = markdown_text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :]).strip()
    return markdown_text.strip()


def load_agent_skill_content(agent_name: str) -> str:
    """Load and parse an agent-specific SKILL.md and return only instruction body."""
    normalized = (agent_name or "").strip().lower()
    skill_file = _SKILLS_ROOT / normalized / "SKILL.md"

    if not skill_file.exists():
        return (
            f"Skill file not found for agent '{normalized}' at {skill_file}. "
            "Proceed with default policy-agent behavior."
        )

    try:
        raw = skill_file.read_text(encoding="utf-8")
        body = _strip_frontmatter(raw)
        return body or f"Skill file for '{normalized}' is empty."
    except Exception as exc:
        return f"Failed to load skill for '{normalized}': {exc}"


def get_agent_skill_tool():
    """Returns a FunctionTool wrapper for loading agent skill content by name."""
    return FunctionTool(load_agent_skill_content)


def extract_skill_keywords(agent_name: str) -> list[str]:
    """Parse the '## Search Keywords' section from a SKILL.md and return keyword lines."""
    normalized = (agent_name or "").strip().lower()
    skill_file = _SKILLS_ROOT / normalized / "SKILL.md"

    if not skill_file.exists():
        return []

    try:
        raw = skill_file.read_text(encoding="utf-8")
        # Find the ## Search Keywords section
        match = re.search(
            r"##\s*Search Keywords\s*\n(.*?)(?=\n##|\Z)",
            raw,
            re.DOTALL,
        )
        if not match:
            return []

        lines = match.group(1).strip().splitlines()
        keywords = []
        for line in lines:
            cleaned = line.strip().lstrip("-").strip()
            if cleaned:
                keywords.append(cleaned)
        return keywords
    except Exception:
        return []


def prefetch_data(topic: str, keywords: list[str], max_results: int = 3) -> str:
    """Run DDGS searches for each topic+keyword combo and return aggregated results."""
    print(f"\n[Pre-fetch] Starting batch search for topic: '{topic}' with {len(keywords)} keyword groups...")
    all_results = []
    seen_urls = set()

    for kw in keywords:
        query = f"{topic} {kw}"
        print(f"[Pre-fetch] Searching: '{query}'")
        try:
            with DDGS() as ddgs:
                results = list(
                    ddgs.text(
                        query=query,
                        region="wt-wt",
                        safesearch="moderate",
                        max_results=max_results,
                    )
                )
            for r in results:
                url = r.get("href") or r.get("url") or ""
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                title = r.get("title", "Untitled")
                body = r.get("body") or r.get("snippet") or "No summary."
                all_results.append(f"Source: {title}\nURL: {url}\nData: {body}")
        except Exception as exc:
            all_results.append(f"Search failed for '{query}': {exc}")

    result_text = "\n\n".join(all_results) if all_results else "No data found."
    print(f"[Pre-fetch] Collected {len(all_results)} unique results.")
    return result_text


def prefetch_rss_news(topic: str) -> str:
    """Pre-fetch Google News RSS for the topic."""
    print(f"\n[RSS Pre-fetch] Fetching news for: '{topic}'...")
    try:
        encoded = urllib.parse.quote(topic)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(rss_url)
        context = []
        for entry in feed.entries[:5]:
            context.append(f"Title: {entry.title}\nLink: {entry.link}\nPublished: {entry.published}")
        result = "\n\n".join(context) if context else "No news found."
        print(f"[RSS Pre-fetch] Found {len(context)} news items.")
        return result
    except Exception as exc:
        return f"RSS fetch failed: {exc}"


def get_ddgs_search_tool(max_results=3, region="wt-wt", safesearch="moderate"):
    """Returns a FunctionTool configured to use DuckDuckGo search via DDGS."""

    def fetch_policy_data(query: str) -> str:
        """
        Searches the web for real-time data, statistics, and news about the policy.
        ALWAYS use this to get facts before answering.
        """
        print(f"\n[DDGS Tool] Searching for: '{query}'...")
        try:
            with DDGS() as ddgs:
                results = list(
                    ddgs.text(
                        query=query,
                        region=region,
                        safesearch=safesearch,
                        max_results=max_results,
                    )
                )

            context = []
            for result in results:
                title = result.get("title", "Untitled")
                url = result.get("href") or result.get("url") or "N/A"
                content = result.get("body") or result.get("snippet") or "No summary available."
                context.append(f"Source: {title}\nURL: {url}\nData: {content}")

            result_text = "\n\n".join(context) if context else "No results found."
            print(f"[DDGS Tool] Found {len(context)} results.")
            return result_text
        except Exception as exc:
            error_msg = f"Error during search: {str(exc)}"
            print(f"[DDGS Tool] Failed: {error_msg}")
            return error_msg

    return FunctionTool(fetch_policy_data)


def get_rss_tool():
    """Returns a FunctionTool that fetches Google News RSS feeds."""

    def search_rss_news(query: str) -> str:
        """Searches Google News RSS for recent news, public sentiment, and controversies."""
        print(f"\n[RSS Tool] Fetching news for: '{query}'...")
        try:
            encoded_query = urllib.parse.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"

            feed = feedparser.parse(rss_url)
            context = []
            for entry in feed.entries[:5]:
                context.append(f"Title: {entry.title}\nLink: {entry.link}\nPublished: {entry.published}")

            result_text = "\n\n".join(context) if context else "No news found."
            print(f"[RSS Tool] Found {len(context)} news items.")
            return result_text
        except Exception as exc:
            error_msg = f"Error fetching RSS: {str(exc)}"
            print(f"[RSS Tool] Failed: {error_msg}")
            return error_msg

    return FunctionTool(search_rss_news)

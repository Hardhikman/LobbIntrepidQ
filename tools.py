import re
from pathlib import Path

import feedparser
import urllib.parse
import requests
from bs4 import BeautifulSoup

from google.adk.tools import FunctionTool

from ddgs import DDGS


# --- Trusted Source Domains ---
# Each keyword is searched against each domain separately (1 result per domain).
TRUSTED_DOMAINS = [
    "thehindu.com",
    "indianexpress.com",
]

# Browser-like headers for article fetching
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}



# Regex pattern for statistics: numbers, percentages, currency (Rs, ₹, crore, lakh, $, billion)
_STATS_PATTERN = re.compile(
    r"(?:Rs\.?|₹|\$)\s*[\d,]+|"       # Currency values
    r"[\d,]+\s*(?:crore|lakh|billion|million|trillion)|"  # Large numbers
    r"\d+\.?\d*\s*%|"                  # Percentages
    r"\b\d{4}\b|"                       # Years (2024, 1990, etc.)
    r"\b[\d,]+\.?\d*\b",               # General numbers
    re.IGNORECASE
)


def _score_and_filter_sentences(text: str, topic: str, top_n: int = 5) -> str:
    """Score sentences by topic relevance + data richness, return top N.
    Score = (keyword matches × 2) + (statistics/number matches × 3)"""
    # Build keyword set from topic
    topic_words = set(w.lower() for w in re.findall(r'\w+', topic) if len(w) > 2)

    # Split into sentences (rough split by period, exclamation, question mark)
    sentences = re.split(r'(?<=[.!?])\s+', text)

    scored = []
    for sent in sentences:
        if len(sent.strip()) < 30:
            continue
        sent_lower = sent.lower()

        # Keyword score: count how many topic words appear
        keyword_hits = sum(1 for w in topic_words if w in sent_lower)

        # Stats score: count statistics/numbers found
        stats_hits = len(_STATS_PATTERN.findall(sent))

        score = (keyword_hits * 2) + (stats_hits * 3)
        scored.append((score, sent))

    # Sort by score descending, keep top N
    scored.sort(key=lambda x: x[0], reverse=True)
    top_sentences = [sent for score, sent in scored[:top_n] if score > 0]

    return " ".join(top_sentences) if top_sentences else text[:800]


def _extract_article_text(url: str, topic: str = "", max_chars: int = 2000) -> str:
    """Fetch a URL, extract article text, and filter to most relevant sentences.
    Returns scored/filtered text, or empty string on failure."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=8)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove unwanted elements
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
            tag.decompose()

        # Try common article containers first
        article = (
            soup.find("article")
            or soup.find("div", class_=re.compile(r"article|story|content|post", re.I))
            or soup.find("main")
        )
        target = article if article else soup.body
        if not target:
            return ""

        # Extract and clean text
        paragraphs = target.find_all("p")
        raw_text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
        if not raw_text:
            return ""

        # Score and filter sentences if topic is provided
        if topic:
            filtered = _score_and_filter_sentences(raw_text, topic)
        else:
            filtered = raw_text[:max_chars]

        return filtered.strip()
    except Exception:
        return ""


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


def prefetch_data(topic: str, keywords: list[str]) -> str:
    """For each keyword, search each TRUSTED_DOMAIN separately (1 result per domain).
    Extract full article text from each URL."""
    total_searches = len(keywords) * len(TRUSTED_DOMAINS)
    print(f"\n[Pre-fetch] Starting search: {len(keywords)} keywords × {len(TRUSTED_DOMAINS)} domains = {total_searches} searches...")
    all_results = []
    seen_urls = set()

    for kw in keywords:
        for domain in TRUSTED_DOMAINS:
            query = f"{topic} {kw} site:{domain}"
            print(f"[Pre-fetch] [{domain}] '{topic} {kw}'")
            try:
                with DDGS() as ddgs:
                    results = list(
                        ddgs.text(
                            query=query,
                            region="wt-wt",
                            safesearch="moderate",
                            max_results=1,
                        )
                    )
                for r in results:
                    url = r.get("href") or r.get("url") or ""
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    title = r.get("title", "Untitled")
                    snippet = r.get("body") or r.get("snippet") or "No summary."

                    # Extract and filter article text
                    article_text = _extract_article_text(url, topic=topic)
                    body = article_text if article_text else snippet

                    all_results.append(f"Source: {title}\nURL: {url}\nData: {body}")
            except Exception as exc:
                print(f"[Pre-fetch] [{domain}] Search failed: {exc}")

    result_text = "\n\n".join(all_results) if all_results else "No data found."
    print(f"[Pre-fetch] Collected {len(all_results)} unique articles.")
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
    """Returns a FunctionTool configured to use DuckDuckGo search via DDGS.
    Searches each TRUSTED_DOMAIN separately."""

    def fetch_policy_data(query: str) -> str:
        """
        Searches the web for real-time data, statistics, and news about the policy.
        ALWAYS use this to get facts before answering.
        """
        print(f"\n[DDGS Tool] Searching for: '{query}'...")
        context = []
        for domain in TRUSTED_DOMAINS:
            try:
                full_query = f"{query} site:{domain}"
                with DDGS() as ddgs:
                    results = list(
                        ddgs.text(
                            query=full_query,
                            region=region,
                            safesearch=safesearch,
                            max_results=max_results,
                        )
                    )

                for result in results:
                    title = result.get("title", "Untitled")
                    url = result.get("href") or result.get("url") or "N/A"
                    content = result.get("body") or result.get("snippet") or "No summary available."
                    context.append(f"Source: {title}\nURL: {url}\nData: {content}")
            except Exception as exc:
                print(f"[DDGS Tool] [{domain}] Failed: {exc}")

        result_text = "\n\n".join(context) if context else "No results found."
        print(f"[DDGS Tool] Found {len(context)} results.")
        return result_text

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

#!/usr/bin/env python3
"""Builds a weekly combined RSS feed covering AI security news and AI
protocol changes (MCP, A2A) from a curated set of sources.

Run weekly by .github/workflows/weekly-digest.yml. Writes docs/feed.xml
(served by GitHub Pages) and docs/index.html (human-readable view).
"""
import re
import sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import feedparser
import requests
from feedgen.feed import FeedGenerator

FEED_TITLE = "AI Security & Protocol Weekly Digest"
FEED_LINK = "https://cchilson13.github.io/ai-security-digest/"
FEED_DESCRIPTION = (
    "Weekly digest of AI security news and AI protocol changes "
    "(MCP, A2A) from Anthropic, OpenAI, DeepMind, and security researchers."
)

# How far back to look each run. The workflow runs weekly, but a wider
# window guards against a missed/delayed run still catching everything.
LOOKBACK_DAYS = 9
MAX_ITEMS_PER_SOURCE = 8
USER_AGENT = "Mozilla/5.0 (compatible; ai-security-digest/1.0)"

# Security/protocol-specific signal. Matched as substrings (all multi-word
# or long enough to avoid false hits).
NARROW_PHRASE_KEYWORDS = [
    "model context protocol", "agent2agent", "agent-to-agent",
    "prompt injection", "jailbreak", "red team", "red-team", "redteam",
    "adversarial", "guardrail", "safeguard", "data poisoning",
    "model extraction", "supply chain", "exploit", "vulnerability",
    "breach", "deepfake", "alignment", "misuse", "incident",
    "safety", "security",
]

# Security/protocol-specific signal that's ambiguous as a raw substring
# (e.g. "mcp" inside another word), so matched as whole words only.
NARROW_WORD_KEYWORDS = ["mcp", "a2a", "cve"]

# Generic AI-topic signal. Only useful for sources that AREN'T already
# 100% about AI (e.g. a general security blog) -- for AI-dedicated
# sources (OpenAI's own blog, an "AI" news section, etc.) nearly every
# post would match these, so they add no filtering signal there.
GENERIC_AI_WORD_KEYWORDS = ["ai", "llm", "claude", "gemini", "gpt", "chatgpt"]
GENERIC_AI_PHRASE_KEYWORDS = [
    "openai", "anthropic", "artificial intelligence", "machine learning",
]

NARROW_WORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in NARROW_WORD_KEYWORDS) + r")\b"
)
GENERIC_AI_WORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in GENERIC_AI_WORD_KEYWORDS) + r")\b"
)

# type "feed": parsed with feedparser (RSS or Atom)
# type "anthropic": custom scraper for anthropic.com/news (no RSS available)
# filter=False: keep every recent entry (source is a protocol changelog --
#   everything it publishes is in-scope by definition)
# filter=True, broad=False: source is already AI-dedicated (an AI company's
#   blog, an "AI" news vertical) -- require the narrow security/protocol
#   keywords, since a bare "AI" mention matches nearly every post there
# filter=True, broad=True: source covers many unrelated topics -- a bare
#   AI mention is itself notable, so also match on generic AI keywords
SOURCES = [
    {"name": "Anthropic", "type": "anthropic",
     "url": "https://www.anthropic.com/news", "filter": True, "broad": False},
    {"name": "OpenAI", "type": "feed",
     "url": "https://openai.com/news/rss.xml", "filter": True, "broad": False},
    {"name": "Model Context Protocol", "type": "feed",
     "url": "https://github.com/modelcontextprotocol/modelcontextprotocol/releases.atom",
     "filter": False, "broad": False},
    {"name": "A2A Protocol", "type": "feed",
     "url": "https://github.com/a2aproject/A2A/releases.atom", "filter": False, "broad": False},
    {"name": "Google DeepMind", "type": "feed",
     "url": "https://deepmind.google/blog/rss.xml", "filter": True, "broad": False},
    {"name": "Schneier on Security", "type": "feed",
     "url": "https://www.schneier.com/feed/atom/", "filter": True, "broad": True},
    {"name": "Simon Willison", "type": "feed",
     "url": "https://simonwillison.net/atom/everything/", "filter": True, "broad": False},
    {"name": "Ars Technica AI", "type": "feed",
     "url": "https://arstechnica.com/ai/feed/", "filter": True, "broad": False},
]


def matches_keywords(text, broad):
    text = text.lower()
    if any(kw in text for kw in NARROW_PHRASE_KEYWORDS):
        return True
    if NARROW_WORD_RE.search(text):
        return True
    if broad:
        if any(kw in text for kw in GENERIC_AI_PHRASE_KEYWORDS):
            return True
        if GENERIC_AI_WORD_RE.search(text):
            return True
    return False


def fetch_feed_entries(source):
    resp = requests.get(source["url"], headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    entries = []
    for entry in parsed.entries:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if not published:
            continue
        published_dt = datetime(*published[:6], tzinfo=timezone.utc)
        title = entry.get("title", "").strip()
        summary = entry.get("summary", "") or entry.get("description", "")
        entries.append({
            "title": title,
            "link": entry.get("link", ""),
            "summary": summary,
            "published": published_dt,
            "source": source["name"],
        })
    return entries


ANTHROPIC_ITEM_RE = re.compile(
    r'<a href="(?P<href>/news/[^"]+)" class="[^"]*listItem[^"]*">'
    r'.*?<time[^>]*>(?P<date>[^<]+)</time>'
    r'.*?<span class="[^"]*subject[^"]*"[^>]*>(?P<category>[^<]*)</span>'
    r'.*?<span class="[^"]*title[^"]*"[^>]*>(?P<title>[^<]*)</span>',
    re.S,
)


def fetch_anthropic_entries(source):
    resp = requests.get(source["url"], headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    html = resp.text
    entries = []
    for m in ANTHROPIC_ITEM_RE.finditer(html):
        try:
            published_dt = datetime.strptime(m.group("date").strip(), "%b %d, %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        entries.append({
            "title": m.group("title").strip(),
            "link": "https://www.anthropic.com" + m.group("href"),
            "summary": m.group("category").strip(),
            "published": published_dt,
            "source": source["name"],
        })
    return entries


def collect_entries():
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    all_entries = []
    for source in SOURCES:
        try:
            if source["type"] == "anthropic":
                entries = fetch_anthropic_entries(source)
            else:
                entries = fetch_feed_entries(source)
        except Exception as exc:
            print(f"WARNING: failed to fetch {source['name']}: {exc}", file=sys.stderr)
            continue

        entries = [e for e in entries if e["published"] >= cutoff]
        if source["filter"]:
            entries = [e for e in entries if matches_keywords(e["title"] + " " + e["summary"], source["broad"])]
        entries.sort(key=lambda e: e["published"], reverse=True)
        entries = entries[:MAX_ITEMS_PER_SOURCE]

        print(f"{source['name']}: {len(entries)} item(s)")
        all_entries.extend(entries)

    all_entries.sort(key=lambda e: e["published"], reverse=True)
    return all_entries


def build_feed(entries):
    fg = FeedGenerator()
    fg.title(FEED_TITLE)
    fg.link(href=FEED_LINK, rel="alternate")
    fg.description(FEED_DESCRIPTION)
    fg.language("en")

    for e in entries:
        fe = fg.add_entry()
        fe.title(f"[{e['source']}] {e['title']}")
        fe.link(href=e["link"])
        fe.guid(e["link"], permalink=True)
        fe.description(e["summary"])
        fe.pubDate(format_datetime(e["published"]))

    return fg


def build_index_html(entries):
    rows = []
    for e in entries:
        date_str = e["published"].strftime("%Y-%m-%d")
        rows.append(
            f'<li><span class="date">{date_str}</span> '
            f'<span class="source">{e["source"]}</span> '
            f'<a href="{e["link"]}">{e["title"]}</a></li>'
        )
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{FEED_TITLE}</title>
<link rel="alternate" type="application/rss+xml" title="{FEED_TITLE}" href="feed.xml">
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; color: #222; }}
h1 {{ font-size: 1.4rem; }}
ul {{ list-style: none; padding: 0; }}
li {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
.date {{ color: #888; font-size: 0.85rem; margin-right: 8px; }}
.source {{ font-weight: 600; margin-right: 8px; }}
a {{ color: #0645ad; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
footer {{ margin-top: 24px; color: #888; font-size: 0.8rem; }}
</style>
</head>
<body>
<h1>{FEED_TITLE}</h1>
<p>Subscribe to the <a href="feed.xml">RSS feed</a>. Rebuilt every Monday.</p>
<ul>
{''.join(rows)}
</ul>
<footer>Last built {updated}</footer>
</body>
</html>
"""


def main():
    entries = collect_entries()
    print(f"Total entries: {len(entries)}")

    fg = build_feed(entries)
    fg.rss_file("docs/feed.xml", pretty=True)

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(build_index_html(entries))


if __name__ == "__main__":
    main()

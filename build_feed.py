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

# Every source we filter is already guaranteed to be about ONE of the two
# halves of "AI security" -- an AI-dedicated source (OpenAI's blog, an "AI"
# news vertical) is guaranteed to be about AI, and a security-dedicated
# source (Krebs, Unit 42, a "Security" blog) is guaranteed to be about
# security. So instead of requiring generic "security" words (which are
# trivially present in a security blog's own name/boilerplate -- e.g.
# "krebsonsecurity" -- and would match almost every post there), we only
# require the signal for the OTHER half: AI-dedicated sources need a
# SECURITY keyword to narrow down to security-relevant posts, and
# security-dedicated sources need an AI keyword to narrow down to
# AI-relevant posts.

# Indicates the SECURITY half. Checked for sources where AI is already
# guaranteed (broad=False).
SECURITY_PHRASE_KEYWORDS = [
    "prompt injection", "jailbreak", "red team", "red-team", "redteam",
    "adversarial", "guardrail", "safeguard", "data poisoning",
    "model extraction", "supply chain", "exploit", "vulnerability",
    "breach", "deepfake", "alignment", "misuse", "incident",
    "safety", "security",
]
SECURITY_WORD_KEYWORDS = ["cve"]

# Indicates the AI half. Checked for sources where security is already
# guaranteed (broad=True).
AI_PHRASE_KEYWORDS = [
    "model context protocol", "agent2agent", "agent-to-agent",
    "artificial intelligence", "machine learning", "openai", "anthropic",
    "ai agent", "agentic",
]
AI_WORD_KEYWORDS = ["ai", "llm", "mcp", "a2a", "claude", "gemini", "gpt", "chatgpt"]

SECURITY_WORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in SECURITY_WORD_KEYWORDS) + r")\b"
)
AI_WORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in AI_WORD_KEYWORDS) + r")\b"
)

# type "feed": parsed with feedparser (RSS or Atom)
# type "anthropic": custom scraper for anthropic.com/news (no RSS available)
# filter=False: keep every recent entry (source is a protocol changelog --
#   everything it publishes is in-scope by definition)
# filter=True, broad=False: source is already AI-dedicated (an AI company's
#   blog, an "AI" news vertical) -- require the narrow security/protocol
#   keywords, since a bare "AI" mention matches nearly every post there
# filter=True, broad=False: source is already AI-dedicated (an AI
#   company's blog, an "AI" news vertical) -- require a SECURITY keyword
#   to narrow down to security/protocol-relevant posts
# filter=True, broad=True: source is already security-dedicated (a
#   "Security" blog, an infosec news outlet) -- require an AI keyword to
#   narrow down to AI-relevant posts
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
    {"name": "AWS Security Blog", "type": "feed",
     "url": "https://aws.amazon.com/blogs/security/feed/", "filter": True, "broad": True},
    {"name": "AWS Machine Learning Blog", "type": "feed",
     "url": "https://aws.amazon.com/blogs/machine-learning/feed/", "filter": True, "broad": False},
    {"name": "Google Security Blog", "type": "feed",
     "url": "https://security.googleblog.com/feeds/posts/default", "filter": True, "broad": True},
    {"name": "Krebs on Security", "type": "feed",
     "url": "https://krebsonsecurity.com/feed/", "filter": True, "broad": True},
    {"name": "The Hacker News", "type": "feed",
     "url": "https://feeds.feedburner.com/TheHackersNews", "filter": True, "broad": True},
    {"name": "Unit 42", "type": "feed",
     "url": "https://unit42.paloaltonetworks.com/feed/", "filter": True, "broad": True},
    {"name": "Ars Technica Security", "type": "feed",
     "url": "https://arstechnica.com/security/feed/", "filter": True, "broad": True},
    {"name": "Embrace The Red", "type": "feed",
     "url": "https://embracethered.com/blog/index.xml", "filter": False, "broad": False},
    {"name": "Auth0 Blog", "type": "feed",
     "url": "https://auth0.com/blog/rss.xml", "filter": True, "broad": True},
    {"name": "WorkOS Blog", "type": "feed",
     "url": "https://workos.com/blog/rss.xml", "filter": True, "broad": True},
    {"name": "Aembit Blog", "type": "feed",
     "url": "https://aembit.io/feed/", "filter": True, "broad": True},
    {"name": "Christian Posta", "type": "feed",
     "url": "https://blog.christianposta.com/feed.xml", "filter": False, "broad": False},
]


def matches_keywords(text, broad):
    text = text.lower()
    if broad:
        # Source is already security-dedicated; require an AI signal.
        if any(kw in text for kw in AI_PHRASE_KEYWORDS):
            return True
        return bool(AI_WORD_RE.search(text))
    else:
        # Source is already AI-dedicated; require a security signal.
        if any(kw in text for kw in SECURITY_PHRASE_KEYWORDS):
            return True
        return bool(SECURITY_WORD_RE.search(text))


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

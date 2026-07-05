# AI Security & Protocol Weekly Digest

A weekly RSS feed of AI security news and AI protocol changes (MCP, A2A),
pulled from a curated set of sources and rebuilt automatically every Monday.

**Feed:** https://cchilson13.github.io/ai-security-digest/feed.xml
**Page:** https://cchilson13.github.io/ai-security-digest/

## Sources

- Anthropic news
- OpenAI news
- Model Context Protocol (release changelog)
- A2A Protocol (release changelog)
- Google DeepMind blog
- Schneier on Security
- Simon Willison's blog
- Ars Technica – AI

Anthropic, OpenAI, DeepMind, and Ars Technica's AI section are filtered to
security/safety/protocol-relevant posts (`build_feed.py`'s `NARROW_*`
keywords) since most of what they publish isn't security news. Schneier's
blog is filtered more loosely since it's a general security blog where any
AI mention is notable. The MCP and A2A changelogs are never filtered —
every release is in scope.

## How it runs

`.github/workflows/weekly-digest.yml` runs `build_feed.py` every Monday
(and on manual dispatch), regenerating `docs/feed.xml` and `docs/index.html`
and committing them if changed. GitHub Pages serves the `docs/` folder.

## Running locally

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build_feed.py
```

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
- AWS Security Blog
- AWS Machine Learning Blog
- Google Security Blog
- Krebs on Security
- The Hacker News
- Unit 42 (Palo Alto Networks)
- Ars Technica – Security
- Embrace The Red
- Auth0 Blog
- WorkOS Blog
- Aembit Blog (non-human/workload identity)
- Christian Posta's blog (agent identity, MCP/agent auth)

AI-dedicated sources (Anthropic, OpenAI, DeepMind, AWS Machine Learning
Blog, Simon Willison, Ars Technica's AI section) are filtered down to
security/protocol-relevant posts, since most of what they publish isn't
security news. Security/identity-dedicated sources (Schneier, AWS Security
Blog, Google Security Blog, Krebs, The Hacker News, Unit 42, Ars
Technica's Security section, Auth0, WorkOS, Aembit) are filtered down to
AI-relevant posts, since most of what they publish isn't AI news. The
MCP/A2A changelogs, Embrace The Red (a blog specifically about AI agent
security), and Christian Posta's blog (currently posting almost
exclusively about agent identity/MCP auth) are never filtered — everything
they publish is already in scope. See `AGENTS.md` for details on the
filter design.

Agent identity / agent auth is a fast-moving, mostly pre-standardization
space right now (IETF has several competing OAuth-for-agents drafts —
`draft-oauth-ai-agents-on-behalf-of-user`, AAuth, WIMSE — with no settled
winner yet, and no clean RSS feed for IETF draft activity). Auth0, WorkOS,
Aembit, and Christian Posta's blog are the best proxies currently available
for surfacing that activity as it happens.

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

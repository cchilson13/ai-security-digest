# AGENTS.md

Instructions for an AI agent (or future you) maintaining this repo.

## What this is

A weekly RSS digest of AI security news and AI protocol changes (MCP, A2A).
`build_feed.py` fetches a curated list of sources, filters entries for
relevance, and writes `docs/feed.xml` + `docs/index.html`. GitHub Pages
serves `docs/` at https://cchilson13.github.io/ai-security-digest/.
`.github/workflows/weekly-digest.yml` runs the script every Monday 13:00 UTC,
commits the regenerated files if changed, and deploys them to Pages.

## Adding a new source

Add an entry to the `SOURCES` list in `build_feed.py`:

```python
{"name": "Display Name", "type": "feed", "url": "https://.../feed.xml",
 "filter": True, "broad": False},
```

- `type`: `"feed"` for anything `feedparser` can parse (RSS or Atom — this
  covers almost everything, including GitHub release feeds via
  `<owner>/<repo>/releases.atom`). Use `"anthropic"` only for the one
  custom HTML scraper (see below) — don't add more scrapers unless a
  source truly has no feed anywhere; check thoroughly first (many sites
  have an undocumented `/feed`, `/rss.xml`, or `/atom.xml` even without a
  visible link).
- `filter`: `False` only for sources where *everything* published is
  already in scope (e.g. a protocol's release changelog). `True` for
  everything else.
- `broad`: only matters when `filter: True`. Every filtered source is
  guaranteed to already be about ONE half of "AI security" — either the
  AI half (a model lab's blog, an "AI" news vertical) or the security half
  (a "Security" blog, an infosec news outlet) — so the filter only needs
  to check for the OTHER half.
  - `broad: False` — the source is already AI-dedicated. Requires a
    `SECURITY_PHRASE_KEYWORDS` / `SECURITY_WORD_KEYWORDS` match to narrow
    down to security/protocol-relevant posts.
  - `broad: True` — the source is already security-dedicated. Requires an
    `AI_PHRASE_KEYWORDS` / `AI_WORD_KEYWORDS` match to narrow down to
    AI-relevant posts.

  Do NOT require a generic "security" word match for a security-dedicated
  source, or a generic "AI" word match for an AI-dedicated source — both
  are near-guaranteed to appear in that source's own boilerplate/branding
  (e.g. "krebsonsecurity" literally contains "security" as a substring,
  which silently defeated the filter for every Krebs post until this was
  caught and fixed) and add no actual filtering signal.

After adding a source, test locally (see below) and sanity-check which
entries it actually contributes — if a source is producing 0 items every
week, check whether `broad` is set correctly, or a keyword is missing. If
a source is producing noise (irrelevant items), tighten the keyword lists
rather than dropping the source, and specifically check *why* it matched
(print the matched keyword and surrounding text) before assuming it's a
false positive — some surprising matches are genuinely relevant (e.g. a
generic Linux kernel CVE story that mentioned an Anthropic model finding
the bug).

## Removing or tightening a noisy keyword

`SECURITY_PHRASE_KEYWORDS` / `AI_PHRASE_KEYWORDS` are matched as raw
substrings — only put words there that are long/specific enough not to
false-positive inside unrelated words (e.g. "vulnerability" is safe, "risk"
is not — it matched inside an unrelated word during testing and was
removed). Short or ambiguous tokens (`mcp`, `a2a`, `cve`, `ai`, `llm`, etc.)
belong in the `*_WORD_KEYWORDS` lists instead, which are matched with regex
word boundaries (`\b`) so they don't match as substrings of other words.

## Testing locally

```
cd /Users/cameronchilson/ai-security-digest
python3 -m venv .venv   # if not already created
.venv/bin/pip install -r requirements.txt
.venv/bin/python build_feed.py
```

This prints a per-source item count and writes `docs/feed.xml` /
`docs/index.html`. Inspect the output before committing — e.g.:

```
.venv/bin/python -c "
import feedparser
for e in feedparser.parse('docs/feed.xml').entries:
    print('-', e.title)
"
```

## Deploying changes

Just commit and push to `main` — the workflow triggers on push (and on the
Monday schedule, and via `gh workflow run weekly-digest.yml -R
cchilson13/ai-security-digest` for manual runs). It commits the regenerated
`docs/` files back to `main` itself if they changed, then deploys to Pages
via `actions/upload-pages-artifact` + `actions/deploy-pages`.

Check a run with:
```
gh run list -R cchilson13/ai-security-digest --limit 5
gh run view --log -R cchilson13/ai-security-digest <run-id>
```

## Known gotchas

- **Pages `build_type` must be `"workflow"`, not `"legacy"`.** When this
  repo was first set up, Pages was configured via `gh api .../pages -X
  POST -f 'source[branch]=main' -f 'source[path]=/docs'`, which defaults to
  `build_type: legacy`. That triggered GitHub's *separate*, hidden
  `pages-build-deployment` workflow, which failed repeatedly with a
  generic "Deployment failed, try again later" error — unrelated to
  anything in this repo. Fix was `gh api repos/cchilson13/ai-security-digest/pages
  -X PUT -f 'build_type=workflow'`, so Pages deploys are driven entirely by
  our own workflow's `actions/deploy-pages` step instead. If Pages ever
  starts failing mysteriously again, verify `build_type` is still
  `"workflow"`: `gh api repos/cchilson13/ai-security-digest/pages --jq
  .build_type`.
- **The Anthropic source has no RSS feed.** `fetch_anthropic_entries()`
  regex-scrapes `anthropic.com/news`'s server-rendered HTML (see
  `ANTHROPIC_ITEM_RE`), matching on CSS class name fragments like
  `*listItem*`, `*date*`, `*subject*`, `*title*` (Anthropic's site uses
  hashed CSS module class names, so exact-match won't survive a rebuild,
  but the fragments should). If this source silently drops to 0 items,
  Anthropic likely redesigned the page — refetch
  `https://www.anthropic.com/news`, inspect the HTML around a `/news/`
  link, and update the regex.
- **Dependabot is enabled** and will open PRs for `feedparser` / `feedgen`
  / `requests` version bumps — safe to merge, this script has no
  security-sensitive dependency surface beyond fetching public feeds over
  HTTPS.
- **`LOOKBACK_DAYS = 9`** (not 7) is intentional slack in case a Monday run
  is delayed or misses — don't shrink it below ~8 or a delayed run could
  skip items.

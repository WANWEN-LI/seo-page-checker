# Listing & Page SEO Checker

**Paste a URL, get a 0–100 score with prioritised fixes for technical SEO, mobile performance and conversion — each issue says what was found, why it matters and how to fix it.**

> Status: work in progress (stage 2 of 4). Screenshots, HTML reports, before/after comparison, UI and AI suggestions are coming in later stages.

## Install

```bash
git clone <repo-url> seo-page-checker && cd seo-page-checker
python3 -m venv .venv && source .venv/bin/activate   # Python 3.11+
pip install -r requirements.txt
cp .env.example .env   # then add your PAGESPEED_API_KEY
```

## Usage

```bash
python -m seo_checker https://example.com/ --keyword "ceramic vase" --page-type product --out report.json
```

| Flag | Meaning |
|---|---|
| `--keyword` | target search term; enables keyword checks |
| `--page-type` | `product`, `landing` or `portfolio`; selects the trust signals that are expected |
| `--no-psi` | skip the PageSpeed Insights call |
| `--no-link-check` | skip broken-link requests |
| `--out` | write the raw JSON report to a file |

## What it checks

**Technical** (requests + BeautifulSoup): title (present, 30–60 chars, keyword), meta description (70–160 chars), exactly one H1, heading levels not skipped, image alt coverage, canonical, robots meta (noindex), `lang`, Open Graph and Twitter tags, JSON-LD (valid, which `@type`s), internal/external link counts, broken links (4xx, first 50 links), robots.txt, sitemap.xml.

**Performance** (Google PageSpeed Insights API, mobile): Lighthouse Performance, Accessibility and SEO scores; Core Web Vitals LCP, CLS, INP. Real-user (CrUX) field data is used when Google has it, for the page first, then the origin; otherwise lab values from Lighthouse are shown and labelled as lab. INP has no lab equivalent, so it shows as "not checked" when no field data exists.

**Content & Conversion** (listing-optimisation heuristics):
- Value proposition: the H1 appears in the opening section, with supporting copy
- Call to action in the opening section: a button or link with an action verb (nav links don't count)
- Keyword placement in the title, the H1 and the first paragraph
- Readability: words per sentence, paragraph length, Flesch reading ease
- Trust signals by page type:
  - product: price, reviews, shipping and returns, Product schema
  - landing: social proof, contact
  - portfolio: contact, evidence of work, Person schema

## Scoring rules

The rules live in [`seo_checker/scoring.py`](seo_checker/scoring.py); this section mirrors them.

**Points per check:** pass = 1, warn = 0.5, fail = 0. Checks marked `info` or `not_checked` (for example no keyword given, or too little text to judge readability) are left out entirely, so they neither help nor hurt.

**Technical and Content & Conversion:** `score = 100 × Σ(weight × points) / Σ(weight of scored checks)`

| Technical check | Weight | | Content check | Weight |
|---|---|---|---|---|
| Title length / present | 3 | | Value proposition above the fold | 3 |
| Single H1 | 3 | | CTA above the fold | 3 |
| Robots meta (no noindex) | 3 | | Keyword placement | 2 |
| Broken links | 3 | | Readability | 1 |
| Keyword in title | 2 | | Price visible (product) | 3 |
| Meta description | 2 | | Contact path (portfolio, landing) | 3 |
| Image alt text | 2 | | Reviews, shipping & returns, social proof, evidence of work | 2 |
| Canonical | 2 | | Product / Person schema | 1 |
| JSON-LD | 2 | | | |
| sitemap.xml | 2 | | | |
| Heading hierarchy, lang, OG, Twitter card, robots.txt | 1 | | | |

**Performance:** `0.6 × Lighthouse Performance + 0.2 × Accessibility + 0.2 × Lighthouse SEO` (mobile). Core Web Vitals appear as issues but are not scored on top: the Performance score already includes lab LCP and CLS.

**Total:** `0.4 × Technical + 0.3 × Performance + 0.3 × Content & Conversion`. When a category is N/A (for example PageSpeed cannot test a localhost URL), the remaining weights are rescaled to add up to 100% and the report says so. The tool never fills in a missing score.

**Severity** (High / Medium / Low) is shown on every issue to rank fixes. It is separate from the weight above.

## Responsible crawling

- Reads robots.txt and skips any URL it disallows. A robots.txt that returns 5xx or can't be reached means "don't crawl", per RFC 9309.
- Waits at least 1 second between requests to the same host. Requests time out after 10 s.
- Sends no cookies or credentials, so it only sees public pages. A 401 or 403 is reported as "not public", and the tool doesn't try to get past it.
- Checks only the URLs you give it, plus the links on those pages (at most 50 per page). It does not crawl whole sites.

## Limitations

- **No JavaScript rendering.** The tool sees the server-sent HTML. Content injected by JS (for example image galleries loaded from a data file) is invisible to it, and to some crawlers as well.
- **"Above the fold" is approximated** as the first 1,500 characters of visible text, because the page is not rendered at a real viewport size.
- **Readability formulas are for English.**
- **PageSpeed Insights only tests public URLs.** Local or staging pages get Performance = N/A.
- **Without a PageSpeed API key**, Google rate-limits anonymous requests (HTTP 429 seen in testing).
- **Heuristics, not ground truth:** CTA, price and review detection uses keyword and pattern matching, so false positives and negatives are possible.
- **Out of scope:** keyword search volume, backlinks and rankings, which need paid data. See "Planned".

## Tests

```bash
python -m pytest
```

## License

MIT

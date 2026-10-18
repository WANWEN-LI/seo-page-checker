# Case study: Page SEO & Conversion Checker

**Wanwen Li · October 2026 · [Code](https://github.com/WANWEN-LI/seo-page-checker) · [Demo and reports](https://liwanwen.com/seo-checker/)**

## 1. The problem

After five years in Amazon e-commerce (two years employed, three running my own stores), I know that a listing wins or loses on details: a title that says what it is, a clear offer, a visible price, reviews and an obvious next step. The same holds for any page that has to rank and convert, including my own portfolio.

Free audit tools usually give a score without saying how it was calculated, mix SEO with unrelated advice, and can't show whether a fix actually helped. I wanted a tool that:

- checks the things that matter for a listing, a landing page or a portfolio page;
- explains every score with published rules;
- says what it found, why it matters and how to fix it for each issue;
- re-checks the page after a fix and shows what changed, using measured numbers only.

## 2. What I built

A Python tool with a Streamlit interface and a command line:

- **Fetching:** `requests` and BeautifulSoup. It reads robots.txt first, waits at least one second between requests to the same site, and only reads public pages.
- **Speed:** the Google PageSpeed Insights API (mobile Lighthouse and Core Web Vitals).
- **Score:** a 0–100 score from three categories. Each check has a weight of 3, 2 or 1, and all the weights are in the README.
- **Reports:** a shareable HTML report plus the raw JSON. Every run is saved, so two runs of the same page can be compared check by check.
- **AI suggestions (optional):** Claude rewrites the title and meta description and ranks fixes, but each suggestion must cite one of the failing checks. This part is unit-tested with a mocked client; I haven't run it against the live API in this project.
- **Tests:** 59 unit tests.

## 3. What it checks, and why

| Area | Checks | Why it matters |
|---|---|---|
| Technical SEO | title length and keyword, meta description, a single H1, heading order, image alt text, canonical, robots meta, `lang`, Open Graph and Twitter tags, JSON-LD, broken links, robots.txt, sitemap | These are what search engines and link previews read first |
| Mobile speed | Lighthouse performance, accessibility and SEO; LCP, CLS, INP (labelled lab or real-user) | A slow mobile page loses visitors before they see the offer |
| Content & conversion | offer in the opening section, a call to action, keyword in title / H1 / first paragraph, readability, trust signals by page type (price, reviews, delivery for products; contact and proof of work for portfolios) | This is listing optimisation applied to any page |

## 4. Real before / after on liwanwen.com

**Before** (18 October 2026, live site): the About page scored 81. Its biggest problem was mobile speed. Lighthouse gave 63, with an LCP of 14.0 s, and PageSpeed's network log showed a 2.3 MB PNG portrait as the largest download. All four pages were missing a canonical tag, Open Graph and Twitter tags, and structured data, and the site had no robots.txt or sitemap. Three page titles were shorter than 30 characters.

**Fixes applied** (the tool's recommendations, approved and deployed the same day):

- converted the portrait to a 700 px WebP (2.3 MB → 57 KB) and gave it fetch priority;
- loaded the home page videos only when they scroll into view;
- added canonical tags, robots.txt, a sitemap, Person structured data and sharing tags;
- wrote unique titles and meta descriptions;
- moved the web font out of a render-blocking CSS `@import`.

**After** (re-checked on the live site). The speed columns are medians of independent Lighthouse mobile runs:

| Page | Tool score | Lighthouse performance | LCP | Runs (before → after) |
|---|---|---|---|---|
| /about | 81 → 93 | 63 → 92 | 14.0 s → 2.4 s | 4 → 3 |
| / (home) | 85 → 93 | 75 → 75.5 | 4.8 s → 4.8 s | 3 → 4 |
| /projects | 84 → 92 | 82 → 83 | 3.8 s → 3.8 s | 2 → 3 |
| /photography | 85 → 89 | 87 → 83 | 3.5 s → 4.0 s | 2 → 4 |

What the numbers show, and what they don't:

- **About** improved clearly and consistently: every after-run scored 91–94.
- **Home:** the two loop videos (2.0 MB and 1.7 MB) no longer appear in PageSpeed's first-load network log, but the Lighthouse score did not measurably change. The after-runs ranged from 73 to 92.
- **Photography** came out slightly slower. The first after-run (LCP 9.9 s) was an outlier taken right after deployment; the later runs were 3.4–4.1 s. I haven't established the cause yet.
- Across the four pages the tool marked 27 checks as fixed. The only regression it reported was that single 9.9 s Photography run.
- These are lab measurements. I make no claim about rankings or traffic: Search Console isn't connected yet.

Sources: `examples/portfolio-before/`, `examples/portfolio-after/` (including `lighthouse-summary.json`) and `portfolio/site-changes-2026-10-18.diff`.

### Other example pages

- **Petal / Atelier demo shop** (my own local project): 75. Speed shows as N/A because PageSpeed can't test local URLs.
- **IKEA Italia product page** (one read-only check): 87.

## 5. What testing taught me (and fixed in the tool)

- **A 200 response isn't always the real page.** The first e-commerce page I tried returned a "Hang tight" queue page with HTTP 200, and the tool scored it. It now detects bot-check and queue pages and refuses to score them.
- **Language matters.** On the Italian IKEA page, "Servizi di consegna" and "Cambi e resi" were missed, so the tool reported shipping info as absent. It now recognises trust words in six languages, and it no longer applies an English readability formula to other languages.
- **Hidden text leaks in.** HTML comments were being counted as visible copy. They are now excluded.
- **Lighthouse needs repeats.** Scores move between runs, and PageSpeed returns cached results for repeated requests within a short window. I only counted runs with a distinct fetch time.

## 6. Limitations

- Reads server-sent HTML only (no JavaScript rendering), checks one page at a time, and approximates "above the fold" as the first 1,500 characters of text.
- CTA, price and review detection is pattern matching. On the IKEA page, an image-zoom button was counted as a call to action.
- It is meant to run locally; it isn't hardened for public hosting.
- No keyword volume, backlinks or rankings, because those need paid data.

## 7. Next steps

- Connect Google Search Console to liwanwen.com and report real impressions, clicks and queries, but only once enough data exists.
- Build repeated, spaced Lighthouse runs into the tool and compare medians automatically.
- Detect duplicate titles and descriptions across a site's pages.
- Investigate why the Photography page got slightly slower. One lead: the page still loads the 2.3 MB PNG through its gallery data file.

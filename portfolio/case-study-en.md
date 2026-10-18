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

## 4. Real before / after on two live pages

### Case 1: Petal / Atelier demo shop ([liwanwen.com/petal](https://liwanwen.com/petal/))

Petal / Atelier is a concept botanical-soap shop I built for my marketing-automation project. Its prices are illustrative and nothing is sold. I published it unchanged, checked it as a product page for the keyword "botanical soap", fixed what the report found and checked it again (18 October 2026).

**Before:** tool score 78 (Technical 83, Performance 79, Content & Conversion 71). On mobile, Lighthouse gave 66 and an LCP of 50.0 s in all three runs. The page weighed 9.7 MB, and 9.5 MB of that was four PNG product images. The title didn't contain "botanical soap", and the page had no canonical tag, no sharing tags, no structured data and not a single crawlable link.

**Applied:**
- converted the four images to WebP (9.5 MB → 383 KB) and gave the hero image fetch priority;
- rewrote the title to "Botanical Soap Gifts | Petal / Atelier (Portfolio Demo)", so the keyword is there and the page says it is a demo;
- moved "botanical" next to "soaps" in the first paragraph;
- added a canonical tag, Open Graph and Twitter tags, WebPage structured data that names it as a portfolio demo, a footer link to my portfolio and a sitemap entry.

**Deliberately not applied:**
- reviews and Product markup with prices, because the shop is fictional and both would mislead people and search engines;
- a keyword in the H1, which is the brand line, so keyword placement stays at "warning".

**After** (live page, medians of independent Lighthouse mobile runs):

| | Before | After |
|---|---|---|
| Tool score | 78 | 92 |
| Technical / Performance / Content | 83 / 79 / 71 | 100 / 99 / 76 |
| Lighthouse performance (3 → 3 runs) | 66 | 100 |
| LCP | 50.0 s | 1.9 s |
| Page weight | 9,734 KB | 408 KB |

Seven checks moved to pass and one improved. Nothing regressed. The two checks still open (reviews and Product markup) are the ones I chose not to fix.

### Case 2: my own portfolio ([liwanwen.com](https://liwanwen.com/))

Same process on four real pages of the site recruiters visit. Before: the About page scored 81, with Lighthouse 63 and an LCP of 14.0 s, because a 2.3 MB PNG portrait was its largest download. All four pages lacked a canonical tag, sharing tags and structured data, and the site had no robots.txt or sitemap.

Applied: the portrait converted to WebP (2.3 MB → 57 KB), home-page videos loaded only on scroll, canonical tags, robots.txt, a sitemap, Person structured data, sharing tags, unique titles and descriptions, and a non-blocking font load.

| Page | Tool score | Lighthouse performance (median) | LCP (median) | Runs |
|---|---|---|---|---|
| /about | 81 → 93 | 63 → 92 | 14.0 s → 2.4 s | 4 → 3 |
| / (home) | 85 → 93 | 75 → 75.5 | 4.8 s → 4.8 s | 3 → 4 |
| /projects | 84 → 92 | 82 → 83 | 3.8 s → 3.8 s | 2 → 3 |
| /photography | 85 → 89 | 87 → 83 | 3.5 s → 4.0 s | 2 → 4 |

- **About** improved clearly.
- **Home:** speed didn't measurably change, although its two loop videos (3.7 MB) no longer load at first view.
- **Photography** came out slightly slower, and I haven't established why.
- Across the four pages, 27 checks moved to pass.

These are lab measurements. I make no claim about rankings or traffic: Search Console isn't connected yet.

Sources: `examples/petal-before/`, `examples/petal-after/`, `examples/portfolio-before/`, `examples/portfolio-after/` and `portfolio/site-changes-2026-10-18.diff`.

### A third-party example

An **IKEA Italia product page**, checked read-only once, scored 87. It shows how the product-page checks behave on a large, real shop.

## 5. What testing taught me (and fixed in the tool)

- **A 200 response isn't always the real page.** The first e-commerce page I tried returned a "Hang tight" queue page with HTTP 200, and the tool scored it. It now detects bot-check and queue pages and refuses to score them.
- **Language matters.** On the Italian IKEA page, "Servizi di consegna" and "Cambi e resi" were missed, so the tool reported shipping info as absent. It now recognises trust words in six languages, and it no longer applies an English readability formula to other languages.
- **Hidden text leaks in.** HTML comments were being counted as visible copy. They are now excluded.
- **Not every recommendation should be applied.** On a fictional shop, adding reviews or priced Product markup would raise the score but mislead people. The tool reports these as open; deciding not to fix them is part of the job.
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
- Fix two small issues I noticed on Petal but left alone to keep the comparison clean: missing spaces in the phone-width headline, and a footer label that still says "local".

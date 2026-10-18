"""Technical SEO: pure HTML parsing (`extract_*`), check evaluation (`evaluate`) and the
network-dependent site checks (broken links, robots.txt, sitemap.xml)."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from .models import Check

TITLE_MIN, TITLE_MAX = 30, 60
DESC_MIN, DESC_MAX = 70, 160
MAX_LINKS_CHECKED = 50
CATEGORY = "technical"

_WS = re.compile(r"\s+")


_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,!?;:])")


def _clean(text: str | None) -> str:
    return _SPACE_BEFORE_PUNCT.sub(r"\1", _WS.sub(" ", text or "")).strip()


def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# --------------------------------------------------------------------------- extraction

def extract_title(soup: BeautifulSoup) -> str | None:
    tag = soup.find("title")
    if tag is None:
        return None
    return _clean(tag.get_text())


def _meta_content(soup: BeautifulSoup, *, name: str | None = None, prop: str | None = None) -> str | None:
    for tag in soup.find_all("meta"):
        if name and (tag.get("name") or "").lower() == name:
            return _clean(tag.get("content"))
        if prop and (tag.get("property") or "").lower() == prop:
            return _clean(tag.get("content"))
    return None


def extract_meta_description(soup: BeautifulSoup) -> str | None:
    return _meta_content(soup, name="description")


def extract_headings(soup: BeautifulSoup) -> dict[str, Any]:
    outline = [(int(t.name[1]), _clean(t.get_text(" "))) for t in soup.find_all(re.compile(r"^h[1-6]$"))]
    return {
        "h1": [text for level, text in outline if level == 1],
        "h2": [text for level, text in outline if level == 2],
        "h3": [text for level, text in outline if level == 3],
        "outline": outline,
    }


def heading_problems(outline: list[tuple[int, str]]) -> list[str]:
    """Return human-readable hierarchy problems: skipped levels (e.g. H1 -> H3)."""
    problems = []
    prev = 0
    for level, text in outline:
        if prev and level > prev + 1:
            problems.append(f"H{prev} followed by H{level} ('{text[:50]}') skips a level")
        elif not prev and level > 1:
            problems.append(f"First heading is H{level} ('{text[:50]}'), not H1")
        prev = level
    return problems


def extract_images(soup: BeautifulSoup) -> dict[str, Any]:
    imgs = soup.find_all("img")
    with_alt = [i for i in imgs if i.has_attr("alt") and _clean(i.get("alt"))]
    empty_alt = [i for i in imgs if i.has_attr("alt") and not _clean(i.get("alt"))]
    missing = [i for i in imgs if not i.has_attr("alt")]
    return {
        "total": len(imgs),
        "with_alt": len(with_alt),
        "empty_alt": len(empty_alt),  # alt="" is valid for decorative images
        "missing_alt": len(missing),
        "missing_alt_src": [i.get("src", "") for i in missing][:20],
    }


def extract_head_meta(soup: BeautifulSoup, page_url: str) -> dict[str, Any]:
    canonical = None
    for link in soup.find_all("link"):
        rel = [r.lower() for r in (link.get("rel") or [])]
        if "canonical" in rel and link.get("href"):
            canonical = urljoin(page_url, link["href"].strip())
            break
    html_tag = soup.find("html")
    return {
        "canonical": canonical,
        "robots": _meta_content(soup, name="robots"),
        "lang": ((html_tag.get("lang") or "").strip() or None) if html_tag else None,
    }


def extract_social(soup: BeautifulSoup) -> dict[str, Any]:
    return {
        "og:title": _meta_content(soup, prop="og:title"),
        "og:description": _meta_content(soup, prop="og:description"),
        "og:image": _meta_content(soup, prop="og:image"),
        "twitter:card": _meta_content(soup, name="twitter:card"),
        "twitter:title": _meta_content(soup, name="twitter:title"),
        "twitter:description": _meta_content(soup, name="twitter:description"),
        "twitter:image": _meta_content(soup, name="twitter:image"),
    }


def _collect_types(node: Any, out: list[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _collect_types(item, out)
    elif isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, str):
            out.append(t)
        elif isinstance(t, list):
            out.extend(x for x in t if isinstance(x, str))
        if "@graph" in node:
            _collect_types(node["@graph"], out)


def extract_json_ld(soup: BeautifulSoup) -> dict[str, Any]:
    blocks, types, errors = [], [], []
    for i, script in enumerate(soup.find_all("script", type=lambda v: v and v.lower() == "application/ld+json")):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"Block {i + 1}: invalid JSON ({exc.msg} at line {exc.lineno})")
            continue
        blocks.append(data)
        _collect_types(data, types)
    return {"count": len(blocks) + len(errors), "valid_blocks": len(blocks), "types": types, "errors": errors}


def _same_site(a: str, b: str) -> bool:
    def host(u: str) -> str:
        h = urlparse(u).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    return host(a) == host(b)


def extract_links(soup: BeautifulSoup, page_url: str) -> dict[str, Any]:
    internal, external = set(), set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        url, _ = urldefrag(urljoin(page_url, href))
        if urlparse(url).scheme not in ("http", "https"):
            continue
        (internal if _same_site(url, page_url) else external).add(url)
    return {"internal": sorted(internal), "external": sorted(external)}


_INTERSTITIAL_TITLE = re.compile(
    r"just a moment|attention required|access denied|checking your browser|hang tight|sit tight|"
    r"please wait|pardon our interruption|are you a robot|verify you are (a )?human|you are in (the )?queue|"
    r"request unsuccessful|security check", re.I)
_INTERSTITIAL_TEXT = re.compile(
    r"captcha|queue-it|cf-browser-verification|enable javascript and cookies to continue|"
    r"verify you are (a )?human|incapsula|perimeterx|px-captcha|routing to checkout|customization instructions", re.I)


def detect_interstitial(facts: dict[str, Any], visible_text: str) -> str | None:
    """Return a reason when the HTML looks like a bot check / waiting room rather than the real page.

    A 200 response is not proof we got the page: CDNs and queue systems serve challenge pages
    with status 200. Scoring those would describe the challenge, not the site.
    """
    title = facts.get("title") or ""
    if _INTERSTITIAL_TITLE.search(title):
        return f'title "{title}"'
    few_links = len(facts["links"]["internal"]) + len(facts["links"]["external"]) < 5
    m = _INTERSTITIAL_TEXT.search(visible_text or "")
    if m and few_links and not facts["headings"]["h1"]:
        return f'page text mentions "{m.group(0)}" and has almost no links'
    return None


def extract_all(html: str, page_url: str) -> dict[str, Any]:
    soup = parse(html)
    return {
        "title": extract_title(soup),
        "meta_description": extract_meta_description(soup),
        "headings": extract_headings(soup),
        "images": extract_images(soup),
        "head": extract_head_meta(soup, page_url),
        "social": extract_social(soup),
        "json_ld": extract_json_ld(soup),
        "links": extract_links(soup, page_url),
    }


# --------------------------------------------------------------------------- evaluation

def _check(id_, label, status, severity, finding, why="", fix="", **data) -> Check:
    return Check(id=id_, category=CATEGORY, label=label, status=status, severity=severity,
                 finding=finding, why=why, fix=fix, data=data)


def evaluate(facts: dict[str, Any], keyword: str | None = None, page_url: str | None = None) -> list[Check]:
    checks: list[Check] = []
    kw = (keyword or "").strip().lower()

    # Title
    title = facts["title"]
    why_title = "The title is the main headline in search results and a strong relevance signal."
    if not title:
        checks.append(_check("title_present", "Title tag", "fail", "High", "No <title> found (or it is empty).",
                             why_title, "Add a unique, descriptive <title> of 30-60 characters."))
    else:
        n = len(title)
        if TITLE_MIN <= n <= TITLE_MAX:
            checks.append(_check("title_length", "Title length", "pass", "Medium",
                                 f"Title is {n} characters: \"{title}\".", length=n, value=title))
        else:
            hint = "short; it may not describe the page well" if n < TITLE_MIN else "long; Google may truncate it"
            checks.append(_check("title_length", "Title length", "warn", "Medium",
                                 f"Title is {n} characters ({hint}): \"{title}\".", why_title,
                                 f"Rewrite to {TITLE_MIN}-{TITLE_MAX} characters, most important words first.",
                                 length=n, value=title))
        if kw:
            if kw in title.lower():
                checks.append(_check("title_keyword", "Keyword in title", "pass", "Medium",
                                     f"Title contains \"{keyword}\"."))
            else:
                checks.append(_check("title_keyword", "Keyword in title", "fail", "Medium",
                                     f"Title does not contain the target keyword \"{keyword}\".",
                                     "Searchers scan titles for the words they typed.",
                                     "Work the keyword naturally into the first half of the title."))

    # Meta description
    desc = facts["meta_description"]
    why_desc = "The meta description is often used as the search snippet and affects click-through rate."
    if not desc:
        checks.append(_check("meta_description", "Meta description", "fail", "Medium",
                             "No meta description found.", why_desc,
                             "Add <meta name=\"description\"> of 70-160 characters summarising the page and its benefit."))
    else:
        n = len(desc)
        ok = DESC_MIN <= n <= DESC_MAX
        checks.append(_check("meta_description", "Meta description", "pass" if ok else "warn", "Medium",
                             f"Meta description is {n} characters.", "" if ok else why_desc,
                             "" if ok else f"Rewrite to {DESC_MIN}-{DESC_MAX} characters.", length=n, value=desc))

    # H1
    h1s = facts["headings"]["h1"]
    why_h1 = "A single clear H1 tells users and search engines what the page is about."
    if len(h1s) == 1:
        checks.append(_check("h1_count", "Single H1", "pass", "High", f"Exactly one H1: \"{h1s[0]}\".", h1=h1s))
    elif not h1s:
        checks.append(_check("h1_count", "Single H1", "fail", "High", "No H1 found.", why_h1,
                             "Add one H1 that states the page's main topic or offer."))
    else:
        checks.append(_check("h1_count", "Single H1", "warn", "Medium", f"{len(h1s)} H1 tags found.", why_h1,
                             "Keep one H1; demote the others to H2.", h1=h1s))

    # Heading hierarchy
    problems = heading_problems(facts["headings"]["outline"])
    if not facts["headings"]["outline"]:
        pass  # covered by the H1 check
    elif problems:
        checks.append(_check("heading_hierarchy", "Heading hierarchy", "warn", "Low",
                             f"{len(problems)} hierarchy issue(s): " + "; ".join(problems[:3]),
                             "A logical outline helps screen readers and helps crawlers understand structure.",
                             "Use headings in order (H1 > H2 > H3) without skipping levels.", problems=problems))
    else:
        checks.append(_check("heading_hierarchy", "Heading hierarchy", "pass", "Low",
                             f"{len(facts['headings']['outline'])} headings, no skipped levels."))

    # Images
    img = facts["images"]
    if img["total"] == 0:
        checks.append(_check("image_alt", "Image alt text", "info", "Low", "No <img> elements on the page."))
    else:
        covered = img["with_alt"] + img["empty_alt"]
        pct = round(100 * covered / img["total"])
        finding = (f"{covered}/{img['total']} images ({pct}%) have an alt attribute "
                   f"({img['empty_alt']} empty, i.e. marked decorative).")
        if img["missing_alt"] == 0:
            checks.append(_check("image_alt", "Image alt text", "pass", "Medium", finding, coverage_pct=pct))
        else:
            checks.append(_check("image_alt", "Image alt text", "fail" if pct < 50 else "warn", "Medium", finding,
                                 "Alt text makes images accessible and lets search engines understand them.",
                                 "Add descriptive alt text to content images; use alt=\"\" for purely decorative ones.",
                                 coverage_pct=pct, missing_src=img["missing_alt_src"]))

    # Canonical
    head = facts["head"]
    if head["canonical"]:
        status, finding = "pass", f"Canonical: {head['canonical']}"
        if page_url and urldefrag(head["canonical"])[0].rstrip("/") != urldefrag(page_url)[0].rstrip("/"):
            status, finding = "info", f"Canonical points to a different URL: {head['canonical']}"
        checks.append(_check("canonical", "Canonical URL", status, "Medium", finding, canonical=head["canonical"]))
    else:
        checks.append(_check("canonical", "Canonical URL", "warn", "Medium", "No <link rel=\"canonical\"> found.",
                             "Without a canonical, URL variants (query strings, http/https) can split ranking signals.",
                             "Add <link rel=\"canonical\" href=\"<preferred absolute URL>\">."))

    # Robots meta
    robots = (head["robots"] or "").lower()
    if "noindex" in robots:
        checks.append(_check("robots_meta", "Robots meta", "fail", "High", f"Robots meta is \"{head['robots']}\".",
                             "noindex tells search engines to drop this page from results.",
                             "Remove noindex if this page should appear in search."))
    else:
        checks.append(_check("robots_meta", "Robots meta", "pass", "High",
                             f"Robots meta: \"{head['robots']}\"." if head["robots"] else
                             "No robots meta (default is index, follow)."))

    # Lang
    if head["lang"]:
        checks.append(_check("lang", "HTML lang attribute", "pass", "Low", f"lang=\"{head['lang']}\"."))
    else:
        checks.append(_check("lang", "HTML lang attribute", "warn", "Low", "<html> has no lang attribute.",
                             "lang helps screen readers pronounce text and helps search engines target language.",
                             "Add lang, e.g. <html lang=\"en\">."))

    # Social tags
    soc = facts["social"]
    og_missing = [k for k in ("og:title", "og:description", "og:image") if not soc[k]]
    if not og_missing:
        checks.append(_check("open_graph", "Open Graph tags", "pass", "Low", "og:title, og:description, og:image present."))
    else:
        checks.append(_check("open_graph", "Open Graph tags", "warn", "Low", "Missing: " + ", ".join(og_missing) + ".",
                             "Without OG tags, shared links on LinkedIn/WhatsApp/Slack show a poor or empty preview.",
                             "Add the missing og:* meta tags; og:image should be at least 1200x630.", missing=og_missing))
    if soc["twitter:card"]:
        checks.append(_check("twitter_card", "Twitter/X card", "pass", "Low", f"twitter:card = \"{soc['twitter:card']}\"."))
    else:
        checks.append(_check("twitter_card", "Twitter/X card", "warn", "Low", "No twitter:card meta.",
                             "X falls back to OG tags but uses a small preview without twitter:card.",
                             "Add <meta name=\"twitter:card\" content=\"summary_large_image\">."))

    # Structured data
    ld = facts["json_ld"]
    if ld["errors"]:
        checks.append(_check("json_ld", "Structured data (JSON-LD)", "fail", "Medium",
                             "; ".join(ld["errors"]), "Invalid JSON-LD is ignored by search engines.",
                             "Fix the JSON syntax; validate with Google's Rich Results Test.", types=ld["types"]))
    elif ld["types"]:
        checks.append(_check("json_ld", "Structured data (JSON-LD)", "pass", "Medium",
                             f"{ld['valid_blocks']} block(s), types: {', '.join(ld['types'])}.", types=ld["types"]))
    else:
        checks.append(_check("json_ld", "Structured data (JSON-LD)", "warn", "Medium", "No JSON-LD found.",
                             "Structured data can unlock rich results (price, rating, profile) in search.",
                             "Add JSON-LD matching the page: Product, Person, Organization, etc."))

    links = facts["links"]
    checks.append(_check("link_counts", "Links", "info", "Low",
                         f"{len(links['internal'])} internal and {len(links['external'])} external unique links.",
                         internal=len(links["internal"]), external=len(links["external"])))
    return checks


# --------------------------------------------------------------------------- network checks

def check_broken_links(fetcher, links: dict[str, list[str]], limit: int = MAX_LINKS_CHECKED) -> Check:
    all_links = links["internal"] + links["external"]
    to_check = all_links[:limit]
    results = [fetcher.status_of(u) for u in to_check]
    broken = [r for r in results if r["status_code"] and 400 <= r["status_code"] < 500]
    server_err = [r for r in results if r["status_code"] and r["status_code"] >= 500]
    unchecked = [r for r in results if r["status_code"] is None]
    note = f" Only the first {limit} of {len(all_links)} were checked." if len(all_links) > limit else ""
    finding = (f"Checked {len(results)} links: {len(broken)} returned 4xx, {len(server_err)} returned 5xx, "
               f"{len(unchecked)} could not be checked (robots.txt or network).{note}")
    data = {"broken": broken, "server_errors": server_err, "unchecked": unchecked, "checked": len(results)}
    if broken:
        return Check("broken_links", CATEGORY, "Broken links (4xx)", "fail", "High", finding,
                     "Broken links waste crawl budget and frustrate visitors.",
                     "Fix or remove: " + ", ".join(r["url"] for r in broken[:5]), data)
    return Check("broken_links", CATEGORY, "Broken links (4xx)", "pass", "High", finding, data=data)


def check_robots_and_sitemap(fetcher, page_url: str) -> list[Check]:
    from .fetcher import origin_of

    origin = origin_of(page_url)
    rules = fetcher.robots_for(page_url)
    checks = []
    if rules.status == "found":
        checks.append(Check("robots_txt", CATEGORY, "robots.txt", "pass", "Low", f"{origin}/robots.txt found.",
                            data={"sitemaps_declared": rules.sitemaps}))
    elif rules.status == "missing":
        checks.append(Check("robots_txt", CATEGORY, "robots.txt", "warn", "Low",
                            f"{origin}/robots.txt returned HTTP {rules.source_status_code}.",
                            "Not required, but robots.txt is the standard place to point crawlers to your sitemap.",
                            "Add a robots.txt with 'User-agent: *', 'Allow: /' and a 'Sitemap:' line."))
    else:
        checks.append(Check("robots_txt", CATEGORY, "robots.txt", "fail", "High",
                            f"robots.txt unreachable ({rules.error}).",
                            "Crawlers treat an unreachable robots.txt (5xx) as 'do not crawl'.",
                            "Make /robots.txt return 200 or 404."))

    candidates = rules.sitemaps or [origin + "/sitemap.xml"]
    found = None
    tried = []
    for sm in candidates[:3]:
        status, text, err = fetcher.get_text(sm)
        tried.append({"url": sm, "status_code": status, "error": err})
        if status == 200 and text and re.search(r"<(urlset|sitemapindex)\b", text):
            found = sm
            break
    if found:
        checks.append(Check("sitemap", CATEGORY, "sitemap.xml", "pass", "Medium", f"Valid sitemap at {found}.",
                            data={"tried": tried}))
    else:
        checks.append(Check("sitemap", CATEGORY, "sitemap.xml", "warn", "Medium",
                            "No valid sitemap found at: " + ", ".join(t["url"] for t in tried) + ".",
                            "A sitemap helps search engines discover all your pages, especially on new sites.",
                            "Generate sitemap.xml listing every public page and reference it in robots.txt.",
                            data={"tried": tried}))
    return checks

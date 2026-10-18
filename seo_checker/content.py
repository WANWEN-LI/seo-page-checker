"""Content & conversion checks, borrowing from Amazon listing practice: is the offer clear
above the fold, is there a next step, does the copy use the target keyword where it counts,
is it easy to read, and are the trust signals a buyer expects present.

All checks read the server-rendered HTML only. "Above the fold" is approximated as the
first FOLD_CHARS characters of visible body text (we do not render the page).
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import CData, Comment, Declaration, Doctype, ProcessingInstruction

from .models import Check
from .technical import _clean

CATEGORY = "content"
FOLD_CHARS = 1500
MIN_WORDS_FOR_READABILITY = 80
LONG_SENTENCE_WORDS = 25
LONG_PARAGRAPH_WORDS = 100

HIDDEN_TAGS = ("script", "style", "noscript", "template", "svg", "head")
CTA_VERBS = re.compile(
    r"\b(buy|shop|add to (cart|bag|basket)|order|book|get started|start|sign ?up|subscribe|join|"
    r"contact|get in touch|hire|email me|let'?s talk|request|download|try|demo|learn more|view|see|explore|"
    r"discover|find|choose|get|claim|reserve)\b",
    re.I,
)
CTA_CLASS = re.compile(r"\b(btn|button|cta)\b", re.I)
PRICE = re.compile(r"(?:[$€£¥]\s?\d[\d.,]*|\d[\d.,]*\s?(?:€|EUR|USD|GBP|kr|zł))", re.I)
# English plus it / fr / de / es / nl terms, so non-English shops are not marked as missing them
REVIEWS = re.compile(r"\b(reviews?|ratings?|rated|stars?|testimonials?|recension\w*|valutazion\w*|stelle|avis|étoiles|"
                     r"bewertung\w*|sterne|reseñas|opiniones|valoraciones|estrellas|beoordeling\w*|sterren)\b", re.I)
SHIPPING = re.compile(r"\b(shipping|delivery|dispatch|returns?|refunds?|spedizion\w*|consegn\w*|resi|reso|rimbors\w*|"
                      r"livraison|retours?|rembourse\w*|versand|lieferung|rückgabe|rücksendung|envíos?|envios?|entregas?|"
                      r"devoluci\w+|verzending|levering)\b", re.I)
SOCIAL_PROOF = re.compile(r"\b(testimonials?|reviews?|clients?|customers?|trusted by|case stud(y|ies)|"
                          r"results?|featured in|as seen in)\b", re.I)
PROOF_OF_WORK = re.compile(r"\b(projects?|case stud(y|ies)|portfolio)\b", re.I)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“])")
WORD = re.compile(r"[A-Za-zÀ-ÿ0-9’']+")


def _words(text: str) -> list[str]:
    return WORD.findall(text)


def _visible_root(soup: BeautifulSoup) -> Tag:
    body = soup.body or soup
    return body


def _is_hidden(node) -> bool:
    for parent in node.parents:
        if isinstance(parent, Tag) and (parent.name in HIDDEN_TAGS or parent.has_attr("hidden")
                                        or parent.get("aria-hidden") == "true"):
            return True
    return False


def above_the_fold(soup: BeautifulSoup) -> dict[str, Any]:
    """Walk the body in document order; collect text and actionable elements until FOLD_CHARS."""
    root = _visible_root(soup)
    chars = 0
    text_parts: list[str] = []
    actions: list[dict[str, str]] = []
    headings: list[str] = []
    for node in root.descendants:
        if chars >= FOLD_CHARS:
            break
        if isinstance(node, NavigableString):
            if isinstance(node, (Comment, CData, Declaration, Doctype, ProcessingInstruction)) or _is_hidden(node):
                continue
            s = " ".join(node.split())
            if s:
                text_parts.append(s)
                chars += len(s) + 1
        elif isinstance(node, Tag):
            if node.name in ("h1", "h2") and not _is_hidden(node):
                headings.append(_clean(node.get_text(" ")))
            is_button = node.name == "button" or (node.name == "input" and node.get("type") in ("submit", "button"))
            is_link = node.name == "a" and node.has_attr("href")
            if (is_button or is_link) and not _is_hidden(node):
                in_nav = node.find_parent("nav") is not None
                label = " ".join((node.get_text(" ") or node.get("value") or node.get("aria-label") or "").split())
                href = node.get("href", "")
                looks_like_button = is_button or bool(CTA_CLASS.search(" ".join(node.get("class", []))))
                if label and (CTA_VERBS.search(label) or href.startswith("mailto:")) and (looks_like_button or not in_nav):
                    actions.append({"label": label[:80], "href": href, "styled_as_button": looks_like_button})
    return {"text": " ".join(text_parts), "chars": chars, "ctas": actions, "headings": headings}


def paragraphs(soup: BeautifulSoup) -> list[str]:
    out = []
    for p in _visible_root(soup).find_all("p"):
        if _is_hidden(p):
            continue
        t = " ".join(p.get_text(" ").split())
        if len(_words(t)) >= 3:
            out.append(t)
    return out


def readability(paras: list[str]) -> dict[str, Any]:
    sentences = [s for p in paras for s in SENTENCE_SPLIT.split(p) if _words(s)]
    sent_lens = [len(_words(s)) for s in sentences]
    para_lens = [len(_words(p)) for p in paras]
    total = sum(para_lens)
    result: dict[str, Any] = {
        "words": total,
        "sentences": len(sentences),
        "paragraphs": len(paras),
        "avg_sentence_words": round(total / len(sentences), 1) if sentences else None,
        "long_sentences": sum(1 for n in sent_lens if n > LONG_SENTENCE_WORDS),
        "avg_paragraph_words": round(total / len(paras), 1) if paras else None,
        "long_paragraphs": sum(1 for n in para_lens if n > LONG_PARAGRAPH_WORDS),
        "flesch_reading_ease": None,
    }
    if total >= MIN_WORDS_FOR_READABILITY:
        import textstat
        result["flesch_reading_ease"] = round(textstat.flesch_reading_ease(" ".join(paras)), 1)
    return result


def _json_ld_objects(soup: BeautifulSoup) -> list[dict]:
    objs: list[dict] = []

    def walk(n):
        if isinstance(n, list):
            for x in n:
                walk(x)
        elif isinstance(n, dict):
            objs.append(n)
            for v in n.values():
                if isinstance(v, (dict, list)):
                    walk(v)

    for s in soup.find_all("script", type=lambda v: v and v.lower() == "application/ld+json"):
        try:
            walk(json.loads(s.string or ""))
        except (json.JSONDecodeError, TypeError):
            pass
    return objs


def trust_signals(soup: BeautifulSoup) -> dict[str, Any]:
    text = " ".join(_visible_root(soup).get_text(" ").split())
    ld = _json_ld_objects(soup)
    ld_types = {t for o in ld for t in ([o.get("@type")] if isinstance(o.get("@type"), str) else o.get("@type") or [])}
    hrefs = [a.get("href", "") for a in soup.find_all("a", href=True)]
    contact_links = list(dict.fromkeys(
        h for h in hrefs if h.startswith(("mailto:", "tel:")) or re.search(r"contact|linkedin\.com", h, re.I)))
    has_form = soup.find("form") is not None
    return {
        "price": bool(PRICE.search(text)) or any("offers" in o or "price" in o for o in ld)
                 or soup.find(attrs={"itemprop": "price"}) is not None,
        "price_examples": PRICE.findall(text)[:3],
        "reviews": bool(REVIEWS.search(text)) or any("aggregateRating" in o or "review" in o for o in ld),
        "shipping_returns": bool(SHIPPING.search(text)),
        "contact": bool(contact_links) or has_form,
        "contact_examples": contact_links[:3],
        "social_proof": bool(SOCIAL_PROOF.search(text)),
        "proof_of_work": bool(PROOF_OF_WORK.search(text)) or any("github.com" in h for h in hrefs),
        "person_schema": "Person" in ld_types,
        "product_schema": "Product" in ld_types,
    }


def extract_all(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    paras = paragraphs(soup)
    return {
        "fold": above_the_fold(soup),
        "first_paragraph": paras[0] if paras else None,
        "readability": readability(paras),
        "trust": trust_signals(soup),
    }


# --------------------------------------------------------------------------- evaluation

def _c(id_, label, status, severity, finding, why="", fix="", **data) -> Check:
    return Check(id_, CATEGORY, label, status, severity, finding, why, fix, data)


# (signal key, label, severity, why, fix) per page type
TRUST_RULES: dict[str, list[tuple[str, str, str, str, str]]] = {
    "product": [
        ("price", "Price visible", "High", "Shoppers bounce when they cannot see the price without extra clicks.",
         "Show the price near the title and add Offer.price in Product JSON-LD."),
        ("reviews", "Reviews / ratings", "Medium", "Reviews are the strongest trust signal on a product page.",
         "Show rating and review count near the price; mark up AggregateRating."),
        ("shipping_returns", "Shipping & returns info", "Medium",
         "Unclear delivery cost or return policy is a top reason for abandoned carts.",
         "State delivery time/cost and the return window near the add-to-cart button."),
        ("product_schema", "Product structured data", "Medium",
         "Product schema enables price and rating rich results in Google.", "Add Product JSON-LD with offers."),
    ],
    "landing": [
        ("social_proof", "Social proof", "Medium", "Visitors trust what other customers say more than your copy.",
         "Add testimonials, client logos or concrete results."),
        ("contact", "Contact path", "Medium", "Visitors with questions need an obvious way to reach you.",
         "Add a contact link, email or form."),
    ],
    "portfolio": [
        ("contact", "Contact path", "High", "A recruiter who likes your work needs one obvious way to reach you.",
         "Add a visible email (mailto:) or LinkedIn link, ideally in the header and footer."),
        ("proof_of_work", "Evidence of work", "Medium", "Claims without projects or results are hard to believe.",
         "Link to projects/case studies with concrete outcomes."),
        ("person_schema", "Person structured data", "Low",
         "Person schema helps Google connect your name, role and profiles (sameAs).",
         "Add Person JSON-LD with name, jobTitle, url and sameAs links."),
    ],
}


def evaluate(facts: dict[str, Any], tech_facts: dict[str, Any], keyword: str | None,
             page_type: str | None) -> list[Check]:
    checks: list[Check] = []
    fold = facts["fold"]
    h1s = tech_facts["headings"]["h1"]

    # Value proposition: an H1 in the fold plus supporting copy
    h1_in_fold = bool(h1s) and any(h == h1s[0] for h in fold["headings"])
    fold_words = len(_words(fold["text"]))
    if h1_in_fold and fold_words >= 20:
        checks.append(_c("value_prop", "Value proposition above the fold", "pass", "High",
                         f"H1 \"{h1s[0]}\" appears in the first {FOLD_CHARS} characters with {fold_words} words of copy."))
    elif h1_in_fold:
        checks.append(_c("value_prop", "Value proposition above the fold", "warn", "High",
                         f"H1 is in the opening section but only {fold_words} words of supporting copy are visible in the HTML.",
                         "Visitors decide within seconds; a headline alone rarely explains who it is for and why it matters.",
                         "Add one sentence under the H1 that says who it is for and the main benefit."))
    elif h1s:
        checks.append(_c("value_prop", "Value proposition above the fold", "fail", "High",
                         f"The H1 \"{h1s[0]}\" is not within the first {FOLD_CHARS} characters of visible text.",
                         "If the headline sits below a long header or intro, visitors may not see the offer first.",
                         "Move the H1 and its supporting sentence to the top of the page content."))
    else:
        checks.append(_c("value_prop", "Value proposition above the fold", "fail", "High",
                         "The page has no H1.",
                         "Without a clear headline at the top, visitors cannot tell what the page offers.",
                         "Put an H1 that states the offer or role at the top of the page."))

    # CTA in the fold
    ctas = fold["ctas"]
    if ctas:
        checks.append(_c("cta_fold", "Call to action above the fold", "pass", "High",
                         f"{len(ctas)} action link(s)/button(s) in the opening section, e.g. \"{ctas[0]['label']}\".",
                         ctas=ctas[:5]))
    else:
        checks.append(_c("cta_fold", "Call to action above the fold", "fail", "High",
                         f"No action-oriented button or link found in the first {FOLD_CHARS} characters (nav links excluded).",
                         "Every page needs one obvious next step (buy, contact, book).",
                         "Add a prominent button with a verb label, e.g. 'Add to cart', 'Contact me', 'View projects'."))

    # Keyword placement
    if keyword:
        kw = keyword.lower()
        places = {
            "title": kw in (tech_facts["title"] or "").lower(),
            "h1": any(kw in h.lower() for h in h1s),
            "first_paragraph": kw in (facts["first_paragraph"] or "").lower(),
        }
        found = [k for k, v in places.items() if v]
        missing = [k for k, v in places.items() if not v]
        status = "pass" if not missing else "warn" if found else "fail"
        checks.append(_c("keyword_placement", "Keyword placement", status, "Medium",
                         f"\"{keyword}\" found in: {', '.join(found) or 'none'}; missing from: {', '.join(missing) or 'none'}.",
                         "" if status == "pass" else "Like an Amazon listing title, the first words people and crawlers read should match the search term.",
                         "" if status == "pass" else "Use the keyword (or a close variant) naturally in " + ", ".join(missing) + ".",
                         places=places))
    else:
        checks.append(_c("keyword_placement", "Keyword placement", "not_checked", "Medium",
                         "No target keyword given."))

    # Readability
    r = facts["readability"]
    lang = ((tech_facts.get("head") or {}).get("lang") or "").lower()
    if lang and not lang.startswith("en"):
        checks.append(_c("readability", "Readability", "not_checked", "Low",
                         f"Page language is '{lang}'; the sentence-length thresholds and Flesch formula used here are "
                         f"calibrated for English, so readability is not scored.", **r))
    elif r["words"] < MIN_WORDS_FOR_READABILITY:
        checks.append(_c("readability", "Readability", "not_checked", "Low",
                         f"Only {r['words']} words in <p> elements in the HTML; too little text to assess.", **r))
    else:
        avg = r["avg_sentence_words"]
        status = "pass" if avg <= 20 and r["long_paragraphs"] == 0 else "warn" if avg <= 25 else "fail"
        finding = (f"{r['words']} words, avg {avg} words/sentence, {r['long_sentences']} sentence(s) over "
                   f"{LONG_SENTENCE_WORDS} words, {r['long_paragraphs']} paragraph(s) over {LONG_PARAGRAPH_WORDS} words; "
                   f"Flesch reading ease {r['flesch_reading_ease']} (English formula).")
        checks.append(_c("readability", "Readability", status, "Low", finding,
                         "" if status == "pass" else "Web visitors scan; long sentences and walls of text get skipped.",
                         "" if status == "pass" else "Aim for under 20 words per sentence and paragraphs under 100 words; use bullets.",
                         **r))

    # Trust signals by page type
    t = facts["trust"]
    if not page_type:
        checks.append(_c("trust_signals", "Trust signals", "not_checked", "Medium",
                         "No page type given, so the expected trust signals are unknown."))
    else:
        for key, label, sev, why, fix in TRUST_RULES[page_type]:
            ok = bool(t[key])
            extra = ""
            if key == "price" and t["price_examples"]:
                extra = f" (e.g. {', '.join(t['price_examples'])})"
            if key == "contact" and t["contact_examples"]:
                extra = f" (e.g. {', '.join(t['contact_examples'])})"
            checks.append(_c(f"trust_{key}", label, "pass" if ok else "fail", sev,
                             (f"Found{extra}." if ok else "Not found in the page HTML."),
                             "" if ok else why, "" if ok else fix))
    return checks

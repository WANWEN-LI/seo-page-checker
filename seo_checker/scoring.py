"""Transparent scoring. This file is the single source of truth for the rules in README.

Technical and Content & Conversion:
    category score = 100 * sum(weight * points) / sum(weight of scored checks)
    points: pass = 1, warn = 0.5, fail = 0. Checks with status info / not_checked are
    excluded from both numerator and denominator (they neither help nor hurt).

Performance (from PageSpeed Insights, mobile, Lighthouse lab scores):
    category score = 0.6 * Performance + 0.2 * Accessibility + 0.2 * Lighthouse SEO
    Core Web Vitals are reported as issues but not scored separately: the Lighthouse
    performance score already includes lab LCP/CLS, and field data is often missing.

Total:
    total = 0.4 * Technical + 0.3 * Performance + 0.3 * Content & Conversion
    If a category is N/A (e.g. PSI could not run), its weight is redistributed
    proportionally across the remaining categories and the report says so.
"""

from __future__ import annotations

from typing import Any

POINTS = {"pass": 1.0, "warn": 0.5, "fail": 0.0}

# weight per check id: 3 = high impact, 2 = medium, 1 = low
WEIGHTS: dict[str, dict[str, int]] = {
    "technical": {
        "title_length": 3, "title_present": 3, "title_keyword": 2,
        "meta_description": 2,
        "h1_count": 3, "heading_hierarchy": 1,
        "image_alt": 2,
        "canonical": 2, "robots_meta": 3, "lang": 1,
        "open_graph": 1, "twitter_card": 1,
        "json_ld": 2,
        "broken_links": 3,
        "robots_txt": 1, "sitemap": 2,
    },
    "content": {
        "value_prop": 3, "cta_fold": 3, "keyword_placement": 2, "readability": 1,
        "trust_price": 3, "trust_reviews": 2, "trust_shipping_returns": 2, "trust_product_schema": 1,
        "trust_social_proof": 2, "trust_contact": 3, "trust_proof_of_work": 2, "trust_person_schema": 1,
    },
}
PERFORMANCE_MIX = {"lh_performance": 0.6, "lh_accessibility": 0.2, "lh_seo": 0.2}
CATEGORY_WEIGHTS = {"technical": 0.4, "performance": 0.3, "content": 0.3}
CATEGORY_LABELS = {"technical": "Technical", "performance": "Performance", "content": "Content & Conversion"}


def _weighted(checks: list[dict[str, Any]], weights: dict[str, int]) -> dict[str, Any]:
    earned = possible = 0.0
    breakdown = []
    for c in checks:
        if c["status"] not in POINTS:
            continue
        w = weights.get(c["id"], 1)
        earned += w * POINTS[c["status"]]
        possible += w
        breakdown.append({"id": c["id"], "status": c["status"], "weight": w, "points": w * POINTS[c["status"]]})
    score = round(100 * earned / possible) if possible else None
    return {"score": score, "earned": earned, "possible": possible, "breakdown": breakdown}


def _performance(checks: list[dict[str, Any]]) -> dict[str, Any]:
    scores = {c["id"]: c["data"].get("score") for c in checks if c["id"] in PERFORMANCE_MIX}
    if any(scores.get(k) is None for k in PERFORMANCE_MIX):
        return {"score": None, "breakdown": scores}
    return {"score": round(sum(PERFORMANCE_MIX[k] * scores[k] for k in PERFORMANCE_MIX)), "breakdown": scores}


def score_report(checks: list[dict[str, Any]]) -> dict[str, Any]:
    by_cat: dict[str, list[dict[str, Any]]] = {k: [] for k in CATEGORY_WEIGHTS}
    for c in checks:
        by_cat.setdefault(c["category"], []).append(c)

    categories = {
        "technical": _weighted(by_cat["technical"], WEIGHTS["technical"]),
        "performance": _performance(by_cat["performance"]),
        "content": _weighted(by_cat["content"], WEIGHTS["content"]),
    }
    available = {k: v["score"] for k, v in categories.items() if v["score"] is not None}
    notes = []
    if not available:
        total = None
    else:
        wsum = sum(CATEGORY_WEIGHTS[k] for k in available)
        total = round(sum(CATEGORY_WEIGHTS[k] * s for k, s in available.items()) / wsum)
        missing = [CATEGORY_LABELS[k] for k in categories if k not in available]
        if missing:
            notes.append(f"{', '.join(missing)} N/A; total uses the remaining categories with weights rescaled "
                         f"to sum to 100%.")
    return {
        "total": total,
        "categories": {k: {"label": CATEGORY_LABELS[k], **v} for k, v in categories.items()},
        "weights": CATEGORY_WEIGHTS,
        "notes": notes,
    }

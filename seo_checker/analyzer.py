"""Runs all checks for one URL and assembles the raw report dict."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import __version__, ai_suggest, content, performance, scoring, technical
from .fetcher import Fetcher

PAGE_TYPES = ("product", "landing", "portfolio")


def analyze(url: str, keyword: str | None = None, page_type: str | None = None,
            fetcher: Fetcher | None = None, check_links: bool = True,
            run_psi: bool = True, run_ai: bool = False) -> dict[str, Any]:
    fetcher = fetcher or Fetcher()
    report: dict[str, Any] = {
        "tool_version": __version__,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": {"url": url, "keyword": keyword, "page_type": page_type},
        "fetch": None,
        "facts": None,
        "checks": [],
        "score": None,
        "pagespeed": None,
        "ai": None,
        "errors": [],
    }
    if page_type and page_type not in PAGE_TYPES:
        report["errors"].append(f"Unknown page_type '{page_type}'; expected one of {PAGE_TYPES}.")

    page = fetcher.fetch_page(url)
    report["fetch"] = page.to_dict()
    if not page.ok or page.text is None:
        report["errors"].append(f"Page could not be audited: [{page.error_type}] {page.error}")
        return report

    page_url = page.final_url or url
    facts = technical.extract_all(page.text, page_url)
    content_facts = content.extract_all(page.text)
    report["facts"] = {**facts, "content": content_facts}

    blocked = technical.detect_interstitial(facts, content_facts["fold"]["text"])
    if blocked:
        report["fetch"]["error_type"] = "interstitial"
        report["errors"].append(f"Page could not be audited: the server returned a bot-check, queue or "
                                f"access page instead of the real page ({blocked}). No score was calculated.")
        return report

    checks = technical.evaluate(facts, keyword=keyword, page_url=page_url)
    checks += technical.check_robots_and_sitemap(fetcher, page_url)
    if check_links:
        checks.append(technical.check_broken_links(fetcher, facts["links"]))

    if run_psi:
        psi = performance.run_pagespeed(page_url)
    else:
        psi = {"ok": False, "error": "PageSpeed Insights disabled for this run (--no-psi).", "skipped": True}
    report["pagespeed"] = psi
    if not psi["ok"]:
        report["errors"].append(f"Performance N/A: {psi['error']}")
    checks += performance.evaluate(psi)

    valid_type = page_type if page_type in PAGE_TYPES else None
    checks += content.evaluate(content_facts, facts, keyword, valid_type)

    report["checks"] = [c.to_dict() for c in checks]
    report["score"] = scoring.score_report(report["checks"])
    if run_ai:
        report["ai"] = ai_suggest.suggest(report)
    return report

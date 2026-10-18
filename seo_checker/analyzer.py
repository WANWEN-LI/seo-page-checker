"""Runs all checks for one URL and assembles the raw report dict."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import __version__, technical
from .fetcher import Fetcher

PAGE_TYPES = ("product", "landing", "portfolio")


def analyze(url: str, keyword: str | None = None, page_type: str | None = None,
            fetcher: Fetcher | None = None, check_links: bool = True) -> dict[str, Any]:
    fetcher = fetcher or Fetcher()
    report: dict[str, Any] = {
        "tool_version": __version__,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": {"url": url, "keyword": keyword, "page_type": page_type},
        "fetch": None,
        "facts": None,
        "checks": [],
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
    report["facts"] = facts
    checks = technical.evaluate(facts, keyword=keyword, page_url=page_url)
    checks += technical.check_robots_and_sitemap(fetcher, page_url)
    if check_links:
        checks.append(technical.check_broken_links(fetcher, facts["links"]))
    report["checks"] = [c.to_dict() for c in checks]
    return report

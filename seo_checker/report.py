"""HTML (shareable) and JSON (raw data) export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import __version__
from .performance import _fmt
from .scoring import CATEGORY_LABELS, PERFORMANCE_MIX, WEIGHTS

TEMPLATES = Path(__file__).resolve().parent / "templates"
SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}
STATUS_ORDER = {"fail": 0, "warn": 1}

_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["j2", "html"]),
                   trim_blocks=True, lstrip_blocks=True)
_env.globals["na"] = lambda v: "N/A" if v is None else v


def split_issues(checks: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Return (issues sorted most important first, everything else)."""
    issues = [c for c in checks if c["status"] in STATUS_ORDER]
    issues.sort(key=lambda c: (SEVERITY_ORDER[c["severity"]], STATUS_ORDER[c["status"]],
                               -WEIGHTS.get(c["category"], {}).get(c["id"], 1)))
    others = [c for c in checks if c["status"] not in STATUS_ORDER]
    return issues, others


def _cwv_rows(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for c in checks:
        if not c["id"].startswith("cwv_"):
            continue
        name = c["id"][4:].upper()
        value = c["data"].get("value")
        rows.append({"name": name, "status": c["status"],
                     "value": _fmt(name, value) if value is not None else "n/a",
                     "source": c["data"].get("source") or c["finding"]})
    return rows


def render_html(report: dict[str, Any]) -> str:
    issues, others = split_issues(report.get("checks", []))
    psi = (report.get("pagespeed") or {}).get("summary")
    cats = (report.get("score") or {}).get("categories", {})
    tech, cont = cats.get("technical", {}), cats.get("content", {})
    sub_for = {
        "technical": f"{len(tech.get('breakdown', []))} scored checks",
        "performance": "0.6 Perf + 0.2 A11y + 0.2 SEO (Lighthouse)" if psi else "PageSpeed not available",
        "content": f"{len(cont.get('breakdown', []))} scored checks",
    }
    return _env.get_template("report.html.j2").render(
        r=report, issues=issues, others=others, psi=psi, cwv=_cwv_rows(report.get("checks", [])),
        cat_label=CATEGORY_LABELS, sub_for=sub_for, tool_version=report.get("tool_version", __version__),
        perf_mix=PERFORMANCE_MIX)


def render_compare_html(cmp: dict[str, Any]) -> str:
    return _env.get_template("compare.html.j2").render(cmp=cmp, tool_version=__version__)


def to_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)

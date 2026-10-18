"""Saved runs and before/after comparison.

Each run is stored as one JSON file: data/history/<host>/<path-slug>/<checked_at>.json
Comparison matches checks by id, so it only reports what was actually measured twice.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "history"
SCORED = {"pass", "warn", "fail"}
RANK = {"fail": 0, "warn": 1, "pass": 2}


def _slug(url: str) -> tuple[str, str]:
    p = urlparse(url)
    host = re.sub(r"[^a-z0-9.-]", "_", p.netloc.lower()) or "unknown"
    path = p.path.strip("/") or "home"
    path = re.sub(r"\.html?$", "", path)
    return host, re.sub(r"[^a-zA-Z0-9_-]+", "_", path)


def run_path(report: dict[str, Any], base: Path = DEFAULT_DIR) -> Path:
    host, path = _slug(report["input"]["url"])
    stamp = report["checked_at"].replace(":", "").replace("+0000", "Z").replace("+00:00", "Z")
    return base / host / path / f"{stamp}.json"


def save(report: dict[str, Any], base: Path = DEFAULT_DIR) -> Path:
    path = run_path(report, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def list_runs(url: str | None = None, base: Path = DEFAULT_DIR) -> list[dict[str, Any]]:
    """Saved runs, newest first. With `url`, only runs for that host + path."""
    if not base.exists():
        return []
    pattern = "*/*/*.json"
    if url:
        host, path = _slug(url)
        pattern = f"{host}/{path}/*.json"
    runs = []
    for f in base.glob(pattern):
        try:
            r = load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(r, dict) or "checked_at" not in r:
            continue
        runs.append({"path": str(f), "url": r["input"]["url"], "checked_at": r["checked_at"],
                     "total": (r.get("score") or {}).get("total")})
    return sorted(runs, key=lambda x: x["checked_at"], reverse=True)


def _checks(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in report.get("checks", [])}


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    b, a = _checks(before), _checks(after)
    fixed, improved, regressed, still_open, new_checks, gone = [], [], [], [], [], []
    for cid in sorted(set(b) | set(a)):
        cb, ca = b.get(cid), a.get(cid)
        if cb is None or ca is None:
            (new_checks if cb is None else gone).append({"id": cid, "label": (ca or cb)["label"]})
            continue
        sb, sa = cb["status"], ca["status"]
        row = {"id": cid, "label": ca["label"], "category": ca["category"], "severity": ca["severity"],
               "before": sb, "after": sa, "finding_before": cb["finding"], "finding_after": ca["finding"]}
        if sb not in SCORED or sa not in SCORED:
            continue  # info / not_checked on either side: nothing to compare
        if RANK[sa] > RANK[sb]:
            (fixed if sa == "pass" else improved).append(row)
        elif RANK[sa] < RANK[sb]:
            regressed.append(row)
        elif sa != "pass":
            still_open.append(row)

    sev = {"High": 0, "Medium": 1, "Low": 2}
    for bucket in (fixed, improved, regressed, still_open):
        bucket.sort(key=lambda x: (sev[x["severity"]], RANK[x["after"]], x["label"]))

    def cat_scores(r):
        sc = r.get("score") or {}
        return {k: v.get("score") for k, v in (sc.get("categories") or {}).items()}, sc.get("total")

    cb_scores, tb = cat_scores(before)
    ca_scores, ta = cat_scores(after)
    labels = {k: v["label"] for k, v in ((after.get("score") or {}).get("categories") or {}).items()}

    def delta(x, y):
        return None if x is None or y is None else y - x

    categories = [{"id": k, "label": labels.get(k, k), "before": cb_scores.get(k), "after": ca_scores.get(k),
                   "delta": delta(cb_scores.get(k), ca_scores.get(k))} for k in ("technical", "performance", "content")]

    notes = []
    if before["input"]["url"] != after["input"]["url"]:
        notes.append(f"URLs differ: {before['input']['url']} vs {after['input']['url']}.")
    if before["input"].get("keyword") != after["input"].get("keyword"):
        notes.append("Target keyword differs between runs, so keyword checks are not like-for-like.")
    if before["input"].get("page_type") != after["input"].get("page_type"):
        notes.append("Page type differs between runs, so trust-signal checks are not like-for-like.")
    if any(c["id"] == "performance" and c["delta"] is not None for c in categories):
        notes.append("Lighthouse lab scores vary between runs (often by several points); "
                     "treat small Performance changes as noise unless repeated.")

    return {
        "before": {"url": before["input"]["url"], "checked_at": before["checked_at"], "total": tb},
        "after": {"url": after["input"]["url"], "checked_at": after["checked_at"], "total": ta},
        "total_delta": delta(tb, ta),
        "categories": categories,
        "fixed": fixed, "improved": improved, "regressed": regressed, "still_open": still_open,
        "new_checks": new_checks, "removed_checks": gone,
        "notes": notes,
    }

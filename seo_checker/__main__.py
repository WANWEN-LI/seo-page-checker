"""CLI.

    python -m seo_checker URL [URL ...] [--keyword K] [--page-type T] [--save] [--html PATH] [--out FILE]
    python -m seo_checker compare BEFORE.json AFTER.json [--html FILE] [--out FILE]
    python -m seo_checker compare --url URL          # latest two saved runs for that URL
    python -m seo_checker history [URL]              # list saved runs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from .analyzer import PAGE_TYPES, analyze
from . import history, report
from .fetcher import Fetcher

ICONS = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "info": "INFO", "not_checked": "SKIP"}


def print_summary(report: dict) -> None:
    print(f"\n== {report['input']['url']}", file=sys.stderr)
    for err in report["errors"]:
        print(f"  ERROR  {err}", file=sys.stderr)
    for c in report["checks"]:
        print(f"  {ICONS[c['status']]:<5} [{c['severity']:<6}] {c['label']}: {c['finding']}", file=sys.stderr)
    sc = report.get("score")
    if sc:
        cats = "  ".join(f"{v['label']}: {v['score'] if v['score'] is not None else 'N/A'}"
                         for v in sc["categories"].values())
        print(f"  SCORE  {sc['total'] if sc['total'] is not None else 'N/A'}/100  ({cats})", file=sys.stderr)
        for n in sc["notes"]:
            print(f"  NOTE   {n}", file=sys.stderr)


def _write(path: str, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def cmd_check(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="seo_checker", description="Audit public pages for SEO, performance and conversion.")
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--keyword")
    ap.add_argument("--page-type", choices=PAGE_TYPES)
    ap.add_argument("--no-link-check", action="store_true", help="skip broken-link requests")
    ap.add_argument("--no-psi", action="store_true", help="skip the PageSpeed Insights API call")
    ap.add_argument("--save", action="store_true", help="store each run in data/history for later comparison")
    ap.add_argument("--html", help="write an HTML report (a directory when several URLs are given)")
    ap.add_argument("--out", help="write JSON to this file instead of stdout")
    args = ap.parse_args(argv)

    fetcher = Fetcher()
    reports = [analyze(u, args.keyword, args.page_type, fetcher, not args.no_link_check, not args.no_psi) for u in args.urls]
    for r in reports:
        print_summary(r)
        if args.save:
            print(f"  SAVED  {history.save(r)}", file=sys.stderr)
    if args.html:
        if len(reports) == 1:
            _write(args.html, report.render_html(reports[0]))
            print(f"\nHTML written to {args.html}", file=sys.stderr)
        else:
            for r in reports:
                host, path = history._slug(r["input"]["url"])
                target = Path(args.html) / f"{host}_{path}.html"
                _write(str(target), report.render_html(r))
                print(f"HTML written to {target}", file=sys.stderr)
    payload = report.to_json(reports[0] if len(reports) == 1 else reports)
    if args.out:
        _write(args.out, payload)
        print(f"\nJSON written to {args.out}", file=sys.stderr)
    elif not args.html:
        print(payload)
    return 0


def cmd_compare(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="seo_checker compare", description="Compare two saved runs.")
    ap.add_argument("files", nargs="*", help="BEFORE.json AFTER.json")
    ap.add_argument("--url", help="use the latest two saved runs for this URL")
    ap.add_argument("--html")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.url:
        runs = history.list_runs(args.url)
        if len(runs) < 2:
            print(f"Need at least two saved runs for {args.url}; found {len(runs)}.", file=sys.stderr)
            return 1
        before, after = history.load(runs[1]["path"]), history.load(runs[0]["path"])
    elif len(args.files) == 2:
        before, after = history.load(args.files[0]), history.load(args.files[1])
    else:
        ap.error("give BEFORE.json AFTER.json, or --url URL")
    cmp = history.compare(before, after)
    tb, ta = cmp["before"]["total"], cmp["after"]["total"]
    print(f"Total: {tb} -> {ta}  | fixed {len(cmp['fixed'])}, improved {len(cmp['improved'])}, "
          f"regressed {len(cmp['regressed'])}, still open {len(cmp['still_open'])}", file=sys.stderr)
    for n in cmp["notes"]:
        print(f"NOTE  {n}", file=sys.stderr)
    if args.html:
        _write(args.html, report.render_compare_html(cmp))
        print(f"HTML written to {args.html}", file=sys.stderr)
    if args.out:
        _write(args.out, report.to_json(cmp))
    if not args.html and not args.out:
        print(report.to_json(cmp))
    return 0


def cmd_history(argv: list[str]) -> int:
    url = argv[0] if argv else None
    for run in history.list_runs(url):
        print(f"{run['checked_at']}  total={run['total']}  {run['url']}\n    {run['path']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    load_dotenv()
    if argv and argv[0] == "compare":
        return cmd_compare(argv[1:])
    if argv and argv[0] == "history":
        return cmd_history(argv[1:])
    return cmd_check(argv)


if __name__ == "__main__":
    sys.exit(main())

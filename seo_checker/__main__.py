"""CLI: python -m seo_checker URL [URL ...] [--keyword K] [--page-type T] [--out FILE]"""

from __future__ import annotations

import argparse
import json
import sys

from .analyzer import PAGE_TYPES, analyze
from .fetcher import Fetcher

ICONS = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "info": "INFO", "not_checked": "SKIP"}


def print_summary(report: dict) -> None:
    print(f"\n== {report['input']['url']}", file=sys.stderr)
    for err in report["errors"]:
        print(f"  ERROR  {err}", file=sys.stderr)
    for c in report["checks"]:
        print(f"  {ICONS[c['status']]:<5} [{c['severity']:<6}] {c['label']}: {c['finding']}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="seo_checker", description="Audit public pages for technical SEO.")
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--keyword")
    ap.add_argument("--page-type", choices=PAGE_TYPES)
    ap.add_argument("--no-link-check", action="store_true", help="skip broken-link requests")
    ap.add_argument("--out", help="write JSON to this file instead of stdout")
    args = ap.parse_args(argv)

    fetcher = Fetcher()
    reports = [analyze(u, args.keyword, args.page_type, fetcher, not args.no_link_check) for u in args.urls]
    for r in reports:
        print_summary(r)
    payload = json.dumps(reports[0] if len(reports) == 1 else reports, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"\nJSON written to {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())

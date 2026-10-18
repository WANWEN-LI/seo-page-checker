"""Build the static showcase (site/seo-checker) with real numbers from examples/*/raw.json.

    python scripts/build_showcase.py [OUT_DIR]   # default: site/build/seo-checker

Scores and dates are read from the saved reports, never typed by hand.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def by_url(runs: list[dict], suffix: str) -> dict:
    return next(r for r in runs if r["input"]["url"].rstrip("/").endswith(suffix.rstrip("/")))


def main(out: Path) -> None:
    portfolio = load(EX / "portfolio-before" / "raw.json")
    petal = load(EX / "petal-store" / "raw.json")
    ikea = load(EX / "ikea-product" / "raw.json")
    home, about = by_url(portfolio, "liwanwen.com/"), by_url(portfolio, "/about")

    values = {
        "{{PORTFOLIO_BEFORE}}": f"{home['score']['total']} (home) · {about['score']['total']} (about)",
        "{{PETAL}}": str(petal["score"]["total"]),
        "{{IKEA}}": str(ikea["score"]["total"]),
        "{{IKEA_DATE}}": ikea["checked_at"][:10],
    }
    html = (ROOT / "site" / "seo-checker" / "index.html").read_text(encoding="utf-8")
    for k, v in values.items():
        assert k in html, k
        html = html.replace(k, v)
    assert "{{" not in html, "unfilled placeholder"

    if out.exists():
        shutil.rmtree(out)
    (out / "reports").mkdir(parents=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    copies = {
        EX / "portfolio-before" / "liwanwen.com_home.html": "portfolio-before-home.html",
        EX / "portfolio-before" / "liwanwen.com_about.html": "portfolio-before-about.html",
        EX / "petal-store" / "report.html": "petal-store.html",
        EX / "ikea-product" / "report.html": "ikea-product.html",
    }
    for src, name in copies.items():
        shutil.copy(src, out / "reports" / name)
    print(f"built {out} with", values)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site" / "build" / "seo-checker")

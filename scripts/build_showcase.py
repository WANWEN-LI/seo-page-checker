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
    petal = load(EX / "petal-before" / "raw.json")
    ikea = load(EX / "ikea-product" / "raw.json")
    home, about = by_url(portfolio, "liwanwen.com/"), by_url(portfolio, "/about")

    lh = load(EX / "portfolio-after" / "lighthouse-summary.json")["pages"]
    after = load(EX / "portfolio-after" / "raw.json")
    rows = []
    for path, name in (("/", "home"), ("/about", "about"), ("/projects", "projects"), ("/photography", "photography")):
        c = load(EX / "portfolio-after" / f"compare-{name}.json"); m = lh[path]
        rows.append(f'    <tr><td>{path}</td><td class="num">{c["before"]["total"]} → {c["after"]["total"]}</td>'
                    f'<td class="num">{m["median"]["before_perf"]:g} → {m["median"]["after_perf"]:g} '
                    f'<span class="note">(n={len(m["before"])}→{len(m["after"])})</span></td>'
                    f'<td class="num">{m["median"]["before_lcp_s"]} s → {m["median"]["after_lcp_s"]} s</td>'
                    f'<td><a href="reports/compare-{name}.html">Compare</a></td></tr>')

    ps = load(EX / "petal-after" / "summary.json"); pm = ps["median"]
    petal_values = {
        "{{P_TOTAL_B}}": str(ps["tool_total"]["before"]), "{{P_TOTAL_A}}": str(ps["tool_total"]["after"]),
        "{{P_CAT_ROWS}}": "\n".join(f'    <tr><td>{k}</td><td class="num">{v[0]}</td><td class="num">{v[1]}</td></tr>'
                                    for k, v in ps["categories"].items()),
        "{{P_NB}}": str(len(ps["before"])), "{{P_NA}}": str(len(ps["after"])),
        "{{P_PERF_B}}": f'{pm["before_perf"]:g}', "{{P_PERF_A}}": f'{pm["after_perf"]:g}',
        "{{P_LCP_B}}": str(pm["before_lcp_s"]), "{{P_LCP_A}}": str(pm["after_lcp_s"]),
        "{{P_KB_B}}": f'{pm["before_total_kb"]:,}', "{{P_KB_A}}": f'{pm["after_total_kb"]:,}',
        "{{P_FIXED}}": ", ".join(ps["fixed"]), "{{P_OPEN}}": ", ".join(ps["still_open"]),
    }
    values = {
        **petal_values,
        "{{BA_ROWS}}": "\n".join(rows),
        "{{AFTER_DATE}}": after[0]["checked_at"][:10],
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
        EX / "petal-before" / "report.html": "petal-before.html",
        EX / "petal-after" / "compare.html": "petal-compare.html",
        EX / "ikea-product" / "report.html": "ikea-product.html",
        **{EX / "portfolio-after" / f"compare-{n}.html": f"compare-{n}.html" for n in ("home", "about", "projects", "photography")},
    }
    for src, name in copies.items():
        shutil.copy(src, out / "reports" / name)
    print(f"built {out} with", values)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site" / "build" / "seo-checker")

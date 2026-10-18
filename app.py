"""Streamlit UI: streamlit run app.py"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from seo_checker import history, report
from seo_checker.analyzer import PAGE_TYPES, analyze
from seo_checker.fetcher import Fetcher

load_dotenv()
MAX_URLS = 10
STATUS_TEXT = {"pass": "✓ Pass", "warn": "! Warning", "fail": "✕ Fail", "info": "i Info", "not_checked": "– Not checked"}

st.set_page_config(page_title="Page SEO Checker", page_icon="🔎", layout="wide")
st.title("Listing & Page SEO Checker")
st.caption("Technical SEO, mobile performance and conversion checks for a public page, "
           "with a transparent 0–100 score and prioritised fixes.")

with st.sidebar:
    st.subheader("Configuration")
    st.write("PageSpeed API key:", "configured" if os.getenv("PAGESPEED_API_KEY") else "not set (anonymous, rate-limited)")
    st.write("AI suggestions:", "configured" if os.getenv("ANTHROPIC_API_KEY") else "off (no ANTHROPIC_API_KEY)")
    st.divider()
    st.caption("Respects robots.txt, waits ≥1 s between requests to a host, reads public pages only. "
               f"Up to {MAX_URLS} URLs per run.")


def issues_frame(checks: list[dict]) -> pd.DataFrame:
    issues, _ = report.split_issues(checks)
    return pd.DataFrame([{
        "Status": STATUS_TEXT[c["status"]], "Severity": c["severity"], "Check": c["label"],
        "Category": report.CATEGORY_LABELS[c["category"]], "Finding": c["finding"], "How to fix": c["fix"],
    } for c in issues])


def score_row(r: dict) -> None:
    sc = r.get("score")
    if not sc:
        return
    cols = st.columns(4)
    cols[0].metric("Total", "N/A" if sc["total"] is None else f"{sc['total']}/100")
    for col, key in zip(cols[1:], ("technical", "performance", "content")):
        c = sc["categories"][key]
        col.metric(c["label"], "N/A" if c["score"] is None else f"{c['score']}/100")
    for n in sc["notes"]:
        st.caption(n)


def show_report(r: dict, key: str) -> None:
    for e in r["errors"]:
        st.warning(e)
    score_row(r)
    if not r["checks"]:
        return
    df = issues_frame(r["checks"])
    st.markdown(f"**Issues to fix ({len(df)})** — sorted by severity")
    if len(df):
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.success("No failing or warning checks.")
    ai = r.get("ai")
    if ai and not ai["ok"]:
        st.caption(f"AI suggestions: {ai['error']}")
    elif ai:
        st.markdown("**AI suggestions** — based only on the findings above; review before use")
        if ai["fixes"]:
            st.dataframe(pd.DataFrame([{"#": i, "Fix": f["title"], "Impact": f["impact"], "Effort": f["effort"],
                                        "Evidence": f["evidence"], "Action": f["action"]}
                                       for i, f in enumerate(ai["fixes"], 1)]), hide_index=True, width="stretch")
        c1, c2 = st.columns(2)
        for col, name, rows in ((c1, "Title options", ai["titles"]), (c2, "Meta description options", ai["descriptions"])):
            col.markdown(f"*{name}*")
            for t in rows:
                col.markdown(f"- {t['text']}  \n  `{t['chars']} chars{'' if t['in_range'] else ' — outside target range'}`")
    with st.expander("All checks (raw)"):
        st.dataframe(pd.DataFrame([{"Status": STATUS_TEXT[c["status"]], "Check": c["label"], "Finding": c["finding"]}
                                   for c in r["checks"]]), hide_index=True, width="stretch")
    host, path = history._slug(r["input"]["url"])
    c1, c2 = st.columns(2)
    c1.download_button("Download HTML report", report.render_html(r), file_name=f"seo-report_{host}_{path}.html",
                       mime="text/html", key=f"html-{key}")
    c2.download_button("Download JSON (raw data)", report.to_json(r), file_name=f"seo-report_{host}_{path}.json",
                       mime="application/json", key=f"json-{key}")


tab_check, tab_compare, tab_history = st.tabs(["Check pages", "Before / after", "History"])

with tab_check:
    with st.form("check"):
        urls_text = st.text_area("URL(s), one per line", placeholder="https://example.com/product")
        c1, c2 = st.columns(2)
        keyword = c1.text_input("Target keyword (optional)")
        page_type = c2.selectbox("Page type (optional)", ["(not set)", *PAGE_TYPES])
        c3, c4, c5, c6 = st.columns(4)
        run_psi = c3.checkbox("Run PageSpeed Insights", value=True)
        check_links = c4.checkbox("Check for broken links", value=True)
        has_ai = bool(os.getenv("ANTHROPIC_API_KEY"))
        run_ai = c5.checkbox("AI suggestions (Claude)", value=has_ai, disabled=not has_ai,
                             help=None if has_ai else "Set ANTHROPIC_API_KEY in .env to enable.")
        save = c6.checkbox("Save to history", value=True)
        submitted = st.form_submit_button("Run check", type="primary")

    if submitted:
        urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
        if not urls:
            st.error("Enter at least one URL.")
        elif len(urls) > MAX_URLS:
            st.error(f"At most {MAX_URLS} URLs per run; this tool is not a crawler.")
        else:
            fetcher, results = Fetcher(), []
            with st.status(f"Checking {len(urls)} page(s)…", expanded=True) as status:
                for u in urls:
                    st.write(f"{u} — fetching, analysing" + (", running PageSpeed (30–60 s)…" if run_psi else "…"))
                    r = analyze(u, keyword or None, None if page_type == "(not set)" else page_type,
                                fetcher, check_links, run_psi, run_ai)
                    if save and r["checks"]:
                        history.save(r)
                    results.append(r)
                status.update(label="Done", state="complete")
            st.session_state["results"] = results

    for i, r in enumerate(st.session_state.get("results", [])):
        st.subheader(r["input"]["url"])
        st.caption(f"Checked {r['checked_at']} · keyword: {r['input']['keyword'] or 'none'} · "
                   f"page type: {r['input']['page_type'] or 'not set'}")
        show_report(r, str(i))
        st.divider()

with tab_compare:
    runs = history.list_runs()
    urls = sorted({x["url"] for x in runs})
    if not urls:
        st.info("No saved runs yet. Run a check with 'Save to history' on, change the page, then run it again.")
    else:
        url = st.selectbox("Page", urls, index=urls.index(runs[0]["url"]))  # default: most recently checked
        page_runs = history.list_runs(url)
        if len(page_runs) < 2:
            st.info(f"Only {len(page_runs)} saved run for this page. Run another check after changing the page.")
        else:
            label = lambda x: f"{x['checked_at']}  (total {x['total']})"
            c1, c2 = st.columns(2)
            b_run = c1.selectbox("Before", page_runs, index=1, format_func=label)
            a_run = c2.selectbox("After", page_runs, index=0, format_func=label)
            cmp = history.compare(history.load(b_run["path"]), history.load(a_run["path"]))
            for n in cmp["notes"]:
                st.caption(n)
            cols = st.columns(4)
            fmt = lambda v: "N/A" if v is None else f"{v}/100"
            cols[0].metric("Total", fmt(cmp["after"]["total"]), cmp["total_delta"])
            for col, c in zip(cols[1:], cmp["categories"]):
                col.metric(c["label"], fmt(c["after"]), c["delta"])
            for title, rows in (("Fixed", cmp["fixed"]), ("Improved", cmp["improved"]),
                                ("Regressed", cmp["regressed"]), ("Still open", cmp["still_open"])):
                st.markdown(f"**{title} ({len(rows)})**")
                if rows:
                    st.dataframe(pd.DataFrame([{"Check": x["label"], "Severity": x["severity"],
                                                "Before": STATUS_TEXT[x["before"]], "After": STATUS_TEXT[x["after"]],
                                                "Finding now": x["finding_after"]} for x in rows]),
                                 hide_index=True, width="stretch")
            host, path = history._slug(url)
            st.download_button("Download comparison (HTML)", report.render_compare_html(cmp),
                               file_name=f"seo-compare_{host}_{path}.html", mime="text/html")

with tab_history:
    runs = history.list_runs()
    if runs:
        st.dataframe(pd.DataFrame([{"Checked at": x["checked_at"], "Total": x["total"], "URL": x["url"]} for x in runs]),
                     hide_index=True, width="stretch")
    else:
        st.info("No saved runs yet.")

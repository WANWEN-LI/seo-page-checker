import copy

from seo_checker import history, report


def make_report(url="https://example.com/about.html", when="2026-10-18T05:00:00+00:00", statuses=None, total=70):
    statuses = statuses or {}
    checks = []
    for cid, cat, sev, default in [("canonical", "technical", "Medium", "warn"),
                                   ("h1_count", "technical", "High", "pass"),
                                   ("json_ld", "technical", "Medium", "fail"),
                                   ("cta_fold", "content", "High", "fail"),
                                   ("link_counts", "technical", "Low", "info")]:
        checks.append({"id": cid, "category": cat, "label": cid, "status": statuses.get(cid, default),
                       "severity": sev, "finding": f"{cid} finding", "why": "", "fix": "", "data": {}})
    return {"tool_version": "test", "checked_at": when,
            "input": {"url": url, "keyword": None, "page_type": "portfolio"},
            "checks": checks, "errors": [], "pagespeed": None,
            "score": {"total": total, "notes": [], "categories": {
                "technical": {"label": "Technical", "score": total, "breakdown": []},
                "performance": {"label": "Performance", "score": None, "breakdown": {}},
                "content": {"label": "Content & Conversion", "score": total, "breakdown": []}}}}


def test_slug_normalises_html_suffix_and_home():
    assert history._slug("https://Example.com/about.html") == ("example.com", "about")
    assert history._slug("https://example.com/about") == ("example.com", "about")
    assert history._slug("https://example.com/") == ("example.com", "home")


def test_save_and_list_newest_first(tmp_path):
    history.save(make_report(when="2026-10-18T05:00:00+00:00", total=70), tmp_path)
    history.save(make_report(when="2026-10-19T05:00:00+00:00", total=80), tmp_path)
    history.save(make_report(url="https://example.com/", total=50), tmp_path)
    runs = history.list_runs("https://example.com/about", tmp_path)
    assert [r["total"] for r in runs] == [80, 70]
    assert len(history.list_runs(base=tmp_path)) == 3


def test_compare_buckets_and_deltas():
    before = make_report(total=60)
    after = make_report(when="2026-10-19T05:00:00+00:00", total=75,
                        statuses={"canonical": "pass", "json_ld": "warn", "h1_count": "fail"})
    cmp = history.compare(before, after)
    assert [x["id"] for x in cmp["fixed"]] == ["canonical"]
    assert [x["id"] for x in cmp["improved"]] == ["json_ld"]
    assert [x["id"] for x in cmp["regressed"]] == ["h1_count"]
    assert [x["id"] for x in cmp["still_open"]] == ["cta_fold"]
    assert cmp["total_delta"] == 15
    perf = next(c for c in cmp["categories"] if c["id"] == "performance")
    assert perf["delta"] is None  # N/A on both sides: no fabricated change


def test_compare_flags_different_inputs():
    after = make_report(url="https://example.com/about")
    after["input"]["keyword"] = "seo"
    notes = " ".join(history.compare(make_report(), after)["notes"])
    assert "URLs differ" in notes and "keyword" in notes


def test_issue_order_high_fail_first():
    issues, others = report.split_issues(make_report()["checks"])
    assert [c["id"] for c in issues] == ["cta_fold", "json_ld", "canonical"]
    assert {c["id"] for c in others} == {"h1_count", "link_counts"}


def test_html_report_escapes_page_content():
    r = make_report()
    r["checks"][0]["finding"] = '<script>alert(1)</script>'
    html = report.render_html(r)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "N/A" in html  # performance tile


def test_compare_html_renders():
    html = report.render_compare_html(history.compare(make_report(), make_report(statuses={"canonical": "pass"})))
    assert "Before / after comparison" in html and "Fixed (1)" in html


def test_failed_fetch_report_renders():
    r = make_report()
    r.update(checks=[], score=None, errors=["Page could not be audited: [timeout] No response within 10s."])
    assert "could not be audited" in report.render_html(r)


def test_compare_rows_sorted_by_severity():
    before = make_report(statuses={"canonical": "fail", "h1_count": "warn"})
    after = make_report(statuses={"canonical": "fail", "h1_count": "warn"})
    assert [x["severity"] for x in history.compare(before, after)["still_open"]][:2] == ["High", "High"]

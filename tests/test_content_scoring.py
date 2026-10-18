from pathlib import Path

from seo_checker import content, performance, scoring, technical

FIX = Path(__file__).parent / "fixtures"
URL = "https://example.com/vase"


def run(name, keyword=None, page_type=None):
    html = (FIX / name).read_text()
    tech = technical.extract_all(html, URL)
    facts = content.extract_all(html)
    return facts, {c.id: c for c in content.evaluate(facts, tech, keyword, page_type)}


# --- content ----------------------------------------------------------------
def test_product_page_fold_cta_and_trust():
    facts, checks = run("product.html", keyword="ceramic vase", page_type="product")
    assert checks["cta_fold"].status == "pass"
    assert facts["fold"]["ctas"][0]["label"] == "Add to cart"
    assert checks["value_prop"].status in {"pass", "warn"}
    for key in ("trust_price", "trust_reviews", "trust_shipping_returns", "trust_product_schema"):
        assert checks[key].status == "pass", key
    assert "€48.00" in facts["trust"]["price_examples"]


def test_nav_links_are_not_counted_as_cta():
    html = "<body><nav><a href='/shop'>Shop now</a></nav><h1>Hi</h1><p>Text only here.</p></body>"
    fold = content.above_the_fold(content.BeautifulSoup(html, "lxml"))
    assert fold["ctas"] == []


def test_keyword_placement_partial():
    _, checks = run("product.html", keyword="stoneware")
    c = checks["keyword_placement"]
    assert c.status == "warn"
    assert c.data["places"] == {"title": False, "h1": False, "first_paragraph": True}


def test_missing_trust_signals_for_portfolio():
    _, checks = run("bad.html", page_type="portfolio")
    assert checks["trust_contact"].status == "fail"
    assert checks["cta_fold"].status == "fail"


def test_no_page_type_means_not_checked():
    _, checks = run("product.html")
    assert checks["trust_signals"].status == "not_checked"
    assert checks["keyword_placement"].status == "not_checked"


def test_readability_counts():
    r = content.readability(["One two three four. Five six seven eight nine ten.", "Short para here."])
    assert r["sentences"] == 3 and r["words"] == 13 and r["paragraphs"] == 2
    assert r["flesch_reading_ease"] is None  # under the minimum word count


# --- performance --------------------------------------------------------------
def test_localhost_is_not_public():
    assert performance.is_public_url("http://localhost:4174/")[0] is False
    assert performance.is_public_url("http://127.0.0.1:8931/")[0] is False


def test_psi_skipped_for_local_url():
    r = performance.run_pagespeed("http://127.0.0.1:8931/")
    assert r["ok"] is False and "public" in r["error"]
    assert performance.evaluate(r)[0].status == "not_checked"


def test_psi_summarize_and_evaluate():
    raw = {
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.72}, "seo": {"score": 0.92}, "accessibility": {"score": 0.88}},
            "audits": {"largest-contentful-paint": {"numericValue": 3120.4},
                       "cumulative-layout-shift": {"numericValue": 0.0213}},
        },
        "loadingExperience": {},
        "originLoadingExperience": {"metrics": {"INTERACTION_TO_NEXT_PAINT": {"percentile": 180, "category": "FAST"}}},
    }
    s = performance.summarize(raw)
    assert s["scores"] == {"performance": 72, "seo": 92, "accessibility": 88}
    assert s["lab"] == {"LCP": 3120, "CLS": 0.021}
    checks = {c.id: c for c in performance.evaluate({"ok": True, "summary": s})}
    assert checks["lh_performance"].status == "warn"
    assert checks["cwv_lcp"].status == "warn" and "lab" in checks["cwv_lcp"].data["source"]
    assert checks["cwv_inp"].status == "pass" and "origin" in checks["cwv_inp"].data["source"]


# --- scoring ------------------------------------------------------------------
def chk(id_, cat, status, **data):
    return {"id": id_, "category": cat, "status": status, "data": data}


def test_weighted_category_score_ignores_info_and_not_checked():
    checks = [chk("h1_count", "technical", "pass"),        # w3 -> 3
              chk("canonical", "technical", "warn"),       # w2 -> 1
              chk("lang", "technical", "fail"),            # w1 -> 0
              chk("link_counts", "technical", "info"),
              chk("keyword_placement", "content", "not_checked")]
    s = scoring.score_report(checks)
    assert s["categories"]["technical"]["score"] == round(100 * 4 / 6)
    assert s["categories"]["content"]["score"] is None


def test_total_renormalises_when_performance_missing():
    checks = [chk("h1_count", "technical", "pass"), chk("cta_fold", "content", "fail")]
    s = scoring.score_report(checks)
    # technical 100 (w0.4), content 0 (w0.3) -> 40/0.7 = 57
    assert s["total"] == 57
    assert s["notes"] and "Performance" in s["notes"][0]


def test_performance_mix():
    checks = [chk("lh_performance", "performance", "warn", score=70),
              chk("lh_accessibility", "performance", "pass", score=90),
              chk("lh_seo", "performance", "pass", score=100)]
    assert scoring.score_report(checks)["categories"]["performance"]["score"] == 80


def test_fold_heading_matches_h1_with_split_punctuation():
    html = "<body><h1>Understanding the work<span>.</span> Building</h1>" + "<p>word </p>" * 30 + "</body>"
    tech = technical.extract_all(html, URL)
    checks = {c.id: c for c in content.evaluate(content.extract_all(html), tech, None, None)}
    assert checks["value_prop"].status == "pass"


class FakeResp:
    def __init__(self, status, payload=None):
        self.status_code, self._payload, self.text = status, payload, "<html>Sorry</html>"

    def json(self):
        if self._payload is None:
            raise ValueError
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), 0

    def get(self, *a, **kw):
        self.calls += 1
        return self.responses.pop(0)


def test_psi_retries_once_on_429(monkeypatch):
    monkeypatch.setattr(performance, "is_public_url", lambda u: (True, ""))
    monkeypatch.setattr(performance, "RETRY_DELAY", 0)
    ok = {"lighthouseResult": {"categories": {"performance": {"score": 0.5}}}}
    s = FakeSession([FakeResp(429), FakeResp(200, ok)])
    r = performance.run_pagespeed("https://example.com/", api_key="k", session=s)
    assert r["ok"] and s.calls == 2


def test_psi_429_message_does_not_leak_key(monkeypatch):
    monkeypatch.setattr(performance, "is_public_url", lambda u: (True, ""))
    monkeypatch.setattr(performance, "RETRY_DELAY", 0)
    s = FakeSession([FakeResp(429), FakeResp(429, {"error": {"message": "bad key SECRETKEY"}})])
    r = performance.run_pagespeed("https://example.com/", api_key="SECRETKEY", session=s)
    assert not r["ok"] and "SECRETKEY" not in r["error"] and "rate-limited" in r["error"]


def test_fold_text_ignores_html_comments():
    html = "<body><!-- Google Tag Manager (noscript) --><h1>Vase</h1><!-- <p>old banner</p> --><p>Real copy.</p></body>"
    text = content.above_the_fold(content.BeautifulSoup(html, "lxml"))["text"]
    assert "Google Tag Manager" not in text and "old banner" not in text and "Real copy." in text


def test_trust_signals_in_italian():
    html = "<body><h1>Scaffale</h1><p>Prezzo € 55. Servizi di consegna. Cambi e resi. Recensioni totali: 1884</p></body>"
    t = content.trust_signals(content.BeautifulSoup(html, "lxml"))
    assert t["shipping_returns"] and t["reviews"] and t["price"]


def test_readability_not_scored_for_non_english():
    html = '<html lang="it-IT"><body><h1>Scaffale</h1>' + "<p>Questa è una frase di prova per il testo.</p>" * 30 + "</body></html>"
    tech = technical.extract_all(html, URL)
    checks = {c.id: c for c in content.evaluate(content.extract_all(html), tech, None, None)}
    assert checks["readability"].status == "not_checked" and "it-it" in checks["readability"].finding


def test_cta_verbs_cover_discover_find_choose():
    html = "<body><h1>Soap</h1><a href='#subscribe'>Discover the €5.99 welcome off</a><button>Choose chamomile →</button></body>"
    labels = [c["label"] for c in content.above_the_fold(content.BeautifulSoup(html, "lxml"))["ctas"]]
    assert labels == ["Discover the €5.99 welcome off", "Choose chamomile →"]

from pathlib import Path

import pytest

from seo_checker import technical as t
from seo_checker.fetcher import RobotsRules

FIX = Path(__file__).parent / "fixtures"
URL = "https://example.com/vases"


@pytest.fixture
def good():
    return t.extract_all((FIX / "good.html").read_text(), URL)


@pytest.fixture
def bad():
    return t.extract_all((FIX / "bad.html").read_text(), URL)


def by_id(checks):
    return {c.id: c for c in checks}


# --- title ---------------------------------------------------------------
def test_title_extracted_and_whitespace_collapsed(good, bad):
    assert good["title"] == "Handmade Ceramic Vases | Petal Atelier Studio"
    assert bad["title"] == "Home"


def test_title_missing():
    assert t.extract_title(t.parse("<html><head></head></html>")) is None


def test_title_length_and_keyword(good, bad):
    g = by_id(t.evaluate(good, keyword="ceramic vases"))
    assert g["title_length"].status == "pass" and g["title_length"].data["length"] == 45
    assert g["title_keyword"].status == "pass"
    b = by_id(t.evaluate(bad, keyword="ceramic vases"))
    assert b["title_length"].status == "warn"
    assert b["title_keyword"].status == "fail"


# --- meta ----------------------------------------------------------------
def test_meta_description(good, bad):
    assert good["meta_description"].startswith("Small-batch ceramic vases")
    assert bad["meta_description"] is None
    assert by_id(t.evaluate(good))["meta_description"].status == "pass"
    assert by_id(t.evaluate(bad))["meta_description"].status == "fail"


def test_meta_name_is_case_insensitive():
    soup = t.parse('<meta NAME="Description" content="Hello">')
    assert t.extract_meta_description(soup) == "Hello"


def test_robots_noindex_and_lang(good, bad):
    assert bad["head"]["robots"] == "noindex, nofollow"
    assert by_id(t.evaluate(bad))["robots_meta"].status == "fail"
    assert good["head"]["lang"] == "en" and bad["head"]["lang"] is None


def test_canonical_resolved(good):
    assert good["head"]["canonical"] == "https://example.com/vases"
    assert by_id(t.evaluate(good, page_url=URL))["canonical"].status == "pass"


# --- headings ------------------------------------------------------------
def test_single_h1(good):
    assert good["headings"]["h1"] == ["Handmade ceramic vases"]
    assert by_id(t.evaluate(good))["h1_count"].status == "pass"


def test_multiple_h1_and_hierarchy(bad):
    assert bad["headings"]["h1"] == ["First", "Second"]
    checks = by_id(t.evaluate(bad))
    assert checks["h1_count"].status == "warn"
    problems = checks["heading_hierarchy"].data["problems"]
    assert any("First heading is H3" in p for p in problems)
    assert any("H1 followed by H4" in p for p in problems)


def test_no_h1():
    facts = t.extract_all("<html><body><h2>x</h2></body></html>", URL)
    assert by_id(t.evaluate(facts))["h1_count"].status == "fail"


def test_valid_hierarchy_has_no_problems(good):
    assert t.heading_problems(good["headings"]["outline"]) == []


# --- JSON-LD -------------------------------------------------------------
def test_json_ld_graph_types(good):
    ld = good["json_ld"]
    assert ld["valid_blocks"] == 1
    assert set(ld["types"]) == {"Organization", "Product"}
    assert by_id(t.evaluate(good))["json_ld"].status == "pass"


def test_json_ld_invalid(bad):
    assert bad["json_ld"]["valid_blocks"] == 0
    assert bad["json_ld"]["errors"]
    assert by_id(t.evaluate(bad))["json_ld"].status == "fail"


def test_json_ld_list_and_type_array():
    html = '''<script type="application/ld+json">[{"@type": ["Person", "Thing"]}, {"@type": "WebSite"}]</script>'''
    assert t.extract_json_ld(t.parse(html))["types"] == ["Person", "Thing", "WebSite"]


def test_json_ld_absent():
    assert t.extract_json_ld(t.parse("<p>hi</p>"))["count"] == 0


# --- images, social, links ----------------------------------------------
def test_image_alt_counts(good, bad):
    assert good["images"] == {"total": 2, "with_alt": 1, "empty_alt": 1, "missing_alt": 0, "missing_alt_src": []}
    assert bad["images"]["missing_alt"] == 2
    assert by_id(t.evaluate(bad))["image_alt"].data["coverage_pct"] == 33


def test_social_tags(good, bad):
    assert by_id(t.evaluate(good))["open_graph"].status == "pass"
    assert by_id(t.evaluate(bad))["open_graph"].data["missing"] == ["og:title", "og:description", "og:image"]


def test_links_internal_external_dedup(good):
    links = good["links"]
    # /about and /about#team collapse into one; www. counts as same site; mailto and # are ignored
    assert links["internal"] == ["https://example.com/about", "https://www.example.com/contact"]
    assert links["external"] == ["https://instagram.com/petal"]


# --- robots.txt ----------------------------------------------------------
def test_robots_rules():
    rules = RobotsRules.from_text("User-agent: *\nDisallow: /private\nSitemap: https://example.com/sm.xml\n")
    assert rules.allowed("https://example.com/vases")
    assert not rules.allowed("https://example.com/private/x")
    assert rules.sitemaps == ["https://example.com/sm.xml"]


def test_robots_missing_and_unreachable():
    assert RobotsRules("missing").allowed("https://example.com/")
    assert not RobotsRules("unreachable").allowed("https://example.com/")


def test_heading_text_keeps_space_across_inline_tags():
    soup = t.parse("<h1>Understanding the work.<br>Building <span>what</span> helps<span>.</span></h1>")
    assert t.extract_headings(soup)["h1"] == ["Understanding the work. Building what helps."]

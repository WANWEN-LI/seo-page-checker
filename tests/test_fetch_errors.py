from seo_checker.analyzer import analyze
from seo_checker.fetcher import Fetcher


def test_invalid_url_is_reported_not_raised():
    r = analyze("not-a-url", fetcher=Fetcher(min_interval=0))
    assert r["fetch"]["error_type"] == "invalid_url"
    assert r["checks"] == [] and r["errors"]


def test_unreachable_host_is_reported_not_raised():
    # port 9 (discard) on localhost is normally closed -> connection refused
    r = analyze("http://127.0.0.1:9/", fetcher=Fetcher(timeout=2, min_interval=0))
    assert r["fetch"]["error_type"] in {"robots_disallowed", "connection", "timeout"}
    assert r["errors"]

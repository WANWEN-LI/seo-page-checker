"""Polite HTTP fetching: robots.txt compliance, per-domain rate limiting, timeouts and
classified errors. No cookies or credentials are ever sent, so only public pages are read."""

from __future__ import annotations

import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from .models import FetchResult

USER_AGENT = "SEOPageChecker/0.1 (read-only SEO audit tool)"
ROBOTS_AGENT = "SEOPageChecker"
DEFAULT_TIMEOUT = 10.0
DEFAULT_MIN_INTERVAL = 1.0  # seconds between requests to the same host
MAX_HTML_BYTES = 5 * 1024 * 1024


def origin_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


class RobotsRules:
    """Parsed robots.txt for one origin, following RFC 9309 for unreachable files:
    4xx -> everything allowed, 5xx or network error -> everything disallowed."""

    def __init__(self, status: str, text: str = "", source_status_code: int | None = None, error: str | None = None):
        self.status = status  # "found" | "missing" | "unreachable"
        self.text = text
        self.source_status_code = source_status_code
        self.error = error
        self._parser = RobotFileParser()
        if status == "found":
            self._parser.parse(text.splitlines())

    @classmethod
    def from_text(cls, text: str) -> "RobotsRules":
        return cls("found", text, 200)

    def allowed(self, url: str, agent: str = ROBOTS_AGENT) -> bool:
        if self.status == "missing":
            return True
        if self.status == "unreachable":
            return False
        return self._parser.can_fetch(agent, url)

    @property
    def sitemaps(self) -> list[str]:
        if self.status != "found":
            return []
        return list(self._parser.site_maps() or [])


class Fetcher:
    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        user_agent: str = USER_AGENT,
        session: requests.Session | None = None,
    ):
        self.timeout = timeout
        self.min_interval = min_interval
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Language": "en"})
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotsRules] = {}

    # --- rate limiting -------------------------------------------------
    def _wait_turn(self, url: str) -> None:
        host = urlparse(url).netloc.lower()
        last = self._last_request.get(host)
        if last is not None:
            remaining = self.min_interval - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request[host] = time.monotonic()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        self._wait_turn(url)
        return self.session.request(method, url, timeout=self.timeout, **kwargs)

    # --- robots.txt ----------------------------------------------------
    def robots_for(self, url: str) -> RobotsRules:
        origin = origin_of(url)
        if origin in self._robots:
            return self._robots[origin]
        robots_url = origin + "/robots.txt"
        try:
            resp = self._request("GET", robots_url, allow_redirects=True)
            if resp.status_code == 200:
                rules = RobotsRules("found", resp.text, 200)
            elif 400 <= resp.status_code < 500:
                rules = RobotsRules("missing", source_status_code=resp.status_code)
            else:
                rules = RobotsRules("unreachable", source_status_code=resp.status_code,
                                    error=f"robots.txt returned HTTP {resp.status_code}")
        except requests.RequestException as exc:
            rules = RobotsRules("unreachable", error=f"{type(exc).__name__}: {exc}")
        self._robots[origin] = rules
        return rules

    # --- page fetch ----------------------------------------------------
    def fetch_page(self, url: str) -> FetchResult:
        """Fetch an HTML page. Never raises; failures are described in the result."""
        result = FetchResult(url=url)
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            result.error_type, result.error = "invalid_url", "Only absolute http(s) URLs are supported."
            return result

        robots = self.robots_for(url)
        if not robots.allowed(url):
            result.error_type = "robots_disallowed"
            if robots.status == "unreachable":
                result.error = (f"robots.txt could not be read ({robots.error}); "
                                "treating the site as disallowed per RFC 9309.")
            else:
                result.error = "robots.txt disallows this URL for our user agent; page was not fetched."
            return result

        start = time.monotonic()
        try:
            resp = self._request("GET", url, allow_redirects=True, stream=True)
            raw = resp.raw.read(MAX_HTML_BYTES + 1, decode_content=True)
        except requests.Timeout:
            result.error_type, result.error = "timeout", f"No response within {self.timeout:.0f}s."
            return result
        except requests.exceptions.SSLError as exc:
            result.error_type, result.error = "ssl", f"SSL error: {exc}"
            return result
        except requests.ConnectionError as exc:
            result.error_type, result.error = "connection", f"Could not connect: {exc}"
            return result
        except requests.RequestException as exc:
            result.error_type, result.error = "other", f"{type(exc).__name__}: {exc}"
            return result

        result.elapsed_ms = int((time.monotonic() - start) * 1000)
        result.status_code = resp.status_code
        result.final_url = resp.url
        result.redirects = [r.url for r in resp.history]
        result.content_type = resp.headers.get("Content-Type", "")

        if resp.status_code in (401, 403):
            result.error_type = "auth_required"
            result.error = f"HTTP {resp.status_code}: page is not publicly accessible; not audited."
            return result
        if resp.status_code >= 400:
            result.error_type, result.error = "http_error", f"HTTP {resp.status_code}."
            return result
        if "html" not in result.content_type.lower():
            result.error_type = "not_html"
            result.error = f"Content-Type is '{result.content_type}', not HTML."
            return result

        encoding = resp.encoding if resp.encoding and resp.encoding.lower() != "iso-8859-1" else None
        encoding = encoding or resp.apparent_encoding or "utf-8"
        result.text = raw[:MAX_HTML_BYTES].decode(encoding, errors="replace")
        return result

    # --- lightweight status checks ------------------------------------
    def status_of(self, url: str) -> dict:
        """Return {'url', 'status_code', 'error'} for a link, respecting robots.txt.
        Tries HEAD first and falls back to GET when HEAD is rejected."""
        if not self.robots_for(url).allowed(url):
            return {"url": url, "status_code": None, "error": "robots_disallowed"}
        try:
            resp = self._request("HEAD", url, allow_redirects=True)
            if resp.status_code in (405, 501) or resp.status_code == 403:
                resp = self._request("GET", url, allow_redirects=True, stream=True)
                resp.close()
            return {"url": url, "status_code": resp.status_code, "error": None}
        except requests.Timeout:
            return {"url": url, "status_code": None, "error": "timeout"}
        except requests.RequestException as exc:
            return {"url": url, "status_code": None, "error": type(exc).__name__}

    def get_text(self, url: str) -> tuple[int | None, str | None, str | None]:
        """Small GET for auxiliary files (sitemap). Returns (status, text, error)."""
        if not self.robots_for(url).allowed(url):
            return None, None, "robots_disallowed"
        try:
            resp = self._request("GET", url, allow_redirects=True)
            return resp.status_code, resp.text[:MAX_HTML_BYTES], None
        except requests.RequestException as exc:
            return None, None, f"{type(exc).__name__}: {exc}"


def absolute(base: str, href: str) -> str:
    return urljoin(base, href)

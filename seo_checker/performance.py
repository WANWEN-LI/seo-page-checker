"""Mobile performance via the Google PageSpeed Insights v5 API.

Lab scores come from Lighthouse (`lighthouseResult`). Core Web Vitals come from real-user
CrUX field data (`loadingExperience`), which Google only has for pages with enough traffic;
when it is missing we say so rather than substituting lab numbers for INP.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import time
from typing import Any
from urllib.parse import urlparse

import requests

from .models import Check

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PSI_TIMEOUT = 120.0  # PSI runs a full Lighthouse audit; 30-60 s is normal
RETRIES_ON_429 = 1
RETRY_DELAY = 5.0
CATEGORY = "performance"

# Google's published Core Web Vitals thresholds (good, needs improvement); above = poor.
CWV_THRESHOLDS = {
    "LCP": (2500, 4000, "ms"),
    "CLS": (0.1, 0.25, ""),
    "INP": (200, 500, "ms"),
}
FIELD_KEYS = {
    "LCP": "LARGEST_CONTENTFUL_PAINT_MS",
    "CLS": "CUMULATIVE_LAYOUT_SHIFT_SCORE",
    "INP": "INTERACTION_TO_NEXT_PAINT",
}
LAB_AUDITS = {"LCP": "largest-contentful-paint", "CLS": "cumulative-layout-shift", "TBT": "total-blocking-time"}


def is_public_url(url: str) -> tuple[bool, str]:
    """PSI fetches the page from Google's servers, so localhost / private IPs cannot be tested."""
    host = urlparse(url).hostname or ""
    if host in ("localhost",) or host.endswith((".localhost", ".local", ".test")):
        return False, f"'{host}' is a local hostname."
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, f"'{host}' does not resolve in DNS."
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False, f"'{host}' resolves to a private address ({ip})."
    return True, ""


def run_pagespeed(url: str, api_key: str | None = None, strategy: str = "mobile",
                  session: requests.Session | None = None) -> dict[str, Any]:
    """Call PSI. Returns {'ok': bool, 'error': str|None, 'raw_summary': {...}}. Never raises."""
    api_key = api_key if api_key is not None else os.getenv("PAGESPEED_API_KEY") or None
    public, reason = is_public_url(url)
    if not public:
        return {"ok": False, "error": f"PageSpeed Insights only tests public URLs: {reason}", "skipped": True}

    params = [("url", url), ("strategy", strategy),
              ("category", "PERFORMANCE"), ("category", "SEO"), ("category", "ACCESSIBILITY")]
    if api_key:
        params.append(("key", api_key))
    http = session or requests
    for attempt in range(1 + RETRIES_ON_429):
        try:
            resp = http.get(PSI_ENDPOINT, params=params, timeout=PSI_TIMEOUT)
        except requests.Timeout:
            return {"ok": False, "error": f"PageSpeed Insights did not respond within {PSI_TIMEOUT:.0f}s."}
        except requests.RequestException as exc:
            return {"ok": False, "error": f"PageSpeed Insights request failed: {type(exc).__name__}"}
        if resp.status_code != 429 or attempt == RETRIES_ON_429:
            break
        time.sleep(RETRY_DELAY)

    if resp.status_code != 200:
        try:
            msg = resp.json().get("error", {}).get("message", "")
        except ValueError:
            msg = "non-JSON response from Google"
        hint = ""
        if resp.status_code == 429:
            hint = (" (rate-limited by Google; a newly created key can take a few minutes to activate, retry later)"
                    if api_key else " (anonymous quota exceeded; set PAGESPEED_API_KEY in .env)")
        # never echo the key back
        if api_key:
            msg = msg.replace(api_key, "***")
        return {"ok": False, "error": f"PageSpeed Insights HTTP {resp.status_code}: {msg}{hint}"}

    return {"ok": True, "error": None, "summary": summarize(resp.json()), "strategy": strategy}


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    """Pull the numbers we report out of a raw PSI response."""
    lh = data.get("lighthouseResult", {})
    cats = lh.get("categories", {})

    def score(key: str) -> int | None:
        s = cats.get(key, {}).get("score")
        return round(s * 100) if isinstance(s, (int, float)) else None

    audits = lh.get("audits", {})
    lab = {}
    for name, audit_id in LAB_AUDITS.items():
        v = audits.get(audit_id, {}).get("numericValue")
        if isinstance(v, (int, float)):
            lab[name] = round(v, 3) if name == "CLS" else round(v)

    def field_from(exp: dict[str, Any]) -> dict[str, Any]:
        metrics = exp.get("metrics", {}) if exp else {}
        out = {}
        for name, key in FIELD_KEYS.items():
            m = metrics.get(key)
            if m and "percentile" in m:
                p = m["percentile"]
                out[name] = {"p75": p / 100 if name == "CLS" else p, "category": m.get("category")}
        return out

    return {
        "scores": {"performance": score("performance"), "seo": score("seo"), "accessibility": score("accessibility")},
        "lab": lab,
        "field_page": field_from(data.get("loadingExperience", {})),
        "field_origin": field_from(data.get("originLoadingExperience", {})),
        "lighthouse_version": lh.get("lighthouseVersion"),
        "fetch_time": lh.get("fetchTime"),
        "final_url": lh.get("finalDisplayedUrl") or lh.get("finalUrl"),
    }


def _lh_status(score: int) -> str:
    # Lighthouse colour bands: 90-100 green, 50-89 orange, 0-49 red
    return "pass" if score >= 90 else "warn" if score >= 50 else "fail"


def _cwv_status(name: str, value: float) -> str:
    good, ni, _ = CWV_THRESHOLDS[name]
    return "pass" if value <= good else "warn" if value <= ni else "fail"


def _fmt(name: str, value: float) -> str:
    unit = CWV_THRESHOLDS.get(name, (0, 0, "ms"))[2]
    if unit == "ms" and value >= 1000:
        return f"{value / 1000:.1f} s"
    return f"{value:g} {unit}".strip()


def evaluate(result: dict[str, Any]) -> list[Check]:
    if not result.get("ok"):
        return [Check("psi_unavailable", CATEGORY, "PageSpeed Insights", "not_checked", "Low",
                      result.get("error") or "PageSpeed Insights not run.",
                      "Performance score is reported as N/A and excluded from the total.")]

    s = result["summary"]
    checks: list[Check] = []
    labels = {
        "performance": ("lh_performance", "Mobile performance score", "High",
                        "Slow mobile pages lose visitors before they see the offer; speed is also a ranking signal.",
                        "Open the PSI report and fix the top 'Opportunities' (image size, render-blocking JS/CSS)."),
        "accessibility": ("lh_accessibility", "Accessibility score", "Medium",
                          "Accessibility issues block some users and often overlap with SEO (alt text, contrast, labels).",
                          "Fix the failing Lighthouse accessibility audits."),
        "seo": ("lh_seo", "Lighthouse SEO score", "Medium",
                "Lighthouse's SEO audit catches crawlability basics.", "Fix the failing Lighthouse SEO audits."),
    }
    for key, (cid, label, sev, why, fix) in labels.items():
        val = s["scores"][key]
        if val is None:
            checks.append(Check(cid, CATEGORY, label, "not_checked", sev, "Score missing from PSI response."))
            continue
        st = _lh_status(val)
        checks.append(Check(cid, CATEGORY, label, st, sev, f"{val}/100 (Lighthouse, mobile).",
                            "" if st == "pass" else why, "" if st == "pass" else fix, {"score": val}))

    # Core Web Vitals: prefer page-level field data, then origin-level, else lab (LCP/CLS only).
    for name in ("LCP", "CLS", "INP"):
        source, value = None, None
        if name in s["field_page"]:
            source, value = "field (this URL, CrUX p75)", s["field_page"][name]["p75"]
        elif name in s["field_origin"]:
            source, value = "field (whole origin, CrUX p75)", s["field_origin"][name]["p75"]
        elif name in s["lab"]:
            source, value = "lab (Lighthouse, single run)", s["lab"][name]
        cid, label = f"cwv_{name.lower()}", f"Core Web Vital: {name}"
        if value is None:
            note = "INP needs real-user data; " if name == "INP" else ""
            checks.append(Check(cid, CATEGORY, label, "not_checked", "Low",
                                f"{note}no CrUX field data for this page or origin (common for low-traffic sites)."))
            continue
        st = _cwv_status(name, value)
        good, ni, _ = CWV_THRESHOLDS[name]
        checks.append(Check(cid, CATEGORY, label, st, "Medium",
                            f"{name} = {_fmt(name, value)} from {source}.",
                            "" if st == "pass" else f"Google rates {name} good at <= {_fmt(name, good)}, poor above {_fmt(name, ni)}.",
                            "" if st == "pass" else {
                                "LCP": "Compress and preload the hero image; reduce render-blocking resources.",
                                "CLS": "Set width/height on images and embeds; avoid inserting content above existing content.",
                                "INP": "Break up long JavaScript tasks; defer non-critical scripts.",
                            }[name],
                            {"value": value, "source": source}))
    return checks

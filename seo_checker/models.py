"""Shared data structures for checks and reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Severity = Literal["High", "Medium", "Low"]
Status = Literal["pass", "warn", "fail", "info", "not_checked"]


@dataclass
class Check:
    """One check result.

    `status` is the outcome; `severity` is how much a non-pass outcome matters.
    `finding` states what was observed, `why` explains the impact, `fix` says how to resolve it.
    """

    id: str
    category: str
    label: str
    status: Status
    severity: Severity
    finding: str
    why: str = ""
    fix: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FetchResult:
    url: str
    final_url: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    text: str | None = None
    elapsed_ms: int | None = None
    redirects: list[str] = field(default_factory=list)
    # error_type is one of: robots_disallowed, timeout, connection, ssl, http_error,
    # auth_required, not_html, invalid_url, other
    error_type: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_type is None and self.status_code is not None and self.status_code < 400

    def to_dict(self, include_text: bool = False) -> dict[str, Any]:
        d = asdict(self)
        if not include_text:
            d.pop("text", None)
        return d

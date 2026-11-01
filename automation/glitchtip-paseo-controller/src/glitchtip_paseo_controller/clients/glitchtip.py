from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, cast
from urllib.parse import urlencode, urlparse

from . import Incompatibility


@dataclass(frozen=True)
class CapturedResponse:
    body: object
    headers: Mapping[str, str]


@dataclass(frozen=True)
class GlitchTipIssue:
    id: str
    status: str
    title: str
    count: str
    first_seen: str
    last_seen: str
    project_id: str
    project_slug: str


@dataclass(frozen=True)
class IssueListing:
    issues: tuple[GlitchTipIssue, ...]
    page_urls: tuple[str, ...]
    duplicate_ids: tuple[str, ...]
    complete: bool


class GlitchTipLifecycleClient(Protocol):
    def current_issue(self, *, project_id: int, issue_id: str) -> GlitchTipIssue | None: ...

    def resolve_issue(self, *, project_id: int, issue_id: str) -> GlitchTipIssue | None: ...


class GlitchTipAdapter:
    def __init__(self, fetch: Callable[[str], CapturedResponse]) -> None:
        self._fetch = fetch

    def list_unresolved(self, base_url: str, organization: str, project_id: int) -> IssueListing:
        query = urlencode({"query": "is:unresolved", "project": str(project_id)})
        url = f"{base_url.rstrip('/')}/api/0/organizations/{organization}/issues/?{query}"
        expected_origin = urlparse(base_url).netloc
        seen_urls: set[str] = set()
        page_urls: list[str] = []
        by_id: dict[str, GlitchTipIssue] = {}
        duplicates: set[str] = set()

        while url:
            if url in seen_urls:
                raise Incompatibility("PAGINATION_CYCLE", f"repeated page {url}")
            seen_urls.add(url)
            page_urls.append(url)
            response = self._fetch(url)
            raw_body = response.body
            if not isinstance(raw_body, list):
                raise Incompatibility(
                    "MALFORMED_GLITCHTIP_RESPONSE", "issue list body must be an array"
                )
            body = cast(list[object], raw_body)
            for raw_issue in body:
                issue = _parse_issue(raw_issue)
                if issue.project_id != str(project_id):
                    raise Incompatibility(
                        "GLITCHTIP_PROJECT_MISMATCH",
                        f"issue {issue.id} belongs to project {issue.project_id}, not {project_id}",
                    )
                existing = by_id.get(issue.id)
                if existing is not None:
                    duplicates.add(issue.id)
                    if issue.last_seen > existing.last_seen:
                        by_id[issue.id] = issue
                else:
                    by_id[issue.id] = issue
            url = _next_link(response.headers.get("Link", ""), expected_origin)

        return IssueListing(
            issues=tuple(sorted(by_id.values(), key=lambda issue: issue.id)),
            page_urls=tuple(page_urls),
            duplicate_ids=tuple(sorted(duplicates)),
            complete=True,
        )

    def issue_detail(self, url: str, project_id: int) -> GlitchTipIssue:
        issue = _parse_issue(self._fetch(url).body)
        if issue.project_id != str(project_id):
            raise Incompatibility("GLITCHTIP_PROJECT_MISMATCH", issue.id)
        return issue


def _parse_issue(value: object) -> GlitchTipIssue:
    if not isinstance(value, dict):
        raise Incompatibility("MALFORMED_GLITCHTIP_RESPONSE", "issue must be an object")
    issue = cast(dict[str, object], value)
    required = {"id", "status", "title", "count", "firstSeen", "lastSeen", "project"}
    missing = sorted(required.difference(issue))
    if missing:
        raise Incompatibility("MISSING_GLITCHTIP_FIELD", ", ".join(missing))
    project_value = issue["project"]
    if not isinstance(project_value, dict):
        raise Incompatibility("MALFORMED_GLITCHTIP_PROJECT", "project requires id and slug")
    project = cast(dict[str, object], project_value)
    if {"id", "slug"}.difference(project):
        raise Incompatibility("MALFORMED_GLITCHTIP_PROJECT", "project requires id and slug")
    fields = (
        issue["id"],
        issue["status"],
        issue["title"],
        issue["count"],
        issue["firstSeen"],
        issue["lastSeen"],
        project["id"],
        project["slug"],
    )
    if not all(isinstance(field, str) and field for field in fields):
        raise Incompatibility(
            "MALFORMED_GLITCHTIP_RESPONSE", "issue identity and activity fields must be strings"
        )
    return GlitchTipIssue(*(cast(tuple[str, str, str, str, str, str, str, str], fields)))


def _next_link(header: str, expected_origin: str) -> str | None:
    if not header:
        return None
    matches: list[tuple[str, str, str]] = re.findall(
        r"<([^>]+)>\s*;\s*rel=\"([^\"]+)\"(?:\s*;\s*results=\"([^\"]+)\")?", header
    )
    if not matches:
        raise Incompatibility("MALFORMED_PAGINATION_LINK", header)
    next_links = [(url, results) for url, relation, results in matches if relation == "next"]
    if len(next_links) > 1:
        raise Incompatibility("MALFORMED_PAGINATION_LINK", "multiple next links")
    if not next_links:
        return None
    next_url, results = next_links[0]
    if results == "false":
        return None
    parsed = urlparse(next_url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != expected_origin
        or not parsed.path.startswith("/api/0/")
    ):
        raise Incompatibility(
            "MALFORMED_PAGINATION_LINK", "next link is outside the GlitchTip API origin"
        )
    return next_url

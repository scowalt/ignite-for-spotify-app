from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

MAX_TEXT = 500
MAX_FRAMES = 8
MAX_BREADCRUMBS = 12

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_WHITESPACE = re.compile(r"\s+")
_QUERY_STRING = re.compile(r"([^\s?]+)\?[^\s]*")
_SECRET_VALUE = re.compile(
    r"(?i)\b(?:access[_-]?token|api[_-]?key|authorization|cookie|key|password|passwd|secret|token)"
    r"\s*(?:=|:)\s*(?:bearer\s+)?[^\s,;]+"
)
_BEARER_VALUE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)\b")
_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


@dataclass(frozen=True)
class StackFrame:
    filename: str
    function: str
    line: int | None
    context: str | None


@dataclass(frozen=True)
class Breadcrumb:
    category: str | None
    level: str | None
    message: str | None


@dataclass(frozen=True)
class IssueContext:
    title: str
    message: str
    frames: tuple[StackFrame, ...]
    breadcrumbs: tuple[Breadcrumb, ...]


def build_issue_context(
    detail: Mapping[str, object], latest_event: Mapping[str, object]
) -> IssueContext:
    return IssueContext(
        title=_safe_text(detail.get("title"), fallback="(untitled issue)"),
        message=_safe_text(latest_event.get("message"), fallback="(no event message)"),
        frames=_frames(latest_event),
        breadcrumbs=_breadcrumbs(latest_event),
    )


def render_issue_context(context: IssueContext) -> str:
    lines = [
        f"Title: {_safe_text(context.title, fallback='(untitled issue)')}",
        f"Message: {_safe_text(context.message, fallback='(no event message)')}",
    ]
    if context.frames:
        lines.append("Frames:")
        for frame in context.frames[:MAX_FRAMES]:
            fields = (
                _safe_text(frame.filename, fallback="(unknown file)"),
                _safe_text(frame.function, fallback="(unknown function)"),
                None
                if frame.line is None or isinstance(frame.line, bool)
                else f"line {frame.line}",
                _optional_safe_text(frame.context),
            )
            lines.append("- " + " | ".join(item for item in fields if item))
    if context.breadcrumbs:
        lines.append("Breadcrumbs:")
        for breadcrumb in context.breadcrumbs[:MAX_BREADCRUMBS]:
            fields = (
                _optional_safe_text(breadcrumb.category),
                _optional_safe_text(breadcrumb.level),
                _optional_safe_text(breadcrumb.message),
            )
            lines.append("- " + " | ".join(item for item in fields if item))
    return "\n".join(lines)


def _frames(event: Mapping[str, object]) -> tuple[StackFrame, ...]:
    frames: list[StackFrame] = []
    exception = _mapping(event.get("exception"))
    values = exception.get("values")
    if not isinstance(values, list):
        return ()
    for exception_value in cast(list[object], values):
        stacktrace = _mapping(_mapping(exception_value).get("stacktrace"))
        raw_frames = stacktrace.get("frames")
        if not isinstance(raw_frames, list):
            continue
        for raw_frame in cast(list[object], raw_frames):
            frame = _mapping(raw_frame)
            filename = _safe_text(frame.get("filename"), fallback="(unknown file)")
            function = _safe_text(frame.get("function"), fallback="(unknown function)")
            line = frame.get("lineno")
            frames.append(
                StackFrame(
                    filename,
                    function,
                    line if isinstance(line, int) and not isinstance(line, bool) else None,
                    _optional_safe_text(frame.get("context_line")),
                )
            )
            if len(frames) == MAX_FRAMES:
                return tuple(frames)
    return tuple(frames)


def _breadcrumbs(event: Mapping[str, object]) -> tuple[Breadcrumb, ...]:
    values = _mapping(event.get("breadcrumbs")).get("values")
    if not isinstance(values, list):
        return ()
    breadcrumbs: list[Breadcrumb] = []
    for raw_breadcrumb in cast(list[object], values)[:MAX_BREADCRUMBS]:
        breadcrumb = _mapping(raw_breadcrumb)
        breadcrumbs.append(
            Breadcrumb(
                _optional_safe_text(breadcrumb.get("category")),
                _optional_safe_text(breadcrumb.get("level")),
                _optional_safe_text(breadcrumb.get("message")),
            )
        )
    return tuple(breadcrumbs)


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        return {}
    return cast(Mapping[str, object], mapping)


def _optional_safe_text(value: object) -> str | None:
    return _safe_text(value, fallback="") or None


def _safe_text(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    clean = _CONTROL_CHARACTERS.sub(" ", value)
    clean = _QUERY_STRING.sub(r"\1", clean)
    for pattern in (_SECRET_VALUE, _BEARER_VALUE, _GITHUB_TOKEN, _AWS_KEY, _JWT):
        clean = pattern.sub("[REDACTED]", clean)
    clean = _WHITESPACE.sub(" ", clean).strip()
    if not clean:
        return fallback
    return clean if len(clean) <= MAX_TEXT else f"{clean[: MAX_TEXT - 1]}…"

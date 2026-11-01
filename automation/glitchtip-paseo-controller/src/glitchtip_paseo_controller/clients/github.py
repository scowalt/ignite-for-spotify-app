from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Protocol, cast

from . import Incompatibility

type JsonValue = None | bool | int | float | str | tuple[JsonValue, ...] | Mapping[str, JsonValue]


@dataclass(frozen=True)
class RequiredCheck:
    context: str
    app_id: int | None


@dataclass(frozen=True)
class ClassicProtection:
    strict: bool
    required_contexts: tuple[str, ...]
    required_checks: tuple[RequiredCheck, ...]
    required_approvals: int | None
    conversation_resolution_required: bool
    controls: Mapping[str, JsonValue]
    status_check_metadata: Mapping[str, JsonValue]


@dataclass(frozen=True)
class RulesetEvidence:
    id: int
    name: str
    target: str
    enforcement: str
    ref_includes: tuple[str, ...]
    ref_excludes: tuple[str, ...]
    rules: tuple[Mapping[str, JsonValue], ...]
    metadata: Mapping[str, JsonValue]


@dataclass(frozen=True)
class GitHubPolicyEvidence:
    classic_protection: ClassicProtection
    rulesets: tuple[RulesetEvidence, ...]


@dataclass(frozen=True)
class GitHubCredential:
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("GitHub credential must not be empty")


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str
    head_branch: str
    body: str


@dataclass(frozen=True)
class PullRequestOutcome:
    number: int
    state: Literal["open", "merged", "closed", "ci_failed", "unknown"]


class GitHubRemediationClient(Protocol):
    def find_linked_pull_requests(
        self, *, repository: str, branch: str, marker: str
    ) -> tuple[PullRequest, ...]: ...

    def request_auto_merge(
        self, *, repository: str, pull_request: int, credential: GitHubCredential
    ) -> None: ...


class GitHubLifecycleClient(Protocol):
    def observe_pull_request(
        self, *, repository: str, pull_request: int
    ) -> PullRequestOutcome | None: ...


class GitHubAdapter:
    def __init__(self, captured: object) -> None:
        self._captured = captured

    def collect_policy(self) -> GitHubPolicyEvidence:
        captured = _root(self._captured)
        protection = _protection(_mapping(captured.get("protection"), "protection"))
        rulesets_value = captured.get("rulesets")
        if not isinstance(rulesets_value, list):
            raise Incompatibility("MALFORMED_GITHUB_RULESETS", "rulesets must be an array")
        rulesets = tuple(_ruleset(item) for item in cast(list[object], rulesets_value))
        return GitHubPolicyEvidence(protection, rulesets)


def _root(value: object) -> Mapping[str, object]:
    root = _mapping(value, "GitHub evidence")
    _no_unknown(root, {"protection", "rulesets"}, "UNKNOWN_GITHUB_ROOT_FIELD")
    if {"protection", "rulesets"}.difference(root):
        raise Incompatibility("MALFORMED_GITHUB_ROOT", "policy evidence is incomplete")
    return root


def _protection(value: Mapping[str, object]) -> ClassicProtection:
    structural = {
        "required_status_checks",
        "required_pull_request_reviews",
        "required_conversation_resolution",
    }
    controls = {
        "allow_deletions",
        "allow_force_pushes",
        "allow_fork_syncing",
        "block_creations",
        "enforce_admins",
        "lock_branch",
        "required_linear_history",
        "required_signatures",
        "url",
    }
    _no_unknown(value, structural | controls, "UNKNOWN_GITHUB_PROTECTION_FIELD")
    status_checks = _mapping(value.get("required_status_checks"), "required_status_checks")
    status_allowed = {"strict", "contexts", "checks", "contexts_url", "url"}
    _no_unknown(status_checks, status_allowed, "UNKNOWN_GITHUB_PROTECTION_FIELD")
    contexts = _string_tuple(status_checks.get("contexts"), "required_status_checks.contexts")
    raw_checks = status_checks.get("checks")
    if not isinstance(raw_checks, list):
        raise Incompatibility("MALFORMED_GITHUB_PROTECTION", "checks must be an array")
    checks = tuple(_required_check(item) for item in cast(list[object], raw_checks))
    reviews = value.get("required_pull_request_reviews")
    approvals: int | None
    if reviews is None:
        approvals = None
    else:
        review_data = _mapping(reviews, "required_pull_request_reviews")
        _no_unknown(
            review_data, {"required_approving_review_count"}, "UNKNOWN_GITHUB_PROTECTION_FIELD"
        )
        observed_approvals = review_data.get("required_approving_review_count")
        if not isinstance(observed_approvals, int):
            raise Incompatibility(
                "MALFORMED_GITHUB_PROTECTION", "approval count must be an integer"
            )
        approvals = observed_approvals
    conversation = _mapping(
        value.get("required_conversation_resolution"), "required_conversation_resolution"
    )
    _no_unknown(conversation, {"enabled"}, "UNKNOWN_GITHUB_PROTECTION_FIELD")
    enabled = conversation.get("enabled")
    strict = status_checks.get("strict")
    if not isinstance(enabled, bool) or not isinstance(strict, bool):
        raise Incompatibility(
            "MALFORMED_GITHUB_PROTECTION", "conversation and strict gates must be boolean"
        )
    return ClassicProtection(
        strict,
        contexts,
        checks,
        approvals,
        enabled,
        _freeze_mapping({key: value[key] for key in controls if key in value}),
        _freeze_mapping(
            {key: status_checks[key] for key in {"contexts_url", "url"} if key in status_checks}
        ),
    )


def _required_check(value: object) -> RequiredCheck:
    item = _mapping(value, "required check")
    _no_unknown(item, {"context", "app_id"}, "UNKNOWN_GITHUB_PROTECTION_FIELD")
    context = item.get("context")
    app_id = item.get("app_id")
    if (
        not isinstance(context, str)
        or not context
        or (app_id is not None and not isinstance(app_id, int))
    ):
        raise Incompatibility(
            "MALFORMED_GITHUB_PROTECTION", "required check must have context and optional app_id"
        )
    return RequiredCheck(context, app_id)


def _ruleset(value: object) -> RulesetEvidence:
    item = _mapping(value, "ruleset")
    core = {"id", "name", "target", "enforcement", "conditions", "rules"}
    metadata_keys = {
        "node_id",
        "source_type",
        "source",
        "created_at",
        "updated_at",
        "bypass_actors",
        "_links",
        "links",
    }
    _no_unknown(item, core | metadata_keys, "UNKNOWN_GITHUB_RULESET_FIELD")
    identifier, name, target, enforcement, rules = (
        item.get("id"),
        item.get("name"),
        item.get("target"),
        item.get("enforcement"),
        item.get("rules"),
    )
    if (
        not isinstance(identifier, int)
        or not all(isinstance(field, str) and field for field in (name, target, enforcement))
        or not isinstance(rules, list)
    ):
        raise Incompatibility(
            "MALFORMED_GITHUB_RULESET", "ruleset identity, target, and rules are required"
        )
    conditions = _mapping(item.get("conditions"), "ruleset conditions")
    _no_unknown(conditions, {"ref_name"}, "UNKNOWN_GITHUB_RULESET_FIELD")
    ref_name = _mapping(conditions.get("ref_name"), "ruleset ref_name")
    _no_unknown(ref_name, {"include", "exclude"}, "UNKNOWN_GITHUB_RULESET_FIELD")
    includes = _string_tuple(ref_name.get("include"), "ruleset ref includes")
    excludes = _string_tuple(ref_name.get("exclude"), "ruleset ref excludes")
    typed_rules = tuple(
        _freeze_mapping(_mapping(rule, "rule")) for rule in cast(list[object], rules)
    )
    assert isinstance(name, str) and isinstance(target, str) and isinstance(enforcement, str)
    return RulesetEvidence(
        identifier,
        name,
        target,
        enforcement,
        includes,
        excludes,
        typed_rules,
        _freeze_mapping({key: item[key] for key in metadata_keys if key in item}),
    )


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        code = "MALFORMED_GITHUB_ROOT" if name == "GitHub evidence" else "MALFORMED_GITHUB_RESPONSE"
        raise Incompatibility(code, f"{name} must be an object")
    return cast(dict[str, object], value)


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise Incompatibility("MALFORMED_GITHUB_PROTECTION", f"{name} must be strings")
    values = cast(list[object], value)
    if not all(isinstance(item, str) and item for item in values):
        raise Incompatibility("MALFORMED_GITHUB_PROTECTION", f"{name} must be strings")
    return tuple(cast(list[str], values))


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, JsonValue]:
    return MappingProxyType({key: _freeze(item) for key, item in value.items()})


def _freeze(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        if not all(isinstance(key, str) for key in mapping):
            raise Incompatibility("MALFORMED_GITHUB_RESPONSE", "metadata keys must be strings")
        return _freeze_mapping(cast(dict[str, object], mapping))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in cast(list[object], value))
    raise Incompatibility("MALFORMED_GITHUB_RESPONSE", "metadata must be JSON data")


def _no_unknown(value: Mapping[str, object], allowed: set[str], code: str) -> None:
    unknown = sorted(set(value).difference(allowed))
    if unknown:
        raise Incompatibility(code, ", ".join(unknown))

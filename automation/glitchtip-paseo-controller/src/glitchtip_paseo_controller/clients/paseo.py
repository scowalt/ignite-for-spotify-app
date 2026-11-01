from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from . import Incompatibility
from .github import GitHubCredential

_REQUIRED_COMMANDS = frozenset({"ls", "inspect", "archive", "run", "worktree"})


@dataclass(frozen=True)
class PaseoAgentEvidence:
    id: str
    labels: Mapping[str, str]
    archived: bool
    result_status: str | None
    result_head_sha: str | None


@dataclass(frozen=True)
class PaseoCapabilities:
    version: str
    commands: tuple[str, ...]
    pi_version: str
    pi_model_available: bool
    agent: PaseoAgentEvidence | None


@dataclass(frozen=True)
class OriginMain:
    reference: str
    commit_sha: str


@dataclass(frozen=True)
class WorkspaceLaunch:
    workspace: str
    agent_identity: str
    branch: str
    marker: str
    base: OriginMain
    prompt: str


@dataclass(frozen=True)
class AgentResult:
    agent_identity: str
    status: Literal["running", "complete", "failed"]
    failure_reason: str | None


class PaseoRemediationClient(Protocol):
    def fresh_origin_main(self) -> OriginMain: ...

    def agent_result(self, agent_identity: str) -> AgentResult | None: ...

    def launch(self, request: WorkspaceLaunch, credential: GitHubCredential) -> AgentResult: ...


class PaseoLifecycleClient(Protocol):
    def archive_agent(self, agent_identity: str) -> None: ...

    def remove_workspace(self, workspace: str) -> None: ...

    def remove_local_branch(self, branch: str) -> None: ...

    def remove_remote_branch(self, branch: str) -> None: ...


class PaseoAdapter:
    def __init__(self, captured: object) -> None:
        self._captured = captured

    def capabilities(self, required_version: str) -> PaseoCapabilities:
        captured = _root(self._captured)
        version = captured.get("version")
        if not isinstance(version, str):
            raise Incompatibility("MALFORMED_PASEO_VERSION", "version must be a string")
        if version != required_version:
            raise Incompatibility(
                "UNSUPPORTED_PASEO_VERSION", f"observed {version}; require {required_version}"
            )
        raw_commands = captured.get("commands")
        if not isinstance(raw_commands, list):
            raise Incompatibility("MALFORMED_PASEO_CAPABILITIES", "commands must be strings")
        command_values = cast(list[object], raw_commands)
        if not all(isinstance(command, str) for command in command_values):
            raise Incompatibility("MALFORMED_PASEO_CAPABILITIES", "commands must be strings")
        commands = tuple(cast(list[str], command_values))
        missing = sorted(_REQUIRED_COMMANDS.difference(commands))
        if missing:
            raise Incompatibility("MISSING_PASEO_COMMAND", ", ".join(missing))
        pi_version = captured.get("pi_version")
        model_available = captured.get("pi_model_available")
        if (
            not isinstance(pi_version, str)
            or not pi_version
            or not isinstance(model_available, bool)
        ):
            raise Incompatibility(
                "MALFORMED_PI_CAPABILITIES", "Pi version and model availability are required"
            )
        if not model_available:
            raise Incompatibility("UNSUPPORTED_PI_MODEL", "configured model is unavailable")
        raw_agent = captured.get("agent")
        return PaseoCapabilities(
            version,
            commands,
            pi_version,
            model_available,
            _agent(raw_agent) if raw_agent is not None else None,
        )


def _root(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise Incompatibility("MALFORMED_PASEO_ROOT", "Paseo evidence must be an object")
    root = cast(dict[str, object], value)
    allowed = {"version", "commands", "pi_version", "pi_model_available", "agent"}
    unknown = sorted(set(root).difference(allowed))
    if unknown:
        raise Incompatibility("UNKNOWN_PASEO_ROOT_FIELD", ", ".join(unknown))
    missing = {"version", "commands", "pi_version", "pi_model_available"}.difference(root)
    if missing:
        raise Incompatibility("MALFORMED_PASEO_ROOT", f"missing {', '.join(sorted(missing))}")
    return root


def _agent(value: object) -> PaseoAgentEvidence:
    if not isinstance(value, dict):
        raise Incompatibility("MALFORMED_PASEO_AGENT", "agent must be an object")
    agent = cast(dict[str, object], value)
    allowed = {"id", "labels", "archived", "result"}
    unknown = sorted(set(agent).difference(allowed))
    if unknown:
        raise Incompatibility("UNKNOWN_PASEO_FIELD", ", ".join(unknown))
    identifier = agent.get("id")
    labels = agent.get("labels")
    archived = agent.get("archived")
    result = agent.get("result")
    if (
        not isinstance(identifier, str)
        or not isinstance(labels, dict)
        or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in cast(dict[object, object], labels).items()
        )
        or not isinstance(archived, bool)
    ):
        raise Incompatibility(
            "MALFORMED_PASEO_AGENT", "agent identity, labels, and archive state are required"
        )
    typed_labels = cast(dict[str, str], cast(dict[object, object], labels))
    if result is None:
        return PaseoAgentEvidence(identifier, typed_labels, archived, None, None)
    if not isinstance(result, dict):
        raise Incompatibility("MALFORMED_PASEO_RESULT", "result shape is unsupported")
    typed_result = cast(dict[str, object], result)
    if set(typed_result).difference({"status", "head_sha"}):
        raise Incompatibility("MALFORMED_PASEO_RESULT", "result shape is unsupported")
    status = typed_result.get("status")
    head_sha = typed_result.get("head_sha")
    if not isinstance(status, str) or not isinstance(head_sha, str):
        raise Incompatibility("MALFORMED_PASEO_RESULT", "result status and head must be strings")
    return PaseoAgentEvidence(identifier, typed_labels, archived, status, head_sha)

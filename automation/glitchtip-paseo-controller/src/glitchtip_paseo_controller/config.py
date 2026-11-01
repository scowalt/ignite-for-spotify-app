from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast


class ConfigurationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class GlitchTipConfig:
    base_url: str
    organization: str
    project_ids: tuple[int, ...]
    credential_capability: str


@dataclass(frozen=True)
class GitHubConfig:
    repository: str
    credential_capability: str


@dataclass(frozen=True)
class PaseoConfig:
    required_version: str


@dataclass(frozen=True)
class PiConfig:
    model: str
    thinking: str


@dataclass(frozen=True)
class LegacyArtifactConfig:
    repository: str
    pull_request: int
    branch: str
    registration_path: Path
    workspace_path: Path


@dataclass(frozen=True)
class LegacyCleanupConfig:
    enabled: bool
    marker: str
    local_root: Path
    repositories: tuple[str, ...]
    artifacts: tuple[LegacyArtifactConfig, ...]


@dataclass(frozen=True)
class ControllerConfig:
    state_directory: Path
    workspace_root: Path | None
    dispatch_enabled: bool
    glitchtip: GlitchTipConfig
    github: GitHubConfig
    paseo: PaseoConfig
    pi: PiConfig
    legacy_cleanup: LegacyCleanupConfig
    required_capabilities: tuple[str, ...]
    fingerprint: str


def load_config(
    path: Path,
    *,
    available_capabilities: set[str],
    environ: Mapping[str, str] | None = None,
) -> ControllerConfig:
    try:
        raw = cast(dict[str, object], tomllib.loads(path.read_text()))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError("INVALID_CONFIGURATION", str(error)) from error

    _exact_keys(
        raw,
        {"controller", "glitchtip", "github", "paseo", "pi", "legacy_cleanup", "capabilities"},
        "root",
    )
    controller = _table(raw, "controller")
    glitchtip = _table(raw, "glitchtip")
    github = _table(raw, "github")
    paseo = _table(raw, "paseo")
    pi = _table(raw, "pi")
    legacy_cleanup = _table(raw, "legacy_cleanup")
    capabilities = _table(raw, "capabilities")
    _required_and_optional_keys(
        controller,
        required={"state_directory"},
        optional={"workspace_root", "dispatch_enabled"},
        name="controller",
    )
    _exact_keys(
        glitchtip, {"base_url", "organization", "project_ids", "credential_capability"}, "glitchtip"
    )
    _exact_keys(github, {"repository", "credential_capability"}, "github")
    _exact_keys(paseo, {"required_version"}, "paseo")
    _exact_keys(pi, {"model", "thinking"}, "pi")
    _exact_keys(
        legacy_cleanup,
        {"enabled", "marker", "local_root", "repositories", "artifacts"},
        "legacy_cleanup",
    )
    _exact_keys(capabilities, {"required"}, "capabilities")

    projects = _int_tuple(glitchtip["project_ids"], "glitchtip.project_ids")
    if projects != (1, 2):
        raise ConfigurationError(
            "UNSUPPORTED_PROJECTS", "only GlitchTip projects 1 and 2 are in scope"
        )
    organization = _string(glitchtip["organization"], "glitchtip.organization")
    repository = _string(github["repository"], "github.repository")
    model = _string(pi["model"], "pi.model")
    thinking = _string(pi["thinking"], "pi.thinking")
    if organization != "scowalt":
        raise ConfigurationError("UNSUPPORTED_ORGANIZATION", "organization must be scowalt")
    if repository != "scowalt/ignite-for-spotify-app":
        raise ConfigurationError(
            "UNSUPPORTED_REPOSITORY", "repository must be scowalt/ignite-for-spotify-app"
        )
    if model != "gpt-5.6-terra" or thinking != "xhigh":
        raise ConfigurationError(
            "UNSUPPORTED_MODEL_CONTRACT", "model must be gpt-5.6-terra at xhigh"
        )

    glitchtip_capability = _string(
        glitchtip["credential_capability"], "glitchtip.credential_capability"
    )
    github_capability = _string(github["credential_capability"], "github.credential_capability")
    required = _string_tuple(capabilities["required"], "capabilities.required")
    named = (glitchtip_capability, github_capability)
    if tuple(sorted(required)) != tuple(sorted(named)):
        raise ConfigurationError(
            "INVALID_CAPABILITY_DECLARATION", "required capability names must match adapter inputs"
        )
    missing = sorted(set(required).difference(available_capabilities))
    if missing:
        raise ConfigurationError("MISSING_CAPABILITY", ", ".join(missing))

    env = os.environ if environ is None else environ
    state_directory = _state_directory(
        _string(controller["state_directory"], "controller.state_directory"), env
    )
    dispatch_enabled = controller.get("dispatch_enabled", False)
    if not isinstance(dispatch_enabled, bool):
        raise ConfigurationError(
            "INVALID_CONFIGURATION", "controller.dispatch_enabled must be a boolean"
        )
    workspace_value = controller.get("workspace_root")
    workspace_root = (
        None
        if workspace_value is None
        else _workspace_root(_string(workspace_value, "controller.workspace_root"), env)
    )
    if dispatch_enabled and workspace_root is None:
        raise ConfigurationError(
            "DISPATCH_WORKSPACE_ROOT_REQUIRED",
            "enabled dispatch requires controller.workspace_root",
        )
    if workspace_root == state_directory:
        raise ConfigurationError(
            "INVALID_WORKSPACE_ROOT", "workspace_root must not be the state directory"
        )
    base_url = _string(glitchtip["base_url"], "glitchtip.base_url")
    if base_url != "https://glitchtip.scowalt.com":
        raise ConfigurationError(
            "UNSUPPORTED_GLITCHTIP_URL", "base_url must be https://glitchtip.scowalt.com"
        )
    required_version = _string(paseo["required_version"], "paseo.required_version")
    cleanup = _legacy_cleanup_config(legacy_cleanup, env)
    fingerprint = _fingerprint(
        state_directory,
        workspace_root,
        dispatch_enabled,
        base_url,
        projects,
        glitchtip_capability,
        github_capability,
        required,
        required_version,
        cleanup,
    )
    return ControllerConfig(
        state_directory=state_directory,
        workspace_root=workspace_root,
        dispatch_enabled=dispatch_enabled,
        glitchtip=GlitchTipConfig(base_url, organization, projects, glitchtip_capability),
        github=GitHubConfig(repository, github_capability),
        paseo=PaseoConfig(required_version),
        pi=PiConfig(model, thinking),
        legacy_cleanup=cleanup,
        required_capabilities=tuple(sorted(required)),
        fingerprint=fingerprint,
    )


def _fingerprint(
    state_directory: Path,
    workspace_root: Path | None,
    dispatch_enabled: bool,
    base_url: str,
    projects: tuple[int, ...],
    glitchtip_capability: str,
    github_capability: str,
    required: tuple[str, ...],
    required_version: str,
    cleanup: LegacyCleanupConfig,
) -> str:
    canonical = repr(
        (
            str(state_directory),
            str(workspace_root),
            dispatch_enabled,
            base_url,
            projects,
            glitchtip_capability,
            github_capability,
            sorted(required),
            required_version,
            cleanup,
            "gpt-5.6-terra",
            "xhigh",
        )
    )
    return sha256(canonical.encode()).hexdigest()


def _legacy_cleanup_config(
    value: Mapping[str, object], environ: Mapping[str, str]
) -> LegacyCleanupConfig:
    enabled = value.get("enabled")
    if not isinstance(enabled, bool):
        raise ConfigurationError(
            "INVALID_CONFIGURATION", "legacy_cleanup.enabled must be a boolean"
        )
    raw_marker = value["marker"]
    if not isinstance(raw_marker, str):
        raise ConfigurationError("INVALID_CONFIGURATION", "legacy_cleanup.marker must be a string")
    marker = raw_marker
    local_root = _local_root(_string(value["local_root"], "legacy_cleanup.local_root"), environ)
    repositories = _string_tuple(value["repositories"], "legacy_cleanup.repositories")
    if len(set(repositories)) != len(repositories) or not all(
        _repository_name(item) for item in repositories
    ):
        raise ConfigurationError(
            "INVALID_LEGACY_ALLOWLIST",
            "repositories must contain distinct exact owner/repository names",
        )
    raw_artifacts = value["artifacts"]
    if not isinstance(raw_artifacts, list):
        raise ConfigurationError("INVALID_CONFIGURATION", "legacy_cleanup.artifacts must be a list")
    artifacts = tuple(
        _legacy_artifact(item, local_root, index)
        for index, item in enumerate(cast(list[object], raw_artifacts), start=1)
    )
    if enabled and (not marker or not repositories or not artifacts):
        raise ConfigurationError(
            "INCOMPLETE_LEGACY_CLEANUP",
            "enabled cleanup requires marker, allowlisted repositories, and artifacts",
        )
    if "\n" in marker or "\r" in marker:
        raise ConfigurationError("INVALID_LEGACY_MARKER", "marker must be one exact line")
    if not enabled and (repositories or artifacts):
        raise ConfigurationError(
            "DISABLED_LEGACY_CLEANUP_HAS_TARGETS",
            "disabled cleanup must not retain deletion targets",
        )
    if not enabled and marker:
        raise ConfigurationError(
            "DISABLED_LEGACY_CLEANUP_HAS_MARKER",
            "disabled cleanup must not retain a deletion marker",
        )
    if any(artifact.repository not in repositories for artifact in artifacts):
        raise ConfigurationError(
            "LEGACY_REPOSITORY_NOT_ALLOWLISTED", "artifact repository is not allowlisted"
        )
    identities = {
        (artifact.repository, artifact.pull_request, artifact.branch) for artifact in artifacts
    }
    paths = {
        path
        for artifact in artifacts
        for path in (artifact.registration_path, artifact.workspace_path)
    }
    if len(identities) != len(artifacts) or len(paths) != len(artifacts) * 2:
        raise ConfigurationError(
            "DUPLICATE_LEGACY_ARTIFACT", "legacy artifact identities and paths are unique"
        )
    return LegacyCleanupConfig(enabled, marker, local_root, repositories, artifacts)


def _legacy_artifact(value: object, root: Path, index: int) -> LegacyArtifactConfig:
    if not isinstance(value, dict):
        raise ConfigurationError(
            "INVALID_CONFIGURATION", f"legacy_cleanup.artifacts[{index}] must be a table"
        )
    item = cast(dict[str, object], value)
    _exact_keys(
        item,
        {"repository", "pull_request", "branch", "registration_path", "workspace_path"},
        f"legacy_cleanup.artifacts[{index}]",
    )
    repository = _string(item["repository"], f"legacy_cleanup.artifacts[{index}].repository")
    if not _repository_name(repository):
        raise ConfigurationError("INVALID_LEGACY_REPOSITORY", repository)
    pull_request = item["pull_request"]
    if not isinstance(pull_request, int) or pull_request < 1:
        raise ConfigurationError("INVALID_LEGACY_PULL_REQUEST", str(pull_request))
    branch = _string(item["branch"], f"legacy_cleanup.artifacts[{index}].branch")
    if _has_wildcard(branch) or branch.startswith("/") or ".." in branch.split("/"):
        raise ConfigurationError("INVALID_LEGACY_BRANCH", branch)
    registration = _path_below_root(
        _string(item["registration_path"], f"legacy_cleanup.artifacts[{index}].registration_path"),
        root,
    )
    workspace = _path_below_root(
        _string(item["workspace_path"], f"legacy_cleanup.artifacts[{index}].workspace_path"), root
    )
    return LegacyArtifactConfig(repository, pull_request, branch, registration, workspace)


def _repository_name(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", value) is not None


def _has_wildcard(value: str) -> bool:
    return any(character in value for character in "*?[]")


def _local_root(value: str, environ: Mapping[str, str]) -> Path:
    xdg_value = re.fullmatch(r"\$\{XDG_STATE_HOME:-([^}]+)\}/(.+)", value)
    if xdg_value is not None:
        configured_home = environ.get("XDG_STATE_HOME") or xdg_value.group(1)
        root = Path(configured_home).expanduser() / xdg_value.group(2)
    else:
        root = Path(value).expanduser()
    if not root.is_absolute():
        raise ConfigurationError("INVALID_LEGACY_LOCAL_ROOT", "local_root must be absolute")
    return Path(os.path.abspath(root))


def _path_below_root(value: str, root: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or not value or _has_wildcard(value) or ".." in path.parts:
        raise ConfigurationError("INVALID_LEGACY_LOCAL_PATH", value)
    return root / path


def _table(value: Mapping[str, object], name: str) -> Mapping[str, object]:
    result = value.get(name)
    if not isinstance(result, dict):
        raise ConfigurationError("INVALID_CONFIGURATION", f"{name} must be a TOML table")
    return cast(dict[str, object], result)


def _exact_keys(value: Mapping[str, object], expected: set[str], name: str) -> None:
    _required_and_optional_keys(value, required=expected, optional=set(), name=name)


def _required_and_optional_keys(
    value: Mapping[str, object], *, required: set[str], optional: set[str], name: str
) -> None:
    unknown = sorted(set(value).difference(required | optional))
    missing = sorted(required.difference(value))
    if unknown:
        raise ConfigurationError("UNKNOWN_CONFIGURATION_FIELD", f"{name}: {', '.join(unknown)}")
    if missing:
        raise ConfigurationError("MISSING_CONFIGURATION_FIELD", f"{name}: {', '.join(missing)}")


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError("INVALID_CONFIGURATION", f"{name} must be a non-empty string")
    return value


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigurationError("INVALID_CONFIGURATION", f"{name} must be a list of names")
    values = cast(list[object], value)
    if not all(isinstance(item, str) and item for item in values):
        raise ConfigurationError("INVALID_CONFIGURATION", f"{name} must be a list of names")
    return tuple(cast(list[str], values))


def _int_tuple(value: object, name: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ConfigurationError("INVALID_CONFIGURATION", f"{name} must be a list of integers")
    values = cast(list[object], value)
    if not all(isinstance(item, int) for item in values):
        raise ConfigurationError("INVALID_CONFIGURATION", f"{name} must be a list of integers")
    return tuple(cast(list[int], values))


def _state_directory(value: str, environ: Mapping[str, str]) -> Path:
    return _xdg_state_child(value, environ, "INVALID_STATE_DIRECTORY", "state_directory")


def _workspace_root(value: str, environ: Mapping[str, str]) -> Path:
    return _xdg_state_child(value, environ, "INVALID_WORKSPACE_ROOT", "workspace_root")


def _xdg_state_child(value: str, environ: Mapping[str, str], code: str, name: str) -> Path:
    match = re.fullmatch(r"\$\{XDG_STATE_HOME:-([^}]+)\}/(.+)", value)
    if match is None:
        raise ConfigurationError(code, f"{name} must be under XDG_STATE_HOME")
    configured_home = environ.get("XDG_STATE_HOME") or match.group(1)
    state_home_path = Path(configured_home).expanduser()
    if not state_home_path.is_absolute():
        raise ConfigurationError("INVALID_XDG_STATE_HOME", "XDG_STATE_HOME must be absolute")
    state_home = state_home_path.resolve()
    candidate = (state_home / match.group(2)).resolve()
    if candidate == state_home or not candidate.is_relative_to(state_home):
        raise ConfigurationError(code, f"{name} escapes XDG_STATE_HOME")
    return candidate

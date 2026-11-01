from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .clients import Incompatibility
from .clients.github import GitHubAdapter, GitHubPolicyEvidence
from .clients.glitchtip import GlitchTipAdapter, IssueListing
from .clients.paseo import PaseoAdapter, PaseoCapabilities
from .config import ControllerConfig

__all__ = [
    "ChildEnvironment",
    "Incompatibility",
    "ReadOnlyReport",
    "build_child_environment",
    "build_read_only_report",
]


@dataclass(frozen=True)
class GlitchTipReport:
    issue_ids_by_project: dict[int, tuple[str, ...]]
    listings: tuple[IssueListing, ...]


@dataclass(frozen=True)
class ReadOnlyReport:
    schema_version: int
    config_fingerprint: str
    compatible: bool
    dispatch_enabled: bool
    glitchtip: GlitchTipReport
    github: GitHubPolicyEvidence
    paseo: PaseoCapabilities

    def render(self) -> str:
        projects = ", ".join(
            f"{project}=[{', '.join(issue_ids)}]"
            for project, issue_ids in sorted(self.glitchtip.issue_ids_by_project.items())
        )
        return "\n".join(
            (
                "Read-only compatibility report (schema v1)",
                f"Configuration: {self.config_fingerprint}",
                f"GlitchTip unresolved issue IDs: {projects}",
                f"GitHub classic contexts: {', '.join(self.github.classic_protection.required_contexts)}",
                f"GitHub rulesets: {len(self.github.rulesets)}",
                f"Paseo: {self.paseo.version} ({', '.join(self.paseo.commands)})",
                f"Pi: {self.paseo.pi_version}; configured model: {'available' if self.paseo.pi_model_available else 'unavailable'}",
                "Dispatch: disabled (read-only contract reports never establish readiness)",
            )
        )


@dataclass(frozen=True)
class ChildEnvironment:
    role: str
    environment: dict[str, str]
    home: Path
    xdg_config: Path
    xdg_cache: Path
    xdg_state: Path
    remote: None = None


def build_read_only_report(
    config: ControllerConfig,
    glitchtip: GlitchTipAdapter,
    github: GitHubAdapter,
    paseo: PaseoAdapter,
) -> ReadOnlyReport:
    listings = tuple(
        glitchtip.list_unresolved(
            config.glitchtip.base_url, config.glitchtip.organization, project_id
        )
        for project_id in config.glitchtip.project_ids
    )
    issue_ids = {
        project_id: tuple(issue.id for issue in listing.issues)
        for project_id, listing in zip(config.glitchtip.project_ids, listings, strict=True)
    }
    policy = github.collect_policy()
    capabilities = paseo.capabilities(config.paseo.required_version)
    return ReadOnlyReport(
        schema_version=1,
        config_fingerprint=config.fingerprint,
        compatible=True,
        dispatch_enabled=False,
        glitchtip=GlitchTipReport(issue_ids, listings),
        github=policy,
        paseo=capabilities,
    )


def build_child_environment(
    *,
    role: str,
    root: Path,
    parent_environ: Mapping[str, str],
    controller_secret_names: set[str],
    credential_bearing_remote: str | None = None,
) -> ChildEnvironment:
    if role not in {"remediation", "review"}:
        raise ValueError("role must be remediation or review")
    del credential_bearing_remote
    root.mkdir(parents=True, exist_ok=True)
    child_root = Path(tempfile.mkdtemp(prefix=f"{role}-", dir=root))
    os.chmod(child_root, 0o700)
    home = child_root / "home"
    xdg_config = child_root / "xdg-config"
    xdg_cache = child_root / "xdg-cache"
    xdg_state = child_root / "xdg-state"
    for directory in (home, xdg_config, xdg_cache, xdg_state):
        directory.mkdir(mode=0o700)
        os.chmod(directory, 0o700)

    environment: dict[str, str] = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg_config),
        "XDG_CACHE_HOME": str(xdg_cache),
        "XDG_STATE_HOME": str(xdg_state),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }
    for name in ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ"):
        value = parent_environ.get(name)
        if value and name not in controller_secret_names:
            environment[name] = value
    return ChildEnvironment(role, environment, home, xdg_config, xdg_cache, xdg_state)

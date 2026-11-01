from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import Message
from hashlib import sha256
from pathlib import Path
from typing import Literal, Protocol, cast
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .clients.github import GitHubCredential
from .config import LegacyArtifactConfig, LegacyCleanupConfig


@dataclass(frozen=True)
class LegacyPullRequest:
    repository: str
    number: int
    state: Literal["open", "closed"]
    head_branch: str
    marker: str


class LegacyCleanupClient(Protocol):
    def pull_request(self, *, repository: str, pull_request: int) -> LegacyPullRequest | None: ...

    def close_pull_request(self, *, repository: str, pull_request: int) -> None: ...

    def delete_branch(self, *, repository: str, branch: str) -> None: ...

    def branch_exists(self, *, repository: str, branch: str) -> bool: ...


@dataclass(frozen=True)
class LegacyGitHubResponse:
    status: int
    body: object | None


LegacyGitHubRequest = Callable[[str, str, bytes | None, Mapping[str, str]], LegacyGitHubResponse]


class GitHubLegacyCleanupClient:
    def __init__(
        self,
        *,
        marker: str,
        credential: GitHubCredential,
        request: LegacyGitHubRequest,
    ) -> None:
        self._marker = marker
        self._credential = credential
        self._request = request

    def pull_request(self, *, repository: str, pull_request: int) -> LegacyPullRequest | None:
        response = self._call("GET", f"/repos/{repository}/pulls/{pull_request}", None)
        if response.status == 404:
            return None
        data = _github_object(response, {200})
        number = data.get("number")
        state = data.get("state")
        head = data.get("head")
        base = data.get("base")
        body = data.get("body")
        if not isinstance(head, dict) or not isinstance(base, dict):
            raise ValueError("GitHub pull request head/base is malformed")
        branch = cast(dict[str, object], head).get("ref")
        base_repo = cast(dict[str, object], base).get("repo")
        if not isinstance(base_repo, dict):
            raise ValueError("GitHub pull request repository is malformed")
        remote_repository = cast(dict[str, object], base_repo).get("full_name")
        if (
            not isinstance(number, int)
            or state not in {"open", "closed"}
            or not isinstance(branch, str)
            or not isinstance(remote_repository, str)
            or not isinstance(body, str | type(None))
        ):
            raise ValueError("GitHub pull request evidence is malformed")
        return LegacyPullRequest(
            repository=remote_repository,
            number=number,
            state=cast(Literal["open", "closed"], state),
            head_branch=branch,
            marker=self._marker if self._marker in (body or "").splitlines() else "",
        )

    def close_pull_request(self, *, repository: str, pull_request: int) -> None:
        response = self._call(
            "PATCH",
            f"/repos/{repository}/pulls/{pull_request}",
            json.dumps({"state": "closed"}).encode(),
        )
        _github_object(response, {200})

    def delete_branch(self, *, repository: str, branch: str) -> None:
        response = self._call(
            "DELETE", f"/repos/{repository}/git/refs/heads/{quote(branch, safe='')}", None
        )
        if response.status not in {204, 404}:
            raise ValueError(f"GitHub branch deletion returned HTTP {response.status}")

    def branch_exists(self, *, repository: str, branch: str) -> bool:
        response = self._call(
            "GET", f"/repos/{repository}/git/ref/heads/{quote(branch, safe='')}", None
        )
        if response.status == 404:
            return False
        _github_object(response, {200})
        return True

    def _call(self, method: str, path: str, body: bytes | None) -> LegacyGitHubResponse:
        return self._request(
            method,
            f"https://api.github.com{path}",
            body,
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._credential.value}",
                "Content-Type": "application/json",
            },
        )


@dataclass(frozen=True)
class CleanupInventory:
    ready: bool
    eligible: tuple[LegacyArtifactConfig, ...]
    skipped: Mapping[LegacyArtifactConfig, str]

    def render(self, *, mode: Literal["dry-run", "apply"]) -> str:
        lines = [
            f"mode={mode}",
            f"eligible={len(self.eligible)}",
            f"skipped={len(self.skipped)}",
            f"ready={'yes' if self.ready else 'no'}",
        ]
        for artifact in self.eligible:
            lines.append(f"eligible={_identity(artifact)}")
        for artifact, reason in sorted(self.skipped.items(), key=lambda item: _identity(item[0])):
            lines.append(f"skipped={_identity(artifact)} reason={reason}")
        return "\n".join(lines)


@dataclass(frozen=True)
class CleanupResult:
    inventory: CleanupInventory
    complete: bool
    cutover_enabled: bool
    failed: Mapping[LegacyArtifactConfig, str]

    def render(self) -> str:
        lines = [
            self.inventory.render(mode="apply"),
            f"failed={len(self.failed)}",
            f"complete={'yes' if self.complete else 'no'}",
            f"cutover_enabled={'yes' if self.cutover_enabled else 'no'}",
        ]
        for artifact, reason in sorted(self.failed.items(), key=lambda item: _identity(item[0])):
            lines.append(f"failed={_identity(artifact)} reason={reason}")
        return "\n".join(lines)


def confirmation_token(config: LegacyCleanupConfig) -> str:
    canonical = repr(
        (
            config.marker,
            str(config.local_root),
            config.repositories,
            tuple(
                (
                    artifact.repository,
                    artifact.pull_request,
                    artifact.branch,
                    str(artifact.registration_path),
                    str(artifact.workspace_path),
                )
                for artifact in config.artifacts
            ),
        )
    )
    return f"DELETE-LEGACY-CLEANUP-{sha256(canonical.encode()).hexdigest()[:16]}"


def inventory(config: LegacyCleanupConfig, client: LegacyCleanupClient) -> CleanupInventory:
    if not config.enabled:
        return CleanupInventory(
            ready=False,
            eligible=(),
            skipped={artifact: "CLEANUP_DISABLED" for artifact in config.artifacts},
        )
    root_error = _root_error(config.local_root)
    if root_error is not None:
        return CleanupInventory(
            ready=False,
            eligible=(),
            skipped={artifact: root_error for artifact in config.artifacts},
        )

    eligible: list[LegacyArtifactConfig] = []
    skipped: dict[LegacyArtifactConfig, str] = {}
    for artifact in config.artifacts:
        path_error = _local_path_error(config, artifact)
        if path_error is not None:
            skipped[artifact] = path_error
            continue
        try:
            checkpoint = _checkpoint_stage(config, artifact)
        except OSError, ValueError:
            skipped[artifact] = "LOCAL_CHECKPOINT_INVALID"
            continue
        local_error = _local_evidence_error(config, artifact, checkpoint)
        if local_error is not None and not _legacy_paths_absent(artifact):
            skipped[artifact] = local_error
            continue
        try:
            pull_request = client.pull_request(
                repository=artifact.repository, pull_request=artifact.pull_request
            )
        except Exception:
            skipped[artifact] = "REMOTE_LOOKUP_FAILED"
            continue
        if pull_request is None:
            skipped[artifact] = "PULL_REQUEST_MISSING"
            continue
        remote_error = _remote_evidence_error(config, artifact, pull_request, checkpoint)
        if remote_error is not None:
            skipped[artifact] = remote_error
            continue
        try:
            branch_exists = client.branch_exists(
                repository=artifact.repository, branch=artifact.branch
            )
        except Exception:
            skipped[artifact] = "REMOTE_LOOKUP_FAILED"
            continue
        if not branch_exists and pull_request.state != "closed":
            skipped[artifact] = "BRANCH_MISSING"
            continue
        if local_error is not None and not _observed_remote_absent(pull_request, branch_exists):
            skipped[artifact] = local_error
            continue
        eligible.append(artifact)
    return CleanupInventory(not skipped and bool(eligible), tuple(eligible), skipped)


def apply_cleanup(
    config: LegacyCleanupConfig,
    client: LegacyCleanupClient,
    *,
    confirmation: str,
    legacy_service_stopped: bool,
) -> CleanupResult:
    if confirmation != confirmation_token(config):
        failures = {artifact: "CONFIRMATION_REQUIRED" for artifact in config.artifacts}
        return CleanupResult(CleanupInventory(False, (), {}), False, False, failures)
    if not legacy_service_stopped:
        failures = {artifact: "LEGACY_SERVICE_STOP_REQUIRED" for artifact in config.artifacts}
        return CleanupResult(CleanupInventory(False, (), {}), False, False, failures)
    if not config.enabled:
        failures = {artifact: "CLEANUP_DISABLED" for artifact in config.artifacts}
        return CleanupResult(CleanupInventory(False, (), {}), False, False, failures)

    observed = inventory(config, client)
    failures: dict[LegacyArtifactConfig, str] = {}
    if observed.skipped:
        return CleanupResult(observed, False, False, failures)
    if not observed.eligible:
        return CleanupResult(observed, False, False, failures)

    for artifact in observed.eligible:
        try:
            _resume_remote_cleanup(config, artifact, client)
        except Exception:
            failures[artifact] = "REMOTE_DELETE_FAILED"
    if failures:
        return CleanupResult(observed, False, False, failures)

    for artifact in observed.eligible:
        if not _remote_absent(config, artifact, client):
            failures[artifact] = "REMOTE_ABSENCE_UNVERIFIED"
    if failures:
        return CleanupResult(observed, False, False, failures)

    for artifact in observed.eligible:
        try:
            checkpoint = _checkpoint_stage(config, artifact)
            if checkpoint != "local_clean" and _has_local_resume_evidence(artifact):
                _write_checkpoint(config, artifact, "remote_absent")
        except OSError, ValueError:
            failures[artifact] = "LOCAL_CHECKPOINT_WRITE_FAILED"
    if failures:
        return CleanupResult(observed, False, False, failures)

    for artifact in observed.eligible:
        try:
            _remove_local(config, artifact)
        except OSError:
            failures[artifact] = "LOCAL_DELETE_FAILED"
    complete = not failures
    return CleanupResult(observed, complete, complete, failures)


def _github_object(response: LegacyGitHubResponse, statuses: set[int]) -> Mapping[str, object]:
    raw_body = response.body
    if response.status not in statuses or not isinstance(raw_body, dict):
        raise ValueError(f"unexpected GitHub response HTTP {response.status}")
    body = cast(dict[object, object], raw_body)
    if not all(isinstance(key, str) for key in body):
        raise ValueError("GitHub response keys must be strings")
    return {cast(str, key): value for key, value in body.items()}


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> Request | None:
        del req, fp, code, msg, headers, newurl
        return None


_GITHUB_OPENER = build_opener(_NoRedirectHandler())


def default_github_request(
    method: str, url: str, body: bytes | None, headers: Mapping[str, str]
) -> LegacyGitHubResponse:
    request = Request(url, data=body, headers=dict(headers), method=method)
    try:
        with _GITHUB_OPENER.open(request, timeout=15) as response:
            payload = response.read()
            return LegacyGitHubResponse(
                status=response.status,
                body=None if not payload else cast(object, json.loads(payload.decode())),
            )
    except HTTPError as error:
        payload = error.read()
        return LegacyGitHubResponse(
            status=error.code,
            body=None if not payload else cast(object, json.loads(payload.decode())),
        )


def _remote_evidence_error(
    config: LegacyCleanupConfig,
    artifact: LegacyArtifactConfig,
    pull_request: LegacyPullRequest | None,
    checkpoint: str | None,
) -> str | None:
    if pull_request is None:
        return "PULL_REQUEST_MISSING"
    if pull_request.repository != artifact.repository:
        return "REPOSITORY_MISMATCH"
    if pull_request.number != artifact.pull_request:
        return "PULL_REQUEST_MISMATCH"
    if pull_request.head_branch != artifact.branch:
        return "BRANCH_MISMATCH"
    if pull_request.marker != config.marker:
        return "MARKER_MISMATCH"
    if pull_request.state == "open":
        if checkpoint not in {None, "close_requested"}:
            return "CHECKPOINT_MISMATCH"
        return None
    if checkpoint not in {
        None,
        "close_requested",
        "pull_request_closed",
        "remote_absent",
        "local_clean",
    }:
        return "CHECKPOINT_MISMATCH"
    return None


def _observed_remote_absent(pull_request: LegacyPullRequest, branch_exists: bool) -> bool:
    return pull_request.state == "closed" and not branch_exists


def _resume_remote_cleanup(
    config: LegacyCleanupConfig, artifact: LegacyArtifactConfig, client: LegacyCleanupClient
) -> None:
    checkpoint = _checkpoint_stage(config, artifact)
    pull_request = client.pull_request(
        repository=artifact.repository, pull_request=artifact.pull_request
    )
    remote_error = _remote_evidence_error(config, artifact, pull_request, checkpoint)
    if remote_error is not None or pull_request is None:
        raise OSError(remote_error or "PULL_REQUEST_MISSING")
    if pull_request.state == "open":
        _write_checkpoint(config, artifact, "close_requested")
        client.close_pull_request(
            repository=artifact.repository, pull_request=artifact.pull_request
        )
        closed = client.pull_request(
            repository=artifact.repository, pull_request=artifact.pull_request
        )
        if _remote_evidence_error(config, artifact, closed, "close_requested") is not None:
            raise OSError("PULL_REQUEST_CLOSE_UNVERIFIED")
        _write_checkpoint(config, artifact, "pull_request_closed")
    if client.branch_exists(repository=artifact.repository, branch=artifact.branch):
        client.delete_branch(repository=artifact.repository, branch=artifact.branch)


def _remote_absent(
    config: LegacyCleanupConfig, artifact: LegacyArtifactConfig, client: LegacyCleanupClient
) -> bool:
    try:
        pull_request = client.pull_request(
            repository=artifact.repository, pull_request=artifact.pull_request
        )
        if pull_request is None:
            return False
        if (
            pull_request.repository != artifact.repository
            or pull_request.number != artifact.pull_request
            or pull_request.head_branch != artifact.branch
            or pull_request.marker != config.marker
            or pull_request.state != "closed"
        ):
            return False
        return not client.branch_exists(repository=artifact.repository, branch=artifact.branch)
    except Exception:
        return False


def _local_path_error(config: LegacyCleanupConfig, artifact: LegacyArtifactConfig) -> str | None:
    for path in (artifact.registration_path, artifact.workspace_path, _checkpoint_path(artifact)):
        path_error = _safe_local_path(config.local_root, path)
        if path_error is not None:
            return path_error
    return None


def _local_evidence_error(
    config: LegacyCleanupConfig, artifact: LegacyArtifactConfig, checkpoint: str | None
) -> str | None:
    path_error = _local_path_error(config, artifact)
    if path_error is not None:
        return path_error
    if artifact.workspace_path.exists() and not artifact.workspace_path.is_dir():
        return "LOCAL_WORKSPACE_INVALID"
    if not artifact.registration_path.exists():
        return None if checkpoint is not None else "LOCAL_REGISTRATION_MISSING"
    if not artifact.registration_path.is_file():
        return "LOCAL_REGISTRATION_INVALID"
    try:
        registration = cast(dict[str, object], json.loads(artifact.registration_path.read_text()))
    except OSError, json.JSONDecodeError:
        return "LOCAL_REGISTRATION_INVALID"
    expected = {
        "schema_version": 1,
        "marker": config.marker,
        "repository": artifact.repository,
        "pull_request": artifact.pull_request,
        "branch": artifact.branch,
        "workspace_path": str(artifact.workspace_path),
    }
    return None if registration == expected else "LOCAL_REGISTRATION_MISMATCH"


def _legacy_paths_absent(artifact: LegacyArtifactConfig) -> bool:
    return not artifact.registration_path.exists() and not artifact.workspace_path.exists()


def _has_local_resume_evidence(artifact: LegacyArtifactConfig) -> bool:
    return (
        artifact.registration_path.exists()
        or artifact.workspace_path.exists()
        or _checkpoint_path(artifact).exists()
    )


def _checkpoint_path(artifact: LegacyArtifactConfig) -> Path:
    return artifact.registration_path.with_name(f".{artifact.registration_path.name}.cleanup")


def _checkpoint_stage(config: LegacyCleanupConfig, artifact: LegacyArtifactConfig) -> str | None:
    path = _checkpoint_path(artifact)
    path_error = _safe_local_path(config.local_root, path)
    if path_error is not None:
        raise OSError(path_error)
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise ValueError("checkpoint path is invalid")
    try:
        checkpoint = cast(dict[str, object], json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("checkpoint is invalid") from error
    stage = checkpoint.get("stage")
    expected = {
        "schema_version": 1,
        "marker": config.marker,
        "repository": artifact.repository,
        "pull_request": artifact.pull_request,
        "branch": artifact.branch,
        "workspace_path": str(artifact.workspace_path),
        "stage": stage,
    }
    if (
        stage not in {"close_requested", "pull_request_closed", "remote_absent", "local_clean"}
        or checkpoint != expected
    ):
        raise ValueError("checkpoint identity is invalid")
    return cast(str, stage)


def _write_checkpoint(
    config: LegacyCleanupConfig, artifact: LegacyArtifactConfig, stage: str
) -> None:
    if stage not in {"close_requested", "pull_request_closed", "remote_absent", "local_clean"}:
        raise ValueError("checkpoint stage is invalid")
    path = _checkpoint_path(artifact)
    path_error = _safe_local_path(config.local_root, path)
    if path_error is not None:
        raise OSError(path_error)
    payload = json.dumps(
        {
            "schema_version": 1,
            "marker": config.marker,
            "repository": artifact.repository,
            "pull_request": artifact.pull_request,
            "branch": artifact.branch,
            "workspace_path": str(artifact.workspace_path),
            "stage": stage,
        },
        sort_keys=True,
    )
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _root_error(root: Path) -> str | None:
    if not root.is_absolute() or root == Path(root.anchor):
        return "ROOT_PATH"
    if _has_symlink_component(root):
        return "SYMLINK_PATH"
    return None


def _has_symlink_component(path: Path) -> bool:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if current.is_symlink():
            return True
    return False


def _safe_local_path(root: Path, path: Path) -> str | None:
    root_error = _root_error(root)
    if root_error is not None:
        return root_error
    if not path.is_absolute() or path == Path(path.anchor):
        return "ROOT_PATH"
    normalized_root = Path(os.path.normpath(str(root)))
    normalized_path = Path(os.path.normpath(str(path)))
    try:
        relative = normalized_path.relative_to(normalized_root)
    except ValueError:
        return "OUT_OF_SCOPE_PATH"
    current = normalized_root
    if current.is_symlink():
        return "SYMLINK_PATH"
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            return "SYMLINK_PATH"
    return None


def _remove_local(config: LegacyCleanupConfig, artifact: LegacyArtifactConfig) -> None:
    checkpoint = _checkpoint_path(artifact)
    for path in (artifact.registration_path, artifact.workspace_path, checkpoint):
        path_error = _safe_local_path(config.local_root, path)
        if path_error is not None:
            raise OSError(path_error)
    if artifact.workspace_path.exists():
        shutil.rmtree(artifact.workspace_path)
    if artifact.registration_path.exists():
        artifact.registration_path.unlink()
    if artifact.workspace_path.exists() or artifact.registration_path.exists():
        raise OSError("LOCAL_ABSENCE_UNVERIFIED")
    if checkpoint.exists():
        _write_checkpoint(config, artifact, "local_clean")


def _identity(artifact: LegacyArtifactConfig) -> str:
    return f"{artifact.repository}#{artifact.pull_request}:{artifact.branch}"

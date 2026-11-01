from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .clients.github import GitHubCredential, PullRequest, PullRequestOutcome
from .clients.glitchtip import CapturedResponse, GlitchTipAdapter, GlitchTipIssue, IssueListing
from .clients.paseo import AgentResult, OriginMain, WorkspaceLaunch


class RuntimeClientError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RuntimeResponse:
    status: int
    body: object
    headers: Mapping[str, str]


@dataclass(frozen=True)
class CommandOutput:
    returncode: int
    stdout: str
    stderr: str


HttpRequest = Callable[[str, str, Mapping[str, str], bytes | None], RuntimeResponse]
CommandRunner = Callable[[tuple[str, ...], Path, Mapping[str, str]], CommandOutput]


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> Request | None:
        del req, fp, code, msg, headers, newurl
        return None


_HTTP = build_opener(_NoRedirectHandler())
_USER_AGENT = "ignite-glitchtip-paseo-controller/0.1"
_MAX_OUTPUT = 256 * 1024


def default_http_request(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None
) -> RuntimeResponse:
    request = Request(
        url,
        data=body,
        headers={**headers, "User-Agent": _USER_AGENT},
        method=method,
    )
    try:
        with _HTTP.open(request, timeout=20) as response:
            raw = response.read(_MAX_OUTPUT + 1)
            if len(raw) > _MAX_OUTPUT:
                raise RuntimeClientError("HTTP_BODY_TOO_LARGE")
            parsed = None if not raw else json.loads(raw.decode())
            return RuntimeResponse(
                int(response.status), parsed, {"Link": response.headers.get("Link", "")}
            )
    except RuntimeClientError:
        raise
    except HTTPError as error:
        raise RuntimeClientError(f"HTTP_{error.code}") from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeClientError("HTTP_FAILURE") from error


def default_command_runner(
    command: tuple[str, ...], cwd: Path, environment: Mapping[str, str]
) -> CommandOutput:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=dict(environment),
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeClientError("COMMAND_FAILURE") from error
    stdout = result.stdout[:_MAX_OUTPUT]
    stderr = result.stderr[:_MAX_OUTPUT]
    if len(result.stdout) > _MAX_OUTPUT or len(result.stderr) > _MAX_OUTPUT:
        raise RuntimeClientError("COMMAND_OUTPUT_TOO_LARGE")
    return CommandOutput(result.returncode, stdout, stderr)


class LiveGlitchTipClient:
    def __init__(
        self,
        *,
        base_url: str,
        organization: str,
        token: str,
        request: HttpRequest = default_http_request,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._organization = organization
        self._headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        self._request = request

    def list_unresolved(self, project_id: int) -> IssueListing:
        return GlitchTipAdapter(self._captured_get).list_unresolved(
            self._base_url, self._organization, project_id
        )

    def issue_context_data(
        self, *, project_id: int, issue_id: str
    ) -> tuple[GlitchTipIssue, Mapping[str, object]]:
        detail = self._issue_object(project_id, issue_id)
        issue = GlitchTipAdapter(lambda _: CapturedResponse(detail, {})).issue_detail(
            "https://glitchtip.scowalt.com/detail", project_id
        )
        return issue, detail

    def latest_event(self, *, issue_id: str) -> Mapping[str, object]:
        body = self._json("GET", f"/api/0/issues/{_issue_identifier(issue_id)}/events/latest/")
        return _event_context(_object(body, "MALFORMED_GLITCHTIP_EVENT"))

    def current_issue(self, *, project_id: int, issue_id: str) -> GlitchTipIssue | None:
        try:
            detail = self._issue_object(project_id, issue_id)
        except RuntimeClientError as error:
            if error.code == "HTTP_404":
                return None
            raise
        return GlitchTipAdapter(lambda _: CapturedResponse(detail, {})).issue_detail(
            "https://glitchtip.scowalt.com/detail", project_id
        )

    def resolve_issue(self, *, project_id: int, issue_id: str) -> GlitchTipIssue | None:
        detail = self._json(
            "PUT",
            f"/api/0/issues/{_issue_identifier(issue_id)}/",
            {"status": "resolved"},
        )
        issue = GlitchTipAdapter(lambda _: CapturedResponse(detail, {})).issue_detail(
            "https://glitchtip.scowalt.com/detail", project_id
        )
        return issue

    def _issue_object(self, project_id: int, issue_id: str) -> Mapping[str, object]:
        detail = self._json("GET", f"/api/0/issues/{_issue_identifier(issue_id)}/")
        parsed = _object(detail, "MALFORMED_GLITCHTIP_DETAIL")
        project = _object(parsed.get("project"), "GLITCHTIP_PROJECT_MISMATCH")
        if project.get("id") != str(project_id):
            raise RuntimeClientError("GLITCHTIP_PROJECT_MISMATCH")
        return parsed

    def _captured_get(self, url: str) -> CapturedResponse:
        response = self._request("GET", url, self._headers, None)
        if not 200 <= response.status < 300:
            raise RuntimeClientError(f"HTTP_{response.status}")
        return CapturedResponse(response.body, response.headers)

    def _json(self, method: str, path: str, value: object | None = None) -> object:
        body = None if value is None else json.dumps(value, separators=(",", ":")).encode()
        headers = (
            self._headers if body is None else {**self._headers, "Content-Type": "application/json"}
        )
        response = self._request(method, f"{self._base_url}{path}", headers, body)
        if not 200 <= response.status < 300:
            raise RuntimeClientError(f"HTTP_{response.status}")
        return response.body


class LiveGitHubClient:
    def __init__(
        self,
        *,
        repository: str,
        credential: GitHubCredential,
        request: HttpRequest = default_http_request,
    ) -> None:
        self._repository = repository
        self._credential = credential
        self._request = request
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {credential.value}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def find_linked_pull_requests(
        self, *, repository: str, branch: str, marker: str
    ) -> tuple[PullRequest, ...]:
        self._require_repository(repository)
        query = urlencode({"state": "all", "head": f"scowalt:{branch}", "per_page": "100"})
        body = self._json("GET", f"/pulls?{query}")
        if not isinstance(body, list):
            raise RuntimeClientError("MALFORMED_GITHUB_PULLS")
        typed_body = cast(list[object], body)
        if len(typed_body) > 100:
            raise RuntimeClientError("MALFORMED_GITHUB_PULLS")
        pull_requests = tuple(_pull_request(item) for item in typed_body)
        return tuple(
            pull_request
            for pull_request in pull_requests
            if marker in pull_request.body.splitlines()
        )

    def observe_pull_request(
        self, *, repository: str, pull_request: int
    ) -> PullRequestOutcome | None:
        self._require_repository(repository)
        response = self._response("GET", f"/pulls/{_pull_request_number(pull_request)}")
        if response.status == 404:
            return None
        if not 200 <= response.status < 300:
            raise RuntimeClientError(f"GITHUB_HTTP_{response.status}")
        body = _object(response.body, "MALFORMED_GITHUB_PULL_REQUEST")
        number = body.get("number")
        state = body.get("state")
        merged = body.get("merged")
        if (
            not isinstance(number, int)
            or number != pull_request
            or not isinstance(state, str)
            or not isinstance(merged, bool)
        ):
            raise RuntimeClientError("MALFORMED_GITHUB_PULL_REQUEST")
        if state == "open":
            outcome: Literal["open", "merged", "closed", "ci_failed", "unknown"] = "open"
        elif state == "closed" and merged:
            outcome = "merged"
        elif state == "closed":
            outcome = "closed"
        else:
            outcome = "unknown"
        return PullRequestOutcome(number, outcome)

    def request_auto_merge(
        self, *, repository: str, pull_request: int, credential: GitHubCredential
    ) -> None:
        self._require_repository(repository)
        if credential != self._credential:
            raise RuntimeClientError("GITHUB_CREDENTIAL_MISMATCH")
        number = _pull_request_number(pull_request)
        current = self._response("GET", f"/pulls/{number}")
        if not 200 <= current.status < 300:
            raise RuntimeClientError(f"GITHUB_HTTP_{current.status}")
        current_body = _object(current.body, "MALFORMED_GITHUB_PULL_REQUEST")
        if current_body.get("auto_merge") is not None:
            return
        response = self._response("PUT", f"/pulls/{number}/auto-merge", {})
        if not 200 <= response.status < 300:
            raise RuntimeClientError(f"GITHUB_HTTP_{response.status}")

    def _require_repository(self, repository: str) -> None:
        if repository != self._repository:
            raise RuntimeClientError("GITHUB_REPOSITORY_MISMATCH")

    def _json(self, method: str, path: str) -> object:
        response = self._response(method, path)
        if not 200 <= response.status < 300:
            raise RuntimeClientError(f"GITHUB_HTTP_{response.status}")
        return response.body

    def _response(self, method: str, path: str, value: object | None = None) -> RuntimeResponse:
        body = None if value is None else json.dumps(value, separators=(",", ":")).encode()
        return self._request(
            method, f"https://api.github.com/repos/{self._repository}{path}", self._headers, body
        )


class LivePaseoClient:
    def __init__(
        self,
        *,
        workspace_root: Path,
        repository: str,
        model: str,
        thinking: str,
        credential: GitHubCredential,
        runner: CommandRunner = default_command_runner,
        request: HttpRequest = default_http_request,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._workspace_root = workspace_root
        self._repository = repository
        self._model = model
        self._thinking = thinking
        self._credential = credential
        self._runner = runner
        self._request = request
        self._github_headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {credential.value}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        inherited = os.environ if environment is None else environment
        self._environment = {
            name: value
            for name in ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "PASEO_HOME", "PASEO_HOST")
            if (value := inherited.get(name))
        }

    def _git_fetch_environment(self) -> dict[str, str]:
        basic = base64.b64encode(f"x-access-token:{self._credential.value}".encode()).decode()
        return {
            **self._environment,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.https://github.com/.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
        }

    def fresh_origin_main(self) -> OriginMain:
        environment = self._git_fetch_environment()
        self._ok(("git", "fetch", "origin", "main"), self._workspace_root, environment)
        sha = self._ok(
            ("git", "rev-parse", "--verify", "origin/main"), self._workspace_root, environment
        ).strip()
        if re.fullmatch(r"[0-9a-f]{40,64}", sha) is None:
            raise RuntimeClientError("INVALID_ORIGIN_MAIN")
        return OriginMain("origin/main", sha)

    def launch(self, request: WorkspaceLaunch, credential: GitHubCredential) -> AgentResult:
        if credential != self._credential:
            raise RuntimeClientError("GITHUB_CREDENTIAL_MISMATCH")
        if request.base.reference != "origin/main" or not re.fullmatch(
            r"[0-9a-f]{40,64}", request.base.commit_sha
        ):
            raise RuntimeClientError("INVALID_ORIGIN_MAIN")
        output = self._ok(
            (
                "paseo",
                "run",
                "--detach",
                "--json",
                "--provider",
                "pi",
                "--title",
                request.agent_identity,
                "--model",
                self._model,
                "--thinking",
                self._thinking,
                "--env",
                f"GITHUB_AUTOMATION_TOKEN={credential.value}",
                "--worktree",
                request.workspace,
                "--base",
                request.base.reference,
                "--cwd",
                str(self._workspace_root),
                request.prompt,
            ),
            self._workspace_root,
            self._environment,
        )
        payload = _object(_json_output(output, "MALFORMED_PASEO_LAUNCH"), "MALFORMED_PASEO_LAUNCH")
        if not isinstance(payload.get("agentId"), str) or payload.get("status") not in {
            "running",
            "created",
        }:
            raise RuntimeClientError("MALFORMED_PASEO_LAUNCH")
        return AgentResult(request.agent_identity, "running", None)

    def agent_result(self, agent_identity: str) -> AgentResult | None:
        agent = self._agent(agent_identity)
        if agent is None:
            return None
        details = self._inspect(str(agent["id"]))
        status = details.get("Status")
        archived = details.get("Archived")
        if not isinstance(status, str) or not isinstance(archived, bool):
            raise RuntimeClientError("MALFORMED_PASEO_INSPECT")
        if status == "running":
            return AgentResult(agent_identity, "running", None)
        if status == "idle" and not archived:
            return AgentResult(agent_identity, "complete", None)
        return AgentResult(agent_identity, "failed", None)

    def archive_agent(self, agent_identity: str) -> None:
        agent = self._agent(agent_identity)
        if agent is None:
            raise RuntimeClientError("PASEO_AGENT_MISSING")
        details = self._inspect(str(agent["id"]))
        if details.get("Archived") is True:
            return
        result = self._run(("paseo", "archive", "--json", str(agent["id"])), self._environment)
        if result.returncode != 0:
            raise RuntimeClientError("PASEO_ARCHIVE_FAILED")

    def _worktree_paths(self) -> dict[str, str]:
        raw = self._ok(
            ("git", "worktree", "list", "--porcelain"), self._workspace_root, self._environment
        )
        paths: dict[str, str] = {}
        for line in raw.splitlines():
            if line.startswith("worktree "):
                full = line[len("worktree ") :].strip()
                if full != str(self._workspace_root):
                    paths[full.rsplit("/", 1)[-1]] = full
        return paths

    def remove_workspace(self, workspace: str) -> None:
        path = self._worktree_paths().get(workspace)
        if path is None:
            return
        self._ok(("git", "worktree", "remove", path), self._workspace_root, self._environment)
        if workspace in self._worktree_paths():
            raise RuntimeClientError("PASEO_WORKSPACE_ARCHIVE_FAILED")

    def remove_local_branch(self, branch: str) -> None:
        exists = self._run(
            ("git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"), self._environment
        )
        if exists.returncode == 0:
            self._ok(("git", "branch", "-D", branch), self._workspace_root, self._environment)
        elif exists.returncode != 1:
            raise RuntimeClientError("LOCAL_BRANCH_LOOKUP_FAILED")

    def remove_remote_branch(self, branch: str) -> None:
        if not branch:
            raise RuntimeClientError("INVALID_REMOTE_BRANCH")
        url = (
            f"https://api.github.com/repos/{self._repository}/git/refs/heads/"
            f"{quote(branch, safe='')}"
        )
        try:
            self._request("GET", url, self._github_headers, None)
        except RuntimeClientError as error:
            if error.code == "HTTP_404":
                return
            raise
        try:
            response = self._request("DELETE", url, self._github_headers, None)
        except RuntimeClientError as error:
            if error.code in {"HTTP_404", "HTTP_422"}:
                return
            raise
        if response.status in {204, 404}:
            return
        raise RuntimeClientError(f"GITHUB_HTTP_{response.status}")

    def _agent(self, agent_identity: str) -> Mapping[str, object] | None:
        raw = self._ok(
            ("paseo", "ls", "--all", "--global", "--json"), self._workspace_root, self._environment
        )
        agents = _array(_json_output(raw, "MALFORMED_PASEO_AGENTS"), "MALFORMED_PASEO_AGENTS")
        matches = [
            _object(item, "MALFORMED_PASEO_AGENTS")
            for item in agents
            if _object(item, "MALFORMED_PASEO_AGENTS").get("name") == agent_identity
        ]
        if len(matches) > 1:
            raise RuntimeClientError("PASEO_AGENT_DUPLICATED")
        if not matches:
            return None
        identifier = matches[0].get("id")
        if not isinstance(identifier, str) or not identifier:
            raise RuntimeClientError("MALFORMED_PASEO_AGENTS")
        return matches[0]

    def _inspect(self, agent_id: str) -> Mapping[str, object]:
        output = self._ok(
            ("paseo", "inspect", "--json", agent_id), self._workspace_root, self._environment
        )
        return _object(_json_output(output, "MALFORMED_PASEO_INSPECT"), "MALFORMED_PASEO_INSPECT")

    def _run(self, command: tuple[str, ...], environment: Mapping[str, str]) -> CommandOutput:
        return self._runner(command, self._workspace_root, environment)

    def _ok(self, command: tuple[str, ...], cwd: Path, environment: Mapping[str, str]) -> str:
        result = self._runner(command, cwd, environment)
        if result.returncode != 0:
            if command[0] == "paseo" and _paseo_daemon_unavailable(result):
                raise RuntimeClientError("PASEO_DAEMON_UNAVAILABLE")
            raise RuntimeClientError("PASEO_COMMAND_FAILED")
        return result.stdout


def _paseo_daemon_unavailable(result: CommandOutput) -> bool:
    output = f"{result.stdout}\n{result.stderr}"
    return "DAEMON_NOT_RUNNING" in output or "Cannot connect to daemon" in output


def _issue_identifier(issue_id: str) -> str:
    if re.fullmatch(r"[0-9]+", issue_id) is None:
        raise RuntimeClientError("INVALID_GLITCHTIP_ISSUE_ID")
    return issue_id


def _pull_request_number(number: int) -> int:
    if isinstance(number, bool) or number < 1:
        raise RuntimeClientError("INVALID_GITHUB_PULL_REQUEST")
    return number


def _pull_request(value: object) -> PullRequest:
    item = _object(value, "MALFORMED_GITHUB_PULLS")
    number = item.get("number")
    state = item.get("state")
    body = item.get("body")
    head = item.get("head")
    if body is None:
        body = ""
    if not isinstance(number, int) or not isinstance(state, str) or not isinstance(body, str):
        raise RuntimeClientError("MALFORMED_GITHUB_PULLS")
    head_data = _object(head, "MALFORMED_GITHUB_PULLS")
    branch = head_data.get("ref")
    if state not in {"open", "closed"} or not isinstance(branch, str) or not branch:
        raise RuntimeClientError("MALFORMED_GITHUB_PULLS")
    return PullRequest(number, state, branch, body)


def _event_context(value: Mapping[str, object]) -> Mapping[str, object]:
    if any(key in value for key in ("message", "exception", "breadcrumbs")):
        return value
    entries = value.get("entries")
    if not isinstance(entries, list):
        return value
    result: dict[str, object] = {}
    for entry in cast(list[object], entries):
        item = _object(entry, "MALFORMED_GLITCHTIP_EVENT")
        kind = item.get("type")
        data = item.get("data")
        if not isinstance(kind, str) or not isinstance(data, dict):
            continue
        data_object = cast(dict[str, object], data)
        if kind == "exception" and "exception" not in result:
            result["exception"] = data_object
        elif kind == "breadcrumbs" and "breadcrumbs" not in result:
            result["breadcrumbs"] = data_object
        elif kind == "message" and "message" not in result:
            message = data_object.get("formatted") or data_object.get("message")
            if isinstance(message, str):
                result["message"] = message
    return result


def _json_output(value: str, code: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise RuntimeClientError(code) from error


def _object(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise RuntimeClientError(code)
    return cast(dict[str, object], value)


def _array(value: object, code: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeClientError(code)
    return cast(list[object], value)

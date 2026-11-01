from __future__ import annotations

import base64
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from glitchtip_paseo_controller.clients.github import GitHubCredential
from glitchtip_paseo_controller.clients.paseo import OriginMain, WorkspaceLaunch
from glitchtip_paseo_controller.runtime_clients import (
    CommandOutput,
    LiveGitHubClient,
    LiveGlitchTipClient,
    LivePaseoClient,
    RuntimeClientError,
    RuntimeResponse,
    default_http_request,
)


class RuntimeClientTests(unittest.TestCase):
    def test_glitchtip_parses_detail_event_and_ordinary_resolution(self) -> None:
        calls: list[tuple[str, str, dict[str, str], bytes | None]] = []
        issue = {
            "id": "101",
            "status": "unresolved",
            "title": "Failure",
            "count": "1",
            "firstSeen": "2026-01-01T00:00:00Z",
            "lastSeen": "2026-01-02T00:00:00Z",
            "project": {"id": "2", "slug": "backend"},
        }

        def request(method: str, url: str, headers: object, body: bytes | None) -> RuntimeResponse:
            calls.append((method, url, dict(headers), body))  # type: ignore[arg-type]
            if url.endswith("events/latest/"):
                return RuntimeResponse(
                    200,
                    {
                        "entries": [
                            {"type": "message", "data": {"formatted": "event message"}},
                            {"type": "breadcrumbs", "data": {"values": []}},
                        ]
                    },
                    {},
                )
            if method == "PUT":
                return RuntimeResponse(200, {**issue, "status": "resolved"}, {})
            return RuntimeResponse(200, issue, {})

        client = LiveGlitchTipClient(
            base_url="https://glitchtip.scowalt.com",
            organization="scowalt",
            token="glitchtip-secret",
            request=request,
        )

        observed, detail = client.issue_context_data(project_id=2, issue_id="101")
        event = client.latest_event(issue_id="101")
        resolved = client.resolve_issue(project_id=2, issue_id="101")

        self.assertEqual(observed.id, "101")
        self.assertEqual(detail["title"], "Failure")
        self.assertEqual(event["message"], "event message")
        self.assertEqual(resolved.status if resolved else None, "resolved")
        self.assertEqual(calls[-1][0], "PUT")
        self.assertEqual(calls[-1][2]["Content-Type"], "application/json")
        self.assertEqual(calls[-1][3], b'{"status":"resolved"}')
        with self.assertRaisesRegex(RuntimeClientError, "INVALID_GLITCHTIP_ISSUE_ID"):
            client.current_issue(project_id=2, issue_id="101/escape")

    def test_github_outcome_lookup_and_auto_merge_reject_malformed_responses(self) -> None:
        requests: list[tuple[str, str]] = []

        def request(method: str, url: str, headers: object, body: bytes | None) -> RuntimeResponse:
            del headers, body
            requests.append((method, url))
            if url.endswith("/pulls/42"):
                return RuntimeResponse(200, {"number": 42, "state": "closed", "merged": True}, {})
            if "auto-merge" in url:
                return RuntimeResponse(200, {}, {})
            if "pulls?" in url:
                return RuntimeResponse(
                    200,
                    [
                        {
                            "number": 42,
                            "state": "open",
                            "body": "work\n<!-- marker -->",
                            "head": {"ref": "automation/fix"},
                        }
                    ],
                    {},
                )
            return RuntimeResponse(200, {"auto_merge": None}, {})

        credential = GitHubCredential("github-secret")
        client = LiveGitHubClient(
            repository="scowalt/ignite-for-spotify-2", credential=credential, request=request
        )

        linked = client.find_linked_pull_requests(
            repository="scowalt/ignite-for-spotify-2",
            branch="automation/fix",
            marker="<!-- marker -->",
        )
        outcome = client.observe_pull_request(
            repository="scowalt/ignite-for-spotify-2", pull_request=42
        )
        client.request_auto_merge(
            repository="scowalt/ignite-for-spotify-2", pull_request=42, credential=credential
        )

        self.assertEqual([pull.number for pull in linked], [42])
        self.assertEqual(outcome.state if outcome else None, "merged")
        self.assertTrue(any(method == "PUT" and "auto-merge" in url for method, url in requests))

        malformed = LiveGitHubClient(
            repository="scowalt/ignite-for-spotify-2",
            credential=credential,
            request=lambda *_: RuntimeResponse(200, {"not": "a list"}, {}),
        )
        with self.assertRaisesRegex(RuntimeClientError, "MALFORMED_GITHUB_PULLS"):
            malformed.find_linked_pull_requests(
                repository="scowalt/ignite-for-spotify-2", branch="automation/fix", marker="marker"
            )

    def test_paseo_fetch_authenticates_with_out_of_line_header(self) -> None:
        credential = GitHubCredential("github-secret")
        captures: list[tuple[tuple[str, ...], dict[str, str]]] = []

        def runner(command: tuple[str, ...], cwd: Path, environment: object) -> CommandOutput:
            del cwd
            captures.append((command, dict(environment)))  # type: ignore[arg-type]
            if command == ("git", "rev-parse", "--verify", "origin/main"):
                return CommandOutput(0, "a" * 40 + "\n", "")
            return CommandOutput(0, "", "")

        client = LivePaseoClient(
            workspace_root=Path("/tmp/workspace"),
            repository="scowalt/ignite-for-spotify-2",
            model="gpt-5.6-terra",
            thinking="xhigh",
            credential=credential,
            runner=runner,
            environment={"PATH": "/bin", "UNRELATED_SECRET": "do-not-pass"},
        )

        base = client.fresh_origin_main()

        self.assertEqual(base.commit_sha, "a" * 40)
        fetch_command, fetch_environment = captures[0]
        self.assertEqual(fetch_command, ("git", "fetch", "origin", "main"))
        self.assertNotIn(credential.value, "\0".join(fetch_command))
        self.assertEqual(fetch_environment["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(fetch_environment["GIT_CONFIG_COUNT"], "1")
        self.assertEqual(
            fetch_environment["GIT_CONFIG_KEY_0"], "http.https://github.com/.extraHeader"
        )
        expected = base64.b64encode(f"x-access-token:{credential.value}".encode()).decode()
        self.assertEqual(
            fetch_environment["GIT_CONFIG_VALUE_0"], f"Authorization: Basic {expected}"
        )
        self.assertNotIn("UNRELATED_SECRET", fetch_environment)

    def test_paseo_fetch_failure_never_records_the_credential(self) -> None:
        credential = GitHubCredential("github-secret")
        client = LivePaseoClient(
            workspace_root=Path("/tmp/workspace"),
            repository="scowalt/ignite-for-spotify-2",
            model="gpt-5.6-terra",
            thinking="xhigh",
            credential=credential,
            runner=lambda *_: CommandOutput(1, "", "authentication failed"),
            environment={"PATH": "/bin"},
        )

        with self.assertRaisesRegex(RuntimeClientError, "^PASEO_COMMAND_FAILED$") as raised:
            client.fresh_origin_main()
        self.assertNotIn(credential.value, str(raised.exception))
        self.assertNotIn(
            base64.b64encode(b"x-access-token:github-secret").decode(), str(raised.exception)
        )

    def test_paseo_remove_workspace_uses_the_git_worktree_registry(self) -> None:
        calls: list[tuple[str, ...]] = []
        removed: list[str] = []
        worktree = "/home/controller/.paseo/worktrees/hash/slug-1"

        def runner(command: tuple[str, ...], cwd: Path, environment: object) -> CommandOutput:
            del cwd, environment
            calls.append(command)
            if command == ("git", "worktree", "list", "--porcelain"):
                entries = (
                    "worktree /tmp/workspace\nHEAD aaaa\nbranch refs/heads/main\n"
                    f"worktree {worktree}\nHEAD bbbb\ndetached\n"
                )
                if worktree in removed:
                    entries = "worktree /tmp/workspace\nHEAD aaaa\nbranch refs/heads/main\n"
                return CommandOutput(0, entries, "")
            if command == ("git", "worktree", "remove", worktree):
                removed.append(worktree)
                return CommandOutput(0, "", "")
            raise AssertionError(f"unexpected command {command}")

        client = LivePaseoClient(
            workspace_root=Path("/tmp/workspace"),
            repository="scowalt/ignite-for-spotify-2",
            model="gpt-5.6-terra",
            thinking="xhigh",
            credential=GitHubCredential("github-secret"),
            runner=runner,
            environment={"PATH": "/bin"},
        )

        client.remove_workspace("slug-1")
        self.assertEqual(removed, [worktree])

        client.remove_workspace("never-existed")
        self.assertEqual(removed, [worktree])

        def stuck_runner(command: tuple[str, ...], cwd: Path, environment: object) -> CommandOutput:
            del cwd, environment
            if command == ("git", "worktree", "list", "--porcelain"):
                return CommandOutput(
                    0,
                    f"worktree /tmp/workspace\nHEAD aaaa\nworktree {worktree}\n",
                    "",
                )
            if command == ("git", "worktree", "remove", worktree):
                return CommandOutput(0, "", "")
            raise AssertionError(f"unexpected command {command}")

        stuck = LivePaseoClient(
            workspace_root=Path("/tmp/workspace"),
            repository="scowalt/ignite-for-spotify-2",
            model="gpt-5.6-terra",
            thinking="xhigh",
            credential=GitHubCredential("github-secret"),
            runner=stuck_runner,
            environment={"PATH": "/bin"},
        )
        with self.assertRaisesRegex(RuntimeClientError, "PASEO_WORKSPACE_ARCHIVE_FAILED"):
            stuck.remove_workspace("slug-1")

    def test_paseo_receives_github_token_through_its_explicit_agent_env_option(self) -> None:
        credential = GitHubCredential("github-token-that-must-not-appear")
        captures: list[tuple[tuple[str, ...], dict[str, str]]] = []

        def runner(command: tuple[str, ...], cwd: Path, environment: object) -> CommandOutput:
            del cwd
            captures.append((command, dict(environment)))  # type: ignore[arg-type]
            if command[:2] == ("paseo", "run"):
                return CommandOutput(
                    0, json.dumps({"agentId": "agent-id", "status": "running"}), ""
                )
            raise AssertionError(f"unexpected command {command}")

        client = LivePaseoClient(
            workspace_root=Path("/tmp/workspace"),
            repository="scowalt/ignite-for-spotify-2",
            model="gpt-5.6-terra",
            thinking="xhigh",
            credential=credential,
            runner=runner,
            environment={
                "PATH": "/bin",
                "PASEO_HOME": "/home/controller/.paseo",
                "PASEO_HOST": "127.0.0.1:6767",
                "UNRELATED_SECRET": "do-not-pass",
            },
        )
        prompt = "Investigate safely; never include github-token-that-must-not-appear."
        launch = WorkspaceLaunch(
            "worktree-1",
            "agent-title-1",
            "automation/fix",
            "<!-- marker -->",
            OriginMain("origin/main", "a" * 40),
            prompt.replace("github-token-that-must-not-appear", "[REDACTED]"),
        )

        result = client.launch(launch, credential)

        command, environment = captures[0]
        command_text = "\0".join(command)
        self.assertEqual(result.agent_identity, "agent-title-1")
        provider_index = command.index("--provider")
        self.assertEqual(command[provider_index + 1], "pi")
        self.assertNotIn("GITHUB_AUTOMATION_TOKEN", environment)
        self.assertNotIn("UNRELATED_SECRET", environment)
        self.assertEqual(environment["PASEO_HOME"], "/home/controller/.paseo")
        self.assertEqual(environment["PASEO_HOST"], "127.0.0.1:6767")
        env_index = command.index("--env")
        self.assertEqual(command[env_index + 1], f"GITHUB_AUTOMATION_TOKEN={credential.value}")
        self.assertIn(credential.value, command_text)
        self.assertNotIn(credential.value, launch.prompt)

        malformed = LivePaseoClient(
            workspace_root=Path("/tmp/workspace"),
            repository="scowalt/ignite-for-spotify-2",
            model="gpt-5.6-terra",
            thinking="xhigh",
            credential=credential,
            runner=lambda *_: CommandOutput(0, "not-json", ""),
        )
        with self.assertRaisesRegex(RuntimeClientError, "MALFORMED_PASEO_LAUNCH"):
            malformed.launch(launch, credential)

    def test_paseo_daemon_connection_failure_has_a_distinct_safe_code(self) -> None:
        credential = GitHubCredential("github-secret")
        client = LivePaseoClient(
            workspace_root=Path("/tmp/workspace"),
            repository="scowalt/ignite-for-spotify-2",
            model="gpt-5.6-terra",
            thinking="xhigh",
            credential=credential,
            runner=lambda *_: CommandOutput(
                1,
                "",
                '{"error":{"code":"DAEMON_NOT_RUNNING","message":"Cannot connect to daemon"}}',
            ),
        )

        with self.assertRaisesRegex(RuntimeClientError, "PASEO_DAEMON_UNAVAILABLE"):
            client.agent_result("agent-id")

    def test_remote_branch_deletion_uses_authenticated_github_rest_not_git(self) -> None:
        credential = GitHubCredential("github-delete-token")
        requests: list[tuple[str, str, dict[str, str], bytes | None]] = []

        def request(method: str, url: str, headers: object, body: bytes | None) -> RuntimeResponse:
            requests.append((method, url, dict(headers), body))  # type: ignore[arg-type]
            return RuntimeResponse(204, {}, {})

        client = LivePaseoClient(
            workspace_root=Path("/tmp/workspace"),
            repository="scowalt/ignite-for-spotify-2",
            model="gpt-5.6-terra",
            thinking="xhigh",
            credential=credential,
            request=request,
            runner=lambda *_: (_ for _ in ()).throw(AssertionError("git must not run")),
        )

        client.remove_remote_branch("automation/fix/42")

        self.assertEqual([r[0] for r in requests][:2], ["GET", "DELETE"])
        method, url, headers, body = requests[1]
        self.assertEqual(method, "DELETE")
        self.assertTrue(url.endswith("/git/refs/heads/automation%2Ffix%2F42"))
        self.assertEqual(headers["Authorization"], f"Bearer {credential.value}")
        self.assertIsNone(body)

    def test_remote_branch_already_deleted_by_github_is_clean(self) -> None:
        credential = GitHubCredential("github-delete-token")
        requests: list[str] = []

        def request(method: str, url: str, headers: object, body: bytes | None) -> RuntimeResponse:
            requests.append(method)
            if method == "GET":
                raise RuntimeClientError("HTTP_404")
            raise AssertionError("a missing remote ref must not be deleted again")

        client = LivePaseoClient(
            workspace_root=Path("/tmp/workspace"),
            repository="scowalt/ignite-for-spotify-2",
            model="gpt-5.6-terra",
            thinking="xhigh",
            credential=credential,
            request=request,
            runner=lambda *_: (_ for _ in ()).throw(AssertionError("git must not run")),
        )

        client.remove_remote_branch("automation/fix/42")

        self.assertEqual(requests, ["GET"])

    def test_remote_branch_deleted_between_lookup_and_delete_is_clean(self) -> None:
        credential = GitHubCredential("github-delete-token")
        requests: list[str] = []

        def request(method: str, url: str, headers: object, body: bytes | None) -> RuntimeResponse:
            requests.append(method)
            if method == "GET":
                return RuntimeResponse(200, {}, {})
            raise RuntimeClientError("HTTP_422")

        client = LivePaseoClient(
            workspace_root=Path("/tmp/workspace"),
            repository="scowalt/ignite-for-spotify-2",
            model="gpt-5.6-terra",
            thinking="xhigh",
            credential=credential,
            request=request,
            runner=lambda *_: (_ for _ in ()).throw(AssertionError("git must not run")),
        )

        client.remove_remote_branch("automation/fix/42")

        self.assertEqual(requests, ["GET", "DELETE"])

    def test_default_request_preserves_an_empty_successful_delete_response(self) -> None:
        class EmptyResponse:
            status = 204
            headers: dict[str, str] = {}

            def __enter__(self) -> EmptyResponse:
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def read(self, _: int) -> bytes:
                return b""

        class EmptyResponseOpener:
            def open(self, *_: object, **__: object) -> EmptyResponse:
                return EmptyResponse()

        with patch("glitchtip_paseo_controller.runtime_clients._HTTP", EmptyResponseOpener()):
            response = default_http_request("DELETE", "https://api.github.com/example", {}, None)

        self.assertEqual(response.status, 204)
        self.assertIsNone(response.body)

    def test_redirect_or_http_error_is_a_redacted_typed_failure(self) -> None:
        secret = "redirect-secret"

        class RedirectingOpener:
            def open(self, *_: object, **__: object) -> object:
                raise HTTPError(
                    f"https://example.invalid/?token={secret}", 302, "redirect", {}, None
                )

        with patch("glitchtip_paseo_controller.runtime_clients._HTTP", RedirectingOpener()):
            with self.assertRaises(RuntimeClientError) as raised:
                default_http_request(
                    "GET", "https://example.invalid", {"Authorization": f"Bearer {secret}"}, None
                )

        self.assertEqual(raised.exception.code, "HTTP_302")
        self.assertNotIn(secret, str(raised.exception))


if __name__ == "__main__":
    unittest.main()

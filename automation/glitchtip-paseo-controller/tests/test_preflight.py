from __future__ import annotations

import io
import json
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import cast
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from glitchtip_paseo_controller.cli import (
    _default_http_get,
    _github_evidence,
    _NoRedirectHandler,
    _paseo_evidence,
    build_live_adapters,
    main,
)
from glitchtip_paseo_controller.clients.github import GitHubAdapter
from glitchtip_paseo_controller.clients.glitchtip import CapturedResponse, GlitchTipAdapter
from glitchtip_paseo_controller.clients.paseo import PaseoAdapter
from glitchtip_paseo_controller.config import load_config
from glitchtip_paseo_controller.preflight import (
    Incompatibility,
    build_child_environment,
    build_read_only_report,
)

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
EXAMPLE = ROOT / "config" / "controller.example.toml"
CAPABILITIES = {"glitchtip_api_token", "github_automation_token"}


def fixture_responses() -> dict[str, CapturedResponse]:
    captured = json.loads((FIXTURES / "glitchtip-pages.json").read_text())
    return {
        url: CapturedResponse(body=value["body"], headers={"Link": value["link"]})
        for url, value in captured.items()
    }


def _first_fixture_issue(response: CapturedResponse) -> dict[str, object]:
    body = cast(list[object], response.body)
    if not body:
        raise AssertionError("fixture must contain an issue")
    issue = body[0]
    if not isinstance(issue, dict):
        raise AssertionError("fixture issue must be an object")
    return cast(dict[str, object], issue)


class ReadOnlyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(
            EXAMPLE, available_capabilities=CAPABILITIES, environ={"XDG_STATE_HOME": "/tmp/state"}
        )
        self.responses = fixture_responses()
        self.glitchtip = GlitchTipAdapter(lambda url: self.responses[url])
        self.github_evidence = json.loads((FIXTURES / "github-evidence.json").read_text())
        self.github = GitHubAdapter(self.github_evidence)
        self.paseo = PaseoAdapter(json.loads((FIXTURES / "paseo-capabilities.json").read_text()))

    def test_valid_captured_contracts_produce_a_complete_typed_human_report(self) -> None:
        report = build_read_only_report(self.config, self.glitchtip, self.github, self.paseo)

        self.assertTrue(report.compatible)
        self.assertFalse(report.dispatch_enabled)
        self.assertEqual(report.schema_version, 1)
        self.assertEqual(report.config_fingerprint, self.config.fingerprint)
        self.assertEqual(
            report.glitchtip.issue_ids_by_project, {1: ("100", "101", "102"), 2: ("201",)}
        )
        self.assertEqual(report.paseo.agent.labels, {"role": "remediation", "issue": "101"})
        self.assertTrue(report.paseo.agent.archived)
        self.assertEqual(report.paseo.agent.result_status, "complete")
        self.assertEqual(report.paseo.agent.result_head_sha, "aaaaaaaa")
        self.assertIn("Read-only compatibility report", report.render())
        self.assertIn("Pi: 0.50.0; configured model: available", report.render())
        self.assertIn("Dispatch: disabled", report.render())
        self.assertNotIn("check runs", report.render())

    def test_glitchtip_follows_pages_and_stops_at_terminal_next_link(self) -> None:
        result = self.glitchtip.list_unresolved(
            base_url="https://glitchtip.scowalt.com", organization="scowalt", project_id=1
        )

        self.assertTrue(result.complete)
        self.assertEqual(tuple(issue.id for issue in result.issues), ("100", "101", "102"))
        duplicate = next(issue for issue in result.issues if issue.id == "100")
        self.assertEqual(duplicate.last_seen, "2026-07-22T11:00:00Z")
        self.assertEqual(duplicate.title, "Duplicate error")
        self.assertEqual(duplicate.first_seen, "2026-07-20T09:00:00Z")
        self.assertEqual(
            result.page_urls,
            (
                "https://glitchtip.scowalt.com/api/0/organizations/scowalt/issues/?query=is%3Aunresolved&project=1",
                "https://glitchtip.scowalt.com/api/0/organizations/scowalt/issues/?cursor=next-1",
            ),
        )

        bad_body = [
            dict(
                _first_fixture_issue(self.responses[result.page_urls[0]]),
                project={"id": "2", "slug": "wrong"},
            )
        ]
        mismatch = GlitchTipAdapter(lambda _: CapturedResponse(bad_body, {"Link": ""}))
        with self.assertRaisesRegex(Incompatibility, "GLITCHTIP_PROJECT_MISMATCH"):
            mismatch.list_unresolved("https://glitchtip.scowalt.com", "scowalt", 1)

    def test_glitchtip_ignores_unrelated_fields_and_rejects_unsafe_pagination(self) -> None:
        url = "https://glitchtip.scowalt.com/api/0/organizations/scowalt/issues/?query=is%3Aunresolved&project=1"
        body = self.responses[url].body
        for header in (
            "not-a-link",
            '<https://evil.example/api/0/issues/?cursor=next>; rel="next"',
            f'<{url}&cursor=one>; rel="next", <{url}&cursor=two>; rel="next"',
        ):
            adapter = GlitchTipAdapter(lambda _: CapturedResponse(body, {"Link": header}))
            with (
                self.subTest(header=header),
                self.assertRaisesRegex(Incompatibility, "MALFORMED_PAGINATION_LINK"),
            ):
                adapter.list_unresolved("https://glitchtip.scowalt.com", "scowalt", 1)

        cyclic = GlitchTipAdapter(
            lambda _: CapturedResponse(body, {"Link": f'<{url}>; rel="next"'})
        )
        with self.assertRaisesRegex(Incompatibility, "PAGINATION_CYCLE"):
            cyclic.list_unresolved("https://glitchtip.scowalt.com", "scowalt", 1)

        extra_fields = [dict(_first_fixture_issue(self.responses[url]), unexpected="field")]
        listing = GlitchTipAdapter(
            lambda _: CapturedResponse(extra_fields, {"Link": ""})
        ).list_unresolved("https://glitchtip.scowalt.com", "scowalt", 1)
        self.assertEqual(tuple(issue.id for issue in listing.issues), ("101",))
        self.assertNotIn("fixture-metadata-secret", repr(listing.issues[0]))

    def test_glitchtip_rejects_missing_or_malformed_required_fields(self) -> None:
        url = "https://glitchtip.scowalt.com/api/0/organizations/scowalt/issues/?query=is%3Aunresolved&project=1"
        valid_issue = _first_fixture_issue(self.responses[url])

        missing = dict(valid_issue)
        del missing["id"]
        adapter = GlitchTipAdapter(lambda _: CapturedResponse([missing], {"Link": ""}))
        with self.assertRaisesRegex(Incompatibility, "MISSING_GLITCHTIP_FIELD"):
            adapter.list_unresolved("https://glitchtip.scowalt.com", "scowalt", 1)

        for field in ("id", "status", "title", "count", "firstSeen", "lastSeen"):
            malformed = [dict(valid_issue, **{field: None})]
            adapter = GlitchTipAdapter(lambda _: CapturedResponse(malformed, {"Link": ""}))
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(Incompatibility, "MALFORMED_GLITCHTIP_RESPONSE"),
            ):
                adapter.list_unresolved("https://glitchtip.scowalt.com", "scowalt", 1)

        malformed_project = [dict(valid_issue, project={"id": 1, "slug": "frontend"})]
        adapter = GlitchTipAdapter(lambda _: CapturedResponse(malformed_project, {"Link": ""}))
        with self.assertRaisesRegex(Incompatibility, "MALFORMED_GLITCHTIP_RESPONSE"):
            adapter.list_unresolved("https://glitchtip.scowalt.com", "scowalt", 1)

        missing_project_slug = [dict(valid_issue, project={"id": "1"})]
        adapter = GlitchTipAdapter(lambda _: CapturedResponse(missing_project_slug, {"Link": ""}))
        with self.assertRaisesRegex(Incompatibility, "MALFORMED_GLITCHTIP_PROJECT"):
            adapter.list_unresolved("https://glitchtip.scowalt.com", "scowalt", 1)

    def test_github_preserves_branch_policy_and_ruleset_evidence(self) -> None:
        evidence = self.github.collect_policy()

        self.assertTrue(evidence.classic_protection.conversation_resolution_required)
        self.assertIsNone(evidence.classic_protection.required_approvals)
        self.assertTrue(evidence.classic_protection.controls["block_creations"]["enabled"])
        self.assertEqual(
            evidence.classic_protection.status_check_metadata["contexts_url"],
            "https://api.github.test/contexts",
        )
        self.assertEqual(evidence.classic_protection.required_contexts, ("backend", "frontend"))
        self.assertEqual(
            {check.app_id for check in evidence.classic_protection.required_checks}, {11, 22}
        )
        self.assertEqual(evidence.rulesets[0].target, "branch")
        self.assertEqual(evidence.rulesets[0].ref_includes, ("~DEFAULT_BRANCH",))
        self.assertEqual(evidence.rulesets[0].ref_excludes, ("refs/heads/release/*",))
        self.assertEqual(evidence.rulesets[0].metadata["node_id"], "RRS_7")

    def test_github_rejects_malformed_and_unknown_policy_roots(self) -> None:
        with self.assertRaisesRegex(Incompatibility, "MALFORMED_GITHUB_ROOT"):
            GitHubAdapter(["not-an-object"]).collect_policy()  # type: ignore[arg-type]
        with self.assertRaisesRegex(Incompatibility, "UNKNOWN_GITHUB_ROOT_FIELD"):
            GitHubAdapter(dict(self.github_evidence, unexpected=True)).collect_policy()

    def test_paseo_rejects_malformed_or_unknown_roots_and_unsupported_versions(self) -> None:
        with self.assertRaisesRegex(Incompatibility, "MALFORMED_PASEO_ROOT"):
            PaseoAdapter(["not-an-object"]).capabilities("0.3.1")  # type: ignore[arg-type]
        with self.assertRaisesRegex(Incompatibility, "UNKNOWN_PASEO_ROOT_FIELD"):
            PaseoAdapter({"version": "0.3.1", "commands": [], "unexpected": True}).capabilities(
                "0.3.1"
            )
        with self.assertRaisesRegex(Incompatibility, "UNSUPPORTED_PASEO_VERSION"):
            PaseoAdapter(
                {
                    "version": "0.1.111",
                    "commands": ["ls", "inspect", "archive", "run", "worktree"],
                    "pi_version": "0.50.0",
                    "pi_model_available": True,
                }
            ).capabilities("0.3.1")

    def test_live_report_uses_only_injected_gets_and_safe_cli_inspection(self) -> None:
        requests: list[tuple[str, dict[str, str]]] = []
        github_api = "https://api.github.com/repos/scowalt/ignite-for-spotify-app"

        def get(url: str, headers: dict[str, str]) -> CapturedResponse:
            requests.append((url, headers))
            if url in self.responses:
                return self.responses[url]
            responses = {
                f"{github_api}/branches/main/protection": self.github_evidence["protection"],
                f"{github_api}/rulesets?per_page=100": [{"id": 7}],
                f"{github_api}/rulesets/7": self.github_evidence["rulesets"][0],
            }
            return CapturedResponse(responses[url], {})

        outputs = {
            ("paseo", "--version"): "0.3.1\n",
            ("paseo", "--help"): "Commands:\n  ls\n  inspect\n  archive\n  run\n  worktree\n",
            ("pi", "--version"): "0.50.0\n",
            ("pi", "--help"): "Usage: pi [options]\n",
            ("pi", "--list-models", "gpt-5.6-terra"): "openai-codex/gpt-5.6-terra\n",
        }
        adapters = build_live_adapters(
            self.config,
            capability_environment={
                "glitchtip_api_token": "GLITCHTIP_API_TOKEN",
                "github_automation_token": "GITHUB_AUTOMATION_TOKEN",
            },
            environ={
                "GLITCHTIP_API_TOKEN": "glitchtip-sentinel",
                "GITHUB_AUTOMATION_TOKEN": "github-sentinel",
            },
            http_get=get,
            runner=lambda command: outputs[command],
        )
        report = build_read_only_report(self.config, *adapters)

        self.assertTrue(report.compatible)
        self.assertEqual(len(requests), 6)
        self.assertTrue(
            all(headers["Authorization"].startswith("Bearer ") for _, headers in requests)
        )
        self.assertFalse(any("/check-runs" in url for url, _ in requests))
        self.assertNotIn("glitchtip-sentinel", report.render())
        self.assertNotIn("github-sentinel", report.render())
        self.assertEqual(report.paseo.pi_version, "0.50.0")
        self.assertTrue(report.paseo.pi_model_available)

    def test_paseo_evidence_probes_commands_hidden_from_top_level_help(self) -> None:
        runner_data = {
            ("paseo", "--version"): "0.3.1\n",
            ("paseo", "--help"): "Commands:\n  ls\n  inspect\n  archive\n  run\n",
            ("paseo", "worktree", "--help"): "Usage: paseo worktree [options] [command]\n",
            ("pi", "--version"): "0.50.0\n",
            ("pi", "--help"): "Usage: pi [options]\n",
            ("pi", "--list-models", "gpt-5.6-terra"): "openai-codex/gpt-5.6-terra\n",
        }

        evidence = _paseo_evidence("gpt-5.6-terra", lambda *_: None, lambda cmd: runner_data[cmd])  # type: ignore[arg-type]

        self.assertIn("worktree", evidence["commands"])

    def test_paseo_evidence_omits_missing_hidden_commands(self) -> None:
        def runner(cmd: tuple[str, ...]) -> str:
            data = {
                ("paseo", "--version"): "0.3.1\n",
                ("paseo", "--help"): "Commands:\n  ls\n  inspect\n  archive\n  run\n",
                ("pi", "--version"): "0.50.0\n",
                ("pi", "--help"): "Usage: pi [options]\n",
                ("pi", "--list-models", "gpt-5.6-terra"): "openai-codex/gpt-5.6-terra\n",
            }
            if cmd in data:
                return data[cmd]
            raise Incompatibility("READ_ONLY_CLI_FAILURE", " ".join(cmd))

        evidence = _paseo_evidence("gpt-5.6-terra", lambda *_: None, runner)  # type: ignore[arg-type]

        self.assertNotIn("worktree", evidence["commands"])

    def test_github_live_pagination_collects_ruleset_pages_and_rejects_unsafe_links(self) -> None:
        api = "https://api.github.com/repos/scowalt/ignite-for-spotify-2"
        headers = {"Authorization": "Bearer sentinel"}
        pages = {
            f"{api}/branches/main/protection": CapturedResponse(
                self.github_evidence["protection"], {}
            ),
            f"{api}/rulesets?per_page=100": CapturedResponse(
                [{"id": 7}], {"Link": f'<{api}/rulesets?per_page=100&page=2>; rel="next"'}
            ),
            f"{api}/rulesets?per_page=100&page=2": CapturedResponse([{"id": 8}], {}),
            f"{api}/rulesets/7": CapturedResponse(self.github_evidence["rulesets"][0], {}),
            f"{api}/rulesets/8": CapturedResponse(
                dict(self.github_evidence["rulesets"][0], id=8, name="second rule"), {}
            ),
        }
        evidence = _github_evidence(
            "scowalt/ignite-for-spotify-2", lambda url, _: pages[url], headers
        )
        self.assertEqual([rule["id"] for rule in evidence["rulesets"]], [7, 8])
        self.assertNotIn("check_runs", evidence)

        bad_pages = dict(pages)
        bad_pages[f"{api}/rulesets?per_page=100"] = CapturedResponse(
            [{"id": 7}], {"Link": '<https://evil.example/rulesets?page=2>; rel="next"'}
        )
        with self.assertRaisesRegex(Incompatibility, "MALFORMED_GITHUB_PAGINATION"):
            _github_evidence("scowalt/ignite-for-spotify-2", lambda url, _: bad_pages[url], headers)
        bad_pages[f"{api}/rulesets?per_page=100"] = CapturedResponse(
            [{"id": 7}], {"Link": "not-a-link"}
        )
        with self.assertRaisesRegex(Incompatibility, "MALFORMED_GITHUB_PAGINATION"):
            _github_evidence("scowalt/ignite-for-spotify-2", lambda url, _: bad_pages[url], headers)

    def test_github_live_pagination_rejects_ruleset_cycles(self) -> None:
        api = "https://api.github.com/repos/scowalt/ignite-for-spotify-2"
        headers = {"Authorization": "Bearer sentinel"}
        pages = {
            f"{api}/branches/main/protection": CapturedResponse(
                self.github_evidence["protection"], {}
            ),
            f"{api}/rulesets?per_page=100": CapturedResponse(
                [], {"Link": f'<{api}/rulesets?per_page=100>; rel="next"'}
            ),
        }
        with self.assertRaisesRegex(Incompatibility, "GITHUB_PAGINATION_CYCLE"):
            _github_evidence("scowalt/ignite-for-spotify-2", lambda url, _: pages[url], headers)

    def test_redirect_handler_never_constructs_a_follow_up_request(self) -> None:
        self.assertIsNone(
            _NoRedirectHandler().redirect_request(
                None, None, 302, "redirect", {}, "https://evil.example"
            )
        )

    def test_default_http_get_includes_stable_user_agent_and_preserves_authorization(self) -> None:
        requests: list[Request] = []

        class CapturingOpener:
            def open(self, request: Request, **_: object) -> object:
                requests.append(request)
                raise OSError("offline")

        with patch("glitchtip_paseo_controller.cli._NO_REDIRECT_OPENER", CapturingOpener()):
            with self.assertRaisesRegex(Incompatibility, "READ_ONLY_HTTP_FAILURE"):
                _default_http_get(
                    "https://glitchtip.scowalt.com", {"Authorization": "Bearer sentinel"}
                )

        request = requests[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer sentinel")
        self.assertEqual(request.get_header("User-agent"), "ignite-glitchtip-paseo-controller/0.1")

    def test_default_http_get_turns_a_redirect_into_a_typed_failure(self) -> None:
        class RedirectingOpener:
            def open(self, *_: object, **__: object) -> object:
                raise HTTPError("https://api.github.com", 302, "redirect", {}, None)

        with patch("glitchtip_paseo_controller.cli._NO_REDIRECT_OPENER", RedirectingOpener()):
            with self.assertRaisesRegex(Incompatibility, "READ_ONLY_HTTP_FAILURE"):
                _default_http_get("https://api.github.com", {"Authorization": "Bearer sentinel"})

    def test_cli_live_mode_requires_mapped_environment_capabilities(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "report",
                    "--config",
                    str(EXAMPLE),
                    "--live",
                    "--capability-env",
                    "glitchtip_api_token=GLITCHTIP_API_TOKEN",
                ],
                environ={},
            )
        self.assertEqual(exit_code, 2)
        self.assertIn("MISSING_CAPABILITY_MAPPING", output.getvalue())

    def test_child_environment_is_unique_fresh_and_restrictive_for_every_role(self) -> None:
        sentinel = "SENTINEL_DO_NOT_LEAK"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "children"
            parent = {
                "PATH": os.environ.get("PATH", ""),
                "HOME": str(Path(temp_dir) / "home"),
                "DOPPLER_TOKEN": sentinel,
                "GLITCHTIP_API_TOKEN": sentinel,
                "GH_TOKEN": sentinel,
                "SSH_AUTH_SOCK": str(Path(temp_dir) / "agent.sock"),
                "GIT_ASKPASS": sentinel,
            }
            children = [
                build_child_environment(
                    role=role,
                    root=root,
                    parent_environ=parent,
                    controller_secret_names={"DOPPLER_TOKEN", "GLITCHTIP_API_TOKEN", "GH_TOKEN"},
                    credential_bearing_remote=f"https://user:{sentinel}@github.com/example/repo.git",
                )
                for role in ("remediation", "remediation", "review", "review")
            ]
            first = children[0]
            for directory in (first.home, first.xdg_config, first.xdg_cache, first.xdg_state):
                (directory / "prior-child-secret").write_text(sentinel)
            replacement = build_child_environment(
                role="remediation",
                root=root,
                parent_environ=parent,
                controller_secret_names={"DOPPLER_TOKEN", "GLITCHTIP_API_TOKEN", "GH_TOKEN"},
            )
            children.append(replacement)

            roots = {
                (child.home, child.xdg_config, child.xdg_cache, child.xdg_state)
                for child in children
            }
            self.assertEqual(len(roots), len(children))
            for child in children:
                self.assertNotIn(sentinel, "\n".join(child.environment.values()))
                self.assertNotIn("SSH_AUTH_SOCK", child.environment)
                self.assertNotIn("GH_TOKEN", child.environment)
                self.assertIsNone(child.remote)
                for directory in (child.home, child.xdg_config, child.xdg_cache, child.xdg_state):
                    if child is not first:
                        self.assertFalse(any(path.is_file() for path in directory.rglob("*")))
                    self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from email.message import Message
from pathlib import Path
from typing import cast
from urllib.error import HTTPError
from urllib.parse import ParseResult, parse_qs, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .clients import Incompatibility
from .clients.github import GitHubAdapter, GitHubCredential
from .clients.glitchtip import CapturedResponse, GlitchTipAdapter
from .clients.paseo import PaseoAdapter
from .config import ConfigurationError, ControllerConfig, load_config
from .legacy_cleanup import (
    GitHubLegacyCleanupClient,
    LegacyCleanupClient,
    LegacyGitHubRequest,
    apply_cleanup,
    confirmation_token,
    default_github_request,
    inventory,
)
from .preflight import build_read_only_report
from .runtime import DispatchRuntime
from .runtime_clients import (
    LiveGitHubClient,
    LiveGlitchTipClient,
    LivePaseoClient,
    RuntimeClientError,
)
from .state import StateError, StateStore
from .status import render_jobs, render_status

HttpGet = Callable[[str, dict[str, str]], CapturedResponse]
Runner = Callable[[tuple[str, ...]], str]
DispatchFactory = Callable[
    [ControllerConfig, Mapping[str, str], Mapping[str, str]], DispatchRuntime
]


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    runner: Runner | None = None,
    legacy_client: LegacyCleanupClient | None = None,
    legacy_request: LegacyGitHubRequest | None = None,
    dispatch_factory: DispatchFactory | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="glitchtip-paseo-controller")
    subcommands = parser.add_subparsers(dest="command", required=True)
    report = subcommands.add_parser("report", help="render a non-mutating compatibility report")
    report.add_argument("--config", type=Path, required=True)
    source = report.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--fixtures", type=Path, help="captured read-only contract fixture directory"
    )
    source.add_argument(
        "--live", action="store_true", help="use controller-only GET and version/help probes"
    )
    report.add_argument(
        "--capability", action="append", default=[], help="available fixture capability name"
    )
    report.add_argument(
        "--capability-env",
        action="append",
        default=[],
        metavar="CAPABILITY=ENV_VAR",
        help="map a named live capability to its environment variable without printing its value",
    )
    status = subcommands.add_parser("status", help="summarize local durable jobs")
    status.add_argument("--database", type=Path, required=True)
    list_jobs = subcommands.add_parser("list", help="list local durable jobs")
    list_jobs.add_argument("--database", type=Path, required=True)
    retry = subcommands.add_parser("retry", help="queue one explicit retry of a failed job")
    retry.add_argument("--database", type=Path, required=True)
    retry.add_argument("job_id", type=int)
    dispatch = subcommands.add_parser(
        "dispatch", help="run one explicitly enabled local dispatch tick"
    )
    dispatch.add_argument("--config", type=Path, required=True)
    dispatch.add_argument("--once", action="store_true", help="run exactly one tick")
    dispatch.add_argument(
        "--enable-dispatch", action="store_true", help="acknowledge this mutating tick"
    )
    dispatch.add_argument(
        "--capability-env",
        action="append",
        default=[],
        metavar="CAPABILITY=ENV_VAR",
        help="map each dispatch capability to an environment variable without printing its value",
    )
    legacy_cleanup = subcommands.add_parser(
        "legacy-cleanup", help="inventory or explicitly apply exact legacy cleanup"
    )
    legacy_cleanup.add_argument("--config", type=Path, required=True)
    legacy_cleanup.add_argument("--apply", action="store_true", help="perform configured cleanup")
    legacy_cleanup.add_argument(
        "--legacy-service-stopped",
        action="store_true",
        help="acknowledge that the legacy service was manually stopped and verified",
    )
    legacy_cleanup.add_argument(
        "--confirm", metavar="TOKEN", help="exact confirmation token printed by the dry run"
    )
    legacy_cleanup.add_argument(
        "--capability-env",
        action="append",
        default=[],
        metavar="CAPABILITY=ENV_VAR",
        help="map only the GitHub cleanup capability to an environment variable",
    )
    args = parser.parse_args(argv)
    environment = os.environ if environ is None else environ

    try:
        if args.command in {"status", "list", "retry"}:
            store = StateStore(args.database)
            try:
                if args.command == "status":
                    print(render_status(store.jobs()), end="")
                elif args.command == "list":
                    print(render_jobs(store.jobs()), end="")
                else:
                    job = store.retry_job(args.job_id)
                    print(f"queued job={job.id} retry_of={job.retry_of}")
            finally:
                store.close()
            return 0
        if args.command == "dispatch":
            if not args.once:
                raise ConfigurationError("ONCE_REQUIRED", "dispatch requires --once")
            if not args.enable_dispatch:
                raise ConfigurationError(
                    "EXPLICIT_DISPATCH_ENABLE_REQUIRED", "dispatch requires --enable-dispatch"
                )
            mappings = _capability_mappings(args.capability_env)
            config = load_config(
                args.config, available_capabilities=set(mappings), environ=environment
            )
            if not config.dispatch_enabled:
                raise ConfigurationError(
                    "DISPATCH_DISABLED_BY_POLICY", "controller.dispatch_enabled must be true"
                )
            secrets = _resolve_capabilities(config, mappings, environment)
            runtime = (
                dispatch_factory(config, secrets, environment)
                if dispatch_factory is not None
                else _live_dispatch_runtime(config, secrets, environment)
            )
            try:
                print(runtime.tick().render())
            finally:
                runtime.close()
            return 0
        if args.command == "legacy-cleanup":
            config = load_config(
                args.config,
                available_capabilities={"glitchtip_api_token", "github_automation_token"},
                environ=environment,
            )
            client = legacy_client or _legacy_cleanup_client(
                config,
                args.capability_env,
                environment,
                default_github_request if legacy_request is None else legacy_request,
            )
            if not args.apply:
                if args.confirm is not None or args.legacy_service_stopped:
                    raise ConfigurationError(
                        "UNEXPECTED_CLEANUP_ACKNOWLEDGEMENT",
                        "--confirm and --legacy-service-stopped require --apply",
                    )
                report = inventory(config.legacy_cleanup, client)
                print(report.render(mode="dry-run"))
                if config.legacy_cleanup.enabled:
                    print(f"confirmation={confirmation_token(config.legacy_cleanup)}")
                return 0
            if args.confirm is None:
                raise ConfigurationError(
                    "CONFIRMATION_REQUIRED", "--apply requires --confirm TOKEN"
                )
            result = apply_cleanup(
                config.legacy_cleanup,
                client,
                confirmation=args.confirm,
                legacy_service_stopped=args.legacy_service_stopped,
            )
            print(result.render())
            return 0 if result.complete else 2
        mappings = _capability_mappings(args.capability_env)
        available = (
            set(mappings).union({"glitchtip_api_token", "github_automation_token"})
            if args.live
            else set(args.capability)
        )
        config = load_config(args.config, available_capabilities=available, environ=environment)
        if args.live:
            adapters = build_live_adapters(
                config,
                capability_environment=mappings,
                environ=environment,
                http_get=_default_http_get if http_get is None else http_get,
                runner=_default_runner if runner is None else runner,
            )
        else:
            adapters = _fixture_adapters(args.fixtures)
        print(build_read_only_report(config, *adapters).render())
    except (
        ConfigurationError,
        Incompatibility,
        RuntimeClientError,
        StateError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"Incompatible: {error}")
        return 2
    return 0


def _live_dispatch_runtime(
    config: ControllerConfig, secrets: Mapping[str, str], environment: Mapping[str, str]
) -> DispatchRuntime:
    credential = GitHubCredential(secrets[config.github.credential_capability])
    workspace_root = config.workspace_root
    if workspace_root is None:
        raise ConfigurationError(
            "DISPATCH_WORKSPACE_ROOT_REQUIRED",
            "enabled dispatch requires controller.workspace_root",
        )
    store = StateStore(config.state_directory / "state.db")
    try:
        return DispatchRuntime(
            config,
            store,
            glitchtip=LiveGlitchTipClient(
                base_url=config.glitchtip.base_url,
                organization=config.glitchtip.organization,
                token=secrets[config.glitchtip.credential_capability],
            ),
            github=LiveGitHubClient(repository=config.github.repository, credential=credential),
            paseo=LivePaseoClient(
                workspace_root=workspace_root,
                repository=config.github.repository,
                model=config.pi.model,
                thinking=config.pi.thinking,
                credential=credential,
                environment=environment,
            ),
            github_credential=credential,
        )
    except Exception:
        store.close()
        raise


def build_live_adapters(
    config: ControllerConfig,
    *,
    capability_environment: Mapping[str, str],
    environ: Mapping[str, str],
    http_get: HttpGet,
    runner: Runner,
) -> tuple[GlitchTipAdapter, GitHubAdapter, PaseoAdapter]:
    secrets = _resolve_capabilities(config, capability_environment, environ)
    glitchtip_headers = {
        "Authorization": f"Bearer {secrets[config.glitchtip.credential_capability]}"
    }
    github_headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {secrets[config.github.credential_capability]}",
    }
    glitchtip = GlitchTipAdapter(lambda url: http_get(url, glitchtip_headers))
    github = GitHubAdapter(_github_evidence(config.github.repository, http_get, github_headers))
    paseo = PaseoAdapter(_paseo_evidence(config.pi.model, http_get, runner))
    return glitchtip, github, paseo


def _legacy_cleanup_client(
    config: ControllerConfig,
    mappings: Sequence[str],
    environ: Mapping[str, str],
    request: LegacyGitHubRequest,
) -> LegacyCleanupClient:
    names = _capability_mappings(mappings)
    capability = config.github.credential_capability
    if set(names) != {capability}:
        raise ConfigurationError(
            "INVALID_LEGACY_CLEANUP_CAPABILITY_MAPPING",
            "cleanup requires exactly its configured GitHub capability mapping",
        )
    environment_name = names[capability]
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", environment_name):
        raise ConfigurationError("INVALID_CAPABILITY_ENV", capability)
    value = environ.get(environment_name)
    if not value:
        raise ConfigurationError("MISSING_CAPABILITY_ENV", f"{capability} ({environment_name})")
    return GitHubLegacyCleanupClient(
        marker=config.legacy_cleanup.marker,
        credential=GitHubCredential(value),
        request=request,
    )


def _capability_mappings(values: Sequence[str]) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for value in values:
        capability, separator, env_name = value.partition("=")
        if not separator or not capability or not env_name or capability in mappings:
            raise Incompatibility("MALFORMED_CAPABILITY_MAPPING", value)
        mappings[capability] = env_name
    return mappings


def _resolve_capabilities(
    config: ControllerConfig,
    mappings: Mapping[str, str],
    environ: Mapping[str, str],
) -> dict[str, str]:
    missing = sorted(set(config.required_capabilities).difference(mappings))
    if missing:
        raise Incompatibility("MISSING_CAPABILITY_MAPPING", ", ".join(missing))
    unknown = sorted(set(mappings).difference(config.required_capabilities))
    if unknown:
        raise Incompatibility("UNKNOWN_CAPABILITY_MAPPING", ", ".join(unknown))
    values: dict[str, str] = {}
    for capability in config.required_capabilities:
        env_name = mappings[capability]
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", env_name):
            raise Incompatibility("INVALID_CAPABILITY_ENV", capability)
        value = environ.get(env_name)
        if not value:
            raise Incompatibility("MISSING_CAPABILITY_ENV", f"{capability} ({env_name})")
        values[capability] = value
    return values


def _github_evidence(
    repository: str, http_get: HttpGet, headers: dict[str, str]
) -> dict[str, object]:
    api = f"https://api.github.com/repos/{repository}"
    protection = _object_body(
        http_get(f"{api}/branches/main/protection", headers), "GitHub protection"
    )
    rule_pages = _github_pages(
        f"{api}/rulesets?per_page=100", headers, http_get, {"per_page": "100"}, "rulesets"
    )
    rule_ids: list[int] = []
    for summary in rule_pages:
        if not isinstance(summary, dict):
            raise Incompatibility("MALFORMED_GITHUB_RULESETS", "ruleset list requires integer IDs")
        identifier = cast(dict[str, object], summary).get("id")
        if not isinstance(identifier, int):
            raise Incompatibility("MALFORMED_GITHUB_RULESETS", "ruleset list requires integer IDs")
        if identifier not in rule_ids:
            rule_ids.append(identifier)
    rulesets = [
        _object_body(http_get(f"{api}/rulesets/{identifier}", headers), "GitHub ruleset")
        for identifier in rule_ids
    ]
    return {"protection": protection, "rulesets": rulesets}


def _github_pages(
    initial_url: str,
    headers: dict[str, str],
    http_get: HttpGet,
    required_query: dict[str, str],
    name: str,
) -> list[object]:
    pages: list[object] = []
    url: str | None = initial_url
    seen: set[str] = set()
    while url is not None:
        if url in seen:
            raise Incompatibility("GITHUB_PAGINATION_CYCLE", name)
        seen.add(url)
        response = http_get(url, headers)
        pages.extend(_array_body(response, f"GitHub {name}"))
        url = _github_next_link(response.headers.get("Link", ""), initial_url, required_query)
    return pages


def _github_next_link(header: str, initial_url: str, required_query: dict[str, str]) -> str | None:
    if not header:
        return None
    matches: list[tuple[str, str]] = re.findall(r'<([^>]+)>\s*;\s*rel="([^"]+)"', header)
    if not matches:
        raise Incompatibility("MALFORMED_GITHUB_PAGINATION", "invalid Link header")
    next_urls = [url for url, relation in matches if relation == "next"]
    if len(next_urls) > 1:
        raise Incompatibility("MALFORMED_GITHUB_PAGINATION", "multiple next links")
    if not next_urls:
        return None
    initial: ParseResult = urlparse(initial_url)
    candidate: ParseResult = urlparse(next_urls[0])
    if (
        candidate.scheme != "https"
        or candidate.netloc != "api.github.com"
        or candidate.path != initial.path
        or candidate.username is not None
        or candidate.password is not None
    ):
        raise Incompatibility(
            "MALFORMED_GITHUB_PAGINATION", "next link leaves expected GitHub API path"
        )
    query: dict[str, list[str]] = parse_qs(candidate.query, keep_blank_values=True)
    if any(query.get(key) != [value] for key, value in required_query.items()):
        raise Incompatibility("MALFORMED_GITHUB_PAGINATION", "next link changes required query")
    return next_urls[0]


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


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler())
_READ_ONLY_USER_AGENT = "ignite-glitchtip-paseo-controller/0.1"


def _paseo_evidence(model: str, http_get: HttpGet, runner: Runner) -> dict[str, object]:
    del http_get
    paseo_version = runner(("paseo", "--version")).strip()
    paseo_help = runner(("paseo", "--help"))
    pi_version = runner(("pi", "--version")).strip()
    pi_help = runner(("pi", "--help"))
    models = runner(("pi", "--list-models", model))
    if "Usage:" not in pi_help:
        raise Incompatibility("UNSUPPORTED_PI_HELP", "pi help output has no usage header")
    commands: list[str] = []
    for command in ("ls", "inspect", "archive", "run", "worktree"):
        if re.search(rf"^\s+{re.escape(command)}(?:\s|\[)", paseo_help, re.MULTILINE):
            commands.append(command)
            continue
        try:
            command_help = runner(("paseo", command, "--help"))
        except Incompatibility:
            continue
        if "Usage:" in command_help:
            commands.append(command)
    return {
        "version": paseo_version,
        "commands": commands,
        "pi_version": pi_version,
        "pi_model_available": model in models,
    }


def _default_http_get(url: str, headers: dict[str, str]) -> CapturedResponse:
    request = Request(url, headers={**headers, "User-Agent": _READ_ONLY_USER_AGENT}, method="GET")
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=15) as response:
            body = json.loads(response.read().decode())
            return CapturedResponse(body, {"Link": response.headers.get("Link", "")})
    except (HTTPError, OSError, json.JSONDecodeError) as error:
        raise Incompatibility("READ_ONLY_HTTP_FAILURE", url) from error


def _default_runner(command: tuple[str, ...]) -> str:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise Incompatibility("READ_ONLY_CLI_FAILURE", " ".join(command))
    return result.stdout


def _fixture_adapters(
    directory: Path | None,
) -> tuple[GlitchTipAdapter, GitHubAdapter, PaseoAdapter]:
    if directory is None:
        raise Incompatibility(
            "MISSING_FIXTURE_DIRECTORY", "--fixtures is required outside live mode"
        )
    pages = json.loads((directory / "glitchtip-pages.json").read_text())
    if not isinstance(pages, dict):
        raise Incompatibility("MALFORMED_FIXTURES", "glitchtip-pages.json must be an object")
    responses: dict[str, CapturedResponse] = {}
    typed_pages = cast(dict[object, object], pages)
    for url, value in typed_pages.items():
        if not isinstance(url, str) or not isinstance(value, dict):
            raise Incompatibility("MALFORMED_FIXTURES", "GlitchTip fixture entries must be objects")
        typed_value = cast(dict[str, object], value)
        link = typed_value.get("link")
        if not isinstance(link, str):
            raise Incompatibility("MALFORMED_FIXTURES", "GlitchTip link must be a string")
        responses[url] = CapturedResponse(typed_value.get("body"), {"Link": link})
    return (
        GlitchTipAdapter(lambda url: responses[url]),
        GitHubAdapter(json.loads((directory / "github-evidence.json").read_text())),
        PaseoAdapter(json.loads((directory / "paseo-capabilities.json").read_text())),
    )


def _object_body(response: CapturedResponse, name: str) -> dict[str, object]:
    body = response.body
    if not isinstance(body, dict):
        raise Incompatibility("MALFORMED_LIVE_RESPONSE", f"{name} must be an object")
    return cast(dict[str, object], body)


def _array_body(response: CapturedResponse, name: str) -> list[object]:
    body = response.body
    if not isinstance(body, list):
        raise Incompatibility("MALFORMED_LIVE_RESPONSE", f"{name} must be an array")
    return cast(list[object], body)


if __name__ == "__main__":
    raise SystemExit(main())

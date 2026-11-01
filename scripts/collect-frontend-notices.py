import argparse
import base64
import importlib.util
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "image_notices", Path(__file__).with_name("collect-image-notices.py")
)
NOTICES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NOTICES)


def registry_json(url):
    parsed = urllib.parse.urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "registry.npmjs.org"
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Unexpected package metadata source")
    with urllib.request.urlopen(url, timeout=30) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError("Package metadata response exceeds limit")
    return json.loads(raw)


def source_reference(name, version, metadata):
    if name == "@microsoft/signalr" and version == "8.0.29":
        return "dotnet/aspnetcore", "03ef277b368eb3b02122ca62f97d155845cfd5fa"
    repository = metadata.get("repository", {})
    if isinstance(repository, str):
        repository = {"url": repository}
    candidate = NOTICES.safe_github_source(
        {
            "url": repository.get("url", "").removeprefix("git+"),
            "commit": metadata.get("gitHead", ""),
        }
    )
    if candidate:
        return candidate
    url = metadata.get("dist", {}).get("attestations", {}).get("url")
    if not url:
        return None
    for attestation in registry_json(url).get("attestations", []):
        payload = attestation.get("bundle", {}).get("dsseEnvelope", {}).get("payload")
        if not payload:
            continue
        statement = json.loads(base64.b64decode(payload))
        if statement.get("predicateType") != "https://slsa.dev/provenance/v1":
            continue
        for dependency in (
            statement.get("predicate", {})
            .get("buildDefinition", {})
            .get("resolvedDependencies", [])
        ):
            uri = dependency.get("uri", "").removeprefix("git+").split("@refs/", 1)[0]
            candidate = NOTICES.safe_github_source(
                {
                    "url": uri,
                    "commit": dependency.get("digest", {}).get("gitCommit", ""),
                }
            )
            if candidate:
                return candidate
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sbom", required=True)
    parser.add_argument("--node-modules", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.node_modules)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    installed = {}
    for path in root.rglob("package.json"):
        directory = path.parent
        if directory.parent.name != "node_modules" and not (
            directory.parent.name.startswith("@")
            and directory.parent.parent.name == "node_modules"
        ):
            continue
        metadata = json.loads(path.read_text())
        installed[(metadata.get("name"), metadata.get("version"))] = (
            directory,
            metadata,
        )
    components = []
    seen = set()
    cache = {}
    for item in json.loads(Path(args.sbom).read_text()).get("components", []):
        if not item.get("purl", "").startswith("pkg:npm/"):
            continue
        name = "/".join(value for value in (item.get("group"), item["name"]) if value)
        version = item["version"]
        requested_name = name
        if "@" in version:
            name, version = version.removeprefix("npm:").rsplit("@", 1)
        if (name, version) in seen:
            continue
        seen.add((name, version))
        package, metadata = installed[(name, version)]
        directory = NOTICES.component_directory(output, name, version)
        notices = NOTICES.copy_notices(package, directory)
        root_license = any(
            Path(n).parent == Path(".")
            and re.match(r"^(?:un)?licen[sc]e", Path(n).name, re.IGNORECASE)
            for n in notices
        )
        fetched = []
        source = None
        if not root_license:
            registry = registry_json(
                f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='')}/{version}"
            )
            reference = source_reference(name, version, registry)
            if reference:
                source = (
                    f"https://github.com/{reference[0]}/archive/{reference[1]}.tar.gz"
                )
                repository = registry.get("repository", {})
                subdirectory = (
                    repository.get("directory", "")
                    if isinstance(repository, dict)
                    else ""
                )
                prefixes = [""]
                if (
                    subdirectory
                    and re.fullmatch(r"[A-Za-z0-9_./-]+", subdirectory)
                    and ".." not in Path(subdirectory).parts
                ):
                    prefixes.append(subdirectory.strip("/") + "/")
                for prefix in prefixes:
                    for filename in (
                        "LICENSE",
                        "LICENSE.txt",
                        "LICENSE.TXT",
                        "LICENSE.md",
                        "license.txt",
                        "UNLICENSE",
                        "NOTICE",
                        "NOTICE.txt",
                    ):
                        url = f"https://raw.githubusercontent.com/{reference[0]}/{reference[1]}/{prefix}{filename}"
                        content = NOTICES.fetch_notice(url, cache)
                        if content:
                            relative = "upstream-" + (prefix + filename).replace(
                                "/", "_"
                            )
                            (directory / relative).write_bytes(content)
                            notices.append(relative)
                            fetched.append(url)
                            if re.match(r"^(?:un)?licen[sc]e", filename, re.IGNORECASE):
                                root_license = True
        license_note = None
        if (
            not root_license
            and name == "tr46"
            and version == "0.0.3"
            and metadata.get("license") == "MIT"
        ):
            standard = (
                Path(__file__).resolve().parents[1]
                / "third-party/standard-licenses/MIT.txt"
            )
            (directory / "SPDX-MIT-standard-text.txt").write_bytes(
                standard.read_bytes()
            )
            notices.append("SPDX-MIT-standard-text.txt")
            root_license = True
            license_note = "Upstream package declares MIT but contains no standalone license file at its recorded source commit. Exact standard MIT terms are supplemented; package author metadata is retained without inventing a copyright notice."
        components.append(
            {
                "name": name,
                "version": version,
                "author": metadata.get("author"),
                "license_note": license_note,
                "requested_name": requested_name,
                "declared_license": metadata.get("license"),
                "package": f"https://www.npmjs.com/package/{name}/v/{version}",
                "source": source,
                "notice_directory": str(directory.relative_to(output)),
                "notice_files": sorted(set(notices)),
                "pinned_notice_sources": fetched,
                "root_license_present": root_license,
            }
        )
    result = {
        "kind": "Frontend production dependency graph",
        "components": components,
        "review_required": [
            f"Missing root license text: {c['name']}@{c['version']}"
            for c in components
            if not c["root_license_present"]
        ],
        "review_notes": [
            f"{c['name']}@{c['version']}: {c['license_note']}"
            for c in components
            if c["license_note"]
        ],
        "scope": "Conservative production lockfile graph, including dependencies that bundling may remove. Package texts and pinned upstream notices are retained unchanged. Registry provenance supplies source references; this collector is not a signature verifier or legal compatibility determination.",
    }
    (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"Collected frontend notices for {len(components)} components; {len(result['review_required'])} gaps require review."
    )


if __name__ == "__main__":
    main()

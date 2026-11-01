import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NOTICE = re.compile(
    r"^(?:unlicen[sc]e|licen[sc]e|copying|notice|copyright|authors|third[-_ ]party[-_ ]notices?)(?:[._-].*)?$",
    re.IGNORECASE,
)
SOURCE_EXTENSIONS = {".go", ".py", ".js", ".ts", ".c", ".h"}
MAX_NOTICE_BYTES = 1_000_000


def notice_name(name):
    return (
        bool(NOTICE.match(Path(name).name))
        or Path(name).name.lower().endswith(".license.txt")
    ) and Path(name).suffix.lower() not in SOURCE_EXTENSIONS


def component_directory(output, name, version):
    key = hashlib.sha256(f"{name}@{version}".encode()).hexdigest()
    directory = output / "notices" / key
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def copy_notices(source, target):
    copied = []
    for directory, names, files in os.walk(source, followlinks=False):
        names[:] = [
            name
            for name in names
            if name not in {".git", "node_modules"}
            and not (Path(directory) / name).is_symlink()
        ]
        for name in sorted(files):
            path = Path(directory) / name
            if (
                not notice_name(name)
                or path.is_symlink()
                or path.stat().st_size > MAX_NOTICE_BYTES
            ):
                continue
            relative = path.relative_to(source)
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(path.read_bytes())
            copied.append(str(relative))
    return sorted(copied)


def decode_stream(text):
    decoder = json.JSONDecoder()
    result = []
    while text.strip():
        value, end = decoder.raw_decode(text.lstrip())
        result.append(value)
        text = text.lstrip()[end:]
    return result


def parse_go_build(text):
    modules = []
    for line in text.splitlines():
        fields = line.strip().split("\t")
        if fields[0] in {"mod", "dep"} and len(fields) >= 3:
            modules.append(
                {"name": fields[1], "version": fields[2], "main": fields[0] == "mod"}
            )
        elif fields[0] == "=>" and modules:
            modules[-1]["replacement"] = {"name": fields[1], "version": fields[2]}
    return modules


def go_escape(value):
    return "".join(
        "!" + letter.lower() if letter.isupper() else letter for letter in value
    )


def collect_go(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    graph = {m["Path"]: m for m in decode_stream(Path(args.modules).read_text())}
    build = subprocess.check_output(["go", "version", "-m", args.binary], text=True)
    components = []
    for item in parse_go_build(build):
        module = graph.get(item["name"], {})
        effective = module.get("Replace", module)
        version = (
            args.main_version
            if item["main"]
            else effective.get("Version", item["version"])
        )
        name = effective.get("Path", item["name"])
        directory = component_directory(output, name, version)
        source = effective.get("Dir")
        notices = copy_notices(Path(source), directory) if source else []
        source_url = (
            args.main_source
            if item["main"]
            else f"https://proxy.golang.org/{go_escape(name)}/@v/{go_escape(version)}.zip"
        )
        components.append(
            {
                "name": name,
                "version": version,
                "source": source_url,
                "notice_directory": str(directory.relative_to(output)),
                "notice_files": notices,
                "replacement_for": item["name"] if name != item["name"] else None,
            }
        )
    goroot = Path(subprocess.check_output(["go", "env", "GOROOT"], text=True).strip())
    for name in ("LICENSE", "PATENTS"):
        if (goroot / name).is_file():
            shutil.copyfile(goroot / name, output / f"Go-{name}")
    shutil.copyfile(args.modfile, output / "effective.mod.txt")
    shutil.copyfile(args.sumfile, output / "effective.sum.txt")
    (output / "build-info.txt").write_text(build)
    return {
        "kind": "Go binary",
        "components": components,
        "review_required": [
            f"Missing notice text: {c['name']}@{c['version']}"
            for c in components
            if not c["notice_files"]
        ],
        "scope": "Modules listed in the shipped binary; texts copied unchanged from their source directories. Effective module inputs document the dependency changes from upstream. Go toolchain license is included separately; corresponding Go source is available at https://go.dev/dl/.",
    }


def safe_github_source(repository):
    parsed = urllib.parse.urlparse(repository.get("url", ""))
    commit = repository.get("commit", "")
    parts = parsed.path.removesuffix(".git").strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or len(parts) != 2
        or not re.fullmatch(r"[0-9a-f]{40,64}", commit)
    ):
        return None
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        return None
    return "/".join(parts), commit


def fetch_notice(url, cache):
    if url in cache:
        return cache[url]
    request = urllib.request.Request(
        url, headers={"User-Agent": "Ignite-image-notice-collector"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if (
                urllib.parse.urlparse(response.url).hostname
                != "raw.githubusercontent.com"
            ):
                raise ValueError("Unexpected notice source redirect")
            content = response.read(MAX_NOTICE_BYTES + 1)
        if len(content) > MAX_NOTICE_BYTES:
            content = None
    except (urllib.error.URLError, TimeoutError):
        content = None
    cache[url] = content
    return content


def copy_package_notices(archive, directory):
    notices = []
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            path = Path(entry.filename)
            if (
                entry.is_dir()
                or entry.file_size > MAX_NOTICE_BYTES
                or path.is_absolute()
                or ".." in path.parts
                or not notice_name(entry.filename)
            ):
                continue
            destination = directory / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(package.read(entry))
            notices.append(entry.filename)
    return notices


def collect_dotnet(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    dependencies = json.loads(Path(args.deps).read_text())["libraries"]
    cache = {}
    components = []
    for spec, library in sorted(dependencies.items()):
        if library["type"] != "package":
            continue
        name, version = spec.rsplit("/", 1)
        package = Path(args.packages) / name.lower() / version.lower()
        nuspecs = list(package.glob("*.nuspec"))
        if not nuspecs:
            raise ValueError(f"Missing package metadata for {name}")
        elements = {
            e.tag.rsplit("}", 1)[-1]: e for e in ET.parse(nuspecs[0]).getroot().iter()
        }
        license_element = elements.get("license")
        repository = elements.get("repository")
        repo = safe_github_source(repository.attrib) if repository is not None else None
        if repo is None and name.startswith("SQLitePCLRaw.") and version == "2.1.12":
            repo = (
                "ericsink/SQLitePCL.raw",
                "ca835d21508bff43121c65081035840ac5006c4c",
            )
        directory = component_directory(output, name, version)
        notices = []
        for archive in sorted(package.glob("*.nupkg")):
            notices.extend(copy_package_notices(archive, directory))
        fetched = []
        if repo:
            for filename in (
                "LICENSE",
                "LICENSE.txt",
                "LICENSE.TXT",
                "LICENSE.md",
                "license.txt",
                "NOTICE",
                "NOTICE.txt",
                "NOTICE.TXT",
                "THIRD-PARTY-NOTICES.txt",
            ):
                url = (
                    f"https://raw.githubusercontent.com/{repo[0]}/{repo[1]}/{filename}"
                )
                text = fetch_notice(url, cache)
                if text:
                    relative = "upstream-" + filename
                    (directory / relative).write_bytes(text)
                    notices.append(relative)
                    fetched.append(url)
        source = (
            f"https://github.com/{repo[0]}/archive/{repo[1]}.tar.gz" if repo else None
        )
        components.append(
            {
                "name": name,
                "version": version,
                "package": f"https://www.nuget.org/packages/{name}/{version}",
                "declared_license": license_element.text
                if license_element is not None
                else None,
                "license_type": license_element.attrib.get("type")
                if license_element is not None
                else None,
                "copyright": elements["copyright"].text
                if "copyright" in elements
                else None,
                "authors": elements["authors"].text if "authors" in elements else None,
                "source": source,
                "notice_directory": str(directory.relative_to(output)),
                "notice_files": sorted(set(notices)),
                "pinned_notice_sources": fetched,
            }
        )
    return {
        "kind": ".NET published dependency graph",
        "components": components,
        "review_required": [
            f"Missing notice text: {c['name']}@{c['version']}"
            for c in components
            if not c["notice_files"]
        ],
        "scope": "Packages in the published deps.json, not the SDK/test dependency graph. Texts copied unchanged from packages and, where available, their pinned upstream source commits. Framework and OS notices remain in the base image.",
    }


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="kind", required=True)
    go = sub.add_parser("go")
    for option in (
        "binary",
        "modules",
        "main-version",
        "main-source",
        "modfile",
        "sumfile",
        "output",
    ):
        go.add_argument("--" + option, required=True)
    dotnet = sub.add_parser("dotnet")
    for option in ("deps", "packages", "output"):
        dotnet.add_argument("--" + option, required=True)
    args = parser.parse_args()
    result = collect_go(args) if args.kind == "go" else collect_dotnet(args)
    (Path(args.output) / "manifest.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(
        f"Collected notices for {len(result['components'])} components; {len(result['review_required'])} gaps require review."
    )


if __name__ == "__main__":
    main()

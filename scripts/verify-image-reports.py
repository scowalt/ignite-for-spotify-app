import json
import re
import sys
from pathlib import Path


def checked_notice_manifest(path):
    data = json.loads(path.read_text())
    if not data.get("components") or data.get("review_required"):
        raise ValueError("Component notice coverage requires review.")
    for component in data["components"]:
        directory = Path(component["notice_directory"])
        if (
            directory.is_absolute()
            or ".." in directory.parts
            or not component.get("notice_files")
        ):
            raise ValueError("Invalid or missing component notices.")
        for name in component["notice_files"]:
            relative = directory / name
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or not (path.parent / relative).is_file()
            ):
                raise ValueError("Missing or unsafe notice-file path.")
    return data


def public_inventory(sbom, image):
    fields = {
        "type",
        "group",
        "name",
        "version",
        "purl",
        "licenses",
        "hashes",
        "cpe",
        "bom-ref",
    }
    return {
        "bomFormat": "CycloneDX",
        "specVersion": sbom.get("specVersion", "1.6"),
        "version": 1,
        "metadata": {
            "component": {"type": "container", "name": image, "bom-ref": "image"}
        },
        "components": [
            {k: v for k, v in c.items() if k in fields}
            for c in sbom.get("components", [])
        ],
    }


def main():
    component, image, private_path, output_path = sys.argv[1:]
    private = Path(private_path)
    output = Path(output_path)
    try:
        for filename, field in (
            ("secrets.json", "Secrets"),
            ("vulnerabilities.json", "Vulnerabilities"),
        ):
            report = json.loads((private / filename).read_text())
            if (
                report.get("SchemaVersion") != 2
                or report.get("ArtifactType") != "container_image"
                or report.get("ArtifactName") != image
            ):
                raise ValueError("Unexpected image report identity/schema.")
            if any(result.get(field) for result in report.get("Results", [])):
                raise ValueError("Image security findings remain.")
        image_id = report.get("Metadata", {}).get("ImageID", "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise ValueError("Missing immutable local image identity.")
        root = private / "notices"
        if (
            not (root / "LICENSE").is_file()
            or not (root / "THIRD_PARTY_NOTICES.md").is_file()
        ):
            raise ValueError("Missing application/dependency license scope.")
        kind = "dotnet" if component == "backend" else "go"
        binary = checked_notice_manifest(root / "components" / kind / "manifest.json")
        manifests = {kind: binary}
        if component == "frontend":
            manifests["frontend"] = checked_notice_manifest(
                private / "frontend-notices" / "manifest.json"
            )
        inventory = public_inventory(
            json.loads((private / "sbom.json").read_text()), image
        )
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(
            f"Image report verification failed: {type(error).__name__}; no raw configuration or findings printed.",
            file=sys.stderr,
        )
        return 1
    output.mkdir(parents=True, exist_ok=True)
    (output / "components.cdx.json").write_text(json.dumps(inventory, indent=2) + "\n")
    for name, manifest in manifests.items():
        (output / f"{name}-notice-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
    summary = {
        "image": image,
        "image_id": image_id,
        "component": component,
        "fixable_high_critical_findings": 0,
        "secret_findings": 0,
        "notice_components": {k: len(v["components"]) for k, v in manifests.items()},
        "review_notes": [
            note
            for manifest in manifests.values()
            for note in manifest.get("review_notes", [])
        ],
        "scope": "Mechanical security-policy and notice-file coverage checks, not a legal compatibility determination. Full Trivy configuration/history/secret reports are deliberately not published.",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

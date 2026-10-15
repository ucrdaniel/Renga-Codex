"""Fail-closed public release gate; never import COM, SDK or native models."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import tomllib
import zipfile

FINGERPRINT_ALGORITHM = "sha256-python-sources-v1"
NORMALIZATION = "utf-8-sig-to-utf-8;CRLF-and-CR-to-LF"
PRIVATE_PARTS = {".venv", "__pycache__", "runtime", "artifacts", "logs", "vendor", "rengasdk",
                 "sdk", "1-hw", "source-analysis", ".git", "local", "private", "attachments"}
PRIVATE_SUFFIXES = {".rnp", ".renga", ".ifc", ".dwg", ".dxf", ".pdf", ".docx", ".xlsx",
                    ".tlb", ".dll", ".exe", ".msi", ".pyd", ".so", ".lib", ".lic", ".key",
                    ".pem", ".pfx", ".sqlite", ".db", ".pyc", ".pyo", ".bak", ".idl",
                    ".h", ".hpp", ".zip", ".7z", ".rar", ".pth"}


def normalized_source(data: bytes) -> bytes:
    return data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").encode("utf8")


def release_metadata(repository: Path) -> dict:
    """Read safe, stable release names from this exact checkout's metadata."""
    project = tomllib.loads((Path(repository) / "pyproject.toml").read_text(encoding="utf8"))["project"]
    version = project.get("version")
    if project.get("name") != "renga-codex-bridge" or not isinstance(version, str) or not re.fullmatch(
            r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version):
        raise ValueError("Release requires renga-codex-bridge and an explicit major.minor.patch version")
    return {"bridge_version": version, "release_tag": "v" + version,
            "release_notes": "docs/RELEASE_NOTES_" + version + ".md",
            "wheel": "renga_codex_bridge-" + version + "-py3-none-any.whl",
            "sdist": "renga_codex_bridge-" + version + ".tar.gz"}


def verify_release_notes(repository: Path) -> dict:
    metadata = release_metadata(repository)
    path = Path(repository) / metadata["release_notes"]
    if not path.is_file() or path.is_symlink():
        raise ValueError("Current version's release notes must be a regular file")
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip() or re.search(r"ROOT_FILL|TODO_RELEASE_PROOF|NOT_READY_FOR_PUBLICATION", text):
        raise ValueError("Release notes still contain unfilled native proof placeholders or are empty")
    if not text.splitlines() or metadata["bridge_version"] not in text.splitlines()[0]:
        raise ValueError("Release notes title must identify the current package version")
    return metadata


def source_fingerprint(repository: Path) -> dict:
    """Fingerprint sorted flat package sources, independent of OS line endings.

    SHA-256 input: algorithm + NUL; for every relative POSIX path, path + NUL +
    decimal normalized byte length + NUL + normalized UTF-8 content + NUL.
    The per-file manifest supports independent archive/source comparison.
    """
    repository = Path(repository).resolve()
    paths = sorted((repository / "src" / "renga_codex_bridge").glob("*.py"),
                   key=lambda path: path.relative_to(repository).as_posix())
    if not paths:
        raise ValueError("No bridge Python sources found")
    digest = hashlib.sha256((FINGERPRINT_ALGORITHM + "\0").encode("ascii"))
    files = []
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError("Source fingerprint requires regular unlinked Python files")
        relative = path.relative_to(repository).as_posix()
        content = normalized_source(path.read_bytes())
        digest.update(relative.encode("utf8") + b"\0" + str(len(content)).encode("ascii") + b"\0" + content + b"\0")
        files.append({"path": relative, "sha256": hashlib.sha256(content).hexdigest()})
    return {"algorithm": FINGERPRINT_ALGORITHM, "normalization": NORMALIZATION,
            "sha256": digest.hexdigest(), "file_count": len(files), "files": files}


def _check_sanitized_evidence(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.casefold() in {"password", "token", "api_key", "activation_key", "license_key",
                                 "raw_log", "user_project", "username", "student_name"}:
                raise ValueError("Private field in public native evidence: " + key)
            _check_sanitized_evidence(item)
    elif isinstance(value, list):
        for item in value:
            _check_sanitized_evidence(item)
    elif isinstance(value, str):
        # A URI scheme such as https:// contains "s:/"; do not mistake it for
        # a drive path. Public official-source URLs are allowed in evidence.
        if re.search(r"(?:(?<![A-Za-z0-9:])[A-Za-z]:[\\/]|\\\\[^\\]+\\|(?<![A-Za-z0-9:/])/(?:Users|home)/)", value):
            raise ValueError("Absolute local path in public native evidence")
        if re.search(r"-----BEGIN .*PRIVATE KEY-----|\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}", value):
            raise ValueError("Credential-like value in public native evidence")


def verify_evidence(repository: Path, evidence: Path) -> dict:
    repository = Path(repository).resolve()
    metadata = release_metadata(repository)
    value = json.loads(Path(evidence).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1 or value.get("status") != "passed":
        raise ValueError("Fresh sanitized native evidence must have schema_version=1 and status=passed")
    if value.get("bridge_version") != metadata["bridge_version"]:
        raise ValueError("Native evidence version does not match the package")
    if type(value.get("computer_use_calls")) is not int or value["computer_use_calls"] != 0:
        raise ValueError("Preview API coverage requires exactly zero Computer Use calls")
    if not isinstance(value.get("renga_version"), str) or not re.fullmatch(r"9\.3\.\d+(?:\.\d+)*", value["renga_version"]):
        raise ValueError("Native evidence must identify the tested Renga 9.3 version")
    expected = source_fingerprint(repository)
    if value.get("source_fingerprint") != expected:
        raise ValueError("Native evidence does not match the current normalized bridge source fingerprint")
    _check_sanitized_evidence(value)
    return value


def _safe_archive_name(name: str):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or "\0" in name or not path.parts:
        raise ValueError("Unsafe archive path: " + name)
    if any(part.casefold() in PRIVATE_PARTS for part in path.parts):
        raise ValueError("Private/vendor directory in archive: " + name)
    filename = path.name.casefold()
    if path.suffix.casefold() in PRIVATE_SUFFIXES or filename == ".env" or filename.startswith(".env."):
        raise ValueError("Forbidden binary/model/credential artifact: " + name)
    if "tests" in {part.casefold() for part in path.parts} and path.suffix.casefold() == ".json":
        if tuple(path.parts[-3:]) != ("tests", "evidence", "windows-renga-9.3.json"):
            raise ValueError("Only the audited sanitized native evidence JSON may be packaged under tests")


def _archive_files(path: Path):
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            for entry in archive.infolist():
                # ZipInfo normalizes Windows separators and truncates NULs in
                # filename; validate the original wire name before that loss.
                _safe_archive_name(entry.orig_filename)
                if stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError("Linked file in release wheel")
                if not entry.is_dir():
                    yield entry.filename, archive.read(entry)
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            for entry in archive.getmembers():
                _safe_archive_name(entry.name)
                if not entry.isfile() and not entry.isdir():
                    raise ValueError("Linked/special file in release sdist")
                if entry.isfile():
                    with archive.extractfile(entry) as stream:
                        yield entry.name, stream.read()
    else:
        raise ValueError("Unexpected release artifact format: " + path.name)


def verify_archives(repository: Path, directory: Path) -> list[dict]:
    metadata = release_metadata(repository)
    fingerprint = source_fingerprint(repository)
    expected = {row["path"]: row["sha256"] for row in fingerprint["files"]}
    artifacts = sorted(Path(directory).iterdir())
    if len(artifacts) != 2 or sum(path.suffix == ".whl" for path in artifacts) != 1 or sum(path.name.endswith(".tar.gz") for path in artifacts) != 1:
        raise ValueError("Release dist must contain exactly one wheel and one sdist")
    results = []
    for artifact in artifacts:
        if not artifact.is_file() or artifact.is_symlink() or artifact.name not in {metadata["wheel"], metadata["sdist"]}:
            raise ValueError("Unexpected artifact name or linked file: " + artifact.name)
        actual_sources = {}
        entries = 0
        for name, data in _archive_files(artifact):
            entries += 1
            parts = PurePosixPath(name).parts
            if artifact.suffix == ".whl" and len(parts) == 2 and parts[0] == "renga_codex_bridge" and parts[1].endswith(".py"):
                source_name = "src/" + name
            elif artifact.name.endswith(".tar.gz") and len(parts) == 4 and parts[1:3] == ("src", "renga_codex_bridge") and parts[3].endswith(".py"):
                source_name = PurePosixPath(*parts[1:]).as_posix()
            else:
                source_name = None
            if "renga_codex_bridge" in parts and source_name is None:
                raise ValueError("Unfingerprinted package member in archive: " + name)
            if source_name is not None:
                if source_name in actual_sources:
                    raise ValueError("Duplicate source member in archive")
                actual_sources[source_name] = hashlib.sha256(normalized_source(data)).hexdigest()
        if actual_sources != expected:
            raise ValueError("Packaged sources differ from the natively tested source fingerprint: " + artifact.name)
        results.append({"file": artifact.name, "bytes": artifact.stat().st_size, "entries": entries,
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--repository", type=Path, default=root)
    parser.add_argument("--evidence", type=Path,
                        help="Defaults to tests/evidence/windows-renga-9.3.json under --repository")
    parser.add_argument("--archives", type=Path)
    parser.add_argument("--fingerprint-only", action="store_true")
    parser.add_argument("--release-metadata", action="store_true",
                        help="Print validated current-version tag, release-notes and artifact names")
    args = parser.parse_args()
    if args.fingerprint_only and args.release_metadata:
        parser.error("Choose only one metadata-only output mode")
    if args.release_metadata:
        result = release_metadata(args.repository)
    elif args.fingerprint_only:
        result = source_fingerprint(args.repository)
    else:
        evidence = verify_evidence(args.repository, args.evidence or
                                   args.repository / "tests/evidence/windows-renga-9.3.json")
        verify_release_notes(args.repository)
        result = {"status": "verified", "bridge_version": evidence["bridge_version"],
                  "source_sha256": evidence["source_fingerprint"]["sha256"]}
        if args.archives:
            result["artifacts"] = verify_archives(args.repository, args.archives)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

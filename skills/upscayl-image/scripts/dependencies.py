#!/usr/bin/env python3
"""Gestion des dependances lourdes optionnelles - independante des autres skills.

Security contract:
- never fetch an unlisted release asset
- require HTTPS GitHub URL and a manifest-pinned SHA-256
- enforce archive size/expanded size and safe members
- install in skill-private .runtime only
- do not silently download: --install is an explicit command
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "references" / "dependencies.json"
MAX_DOWNLOAD = 2 * 1024 * 1024 * 1024
MAX_UNPACKED = 4 * 1024 * 1024 * 1024
HOSTS = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}
KNOWN_ASSETS = {"ffmpeg", "upscayl-ncnn"}
FILES = {"ffmpeg": ("ffmpeg", "ffmpeg.exe"), "upscayl-ncnn": ("upscayl-bin", "upscayl-bin.exe")}


def system_tag() -> str:
    osname = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}.get(platform.system(), "unsupported")
    arch = "x64" if platform.machine().lower() in {"amd64", "x86_64"} else "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "unsupported"
    return f"{osname}-{arch}"


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class GithubHTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_url(value: str) -> None:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.password:
        raise ValueError("Only allowlisted GitHub HTTPS download URLs are permitted")


def available(asset: str) -> bool:
    if asset == "ffmpeg":
        return bool(os.environ.get("FFMPEG_BIN") and Path(os.environ["FFMPEG_BIN"]).is_file()) or bool(shutil.which("ffmpeg"))
    return bool(os.environ.get("UPSCAYL_BIN") and Path(os.environ["UPSCAYL_BIN"]).is_file()) or bool(shutil.which("upscayl-bin"))


def check() -> int:
    print(f"python={platform.python_version()} platform={system_tag()}")
    for name in sorted(KNOWN_ASSETS):
        print(f"{name}: {'available' if available(name) else 'not found (optional asset)'}")
    try:
        import PIL
        print(f"pillow={PIL.__version__}")
    except ImportError:
        print("pillow=missing; install from requirements.txt if the runtime permits pip")
    print(f"manifest={MANIFEST}")
    print("Dependencies are downloaded only with --install; never from an unpinned URL.")
    return 0


def install(asset: str) -> int:
    if asset not in KNOWN_ASSETS:
        raise ValueError("Unrecognized asset")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tag = system_tag()
    spec = data.get("artifacts", {}).get(asset, {}).get(tag)
    if not spec:
        raise RuntimeError(f"No published, verified GitHub asset for {asset} on {tag}. Use an installed system binary or publish a pinned release.")
    url = spec.get("url")
    expected_hash = str(spec.get("sha256", "")).lower()
    if not url or len(expected_hash) != 64 or not all(c in "0123456789abcdef" for c in expected_hash):
        raise RuntimeError("Incomplete release manifest: need an HTTPS URL and the real SHA-256 of the uploaded asset")
    validate_url(url)
    dst = ROOT / ".runtime" / tag / asset
    if dst.exists():
        print(f"Already installed: {dst} (remove manually for upgrades)")
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(GithubHTTPSOnly())
    with tempfile.TemporaryDirectory(dir=dst.parent) as d:
        stage = Path(d)
        archive = stage / "download.zip"
        req = urllib.request.Request(url, headers={"User-Agent": "sam-openai-skills-bootstrap/1.0"})
        total = 0
        with opener.open(req, timeout=90) as response, archive.open("wb") as fh:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > MAX_DOWNLOAD:
                    raise RuntimeError("Download exceeds 2 GiB")
                fh.write(block)
        if hash_file(archive) != expected_hash:
            raise RuntimeError("SHA256 MISMATCH. Asset rejected without extraction.")
        extract = stage / "extracted"
        extract.mkdir()
        with zipfile.ZipFile(archive) as zf:
            members = [x for x in zf.infolist() if not x.is_dir()]
            if sum(x.file_size for x in members) > MAX_UNPACKED:
                raise RuntimeError("Unpacked size exceeds 4 GiB")
            for info in members:
                name = info.filename.replace("\\", "/")
                parts = PurePosixPath(name).parts
                if not parts or name.startswith("/") or ".." in parts or ":" in name or info.is_dir() or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    raise RuntimeError("Unsafe archive member")
            for info in members:
                destination = extract.joinpath(*PurePosixPath(info.filename.replace("\\", "/")).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, destination.open("wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)
        expected_bin = FILES[asset]
        if not any(x.name in expected_bin for x in extract.rglob("*") if x.is_file()):
            raise RuntimeError(f"Artifact does not contain the required {asset} executable")
        shutil.move(str(extract), str(dst))
    print(f"Installed {asset} in {dst}. For runtime, set the executable env variable or use the skill discovery script.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--install", choices=sorted(KNOWN_ASSETS))
    a = p.parse_args()
    try:
        return install(a.install) if a.install else check()
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as e:
        print(f"DEPENDENCY_ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

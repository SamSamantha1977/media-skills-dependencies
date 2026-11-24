#!/usr/bin/env python3
"""Standalone Python image skill for OpenAI. Python >=3.11, Pillow>=10.
No PowerShell, no network access, no dependencies on video2x-video.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from PIL import Image, ImageOps, UnidentifiedImageError

EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
OUT_EXT = {".jpeg": ".jpg", ".jpg": ".jpg", ".png": ".png", ".bmp": ".bmp", ".webp": ".webp", ".tif": ".tif", ".tiff": ".tif"}
MB = 1_000_000


def ensure_image(path: Path) -> Image.Image:
    with Image.open(path) as im:
        im.load()
        return ImageOps.exif_transpose(im).copy()


def has_alpha(im: Image.Image) -> bool:
    if im.mode == "P" and "transparency" in im.info:
        return True
    if "A" not in im.getbands():
        return False
    return im.getchannel("A").getextrema()[0] != 255


def result_extension(im: Image.Image, source: Path, quality_drop: int, requested: str) -> str:
    ext = OUT_EXT.get(source.suffix.lower(), ".png")
    if quality_drop == 0:
        return ext
    if has_alpha(im):
        return ".png"
    return ".jpg"


def converted(im: Image.Image, ext: str) -> Image.Image:
    if ext == ".jpg":
        return im.convert("RGB")
    if ext == ".png" and im.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        return im.convert("RGBA" if has_alpha(im) else "RGB")
    return im


def write_image(im: Image.Image, path: Path, ext: str, quality: int = 100) -> None:
    obj = converted(im, ext)
    options = {}
    if ext == ".jpg":
        options = {"quality": max(1, min(100, quality)), "subsampling": 0, "optimize": True}
    elif ext == ".png":
        options = {"optimize": True, "compress_level": 9}
    elif ext == ".webp":
        options = {"lossless": True, "method": 6}
    elif ext == ".tif":
        options = {"compression": "tiff_deflate"}
    fmt = {".jpg": "JPEG", ".png": "PNG", ".webp": "WEBP", ".tif": "TIFF", ".bmp": "BMP"}[ext]
    obj.save(path, format=fmt, **options)
    with Image.open(path) as check:
        check.verify()


def resized(im: Image.Image, reduction: float) -> Image.Image:
    if reduction == 0:
        return im
    factor = 1.0 - reduction / 100.0
    dims = (max(1, round(im.width * factor)), max(1, round(im.height * factor)))
    return im.resize(dims, Image.Resampling.LANCZOS)


def candidates(im: Image.Image, ext: str, min_quality: int, max_reduction: float):
    # Prefer original resolution; for JPEG, prefer higher quality.
    reductions = [0.0]
    if max_reduction:
        steps = max(1, round(max_reduction * 2))
        reductions += [min(max_reduction, 0.5 * j) for j in range(1, steps + 1)]
        if reductions[-1] != max_reduction:
            reductions.append(max_reduction)
    qualities = [100]
    if ext == ".jpg" and min_quality < 100:
        qualities += list(range(99, min_quality - 1, -1))
    for r in reductions:
        current = resized(im, r)
        for quality in (qualities if r == 0 else qualities[-1:]):
            yield current, quality, r


def destination(source: Path, dst: str | None, suffix: str, ext: str, folder_mode: bool) -> Path:
    if dst and not folder_mode and Path(dst).suffix:
        p = Path(dst)
        return p.with_suffix(ext)
    directory = Path(dst) if dst else source.parent / "processed"
    return directory / (source.stem + suffix + ext)


def save_atomic(stage: Path, dest: Path, force: bool) -> None:
    if stage.resolve() == dest.resolve():
        raise ValueError("Source and destination overlap")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if not force:
            raise FileExistsError(f"Destination exists: {dest}. Use --force.")
        backup_dir = dest.parent / "archives"
        backup_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        backup = backup_dir / (dest.stem + "_BACKUP_" + datetime.now().strftime("%Y%m%d_%H%M%S%f") + dest.suffix)
        shutil.copy2(dest, backup)
        import hashlib
        def sha(p):
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            return h.digest()
        if sha(dest) != sha(backup):
            raise OSError("Backup checksum mismatch")
    os.replace(stage, dest)


def optimize_image(src: Path, dest: Path, args) -> None:
    im = ensure_image(src)
    ext = result_extension(im, src, args.y, args.format)
    limit = int((args.target_mb + (0 if args.strict else 0.5)) * MB)
    if limit < 1:
        raise ValueError("Invalid target")
    if src.suffix.lower().replace(".jpeg", ".jpg") == ext and src.stat().st_size <= limit:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent) as d:
            tmp = Path(d) / ("stage" + ext)
            shutil.copy2(src, tmp)
            save_atomic(tmp, dest, args.force)
        return
    min_quality = max(1, 100 - args.y) if args.y else 100
    with tempfile.TemporaryDirectory() as tmpdir:
        best = None
        best_size = float("inf")
        passed = None
        for idx, (candidate, q, reduction) in enumerate(candidates(im, ext, min_quality, args.x)):
            tmp = Path(tmpdir) / f"candidate-{idx}{ext}"
            write_image(candidate, tmp, ext, q)
            size = tmp.stat().st_size
            if size < best_size:
                best_size = size
                best = tmp
            if size <= limit:
                passed = tmp
                break
        if passed is None and args.strict:
            raise RuntimeError(f"STRICT impossible: best {best_size} bytes, limit {limit} bytes; source unchanged")
        if passed is None:
            # Soft never exceeds the documented ceiling either; fails explicitly.
            raise RuntimeError(f"Soft ceiling impossible: best {best_size} bytes, limit {limit} bytes")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent) as finaldir:
            stage = Path(finaldir) / ("stage" + ext)
            shutil.copy2(passed, stage)
            save_atomic(stage, dest, args.force)


def simple_resize(src: Path, dst: Path, scale: float, force: bool) -> None:
    if not 0 < scale <= 16:
        raise ValueError("Scale must be >0 and <=16")
    im = ensure_image(src)
    dims = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
    out = im.resize(dims, Image.Resampling.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dst.parent) as d:
        tmp = Path(d) / "stage.png"
        write_image(out, tmp, ".png")
        save_atomic(tmp, dst, force)


def enhance(src: Path, dst: Path, scale: int, model: str, force: bool) -> None:
    # Real Upscayl enhancement requires a compatible external ncnn executable + model files.
    exe = os.environ.get("UPSCAYL_BIN") or shutil.which("upscayl-bin")
    models = os.environ.get("UPSCAYL_MODELS")
    if not exe or not models:
        runtime = Path(__file__).resolve().parents[1] / ".runtime"
        if runtime.exists():
            for binary in ("upscayl-bin", "upscayl-bin.exe"):
                matches = list(runtime.rglob(binary))
                if matches:
                    exe = exe or str(matches[0])
                    base = matches[0].parent
                    for candidate in (base / "models", base.parent / "models", base.parent.parent / "models"):
                        if candidate.is_dir():
                            models = models or str(candidate)
                            break
                    break
    if not exe or not models or not Path(models).is_dir():
        raise RuntimeError("Enhance requires a compatible Upscayl NCNN binary and model files; set UPSCAYL_BIN/UPSCAYL_MODELS or install a verified GitHub release via scripts/dependencies.py. GPU/Vulkan may be unavailable in cloud runtimes.")
    if not 1 <= scale <= 4:
        raise ValueError("Enhance scale must be 1..4")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dst.parent) as d:
        raw = Path(d) / "enhanced.png"
        native_scale = 4 if scale == 1 else scale
        cmd = [exe, "-i", str(src), "-o", str(raw), "-n", model, "-s", str(native_scale), "-m", models, "-f", "png"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if result.returncode != 0 or not raw.is_file():
            raise RuntimeError(f"Upscayl NCNN failed ({result.returncode}): {result.stderr[-600:]}")
        stage = Path(d) / "stage.png"
        if scale == 1:
            original = ensure_image(src)
            out = ensure_image(raw).resize(original.size, Image.Resampling.LANCZOS)
            write_image(out, stage, ".png")
        else:
            shutil.copy2(raw, stage)
        save_atomic(stage, dst, force)


def run() -> int:
    p = argparse.ArgumentParser(description="upscayl-image: self-contained OpenAI Skill Python CLI")
    sub = p.add_subparsers(dest="mode", required=True)
    for action in ("resize", "compress", "enhance"):
        s = sub.add_parser(action)
        s.add_argument("--src", required=True)
        s.add_argument("--dst")
        s.add_argument("--force", action="store_true")
        s.add_argument("--dry-run", action="store_true")
        if action == "resize":
            s.add_argument("--scale", type=float, default=2.0)
        elif action == "compress":
            s.add_argument("--target-mb", type=float, required=True)
            s.add_argument("--strict", action="store_true")
            s.add_argument("--x", type=float, default=0)
            s.add_argument("--y", type=int, default=0)
            s.add_argument("--format", default="auto", choices=["auto"])
        else:
            s.add_argument("--scale", type=int, default=2)
            s.add_argument("--model", default="ultramix-balanced-4x")
    args = p.parse_args()
    if args.mode == "compress" and (not 0 <= args.x < 100 or not 0 <= args.y <= 100):
        p.error("--x must be in [0,100), --y in [0,100]")
    source = Path(args.src)
    if not source.exists():
        p.error(f"Source not found: {source}")
    folder = source.is_dir()
    inputs = sorted(x for x in source.iterdir() if x.is_file() and x.suffix.lower() in EXTS) if folder else [source]
    if not inputs:
        p.error("No supported images")
    for src in inputs:
        im = ensure_image(src)
        ext = ".png" if args.mode in ("resize", "enhance") else result_extension(im, src, args.y, args.format)
        dest = destination(src, args.dst, "_" + args.mode, ext, folder)
        if src.resolve() == dest.resolve():
            p.error("Cannot overwrite source")
        print(f"{src} -> {dest}", flush=True)
        if args.dry_run:
            continue
        if args.mode == "resize":
            simple_resize(src, dest, args.scale, args.force)
        elif args.mode == "compress":
            optimize_image(src, dest, args)
        else:
            enhance(src, dest, args.scale, args.model, args.force)
        with Image.open(dest) as result:
            result.verify()
        print(f"OK {dest.stat().st_size} bytes", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (ValueError, RuntimeError, OSError, UnidentifiedImageError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

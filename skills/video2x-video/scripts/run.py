#!/usr/bin/env python3
"""Standalone Python/FFmpeg video Skill; Python >=3.11. No PowerShell."""
from __future__ import annotations
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv", ".flv"}
MB = 1_000_000


def executable(env: str, program: str) -> str:
    candidate = os.environ.get(env) or shutil.which(program)
    if not candidate:
        runtime = Path(__file__).resolve().parents[1] / ".runtime"
        if runtime.exists():
            names = (program, program + ".exe")
            for name in names:
                matches = list(runtime.rglob(name))
                if matches:
                    candidate = str(matches[0])
                    break
    if not candidate:
        raise RuntimeError(f"{program} unavailable. Install the verified binary with scripts/dependencies.py --install ffmpeg (requires published GitHub release and approved network), or set {env}.")
    return candidate


def ffmpeg() -> str:
    return executable("FFMPEG_BIN", "ffmpeg")


def ffprobe() -> str:
    return executable("FFPROBE_BIN", "ffprobe")


def execute(cmd: list[str], timeout: int = 7200) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed rc={result.returncode}: {result.stderr[-1200:]}")


def probe(path: Path) -> dict:
    result = subprocess.run(
        [ffprobe(), "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate,nb_frames,duration:format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"Invalid video: {path} {result.stderr[-500:]}")
    obj = json.loads(result.stdout)
    video = next((s for s in obj.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video or not video.get("width") or not video.get("height"):
        raise RuntimeError("No decodable video stream")
    return obj


def vstream(meta: dict) -> dict:
    return next(s for s in meta["streams"] if s["codec_type"] == "video")


def duration(meta: dict) -> float:
    return float(vstream(meta).get("duration") or meta.get("format", {}).get("duration") or 0)


def fps(meta: dict) -> float:
    a, _, b = str(vstream(meta).get("r_frame_rate", "0/1")).partition("/")
    return float(a) / float(b or "1")


def has_audio(meta: dict) -> bool:
    return any(s.get("codec_type") == "audio" for s in meta.get("streams", []))


def validate(source: dict, target: Path, expected_wh: tuple[int, int], factor: int) -> None:
    after = probe(target)
    v = vstream(after)
    if (v["width"], v["height"]) != expected_wh:
        raise RuntimeError(f"Dimensions mismatch: expected {expected_wh}; got {(v['width'],v['height'])}")
    before_duration = duration(source)
    after_duration = duration(after)
    if before_duration > 0 and not .94 * before_duration <= after_duration <= 1.12 * before_duration:
        raise RuntimeError(f"Duration mismatch {before_duration} vs {after_duration}")
    if has_audio(source) and not has_audio(after):
        raise RuntimeError("Audio disappeared")
    expected_fps = fps(source) * factor
    if abs(fps(after) - expected_fps) > max(.2, .03 * expected_fps):
        raise RuntimeError(f"FPS mismatch {fps(after)} vs {expected_fps}")
    before_frames = int(vstream(source).get("nb_frames") or 0)
    after_frames = int(v.get("nb_frames") or 0)
    if before_frames and after_frames and abs(after_frames - before_frames * factor) > max(1, round(before_frames * factor * .03)):
        raise RuntimeError(f"Frames mismatch {after_frames} vs {before_frames*factor}")


def filter_scale(width: int, height: int, scale: float) -> tuple[str, tuple[int, int]]:
    if not 0 < scale <= 16:
        raise ValueError("scale must be >0 and <=16")
    out_w = max(2, int(width * scale / 2) * 2)
    out_h = max(2, int(height * scale / 2) * 2)
    return f"scale={out_w}:{out_h}:flags=lanczos", (out_w, out_h)


def filter_interpolate(meta: dict, factor: int) -> str:
    if factor not in (2, 4):
        raise ValueError("interpolate multiplier must be 2 or 4")
    hz = fps(meta) * factor
    length = duration(meta)
    if not 0 < hz <= 240 or length <= 0:
        raise ValueError("Invalid target FPS/duration")
    return (
        f"tpad=stop_mode=clone:stop_duration=0.3,"
        f"minterpolate=fps={hz:.6f}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
        f"trim=duration={length:.6f},setpts=PTS-STARTPTS"
    )


def encode(src: Path, dst: Path, filters: list[str], crf: int) -> None:
    vf = ",".join(filters)
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-n", "-i", str(src),
           "-map", "0:v:0", "-map", "0:a?"]
    if filters:
        cmd += ["-vf", vf]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-movflags", "+faststart", str(dst)]
    execute(cmd)


def native_enhance(src: Path, dst: Path, scale: int, model: str) -> None:
    # External Video2X binary required; no cloud Vulkan assumption.
    engine = os.environ.get("VIDEO2X_BIN") or shutil.which("video2x")
    if not engine:
        runtime = Path(__file__).resolve().parents[1] / ".runtime"
        if runtime.exists():
            for name in ("video2x", "video2x.exe"):
                matches = list(runtime.rglob(name))
                if matches:
                    engine = str(matches[0])
                    break
    if not engine:
        raise RuntimeError("Enhance requires Video2X NCNN + Vulkan GPU; configure VIDEO2X_BIN or install a verified GitHub release. GPU may be absent in cloud runtimes.")
    if not 1 <= scale <= 4:
        raise ValueError("Enhance scale must be 1..4")
    native_scale = max(2, scale) if model == "realesr-animevideov3" else 4
    cmd = [engine, "-i", str(src), "-o", str(dst), "-p", "realesrgan", "-s", str(native_scale),
           "--realesrgan-model", model, "-e", "crf=17", "--no-progress"]
    # Video2X on Intel UHD may exit abnormally despite an ostensibly readable output.
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200, cwd=str(Path(engine).resolve().parent) if Path(engine).is_file() else None)
    if p.returncode:
        raise RuntimeError(f"Video2X abnormal native exit ({p.returncode}), output not published. Detail: {p.stderr[-700:]}")
    if not dst.exists():
        raise RuntimeError("Video2X did not produce output")


def safe_publish(staged: Path, dest: Path, force: bool) -> None:
    if dest.exists():
        if not force:
            raise FileExistsError(f"Destination exists: {dest}. Use --force.")
        arch = dest.parent / "archives"
        arch.mkdir(parents=True, exist_ok=True)
        backup = arch / (dest.stem + "_BACKUP_" + datetime.now().strftime("%Y%m%d_%H%M%S%f") + dest.suffix)
        shutil.copy2(dest, backup)
        def digest(p):
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            return h.digest()
        if digest(dest) != digest(backup):
            raise OSError("Backup checksum mismatch")
    os.replace(staged, dest)


def process(src: Path, dst: Path, args) -> None:
    before = probe(src)
    v = vstream(before)
    original = (int(v["width"]), int(v["height"]))
    outwh = original
    interp = args.interpolate or (2 if args.mode == "interpolate" else 0)
    if interp not in (0, 2, 4):
        raise ValueError("interpolate 0, 2 or 4")
    limit = (args.target_mb + (0 if args.strict else .5)) * MB if args.mode == "compress" else None
    if args.mode == "compress" and (args.target_mb <= 0 or args.max_crf < args.crf):
        raise ValueError("compress requires positive --target-mb and --max-crf >= --crf")
    with tempfile.TemporaryDirectory(dir=dst.parent) as directory:
        work = Path(directory)
        base = work / "base.mp4"
        if args.mode == "enhance":
            native = work / "native.mp4"
            native_enhance(src, native, args.scale, args.model)
            # If engine model uses x4 natively, rescale back to the selected size.
            target_w = max(2, (original[0] * args.scale // 2) * 2)
            target_h = max(2, (original[1] * args.scale // 2) * 2)
            outwh = (target_w, target_h)
            encode(native, base, [f"scale={target_w}:{target_h}:flags=lanczos"], args.crf)
        elif args.mode == "resize":
            vf, outwh = filter_scale(*original, args.scale)
            encode(src, base, [vf], args.crf)
        elif args.mode == "interpolate":
            # Avoid an unnecessary extra re-encode of input.
            shutil.copy2(src, base)
        elif args.mode == "compress":
            if not args.target_mb:
                raise ValueError("target_mb required")
            if src.suffix.lower() == ".mp4" and src.stat().st_size <= limit:
                shutil.copy2(src, base)
            else:
                # Optimize within the declared CRF range, never break the weight limit.
                selected = None
                for crf in range(args.crf, args.max_crf + 1):
                    candidate = work / f"crf_{crf}.mp4"
                    encode(src, candidate, [], crf)
                    if candidate.stat().st_size <= limit:
                        selected = candidate
                        break
                if selected is None:
                    raise RuntimeError(f"Target not reachable within allowed CRF range; limit {int(limit)} bytes")
                shutil.copy2(selected, base)
        else:
            raise ValueError("Unsupported mode")
        stage = base
        if interp:
            out = work / "interpolated.mp4"
            encode(base, out, [filter_interpolate(probe(base), interp)], args.crf)
            stage = out
        validate(before, stage, outwh, interp or 1)
        if limit is not None and stage.stat().st_size > limit:
            raise RuntimeError("Target ceiling exceeded after interpolation")
        published = work / "published.mp4"
        shutil.copy2(stage, published)
        safe_publish(published, dst, args.force)


def main():
    p = argparse.ArgumentParser(description="video2x-video portable Python+FFmpeg skill (>=3.11)")
    p.add_argument("--src", required=True)
    p.add_argument("--dst")
    p.add_argument("--mode", required=True, choices=["resize", "enhance", "interpolate", "compress"])
    p.add_argument("--scale", type=float, default=2)
    p.add_argument("--interpolate", type=int, choices=[0, 2, 4], default=0)
    p.add_argument("--crf", type=int, default=17)
    p.add_argument("--max-crf", type=int, default=23)
    p.add_argument("--target-mb", type=float, default=0)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model", default="realesrgan-plus")
    args = p.parse_args()
    if not 0 <= args.crf <= 51 or not 0 <= args.max_crf <= 51:
        p.error("CRF must be 0..51")
    if args.mode == "enhance" and (args.scale != int(args.scale) or not 1 <= args.scale <= 4):
        p.error("Enhance scale must be integer 1..4")
    src = Path(args.src)
    if not src.exists():
        p.error(f"Source does not exist: {src}")
    is_dir = src.is_dir()
    files = sorted(x for x in src.iterdir() if x.is_file() and x.suffix.lower() in EXTS) if is_dir else [src]
    if not files:
        p.error("No videos found")
    for f in files:
        if f.suffix.lower() not in EXTS:
            p.error("Unsupported source format")
        suffix = "_" + args.mode
        if args.interpolate:
            suffix += f"_fpsx{args.interpolate}"
        if args.dst and not is_dir and Path(args.dst).suffix.lower() == ".mp4":
            dst = Path(args.dst)
        else:
            folder = Path(args.dst) if args.dst else f.parent / "processed"
            dst = folder / (f.stem + suffix + ".mp4")
        if dst.resolve() == f.resolve():
            p.error("Cannot overwrite source")
        print(f"{f} -> {dst}", flush=True)
        if args.dry_run:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        process(f, dst, args)
        print(f"OK {dst.stat().st_size} bytes", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

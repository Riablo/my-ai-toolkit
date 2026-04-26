#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow>=10.0.0"]
# ///
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from sprite_utils import (
    DEFAULT_BACKGROUND,
    DEFAULT_TOLERANCE,
    default_output_dir,
    parse_hex_color,
    prepare_frames,
    print_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a 1-second video from a 4x4 sprite sheet after per-frame chroma key removal.",
    )
    parser.add_argument("input", type=Path, help="Path to the generated 4x4 sprite sheet PNG.")
    parser.add_argument("--output-dir", type=Path, help="Directory for generated files.")
    parser.add_argument("--name", help="Output filename stem. Defaults to the input filename stem.")
    parser.add_argument("--cols", type=int, default=4, help="Sprite sheet columns. Default: 4.")
    parser.add_argument("--rows", type=int, default=4, help="Sprite sheet rows. Default: 4.")
    parser.add_argument(
        "--background",
        default=DEFAULT_BACKGROUND,
        help="Background chroma key color to remove. Default: #ff00ff.",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=DEFAULT_TOLERANCE,
        help="RGB tolerance for background removal. Default: 100.",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=1.0,
        help="Output duration in seconds. Default: 1.0.",
    )
    parser.add_argument(
        "--format",
        choices=("mp4", "mov", "webm"),
        default="mp4",
        help="Output video format. Default: mp4.",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=30,
        help="MP4 H.264 CRF quality value. Higher is smaller. Default: 30.",
    )
    parser.add_argument(
        "--matte-color",
        default="#000000",
        help="Matte color used when encoding non-alpha MP4. Default: #000000.",
    )
    return parser


def require_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    raise RuntimeError("ffmpeg is required to create video output but was not found in PATH")


def main() -> None:
    args = build_parser().parse_args()
    if args.duration_seconds <= 0:
        raise ValueError("--duration-seconds must be greater than 0")

    background = parse_hex_color(args.background)
    matte = parse_hex_color(args.matte_color)
    result = prepare_frames(
        input_path=args.input,
        output_dir=args.output_dir,
        name=args.name,
        cols=args.cols,
        rows=args.rows,
        background=background,
        tolerance=args.tolerance,
    )

    output_dir = args.output_dir or default_output_dir(args.input)
    name = args.name or args.input.stem
    video_path = output_dir / f"{name}.{args.format}"
    frame_count = len(result.frames)
    fps = frame_count / args.duration_seconds

    ffmpeg = require_ffmpeg()
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        f"{fps:.6f}",
        "-start_number",
        "1",
        "-i",
        str(result.frames_dir / "frame-%02d.png"),
        "-frames:v",
        str(frame_count),
        "-an",
    ]
    if args.format == "mp4":
        matte_filter = (
            f"color=c=0x{matte[0]:02x}{matte[1]:02x}{matte[2]:02x}:"
            f"s={result.frame_size[0]}x{result.frame_size[1]}:r={fps:.6f}[bg];"
            "[bg][0:v]overlay=format=auto,format=yuv420p"
        )
        command += [
            "-filter_complex",
            matte_filter,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(args.crf),
            "-profile:v",
            "high",
            "-level",
            "4.0",
            "-movflags",
            "+faststart",
        ]
    elif args.format == "mov":
        command += ["-c:v", "qtrle", "-pix_fmt", "argb"]
    else:
        command += [
            "-c:v",
            "libvpx-vp9",
            "-lossless",
            "1",
            "-pix_fmt",
            "yuva420p",
            "-auto-alt-ref",
            "0",
            "-metadata:s:v:0",
            "alpha_mode=1",
        ]
    command.append(str(video_path))
    subprocess.run(command, check=True)

    outputs = {
        "original": result.original_path,
        "video": video_path,
        "transparent_frames": result.frames_dir,
        "frame_width": result.frame_size[0],
        "frame_height": result.frame_size[1],
        "frames": frame_count,
        "duration_seconds": args.duration_seconds,
        "fps": f"{fps:.6f}",
        "format": args.format,
    }
    if args.format == "mp4":
        outputs["mp4_crf"] = args.crf
        outputs["matte_color"] = args.matte_color
    print_outputs(outputs)


if __name__ == "__main__":
    main()

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow>=10.0.0"]
# ///
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from sprite_utils import (
    DEFAULT_BACKGROUND,
    DEFAULT_TOLERANCE,
    parse_hex_color,
    prepare_frames,
    print_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a looping GIF from a 4x4 sprite sheet after per-frame chroma key removal.",
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
        "--duration-ms",
        type=int,
        default=80,
        help="Frame duration in milliseconds. Default: 80.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    background = parse_hex_color(args.background)
    result = prepare_frames(
        input_path=args.input,
        output_dir=args.output_dir,
        name=args.name,
        cols=args.cols,
        rows=args.rows,
        background=background,
        tolerance=args.tolerance,
    )

    output_dir = args.output_dir or args.input.resolve().parent / f"{args.input.stem}-sprite-output"
    name = args.name or args.input.stem
    gif_path = output_dir / f"{name}.gif"

    first, *rest = result.frames
    first.save(
        gif_path,
        save_all=True,
        append_images=rest,
        duration=args.duration_ms,
        loop=0,
        disposal=2,
    )

    print_outputs(
        {
            "original": result.original_path,
            "gif": gif_path,
            "transparent_frames": result.frames_dir,
            "frame_width": result.frame_size[0],
            "frame_height": result.frame_size[1],
            "frames": len(result.frames),
        }
    )


if __name__ == "__main__":
    main()

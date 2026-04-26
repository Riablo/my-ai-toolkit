from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


DEFAULT_BACKGROUND = "#ff00ff"
DEFAULT_TOLERANCE = 100


@dataclass(frozen=True)
class SpriteProcessResult:
    original_path: Path
    frames_dir: Path
    frames: list[Image.Image]
    frame_size: tuple[int, int]


def parse_hex_color(value: str) -> tuple[int, int, int]:
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        raise ValueError(f"expected a 6-digit hex color, got {value!r}")
    try:
        return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError as exc:
        raise ValueError(f"invalid hex color: {value!r}") from exc


def default_output_dir(input_path: Path) -> Path:
    return input_path.resolve().parent / f"{input_path.stem}-sprite-output"


def copy_original(input_path: Path, output_dir: Path, name: str) -> Path:
    suffix = input_path.suffix or ".png"
    target = output_dir / f"{name}-original{suffix}"
    if input_path.resolve() != target.resolve():
        shutil.copy2(input_path, target)
    return target


def crop_frames(sheet: Image.Image, cols: int, rows: int) -> list[Image.Image]:
    if cols <= 0 or rows <= 0:
        raise ValueError("cols and rows must be positive integers")
    width, height = sheet.size
    if width % cols != 0 or height % rows != 0:
        raise ValueError(
            f"sheet size {width}x{height} is not evenly divisible by {cols}x{rows}"
        )

    frame_width = width // cols
    frame_height = height // rows
    frames: list[Image.Image] = []
    for row in range(rows):
        for col in range(cols):
            box = (
                col * frame_width,
                row * frame_height,
                (col + 1) * frame_width,
                (row + 1) * frame_height,
            )
            frames.append(sheet.crop(box).convert("RGBA"))
    return frames


def remove_background(
    frame: Image.Image,
    background: tuple[int, int, int],
    tolerance: int,
) -> Image.Image:
    if tolerance < 0:
        raise ValueError("tolerance must be 0 or greater")

    rgba = frame.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    red, green, blue = background

    for y in range(height):
        for x in range(width):
            pr, pg, pb, pa = pixels[x, y]
            if (
                abs(pr - red) <= tolerance
                and abs(pg - green) <= tolerance
                and abs(pb - blue) <= tolerance
            ):
                pixels[x, y] = (pr, pg, pb, 0)
            else:
                pixels[x, y] = (pr, pg, pb, pa)
    return rgba


def prepare_frames(
    input_path: Path,
    output_dir: Path | None,
    name: str | None,
    cols: int,
    rows: int,
    background: tuple[int, int, int],
    tolerance: int,
) -> SpriteProcessResult:
    if not input_path.exists():
        raise FileNotFoundError(f"input file does not exist: {input_path}")

    output = output_dir or default_output_dir(input_path)
    output.mkdir(parents=True, exist_ok=True)

    output_name = name or input_path.stem
    original_path = copy_original(input_path, output, output_name)

    with Image.open(input_path) as image:
        sheet = image.convert("RGBA")
        raw_frames = crop_frames(sheet, cols, rows)

    frames_dir = output / "frames-transparent"
    frames_dir.mkdir(parents=True, exist_ok=True)

    transparent_frames: list[Image.Image] = []
    for index, frame in enumerate(raw_frames, start=1):
        transparent = remove_background(frame, background, tolerance)
        transparent.save(frames_dir / f"frame-{index:02d}.png")
        transparent_frames.append(transparent)

    frame_size = transparent_frames[0].size if transparent_frames else (0, 0)
    return SpriteProcessResult(
        original_path=original_path,
        frames_dir=frames_dir,
        frames=transparent_frames,
        frame_size=frame_size,
    )


def print_outputs(paths: dict[str, Path | str | int]) -> None:
    for key, value in paths.items():
        print(f"{key}: {value}")

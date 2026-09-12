# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11,<13"]
# ///
"""只读检查 PNG 图标属性；不判断风格或修复图片像素。"""

import argparse
import json
from pathlib import Path

from PIL import Image

VISIBILITY_ALPHA = 16  # 忽略几乎不可见的 alpha 噪点，仅用于边界判断。


def inspect_icon(path: Path) -> dict:
    result = {"path": str(path), "errors": [], "warnings": []}
    try:
        with Image.open(path) as image:
            image.load()
            result.update(format=image.format, mode=image.mode, size=list(image.size))
            if image.format != "PNG":
                result["errors"].append("文件不是 PNG")
            if image.width != image.height:
                result["errors"].append("画布不是正方形")
            if min(image.size) < 512:
                result["warnings"].append("原图小于 512 像素，作为长期参考时细节可能不足")
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            if not has_alpha:
                result["errors"].append("没有透明通道；棋盘格外观不能证明透明")
            else:
                alpha = image.convert("RGBA").getchannel("A")
                low, high = alpha.getextrema()
                result["alpha_range"] = [low, high]
                result["alpha_bbox"] = alpha.getbbox()
                visible = alpha.point([0] * (VISIBILITY_ALPHA + 1)
                                      + [255] * (255 - VISIBILITY_ALPHA))
                bbox = visible.getbbox()
                result["visible_bbox"] = bbox
                result["visibility_alpha_threshold"] = VISIBILITY_ALPHA
                if low != 0:
                    result["errors"].append("没有完全透明的像素")
                if high == 0:
                    result["errors"].append("图像完全透明，没有可见主体")
                elif high <= VISIBILITY_ALPHA:
                    result["errors"].append("主体几乎不可见，检查透明度")
                corners = [(0, 0), (image.width - 1, 0),
                           (0, image.height - 1), (image.width - 1, image.height - 1)]
                if any(alpha.getpixel(point) != 0 for point in corners):
                    result["errors"].append("画布角落不透明，检查背景或裁切")
                if bbox and (bbox[0] == 0 or bbox[1] == 0
                             or bbox[2] == image.width or bbox[3] == image.height):
                    result["warnings"].append("可见像素触及画布边缘，检查留白和裁切")
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        result["errors"].append(f"无法读取图片：{exc}")
    result["file_checks_passed"] = not result["errors"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", type=Path, help="待检查的 PNG 图标路径")
    reports = [inspect_icon(path) for path in parser.parse_args().images]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0 if all(report["file_checks_passed"] for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())

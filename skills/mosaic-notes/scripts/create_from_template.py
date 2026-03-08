#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""
create_from_template.py - 从 Obsidian 模板创建笔记

用法: uv run create_from_template.py --vault <vault_path> --template <template_name> --name <title> --path <relative_path>

模板变量替换:
  {{date}} / {{date:FORMAT}} -> 当前日期 (默认 YYYY-MM-DD)
  {{title}}                  -> 笔记标题 (--name 参数)
  {{time}} / {{time:FORMAT}} -> 当前时间 (默认 HH:mm)

FORMAT 使用 Obsidian (moment.js) 格式，如 YYYY-MM-DD、HH:mm:ss。
"""

import argparse
import os
import re
import sys
from datetime import datetime


# moment.js -> strftime 映射，按长度降序替换避免冲突
MOMENT_TO_STRFTIME = [
    ("YYYY", "%Y"),
    ("YY", "%y"),
    ("MMMM", "%B"),
    ("MMM", "%b"),
    ("MM", "%m"),
    ("DD", "%d"),
    ("dddd", "%A"),
    ("ddd", "%a"),
    ("HH", "%H"),
    ("hh", "%I"),
    ("mm", "%M"),
    ("ss", "%S"),
    ("A", "%p"),
    ("a", "%p"),
]


def moment_to_strftime(fmt):
    """将 moment.js 格式转为 Python strftime 格式"""
    result = fmt
    for moment_fmt, py_fmt in MOMENT_TO_STRFTIME:
        result = result.replace(moment_fmt, py_fmt)
    return result


def substitute_variables(content, title):
    """替换 Obsidian 模板变量"""
    now = datetime.now()

    content = content.replace("{{title}}", title)

    def replace_date(m):
        fmt = m.group(1)
        if fmt:
            return now.strftime(moment_to_strftime(fmt))
        return now.strftime("%Y-%m-%d")

    def replace_time(m):
        fmt = m.group(1)
        if fmt:
            return now.strftime(moment_to_strftime(fmt))
        return now.strftime("%H:%M")

    content = re.sub(r"\{\{date(?::([^}]+))?\}\}", replace_date, content)
    content = re.sub(r"\{\{time(?::([^}]+))?\}\}", replace_time, content)

    return content


def main():
    parser = argparse.ArgumentParser(description="从 Obsidian 模板创建笔记")
    parser.add_argument("--vault", required=True, help="Vault 绝对路径")
    parser.add_argument(
        "--template",
        required=True,
        help="模板名称（不含 'TPL - ' 前缀，如 'Daily Notes'）",
    )
    parser.add_argument("--name", required=True, help="笔记标题")
    parser.add_argument(
        "--path", required=True, help="相对于 vault 的目标路径（如 'Inbox/Title.md'）"
    )
    args = parser.parse_args()

    template_file = os.path.join(args.vault, "Templates", f"TPL - {args.template}.md")
    if not os.path.exists(template_file):
        print(f"错误: 模板不存在: {template_file}", file=sys.stderr)
        sys.exit(1)

    target = os.path.join(args.vault, args.path)

    if os.path.exists(target):
        print(f"跳过: 文件已存在: {target}")
        sys.exit(0)

    with open(template_file, encoding="utf-8") as f:
        content = f.read()

    content = substitute_variables(content, args.name)

    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"已创建: {target}")


if __name__ == "__main__":
    main()

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""
rollover_tasks.py - 把昨天 Daily Note 里未完成的任务移动到今天（移动，非复制）

用法: uv run rollover_tasks.py --vault <vault_path> [--from YYYY-MM-DD] [--to YYYY-MM-DD]

默认行为：--from 昨天，--to 今天
"""

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path


TASKS_HEADING = "## ✅ Tasks"
NOTES_HEADING = "## 📝 Notes"


def get_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def is_task_item(line: str) -> bool:
    return bool(re.match(r"^\s*- \[.\]", line))


def is_unchecked(line: str) -> bool:
    return bool(re.match(r"^\s*- \[ \]", line))


def parse_task_blocks(lines: list[str]) -> list[list[str]]:
    """
    将 Tasks 区块内容行解析为顶层任务块列表。
    每个块 = 一个顶层 task item（缩进=0）+ 其后所有缩进更深的行。
    """
    blocks: list[list[str]] = []
    current_block: list[str] | None = None

    for line in lines:
        if not line.strip():
            if current_block is not None:
                current_block.append(line)
            continue

        if is_task_item(line) and get_indent(line) == 0:
            if current_block is not None:
                blocks.append(current_block)
            current_block = [line]
        else:
            if current_block is not None:
                current_block.append(line)

    if current_block is not None:
        blocks.append(current_block)

    # 去除每个块尾部的空行
    for block in blocks:
        while block and not block[-1].strip():
            block.pop()

    return blocks


def block_has_unchecked(block: list[str]) -> bool:
    return any(is_unchecked(l) for l in block)


def extract_task_section_bounds(lines: list[str]) -> tuple[int | None, int | None]:
    """返回 Tasks 区块标题行索引和结束行索引（下一个 ## 标题或文件末尾）"""
    tasks_start = None
    tasks_end = None
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if stripped == TASKS_HEADING:
            tasks_start = i
        elif tasks_start is not None and re.match(r"^## ", stripped):
            tasks_end = i
            break
    if tasks_start is not None and tasks_end is None:
        tasks_end = len(lines)
    return tasks_start, tasks_end


def rebuild_source(src_lines: list[str], keep_blocks: list[list[str]],
                   tasks_start: int, tasks_end: int) -> list[str]:
    """用 keep_blocks 重建源文件的 Tasks 区块"""
    before = src_lines[:tasks_start + 1]  # 包含标题行
    after = src_lines[tasks_end:]

    middle: list[str] = ["\n"]  # 标题后空一行
    for block in keep_blocks:
        for line in block:
            middle.append(line if line.endswith("\n") else line + "\n")
    if keep_blocks:
        middle.append("\n")  # 内容后空一行（与下一个 ## 分隔）

    return before + middle + after


def insert_tasks_into_dst(dst_lines: list[str], new_blocks: list[list[str]]) -> list[str]:
    """
    将 new_blocks 插入到目标 Daily Note 的 ## ✅ Tasks 区块末尾。
    格式：标题后一个空行，任务项之间无空行。
    """
    tasks_start, tasks_end = extract_task_section_bounds(dst_lines)

    # 构建要插入的行（无块间空行）
    to_insert: list[str] = []
    for block in new_blocks:
        for line in block:
            to_insert.append(line if line.endswith("\n") else line + "\n")

    if tasks_start is None:
        # 没有 Tasks 区块，追加到末尾
        result = list(dst_lines)
        if result and result[-1].strip():
            result.append("\n")
        result.append(TASKS_HEADING + "\n")
        result.append("\n")
        result.extend(to_insert)
        result.append("\n")
        return result

    # 找到 Tasks 区块内现有内容的实际结束位置（排除尾部空行）
    actual_end = tasks_end
    while actual_end > tasks_start + 1 and not dst_lines[actual_end - 1].strip():
        actual_end -= 1

    # 检查标题后是否已有内容
    section_content = dst_lines[tasks_start + 1:actual_end]
    has_existing = any(l.strip() for l in section_content)

    result = list(dst_lines)
    if has_existing:
        # 已有内容，直接在末尾追加（无额外空行）
        result[actual_end:actual_end] = to_insert
    else:
        # 区块为空，标题后插入一个空行再接任务
        insert_at = tasks_start + 1
        # 移除标题后已有的空行，重新控制
        while insert_at < tasks_end and not result[insert_at].strip():
            result.pop(insert_at)
            tasks_end -= 1
            actual_end -= 1
        result[insert_at:insert_at] = ["\n"] + to_insert

    # 确保区块末尾有一个空行（与下一个 ## 分隔）
    # 找到插入后的新结束位置
    new_end = tasks_start + 1
    while new_end < len(result):
        if re.match(r"^## ", result[new_end].rstrip("\n")):
            break
        new_end += 1
    # 去除尾部多余空行，保留一个
    while new_end > tasks_start + 1 and not result[new_end - 1].strip():
        result.pop(new_end - 1)
        new_end -= 1
    result.insert(new_end, "\n")

    return result


def daily_note_path(vault: Path, d: date) -> Path:
    return vault / "Library" / f"{d.isoformat()}.md"


def main():
    parser = argparse.ArgumentParser(description="把昨天未完成的任务移动到今天")
    parser.add_argument("--vault", required=True, help="Vault 根目录路径")
    parser.add_argument("--from", dest="from_date", help="源日期 YYYY-MM-DD（默认昨天）")
    parser.add_argument("--to", dest="to_date", help="目标日期 YYYY-MM-DD（默认今天）")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser()
    today = date.today()
    yesterday = today - timedelta(days=1)

    from_date = date.fromisoformat(args.from_date) if args.from_date else yesterday
    to_date = date.fromisoformat(args.to_date) if args.to_date else today

    src_path = daily_note_path(vault, from_date)
    dst_path = daily_note_path(vault, to_date)

    if not src_path.exists():
        print(f"源文件不存在：{src_path}", file=sys.stderr)
        sys.exit(1)

    src_text = src_path.read_text(encoding="utf-8")
    src_lines = src_text.splitlines(keepends=True)

    tasks_start, tasks_end = extract_task_section_bounds(src_lines)
    if tasks_start is None:
        print(f"{from_date} 没有 Tasks 区块，无需转移。")
        return

    section_lines = [l.rstrip("\n") for l in src_lines[tasks_start + 1:tasks_end]]
    all_blocks = parse_task_blocks(section_lines)

    move_blocks = [b for b in all_blocks if block_has_unchecked(b)]
    keep_blocks = [b for b in all_blocks if not block_has_unchecked(b)]

    if not move_blocks:
        print(f"{from_date} 没有未完成的任务，无需转移。")
        return

    count = sum(1 for b in move_blocks for l in b if is_unchecked(l))
    print(f"找到 {count} 个未完成任务，从 {from_date} 移动到 {to_date}...")

    # 写入目标文件
    if dst_path.exists():
        dst_lines = dst_path.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        print(f"目标文件不存在，创建：{dst_path}")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_lines = [f"{TASKS_HEADING}\n", "\n", f"{NOTES_HEADING}\n"]

    dst_result = insert_tasks_into_dst(dst_lines, move_blocks)
    dst_path.write_text("".join(dst_result), encoding="utf-8")

    # 从源文件删除已转移的任务
    src_result = rebuild_source(src_lines, keep_blocks, tasks_start, tasks_end)
    src_path.write_text("".join(src_result), encoding="utf-8")

    print("完成。已转移：")
    for block in move_blocks:
        for line in block:
            if is_unchecked(line):
                print(f"  {line.strip()}")


if __name__ == "__main__":
    main()

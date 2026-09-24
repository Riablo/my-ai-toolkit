#!/usr/bin/env python3
"""Validate and merge htask's global and project TOML configurations."""

import json
import re
import sys
import tomllib
from pathlib import Path

AGENTS = ("pi", "codex")
LEVELS = {"off", "minimal", "low", "medium", "high", "xhigh", "max"}
ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def fail(path: Path, message: str) -> None:
    raise ValueError(f"配置无效 {path}：{message}")


def check_keys(value: dict, allowed: set[str], path: Path, label: str) -> None:
    unknown = value.keys() - allowed
    if unknown:
        fail(path, f"{label} 有未知字段：{', '.join(sorted(unknown))}")


def load(path: Path) -> dict:
    legacy = path.with_suffix(".json")
    if legacy.exists() or legacy.is_symlink():
        fail(legacy, f"旧版 JSON 配置仍存在；请迁移到 {path} 并移走旧文件")
    if not path.exists() and not path.is_symlink():
        return {}
    if not path.is_file():
        fail(path, "不是普通文件")
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        fail(path, f"TOML 语法错误：{exc}")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        fail(path, "schema_version 必须为 1")
    check_keys(data, {"schema_version", "init", "dev", "dev_profiles", "models"}, path, "根配置")
    for name in ("init", "dev"):
        if name in data and (not isinstance(data[name], list) or any(
            not isinstance(command, str) or not command.strip() for command in data[name]
        )):
            fail(path, f"{name} 必须是非空命令组成的字符串数组（可为空数组）")
    profiles = data.get("dev_profiles", {})
    if not isinstance(profiles, dict):
        fail(path, "dev_profiles 必须是表")
    for name, commands in profiles.items():
        if not ALIAS.fullmatch(name) or not isinstance(commands, list) or not commands or any(
            not isinstance(command, str) or not command.strip() for command in commands
        ):
            fail(path, f"dev_profiles.{name} 必须是非空命令字符串数组，名称不能含空格")
    models = data.get("models", {})
    if not isinstance(models, dict):
        fail(path, "models 必须是表")
    check_keys(models, set(AGENTS), path, "models")
    for agent, presets in models.items():
        if not isinstance(presets, dict):
            fail(path, f"models.{agent} 必须是表")
        for alias, spec in presets.items():
            if not ALIAS.fullmatch(alias) or not isinstance(spec, dict):
                fail(path, f"{agent} 的预设名称或结构无效：{alias}")
            check_keys(spec, {"model", "thinking"}, path, f"{agent}.{alias}")
            for key, value in spec.items():
                if not isinstance(value, str) or not value.strip() or value != value.strip():
                    fail(path, f"{agent}.{alias}.{key} 必须是非空字符串且无首尾空格")
                if key == "thinking" and value not in LEVELS:
                    fail(path, f"{agent}.{alias}.thinking 无效：{value}")
    return data


def main(global_path: Path, project_path: Path) -> None:
    merged = {"init": [], "dev": [], "dev_profiles": {}, "models": {agent: {} for agent in AGENTS}}
    for path in (global_path, project_path):
        data = load(path)
        for name in ("init", "dev"):
            if name in data:
                merged[name] = data[name]
        merged["dev_profiles"].update(data.get("dev_profiles", {}))
        for agent, presets in data.get("models", {}).items():
            for alias, spec in presets.items():
                merged["models"][agent].setdefault(alias, {}).update(spec)
    for agent, presets in merged["models"].items():
        for alias, spec in presets.items():
            model = spec.get("model", "")
            if not model:
                fail(project_path, f"{agent}.{alias} 合并后缺少 model")
            if any(char.isspace() for char in model):
                fail(project_path, f"{agent}.{alias}.model 不能含空白字符")
            if agent == "pi" and (model.count("/") != 1 or not all(model.split("/"))):
                fail(project_path, f"{agent}.{alias}.model 必须是 provider/model")
    print(json.dumps(merged, ensure_ascii=False))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("用法：config.py <全局配置路径> <项目配置路径>")
        main(Path(sys.argv[1]), Path(sys.argv[2]))
    except (ValueError, OSError) as error:
        print(f"错误：{error}", file=sys.stderr)
        sys.exit(1)

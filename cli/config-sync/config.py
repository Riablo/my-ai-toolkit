#!/usr/bin/env python3
"""Validate config-sync's TOML and emit a plan before any SSH operation."""

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    sys.exit("错误：需要 Python 3.11+（brew install python）")

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
SSH = re.compile(r"(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9][A-Za-z0-9_.-]*")


def keys(value: object, allowed: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} 必须是 TOML 表")
    unknown = value.keys() - allowed
    if unknown:
        raise ValueError(f"{label} 有未知字段：{', '.join(sorted(unknown))}")
    return value


def path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or any(
        ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise ValueError(f"{label} 必须是非空路径，不能含控制字符")
    if not value.startswith(("/", "~/")):
        raise ValueError(f"{label} 必须使用绝对路径或 ~/ 开头的路径")
    prefix = "~/" if value.startswith("~/") else "/"
    parts = [part for part in value[len(prefix):].split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        raise ValueError(f"{label} 不能是根目录、家目录，或包含 . / .. 路径段")
    if any(part.endswith(".config-sync-backups") for part in parts):
        raise ValueError(f"{label} 不能使用本工具保留的 .config-sync-backups 路径")
    return prefix + "/".join(parts)


def load(config: Path) -> dict:
    if not config.exists() and not config.is_symlink():
        return {}
    with config.open("rb") as stream:
        data = keys(tomllib.load(stream), {"hosts"}, "根配置")
    hosts = data.get("hosts", {})
    if not isinstance(hosts, dict):
        raise ValueError("hosts 必须是 TOML 表")
    result = {}
    destinations: dict[str, list[str]] = {}
    for host, raw in hosts.items():
        if not NAME.fullmatch(host):
            raise ValueError(f"主机名称无效：{host}；只支持字母、数字、_、-、.")
        spec = keys(raw, {"ssh", "files", "dirs"}, f"hosts.{host}")
        endpoint = spec.get("ssh", host)
        if not isinstance(endpoint, str) or not SSH.fullmatch(endpoint):
            raise ValueError(f"hosts.{host}.ssh 必须是 SSH 别名、主机名或 user@host；端口请配置在 ~/.ssh/config")
        items = {}
        for kind in ("files", "dirs"):
            entries = spec.get(kind, {})
            if not isinstance(entries, dict):
                raise ValueError(f"hosts.{host}.{kind} 必须是 TOML 表")
            for name, value in entries.items():
                label = f"hosts.{host}.{kind}.{name}"
                if not NAME.fullmatch(name) or name in items:
                    raise ValueError(f"{label} 标签无效或重复")
                if isinstance(value, str):
                    source = destination = path(value, label)
                elif isinstance(value, list) and len(value) == 2:
                    source = path(value[0], f"{label}[0] 本机路径")
                    destination = path(value[1], f"{label}[1] 目标路径")
                else:
                    raise ValueError(f"{label} 必须是一个路径字符串或 [本机路径, 目标路径]")
                previous = destinations.setdefault(endpoint, [])
                if any(destination == other or destination.startswith(other + "/")
                       or other.startswith(destination + "/") for other in previous):
                    raise ValueError(f"{label} 与同一 SSH 主机上的其他目标路径重复或嵌套")
                previous.append(destination)
                items[name] = (kind, os.path.expanduser(source), destination)
        result[host] = (endpoint, items)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("action", choices=("init", "sync", "clean", "list", "complete-hosts"))
    parser.add_argument("--hosts", nargs="*", default=[])
    args = parser.parse_args()
    if args.action == "init":
        template = Path(__file__).with_name("config.example.toml").read_bytes()
        args.config.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            descriptor = os.open(args.config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise ValueError(f"配置路径已存在，不覆盖：{args.config}") from None
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(template)
        print(f"已创建配置模板：{args.config}\n所有示例均已注释；请取消所需表头和配置项的注释，并修改主机 / 路径后使用。")
        return
    hosts = load(args.config)
    if args.action == "complete-hosts":
        print("\n".join(hosts), end="\n" if hosts else "")
        return
    for host in args.hosts:
        if host not in hosts:
            raise ValueError(f"未配置目标主机：{host}")
    selected = list(dict.fromkeys(args.hosts)) if args.hosts else list(hosts)
    rows = []
    for host in selected:
        endpoint, items = hosts[host]
        for name, (kind, source, destination) in items.items():
            if args.action == "list":
                print(f"{host} (ssh {endpoint})  {name} [{kind}]  {source} → {destination}")
            else:
                rows.extend((host, endpoint, kind, name, source, destination))
    # Validate the complete local plan before emitting any row or contacting SSH.
    if args.action == "sync":
        for index in range(0, len(rows), 6):
            _, _, kind, name, source, _ = rows[index:index + 6]
            valid = Path(source).is_file() if kind == "files" else Path(source).is_dir()
            if not valid:
                raise ValueError(f"同步项 {name} 的本机{'文件' if kind == 'files' else '目录'}不存在或类型不符：{source}")
            if kind == "files":
                # Resolve local file links without openrsync's unreliable -L behavior.
                rows[index + 4] = path(str(Path(source).resolve()), f"同步项 {name} 的实际文件路径")
    if rows:
        print("\n".join(rows))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"错误：{error}", file=sys.stderr)
        sys.exit(1)

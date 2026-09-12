# /// script
# requires-python = ">=3.10"
# dependencies = ["cos-python-sdk-v5==1.9.44"]
# ///
"""腾讯云 COS 图片上传，保持 Raycast tencent-oss 的对象命名规则。"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import mimetypes
import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

APP = "cos-cli"
CONFIG_PATH = Path.home() / ".config" / APP / "config.json"
SECRET_FIELDS = ("secret_id", "secret_key", "security_token")
IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".avif": "image/avif",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".ico": "image/x-icon",
    ".apng": "image/apng",
    ".jxl": "image/jxl",
}


class CLIError(Exception):
    pass


def default_config() -> dict:
    # 非敏感默认值取自用户的 Raycast 插件 preferences。
    return {
        "secret_id": "",
        "secret_key": "",
        "bucket": "static720-1347846699",
        "region": "ap-beijing",
        "domain": "https://static-t.720static.com",
        "prefix": "imgs",
        "use_md5": True,
        "security_token": "",
        "timeout": 60,
    }


def has_control(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def normalize_prefix(value: str) -> str:
    if not isinstance(value, str) or has_control(value) or "\\" in value:
        raise CLIError("prefix 必须是字符串，不能包含控制字符或反斜杠")
    parts = [part for part in value.split("/") if part and part != "."]
    if ".." in parts:
        raise CLIError("prefix 不能包含 .. 路径段")
    return "/".join(parts)


def validate_config(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise CLIError("配置文件的顶层必须是 JSON 对象")
    unknown = set(raw) - set(default_config())
    if unknown:
        raise CLIError("配置含未知字段，请对照 README 中的配置表修复")
    config = default_config()
    # bucket / region 不能因字段缺失而静默回退到另一个上传目标。
    for field in ("secret_id", "secret_key", "bucket", "region"):
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CLIError(f"配置缺少必填字段或值为空：{field}")
        if value != value.strip() or has_control(value):
            raise CLIError(f"配置字段 {field} 不能包含首尾空白或控制字符")
    config.update(raw)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*-[0-9]+", config["bucket"]):
        raise CLIError("bucket 格式无效，应为存储桶名称-APPID")
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+", config["region"]):
        raise CLIError("region 格式无效，例如 ap-beijing")
    # domain 缺省时使用实际配置的 COS 源站，模板则沿用 Raycast 自定义域名。
    domain = raw.get("domain", "")
    if not isinstance(domain, str):
        raise CLIError("domain 必须是字符串，留空表示使用 COS 默认域名")
    if domain:
        try:
            parsed = urlsplit(domain)
            valid = (
                parsed.scheme in ("http", "https")
                and parsed.hostname
                and parsed.username is None
                and parsed.password is None
                and "?" not in domain
                and "#" not in domain
                and not any(char.isspace() for char in domain)
                and not has_control(domain)
                and "\\" not in domain
            )
            _ = parsed.port  # 同时检查端口格式。
        except ValueError:
            valid = False
        if not valid:
            raise CLIError(
                "domain 需为完整 HTTP(S) 地址，不能包含账号、空白、查询参数或片段"
            )
    config["domain"] = domain.rstrip("/")
    config["prefix"] = normalize_prefix(config["prefix"])
    if type(config["use_md5"]) is not bool:
        raise CLIError("use_md5 必须是 JSON 布尔值 true 或 false")
    if type(config["timeout"]) is not int or not 1 <= config["timeout"] <= 3600:
        raise CLIError("timeout 必须是 1 到 3600 之间的整数（秒）")
    token = config["security_token"]
    if not isinstance(token, str) or token != token.strip() or has_control(token):
        raise CLIError("security_token 必须是字符串，且不能包含首尾空白或控制字符")
    return config


def load_config(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        raise CLIError(
            f"配置文件不存在：{path}\n请先运行 {APP} --config '{path}' config init"
        ) from None
    except json.JSONDecodeError as error:
        raise CLIError(
            f"配置 JSON 格式错误：第 {error.lineno} 行，第 {error.colno} 列（{path}）"
        ) from None
    except UnicodeError:
        raise CLIError(f"配置文件必须使用 UTF-8 编码：{path}") from None
    except OSError:
        raise CLIError(f"无法读取配置文件，请检查路径及权限：{path}") from None
    try:
        return validate_config(raw)
    except CLIError as error:
        raise CLIError(f"{error}\n请编辑配置文件：{path}") from None


def init_config(path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise CLIError(f"配置文件已存在，未覆盖：{path}") from None
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(default_config(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        f"已创建配置模板：{path}\n请填写 secret_id、secret_key，并核对 bucket、region 和 domain。"
    )


def collect_files(inputs: list[str], all_files: bool) -> list[tuple[Path, Path]]:
    collected: list[tuple[Path, Path]] = []

    def walk_error(error: OSError) -> None:
        raise CLIError(f"无法扫描目录：{error.filename}")

    for value in inputs:
        local = Path(os.path.abspath(os.path.expanduser(value)))
        if local.is_symlink():
            raise CLIError(f"不支持符号链接，请传入实际文件或文件夹：{local}")
        if local.is_dir():
            for directory, dirs, files in os.walk(
                local, onerror=walk_error, followlinks=False
            ):
                dirs[:] = sorted(
                    name for name in dirs if not (Path(directory) / name).is_symlink()
                )
                for name in sorted(files):
                    file = Path(directory) / name
                    if file.is_symlink() or not file.is_file():
                        continue
                    if all_files or file.suffix.lower() in IMAGE_TYPES:
                        collected.append(
                            (file, Path(local.name) / file.relative_to(local))
                        )
        elif local.is_file():
            if not all_files and local.suffix.lower() not in IMAGE_TYPES:
                raise CLIError(
                    f"不是支持的图片扩展名：{local}；上传其他文件请加 --all-files"
                )
            collected.append((local, Path(local.name)))
        else:
            raise CLIError(f"路径不存在或不是普通文件／文件夹：{local}")
    if not collected:
        raise CLIError(
            "未找到可上传的图片；文件夹会递归筛选图片，上传所有文件可加 --all-files"
        )
    return collected


def file_fingerprint(path: Path) -> tuple:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise CLIError(f"文件已不再是普通文件：{path}")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def plan_uploads(files: list[tuple[Path, Path]], config: dict) -> list[dict]:
    plans: list[dict] = []
    targets: dict[str, Path] = {}
    base_url = (
        config["domain"]
        or f"https://{config['bucket']}.cos.{config['region']}.myqcloud.com"
    )
    for local, relative in files:
        if has_control(relative.as_posix()) or "\\" in relative.as_posix():
            raise CLIError(f"文件名不能包含控制字符或反斜杠：{str(local)!r}")
        before = file_fingerprint(local)
        digest = hashlib.md5()
        # 即使关闭 MD5，也先打开全部文件，以便在发起上传前发现读取权限错误。
        with local.open("rb") as handle:
            if config["use_md5"]:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        if file_fingerprint(local) != before:
            raise CLIError(f"文件在预览期间发生变化，请重试：{local}")
        filename = relative.name
        if config["use_md5"]:
            filename = f"{relative.stem}.{digest.hexdigest()}{relative.suffix}"
        key = "/".join(
            part
            for part in (config["prefix"], relative.parent.as_posix(), filename)
            if part and part != "."
        )
        key = key.replace(" ", "_")
        if len(key.encode("utf-8")) > 1024:
            raise CLIError(f"目标 Key 超过 1024 字节：{local}")
        if key in targets:
            if targets[key] == local:
                continue
            raise CLIError(
                f"目标 Key 冲突：{key}\n  {targets[key]}\n  {local}\n请调整文件名、前缀或分批上传。"
            )
        targets[key] = local
        plans.append(
            {
                "file": str(local),
                "key": key,
                "url": f"{base_url}/{quote(key, safe='/')}",
                "size": before[2],
                "fingerprint": before,
                "content_type": IMAGE_TYPES.get(local.suffix.lower())
                or mimetypes.guess_type(local.name)[0]
                or "application/octet-stream",
            }
        )
    return plans


def create_client(config: dict):
    from qcloud_cos import CosConfig, CosS3Client

    # SDK 原始日志可能带请求细节；CLI 只输出下方筛选后的错误信息。
    logging.getLogger("qcloud_cos").setLevel(logging.CRITICAL)
    return CosS3Client(
        CosConfig(
            Region=config["region"],
            SecretId=config["secret_id"],
            SecretKey=config["secret_key"],
            Token=config["security_token"] or None,
            Scheme="https",
            Timeout=config["timeout"],
        )
    )


def upload_error(error: Exception, config: dict) -> str:
    def detail(method: str) -> str:
        try:
            return str(getattr(error, method)())
        except (AttributeError, KeyError, TypeError, ValueError):
            return "Unknown"

    if isinstance(error, CLIError):
        message = str(error)
    elif isinstance(error, OSError) and error.errno is not None:
        message = f"本地文件操作失败：{error.strerror}"
    elif callable(getattr(error, "get_error_code", None)):
        message = f"COS {detail('get_error_code')} (HTTP {detail('get_status_code')}, RequestId: {detail('get_request_id')})"
    else:
        # 网络异常可能包含签名 URL，不能直接打印 SDK 原始异常。
        message = f"{type(error).__name__}：上传失败，请检查网络、存储桶、地域和凭据"
    for field in SECRET_FIELDS:
        if config[field]:
            message = message.replace(config[field], "***")
    return " ".join(message.splitlines())


def print_result(result: dict, output_format: str) -> None:
    if output_format == "key":
        print(result["key"], flush=True)
    elif output_format == "markdown":
        label = Path(result["file"]).stem
        for char in ("\\", "[", "]"):
            label = label.replace(char, "\\" + char)
        print(f"![{label}]({result['url']})", flush=True)
    elif output_format == "url":
        print(result["url"], flush=True)


def run_upload(args: argparse.Namespace, config: dict) -> int:
    if args.prefix is not None:
        config["prefix"] = normalize_prefix(args.prefix)
    if args.md5 is not None:
        config["use_md5"] = args.md5
    plans = plan_uploads(collect_files(args.inputs, args.all_files), config)
    client = None if args.dry_run else create_client(config)
    results: list[dict] = []
    failed = 0
    interrupted = False
    for index, plan in enumerate(plans, 1):
        result = {key: value for key, value in plan.items() if key != "fingerprint"}
        label = "预览" if args.dry_run else "上传"
        print(
            f"[{index}/{len(plans)}] {label} {plan['file']} → {plan['key']}",
            file=sys.stderr,
        )
        try:
            if args.dry_run:
                result["status"] = "planned"
            else:
                if file_fingerprint(Path(plan["file"])) != plan["fingerprint"]:
                    raise CLIError("文件自预览后已发生变化，请重新执行上传")
                response = client.upload_file(
                    Bucket=config["bucket"],
                    Key=plan["key"],
                    LocalFilePath=plan["file"],
                    ContentType=plan["content_type"],
                    EnableMD5=True,
                )
                if not response.get("ETag"):
                    raise CLIError(
                        "COS 未返回 ETag，无法确认上传成功，请核对存储桶和地域"
                    )
                result.update(status="uploaded", etag=response["ETag"])
        except KeyboardInterrupt:
            interrupted = True
            result.update(
                status="interrupted", error="上传已中断，当前对象是否完成请到 COS 核实"
            )
        except Exception as error:  # noqa: BLE001 - 隔离每个文件的 SDK 异常，保留批次结果。
            failed += 1
            result.update(status="failed", error=upload_error(error, config))
            print(f"错误：{result['error']}", file=sys.stderr)
        results.append(result)
        if result["status"] in ("planned", "uploaded"):
            print_result(result, args.format)
        if interrupted:
            break
    if args.format == "json":
        print(
            json.dumps(
                {
                    "dry_run": args.dry_run,
                    "bucket": config["bucket"],
                    "region": config["region"],
                    "total": len(plans),
                    "uploaded": sum(item["status"] == "uploaded" for item in results),
                    "failed": failed,
                    "interrupted": interrupted,
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    if interrupted:
        print("上传已中断，已完成的对象不会回滚。", file=sys.stderr)
        return 130
    if args.dry_run:
        print(f"预览完成：共 {len(plans)} 个文件，未发起上传。", file=sys.stderr)
    else:
        print(f"上传完成：成功 {len(plans) - failed}，失败 {failed}。", file=sys.stderr)
    return 1 if failed else 0


def make_parser(**kwargs) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(allow_abbrev=False, add_help=False, **kwargs)
    parser._positionals.title = "参数"
    parser._optionals.title = "选项"
    parser.add_argument("-h", "--help", action="help", help="显示帮助")
    return parser


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    common.add_argument(
        "--config", default=str(CONFIG_PATH), metavar="路径", help="配置文件路径"
    )
    global_args, remaining = common.parse_known_args(argv)
    config_path = Path(global_args.config).expanduser().absolute()
    if remaining and remaining[0] == "config":
        parser = make_parser(
            prog=f"{APP} config",
            parents=[common],
            description="管理本地配置，敏感字段不会显示",
        )
        parser.add_argument(
            "action",
            choices=("init", "check", "show", "path"),
            help="创建模板／校验／脱敏查看／显示路径",
        )
        args = parser.parse_args(remaining[1:])
        if args.action == "init":
            init_config(config_path)
        elif args.action == "path":
            print(config_path)
        else:
            config = load_config(config_path)
            if args.action == "check":
                print(f"配置校验通过（仅本地校验，未连接 COS）：{config_path}")
            else:
                print(
                    json.dumps(
                        {
                            key: ("***" if value else "")
                            if key in SECRET_FIELDS
                            else value
                            for key, value in config.items()
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
        return 0
    parser = make_parser(
        prog=APP,
        parents=[common],
        description="上传图片或文件夹到腾讯云 COS；默认递归、保留目录层级、使用 MD5 文件名。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"示例：\n  {APP} config init\n  {APP} a.png b.jpg\n  {APP} ./photos --prefix imgs/blog --dry-run\n  {APP} ./photos --no-md5 --format json\n\n配置命令：config init | check | show | path\n配置默认路径：{CONFIG_PATH}\n可选用 upload 子命令；以 - 开头的路径请放在 -- 后。",
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        metavar="图片或文件夹",
        help="一个或多个路径；目录默认递归筛选图片",
    )
    parser.add_argument(
        "-p",
        "--prefix",
        metavar="前缀",
        help="对象路径前缀，覆盖配置（默认 imgs）；空字符串表示根目录",
    )
    naming = parser.add_mutually_exclusive_group()
    naming.add_argument(
        "--md5",
        dest="md5",
        action="store_true",
        default=None,
        help="文件名加入内容 MD5（默认开启）",
    )
    naming.add_argument(
        "--no-md5",
        dest="md5",
        action="store_false",
        help="保留原文件名，空格仍替换为下划线",
    )
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="上传任意类型文件，与 Raycast 的目录上传行为一致",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="仅预览实际 Key 和 URL，不连接 COS"
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument(
        "--format",
        choices=("url", "key", "markdown", "json"),
        default="url",
        help="输出格式（默认 url）；进度写入 stderr",
    )
    output.add_argument(
        "--json",
        dest="format",
        action="store_const",
        const="json",
        help="等同于 --format json",
    )
    if remaining and remaining[0] == "upload":
        remaining = remaining[1:]
    args = parser.parse_intermixed_args(remaining)
    if not args.inputs:
        parser.error("请传入图片或文件夹；首次使用请运行 config init")
    return run_upload(args, load_config(config_path))


def entrypoint() -> int:
    try:
        return main()
    except CLIError as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(
            f"错误：本地文件操作失败（{error.strerror}）：{error.filename}",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("操作已中断。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(entrypoint())

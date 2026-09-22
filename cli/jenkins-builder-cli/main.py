# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "pyyaml"]
# ///
from __future__ import annotations

import argparse
import getpass
import io
import json
import os
import stat
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

import requests
import yaml

APP_NAME = "jenkins-builder-cli"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.yaml"
DEFAULT_TIMEOUT_SECONDS = 1200
DEFAULT_POLL_INTERVAL_SECONDS = 5
DEFAULT_VERIFY_SSL = True
USER_AGENT = f"{APP_NAME}/1.0"
DEFAULT_BRANCH_PREFIX = "*/"
BUILD_STATUS_BY_RESULT = {
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "ABORTED": "aborted",
    "UNSTABLE": "unstable",
    "NOT_BUILT": "not_built",
}
CONTAINER_CLASS_MARKERS = (
    "Folder",
    "ComputedFolder",
    "MultiBranchProject",
    "OrganizationFolder",
)
LABEL_DISPLAY = {
    "test": "测试服",
    "prod": "正式服",
}
LABEL_ORDER = {
    "test": 0,
    "prod": 1,
    "": 2,
}


class CLIError(RuntimeError):
    """User-facing error."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class JobEntry:
    full_name: str
    url: str
    class_name: str
    color: str | None
    buildable: bool
    metadata: dict[str, Any]
    live_branch_specifier: str | None = None

    @property
    def label(self) -> str | None:
        label = self.metadata.get("label")
        return label if label in LABEL_DISPLAY else None

    @property
    def label_display(self) -> str:
        return LABEL_DISPLAY.get(self.label or "", "未分类")

    @property
    def description(self) -> str:
        return self.metadata.get("description", "")

    @property
    def branch_display(self) -> str:
        return self.live_branch_specifier or "-"


@dataclass
class RunningBuild:
    run_id: str
    full_name: str
    build_number: int
    url: str
    node_name: str
    display_name: str
    timestamp_ms: int | None


def default_config() -> dict[str, Any]:
    return {
        "jenkins": {
            "url": "",
            "username": "",
            "token": "",
            "verify_ssl": DEFAULT_VERIFY_SSL,
        },
        "defaults": {
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
            "poll_interval_seconds": DEFAULT_POLL_INTERVAL_SECONDS,
        },
        "jobs": {},
    }


def ensure_config_shape(data: dict[str, Any] | None) -> dict[str, Any]:
    merged = default_config()
    if not isinstance(data, dict):
        raise CLIError("配置文件根节点必须是 YAML 对象")

    for section in ("jenkins", "defaults", "jobs"):
        if section in data and not isinstance(data[section], dict):
            raise CLIError(f"配置项 {section} 必须是对象")

    jenkins = data.get("jenkins")
    if isinstance(jenkins, dict):
        merged["jenkins"].update(jenkins)

    defaults = data.get("defaults")
    if isinstance(defaults, dict):
        merged["defaults"].update(defaults)

    jobs = data.get("jobs")
    if isinstance(jobs, dict):
        for name, meta in jobs.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(meta, dict):
                raise CLIError("jobs 必须以非空 job 名称为键、对象为值")
            merged["jobs"][name] = normalize_job_meta(meta)

    return merged


def normalize_job_meta(meta: dict[str, Any]) -> dict[str, Any]:
    label = meta.get("label", meta.get("env", ""))
    if label not in ("", "test", "prod"):
        raise CLIError("job 的 label 必须是 test、prod 或空字符串")
    description = meta.get("description")
    if "description" not in meta:
        # Preserve existing annotations when migrating the old config format.
        parts = []
        for key in ("aliases", "keywords"):
            value = meta.get(key, [])
            if isinstance(value, str):
                value = value.split(",")
            if not isinstance(value, list) or any(not isinstance(part, str) for part in value):
                raise CLIError(f"旧配置的 {key} 必须是字符串或字符串列表")
            parts.extend(part.strip() for part in value if part.strip())
        description = "；".join(dict.fromkeys(parts))
    if not isinstance(description, str):
        raise CLIError("job 的 description 必须是字符串（可以为空）")
    return {"label": label, "description": description.strip()}


def validate_config(config: dict[str, Any], *, required: bool = True) -> None:
    errors = []
    jenkins = config["jenkins"]
    for key in ("url", "username", "token"):
        value = jenkins.get(key)
        if not isinstance(value, str) or (required and not value.strip()):
            errors.append(f"jenkins.{key} 必须是非空字符串")
    url = jenkins.get("url")
    if isinstance(url, str) and url:
        try:
            parsed = urlparse(url)
            valid_url = parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
            _ = parsed.port
        except ValueError:
            valid_url = False
        if not valid_url or any(char.isspace() for char in url):
            errors.append("jenkins.url 必须是有效的 HTTP(S) 地址，不能包含账号、密码、查询参数或片段")
    if not isinstance(jenkins.get("verify_ssl"), bool):
        errors.append("jenkins.verify_ssl 必须是 true 或 false")
    for key in ("timeout_seconds", "poll_interval_seconds"):
        value = config["defaults"].get(key)
        if type(value) is not int or value <= 0:
            errors.append(f"defaults.{key} 必须是正整数")
    if errors:
        raise CLIError("配置检查失败:\n" + "\n".join(f"- {error}" for error in errors))


def load_config(required: bool = True) -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        if required:
            raise CLIError(
                f"配置文件不存在: {CONFIG_PATH}\n请先运行: {APP_NAME} config init"
            )
        return default_config()

    try:
        with CONFIG_PATH.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (yaml.YAMLError, UnicodeError) as exc:
        # YAML errors can include the source line containing credentials.
        raise CLIError(f"配置文件 YAML 格式错误: {CONFIG_PATH}") from exc

    config = ensure_config_shape(data)
    validate_config(config, required=required)
    return config


def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONFIG_DIR, delete=False) as handle:
            temporary_path = Path(handle.name)
            yaml.safe_dump(config, handle, allow_unicode=True, sort_keys=False)
        os.chmod(temporary_path, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary_path, CONFIG_PATH)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def masked_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return "*" * len(token)
    return f"{token[:2]}{'*' * (len(token) - 4)}{token[-2:]}"


def nonempty_value(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("参数不能为空")
    return value


def bool_value(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"无法识别布尔值: {value}")


def contains_ci(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def is_container_class(class_name: str) -> bool:
    return any(marker in class_name for marker in CONTAINER_CLASS_MARKERS)


def canonical_job_url(base_url: str, full_name: str) -> str:
    segments = [segment for segment in full_name.split("/") if segment]
    url = normalize_base_url(base_url)
    for segment in segments:
        url += f"/job/{quote(segment, safe='')}"
    return url


def extract_full_name_from_job_url(base_url: str, job_url: str) -> str:
    parsed_base = urlparse(normalize_base_url(base_url))
    parsed_job = urlparse(job_url)
    path = parsed_job.path
    base_path = parsed_base.path.rstrip("/")
    if base_path and path.startswith(base_path):
        path = path[len(base_path) :]
    parts = [part for part in path.split("/") if part]
    names: list[str] = []
    index = 0
    while index < len(parts):
        if parts[index] != "job" or index + 1 >= len(parts):
            break
        names.append(unquote(parts[index + 1]))
        index += 2
    if not names:
        raise CLIError(f"无法从 job URL 解析 job 名称: {job_url}")
    return "/".join(names)


def parse_run_id(run_id: str) -> tuple[str, int]:
    if "#" not in run_id:
        raise CLIError("run-id 格式必须为 <full-job-name>#<build-number>")
    full_name, build_number_raw = run_id.rsplit("#", 1)
    if not full_name:
        raise CLIError("run-id 缺少 job 名称")
    try:
        build_number = int(build_number_raw)
    except ValueError as exc:
        raise CLIError("run-id 缺少有效的 build number") from exc
    if build_number <= 0:
        raise CLIError("build number 必须大于 0")
    return full_name, build_number


def format_run_id(full_name: str, build_number: int) -> str:
    return f"{full_name}#{build_number}"


def normalize_branch_specifier(branch: str) -> str:
    normalized = branch.strip()
    if not normalized:
        raise CLIError("分支名不能为空")
    if normalized.startswith(DEFAULT_BRANCH_PREFIX):
        return normalized
    if normalized.startswith("refs/"):
        return normalized
    if normalized.startswith(":"):
        return normalized
    return f"{DEFAULT_BRANCH_PREFIX}{normalized}"


def infer_branch_display(specifier: str) -> str:
    if not specifier.startswith(DEFAULT_BRANCH_PREFIX):
        return specifier
    return specifier[len(DEFAULT_BRANCH_PREFIX) :]


def yaml_dump(data: Any) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).rstrip()


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def build_cards(rows: list[list[str]], headers: list[str]) -> str:
    lines = []
    for row in rows:
        lines.append(f"  \033[1m{row[0]}\033[0m")
        for i in range(1, len(row)):
            if row[i] and row[i] != "-":
                lines.append(f"    {headers[i]}: {row[i]}")
        lines.append("")
    return "\n".join(lines).rstrip()


def require_tty() -> None:
    if not sys.stdin.isatty():
        raise CLIError("当前命令需要交互式终端")


class JenkinsClient:
    def __init__(self, config: dict[str, Any]):
        jenkins = config["jenkins"]
        self.base_url = normalize_base_url(str(jenkins["url"]))
        self.verify_ssl = bool(jenkins.get("verify_ssl", DEFAULT_VERIFY_SSL))
        self.session = requests.Session()
        self.session.auth = (str(jenkins["username"]), str(jenkins["token"]))
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._crumb_headers: dict[str, str] | None = None

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return f"{self.base_url}/{path_or_url.lstrip('/')}"

    def _fetch_crumb_headers(self) -> dict[str, str]:
        if self._crumb_headers is not None:
            return self._crumb_headers
        url = self._url("/crumbIssuer/api/json")
        try:
            response = self.session.get(url, timeout=30, verify=self.verify_ssl)
            if response.status_code == 404:
                self._crumb_headers = {}
                return self._crumb_headers
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            self._crumb_headers = {}
            return self._crumb_headers
        field = data.get("crumbRequestField")
        crumb = data.get("crumb")
        if field and crumb:
            self._crumb_headers = {str(field): str(crumb)}
        else:
            self._crumb_headers = {}
        return self._crumb_headers

    def get_json(self, path_or_url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self._url(path_or_url)
        try:
            response = self.session.get(url, params=params, timeout=30, verify=self.verify_ssl)
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise self._http_error(url, exc.response) from exc
        except requests.RequestException as exc:
            raise CLIError(f"请求失败: {url}\n{exc}") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise CLIError(f"Jenkins 返回的不是有效 JSON: {url}") from exc
        if not isinstance(data, dict):
            raise CLIError(f"Jenkins 返回的 JSON 不是对象: {url}")
        return data

    def get_text(self, path_or_url: str) -> str:
        url = self._url(path_or_url)
        try:
            response = self.session.get(url, timeout=30, verify=self.verify_ssl)
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise self._http_error(url, exc.response) from exc
        except requests.RequestException as exc:
            raise CLIError(f"请求失败: {url}\n{exc}") from exc
        return response.text

    def post(
        self,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        expected_codes: tuple[int, ...] = (200, 201, 202),
        allow_redirects: bool = True,
    ) -> requests.Response:
        url = self._url(path_or_url)
        request_headers = dict(headers or {})
        request_headers.update(self._fetch_crumb_headers())
        try:
            response = self.session.post(
                url,
                params=params,
                data=data,
                headers=request_headers,
                timeout=30,
                verify=self.verify_ssl,
                allow_redirects=allow_redirects,
            )
        except requests.RequestException as exc:
            raise CLIError(f"请求失败: {url}\n{exc}") from exc

        if response.status_code not in expected_codes:
            raise self._http_error(url, response)
        return response

    def _http_error(self, url: str, response: requests.Response | None) -> CLIError:
        if response is None:
            return CLIError(f"请求失败: {url}")
        message = response.text.strip()
        if len(message) > 400:
            message = message[:400] + "..."
        if message:
            return CLIError(f"HTTP {response.status_code}: {url}\n{message}", status_code=response.status_code)
        return CLIError(f"HTTP {response.status_code}: {url}", status_code=response.status_code)

    def find_job(self, full_name: str) -> dict[str, Any] | None:
        """Validate one exact name without enumerating unrelated folders."""
        url = canonical_job_url(self.base_url, full_name)
        try:
            item = self.get_json(
                f"{url}/api/json",
                params={"tree": "name,fullName,url,color,_class,buildable"},
            )
        except CLIError as exc:
            if exc.status_code in (403, 404):
                return None
            raise
        class_name = str(item.get("_class") or "")
        name = str(item.get("fullName") or extract_full_name_from_job_url(self.base_url, url))
        if name != full_name or is_container_class(class_name) or item.get("buildable") is False:
            return None
        return {
            "full_name": name,
            "url": str(item.get("url") or url).rstrip("/"),
            "class_name": class_name,
            "color": str(item.get("color") or ""),
            "buildable": True,
        }

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        def walk(container_url: str) -> None:
            data = self.get_json(
                f"{container_url.rstrip('/')}/api/json",
                params={"tree": "jobs[name,fullName,url,color,_class,buildable]"},
            )
            if not isinstance(data.get("jobs"), list):
                raise CLIError("Jenkins 响应缺少 jobs 列表，未同步本地配置")
            for item in data["jobs"]:
                if not isinstance(item, dict) or not item.get("url"):
                    raise CLIError("Jenkins 返回了无效 job，未同步本地配置")
                item_url = str(item.get("url") or "")
                if not item_url or item_url in seen_urls:
                    continue
                seen_urls.add(item_url)
                class_name = str(item.get("_class") or "")
                if is_container_class(class_name):
                    walk(item_url)
                    continue
                buildable = item.get("buildable")
                if buildable is False:
                    continue
                try:
                    full_name = str(item.get("fullName") or extract_full_name_from_job_url(self.base_url, item_url))
                except CLIError as exc:
                    raise CLIError("Jenkins 返回了无效 job 名称，未同步本地配置") from exc
                jobs.append(
                    {
                        "full_name": full_name,
                        "url": item_url.rstrip("/"),
                        "class_name": class_name,
                        "color": str(item.get("color") or ""),
                        "buildable": buildable is not False,
                    }
                )

        walk(self.base_url)
        jobs.sort(key=lambda item: item["full_name"].casefold())
        return jobs

    def trigger_build(self, job_url: str) -> str:
        job_url = job_url.rstrip("/")
        info = self.get_json(f"{job_url}/api/json", params={"tree": "property[_class]"})
        properties = info.get("property")
        if not isinstance(properties, list) or any(not isinstance(prop, dict) for prop in properties):
            raise CLIError("无法读取 job 参数配置，未触发构建")
        parameterized = any(prop.get("_class") == "hudson.model.ParametersDefinitionProperty" for prop in properties)
        # Let Jenkins supply parameter defaults; /build expects form JSON for
        # parameterized jobs and rejects an empty POST with HTTP 400.
        endpoint = f"{job_url}/{'buildWithParameters' if parameterized else 'build'}"
        response = self.post(
            endpoint,
            expected_codes=(200, 201, 202, 302, 303),
            allow_redirects=False,
        )
        location = response.headers.get("Location", "")
        if not location:
            raise CLIError("Jenkins 响应缺少 queue Location，无法确认构建已入队")
        parts = [part for part in location.rstrip("/").split("/") if part]
        try:
            item_index = parts.index("item")
            return parts[item_index + 1]
        except (ValueError, IndexError) as exc:
            raise CLIError(f"无法从 queue Location 提取 queue id: {location}") from exc

    def queue_item(self, queue_id: str) -> dict[str, Any]:
        return self.get_json(f"/queue/item/{queue_id}/api/json")

    def wait_for_build_number(
        self,
        queue_id: str,
        *,
        timeout_seconds: int = 120,
        poll_interval_seconds: int = 2,
    ) -> int:
        started = time.time()
        while True:
            if time.time() - started > timeout_seconds:
                raise CLIError("等待 build number 超时，构建可能仍在队列中")
            item = self.queue_item(queue_id)
            executable = item.get("executable") or {}
            number = executable.get("number")
            if isinstance(number, int):
                return number
            if item.get("cancelled"):
                raise CLIError("构建在队列中被取消")
            time.sleep(poll_interval_seconds)

    def build_info(self, job_url: str, build_number: int) -> dict[str, Any]:
        return self.get_json(f"{job_url.rstrip('/')}/{build_number}/api/json")

    def wait_for_build_result(
        self,
        job_url: str,
        build_number: int,
        *,
        timeout_seconds: int,
        poll_interval_seconds: int,
    ) -> dict[str, Any]:
        started = time.time()
        while True:
            if time.time() - started > timeout_seconds:
                raise CLIError("等待构建完成超时")
            info = self.build_info(job_url, build_number)
            if not info.get("building", False):
                return info
            time.sleep(poll_interval_seconds)

    def console_text(self, job_url: str, build_number: int) -> str:
        return self.get_text(f"{job_url.rstrip('/')}/{build_number}/consoleText")

    def progressive_console(self, job_url: str, build_number: int, start: int) -> tuple[str, int, bool]:
        url = f"{job_url.rstrip('/')}/{build_number}/logText/progressiveText"
        try:
            response = self.session.get(url, params={"start": start}, timeout=30, verify=self.verify_ssl)
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise self._http_error(url, exc.response) from exc
        except requests.RequestException as exc:
            raise CLIError(f"请求失败: {url}\n{exc}") from exc
        # Jenkins offsets count raw log bytes, including stripped console annotations.
        # Neither len(text) nor the size of the UTF-8 response is a valid cursor.
        try:
            next_start = int(response.headers["X-Text-Size"])
            if next_start < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise CLIError("增量日志响应缺少有效的 X-Text-Size 字节游标") from exc
        response.encoding = "utf-8"
        return response.text, next_start, response.headers.get("X-More-Data", "").lower() == "true"

    def stop_build(self, job_url: str, build_number: int) -> None:
        self.post(
            f"{job_url.rstrip('/')}/{build_number}/stop",
            expected_codes=(200, 201, 302),
            allow_redirects=False,
        )

    def job_config_xml(self, job_url: str) -> str:
        return self.get_text(f"{job_url.rstrip('/')}/config.xml")

    def update_job_config_xml(self, job_url: str, xml_text: str) -> None:
        self.post(
            f"{job_url.rstrip('/')}/config.xml",
            data=xml_text.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            expected_codes=(200, 201),
        )

    def list_running_builds(self) -> list[RunningBuild]:
        data = self.get_json(
            "/computer/api/json",
            params={
                "tree": (
                    "computer[displayName,"
                    "executors[currentExecutable[url,number,fullDisplayName,timestamp]],"
                    "oneOffExecutors[currentExecutable[url,number,fullDisplayName,timestamp]]]"
                )
            },
        )
        builds: list[RunningBuild] = []
        for computer in data.get("computer", []):
            node_name = str(computer.get("displayName") or "")
            for bucket_name in ("executors", "oneOffExecutors"):
                for executor in computer.get(bucket_name, []):
                    current = executor.get("currentExecutable")
                    if not isinstance(current, dict):
                        continue
                    url = str(current.get("url") or "").rstrip("/")
                    number = current.get("number")
                    if not url or not isinstance(number, int):
                        continue
                    try:
                        full_name = extract_full_name_from_job_url(self.base_url, url)
                    except CLIError:
                        continue
                    run_id = format_run_id(full_name, number)
                    builds.append(
                        RunningBuild(
                            run_id=run_id,
                            full_name=full_name,
                            build_number=number,
                            url=url,
                            node_name=node_name,
                            display_name=str(current.get("fullDisplayName") or full_name),
                            timestamp_ms=current.get("timestamp") if isinstance(current.get("timestamp"), int) else None,
                        )
                    )
        builds.sort(key=lambda item: item.run_id.casefold())
        return builds


def get_job_meta(config: dict[str, Any], full_name: str) -> dict[str, Any]:
    return normalize_job_meta((config.get("jobs") or {}).get(full_name) or {})


def fetch_live_branch_specifier(client: JenkinsClient, job_url: str) -> str | None:
    try:
        current_xml = client.job_config_xml(job_url)
        current_specifier, _, _ = parse_branch_specifier(current_xml)
        return current_specifier or None
    except CLIError:
        return None


def job_entries_from_live_jobs(
    config: dict[str, Any],
    live_jobs: list[dict[str, Any]],
) -> list[JobEntry]:
    entries = [
        JobEntry(
            full_name=job["full_name"],
            url=job["url"],
            class_name=job["class_name"],
            color=job["color"],
            buildable=job["buildable"],
            metadata=get_job_meta(config, job["full_name"]),
        )
        for job in live_jobs
    ]
    entries.sort(key=job_sort_key)
    return entries


def job_sort_key(entry: JobEntry) -> tuple[int, str]:
    return (LABEL_ORDER.get(entry.label or "", 2), entry.full_name.casefold())


def filter_jobs(entries: list[JobEntry], *, query: str | None) -> list[JobEntry]:
    filtered = entries
    if query:
        filtered = [
            entry
            for entry in filtered
            if query_matches_job(query, entry)
        ]
    return filtered


def query_matches_job(query: str, entry: JobEntry) -> bool:
    haystacks = [entry.full_name, entry.label_display, entry.description]
    return any(contains_ci(haystack, query) for haystack in haystacks if haystack)


def resolve_job_name(job_name: str, entries: list[JobEntry]) -> JobEntry:
    for entry in entries:
        if entry.full_name == job_name:
            return entry

    candidates = [entry for entry in entries if contains_ci(entry.full_name, job_name)]
    if candidates:
        raise CLIError(
            "命令行参数只接受完整 Jenkins job name。\n"
            "可能的 job name 候选:\n"
            + "\n".join(f"- {entry.full_name}" for entry in candidates[:20])
        )
    raise CLIError(
        f"找不到 job: {job_name}\n"
        f"可以先运行: {APP_NAME} jobs list --query \"{job_name}\""
    )


def save_job_meta(config: dict[str, Any], full_name: str, meta: dict[str, Any]) -> None:
    config.setdefault("jobs", {})[full_name] = normalize_job_meta(meta)


def render_jobs(entries: list[JobEntry]) -> str:
    rows = []
    for index, entry in enumerate(entries, start=1):
        rows.append(
            [
                f"{index}. {entry.full_name}",
                entry.label_display,
                entry.branch_display,
                entry.description or "-",
            ]
        )
    if not rows:
        return "没有找到任何 job。"
    return build_cards(rows, ["JOB", "LABEL", "BRANCH", "DESCRIPTION"])


def prompt_choice(prompt: str, count: int) -> int:
    while True:
        print(prompt, end="", file=sys.stderr, flush=True)
        answer = input().strip()
        try:
            index = int(answer)
        except ValueError:
            print("请输入数字序号。", file=sys.stderr)
            continue
        if 1 <= index <= count:
            return index - 1
        print("序号超出范围。", file=sys.stderr)


def interactive_select_job(entries: list[JobEntry]) -> JobEntry:
    require_tty()
    if not entries:
        raise CLIError("当前没有可供选择的 job")
    labels = [label for label in LABEL_ORDER if any((entry.label or "") == label for entry in entries)]
    for index, label in enumerate(labels, start=1):
        print(f"{index}. {LABEL_DISPLAY.get(label, '未分类')}", file=sys.stderr)
    label = labels[prompt_choice("请选择分组序号: ", len(labels))]
    jobs = [entry for entry in entries if (entry.label or "") == label]
    for index, entry in enumerate(jobs, start=1):
        description = " ".join(entry.description.split())
        print(f"{index}. {entry.full_name}" + (f" — {description}" if description else ""), file=sys.stderr)
    return jobs[prompt_choice("请选择 job 序号: ", len(jobs))]


def prompt_branch(client: JenkinsClient, entry: JobEntry, *, optional: bool = False) -> str | None:
    require_tty()
    current = fetch_live_branch_specifier(client, entry.url)
    print(f"当前分支: {current or '无法读取（非经典 Git job 或无配置读取权限）'}", file=sys.stderr)
    while True:
        print("分支名（回车使用当前分支）: " if optional else "请输入分支名: ", end="", file=sys.stderr, flush=True)
        branch = input().strip()
        if branch or optional:
            return branch or None
        print("分支名不能为空。", file=sys.stderr)


def parse_branch_specifier(xml_text: str) -> tuple[str, ET.ElementTree, ET.Element]:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    try:
        root = ET.fromstring(xml_text, parser=parser)
    except ET.ParseError as exc:
        raise CLIError("Jenkins job 配置不是有效 XML") from exc
    tree = ET.ElementTree(root)
    git_scms = [element for element in root.iter() if element.attrib.get("class") == "hudson.plugins.git.GitSCM"]
    if len(git_scms) != 1:
        raise CLIError("当前 job 不是单一经典 Git job，无法安全修改 Branch Specifier")
    git_scm = git_scms[0]
    branch_names = git_scm.findall("./branches/hudson.plugins.git.BranchSpec/name")
    if len(branch_names) != 1:
        raise CLIError("当前 job 的 Git Branch Specifier 不是唯一节点，无法安全修改")
    current = branch_names[0].text or ""
    return current, tree, branch_names[0]


def serialize_tree(tree: ET.ElementTree) -> str:
    buffer = io.BytesIO()
    tree.write(buffer, encoding="utf-8", xml_declaration=True)
    return buffer.getvalue().decode("utf-8")


def job_info_payload(entry: JobEntry) -> dict[str, Any]:
    return {
        "full_name": entry.full_name,
        "url": entry.url,
        "label": entry.label,
        "label_display": entry.label_display,
        "description": entry.description,
        "branch_specifier": entry.live_branch_specifier,
        "buildable": entry.buildable,
        "class_name": entry.class_name,
    }


def build_status(info: dict[str, Any]) -> str:
    if bool(info.get("building", False)):
        return "running"
    result = info.get("result")
    if isinstance(result, str):
        return BUILD_STATUS_BY_RESULT.get(result, result.casefold())
    return "unknown"


def build_status_payload(full_name: str, build_number: int, job_url: str, info: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "run_id": format_run_id(full_name, build_number),
        "job": full_name,
        "build_number": build_number,
        "status": build_status(info),
        "building": bool(info.get("building", False)),
        "result": info.get("result"),
        "url": f"{job_url.rstrip('/')}/{build_number}/",
    }
    if isinstance(info.get("displayName"), str):
        payload["display_name"] = info["displayName"]
    if isinstance(info.get("timestamp"), int):
        payload["timestamp_ms"] = info["timestamp"]
    if isinstance(info.get("duration"), int):
        payload["duration_ms"] = info["duration"]
    if isinstance(info.get("estimatedDuration"), int):
        payload["estimated_duration_ms"] = info["estimatedDuration"]
    return payload


def create_client_and_entries(*, job_name: str | None = None, sync: bool = False) -> tuple[dict[str, Any], JenkinsClient, list[JobEntry]]:
    config = load_config(required=True)
    client = JenkinsClient(config)
    live_jobs = None
    if job_name is not None and not sync:
        exact = client.find_job(job_name)
        if exact is not None:
            live_jobs = [exact]
    if live_jobs is None:
        live_jobs = client.list_jobs()
    if sync:
        config["jobs"] = {job["full_name"]: get_job_meta(config, job["full_name"]) for job in live_jobs}
        save_config(config)
    entries = job_entries_from_live_jobs(config, live_jobs)
    return config, client, entries


def cmd_config_init(args: argparse.Namespace) -> None:
    config = load_config(required=False)
    jenkins = config["jenkins"]

    url = args.url or jenkins.get("url") or ""
    username = args.username or jenkins.get("username") or ""
    token = args.token or jenkins.get("token") or ""
    verify_ssl = DEFAULT_VERIFY_SSL if args.verify_ssl is None else args.verify_ssl
    if args.verify_ssl is None and "verify_ssl" in jenkins:
        verify_ssl = bool(jenkins.get("verify_ssl", DEFAULT_VERIFY_SSL))

    if sys.stdin.isatty():
        prompt_url = input(f"Jenkins URL [{url}]: ").strip()
        if prompt_url:
            url = prompt_url
        prompt_username = input(f"用户名 [{username}]: ").strip()
        if prompt_username:
            username = prompt_username
        prompt_token = getpass.getpass("API Token [留空保留现有值]: ").strip()
        if prompt_token:
            token = prompt_token
        prompt_verify = input(f"校验证书 (true/false) [{str(verify_ssl).lower()}]: ").strip()
        if prompt_verify:
            verify_ssl = bool_value(prompt_verify)

    missing = []
    if not url:
        missing.append("--url")
    if not username:
        missing.append("--username")
    if not token:
        missing.append("--token")
    if missing:
        raise CLIError(f"缺少必填参数: {', '.join(missing)}")

    config["jenkins"] = {
        "url": normalize_base_url(url),
        "username": username,
        "token": token,
        "verify_ssl": bool(verify_ssl),
    }
    validate_config(config)
    save_config(config)
    print(f"配置已写入: {CONFIG_PATH}")


def cmd_config_show(args: argparse.Namespace) -> None:
    config = load_config(required=False)
    masked = ensure_config_shape(config)
    masked["jenkins"]["token"] = masked_token(str(masked["jenkins"].get("token") or ""))
    if args.json:
        print_json(masked)
        return
    print(yaml_dump(masked))


def cmd_config_path(args: argparse.Namespace) -> None:
    print(CONFIG_PATH)


def cmd_doctor(args: argparse.Namespace) -> None:
    _, _, entries = create_client_and_entries(sync=True)
    missing = [entry.full_name for entry in entries if not entry.description]
    payload = {
        "status": "ok",
        "configPath": str(CONFIG_PATH),
        "jobsCount": len(entries),
        "missing_descriptions": missing,
    }
    if args.json:
        print_json(payload)
        return
    print(f"配置与 Jenkins 连接检查通过，已同步 {len(entries)} 个 job。")
    print(f"配置文件: {CONFIG_PATH}")
    if missing:
        print("以下 job 尚未填写描述（可选，不影响使用）:")
        for name in missing:
            print(f"- {name}")


def cmd_jobs_list(args: argparse.Namespace) -> None:
    _, client, entries = create_client_and_entries(sync=True)
    filtered = filter_jobs(entries, query=args.query)
    for entry in filtered:
        entry.live_branch_specifier = fetch_live_branch_specifier(client, entry.url)
    if args.json:
        print_json([job_info_payload(entry) for entry in filtered])
        return
    print(render_jobs(filtered))


def cmd_jobs_label(args: argparse.Namespace) -> None:
    config, _, entries = create_client_and_entries(sync=True)
    entry = resolve_job_name(args.job_name, entries)
    meta = get_job_meta(config, entry.full_name)
    meta["label"] = args.label
    save_job_meta(config, entry.full_name, meta)
    save_config(config)

    payload = {"job": entry.full_name, **normalize_job_meta(config["jobs"][entry.full_name])}
    if args.json:
        print_json(payload)
        return
    print("已更新 job 标签:")
    print(yaml_dump(payload))


def cmd_jobs_unlabel(args: argparse.Namespace) -> None:
    config, _, entries = create_client_and_entries(sync=True)
    entry = resolve_job_name(args.job_name, entries)
    meta = get_job_meta(config, entry.full_name)
    meta["label"] = ""
    save_job_meta(config, entry.full_name, meta)
    save_config(config)

    payload = {"job": entry.full_name, "label": ""}
    if args.json:
        print_json(payload)
        return
    print(f"已移除 job 标签: {entry.full_name}")


def cmd_jobs_desc(args: argparse.Namespace) -> None:
    config, _, entries = create_client_and_entries(sync=True)
    entry = resolve_job_name(args.job_name, entries)
    meta = get_job_meta(config, entry.full_name)
    meta["description"] = args.description.strip()
    save_job_meta(config, entry.full_name, meta)
    save_config(config)
    payload = {"job": entry.full_name, **config["jobs"][entry.full_name]}
    if args.json:
        print_json(payload)
        return
    print("已更新 job 描述:")
    print(yaml_dump(payload))


def update_branch_specifier(
    client: JenkinsClient,
    entry: JobEntry,
    branch_name: str,
) -> dict[str, Any]:
    current_xml = client.job_config_xml(entry.url)
    current_specifier, tree, branch_node = parse_branch_specifier(current_xml)
    new_specifier = normalize_branch_specifier(branch_name)
    branch_node.text = new_specifier
    client.update_job_config_xml(entry.url, serialize_tree(tree))
    return {
        "job": entry.full_name,
        "previous_specifier": current_specifier,
        "new_specifier": new_specifier,
        "branch": infer_branch_display(new_specifier),
    }


def cmd_set_branch(args: argparse.Namespace) -> None:
    if args.job is None or args.branch is None:
        require_tty()
    _, client, entries = create_client_and_entries(job_name=args.job)
    entry = resolve_job_name(args.job, entries) if args.job is not None else interactive_select_job(entries)
    branch = args.branch if args.branch is not None else prompt_branch(client, entry)
    payload = update_branch_specifier(client, entry, branch)
    if args.json:
        print_json(payload)
        return
    print("已更新 Jenkins 分支配置:")
    print(yaml_dump(payload))


def maybe_follow_build(
    client: JenkinsClient,
    config: dict[str, Any],
    entry: JobEntry,
    build_number: int,
) -> dict[str, Any]:
    defaults = config["defaults"]
    result_info = client.wait_for_build_result(
        entry.url,
        build_number,
        timeout_seconds=int(defaults.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
        poll_interval_seconds=int(defaults.get("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS)),
    )
    return build_status_payload(entry.full_name, build_number, entry.url, result_info)


def _trigger_and_collect(
    client: JenkinsClient,
    config: dict[str, Any],
    targets: list[JobEntry],
    *,
    follow: bool,
) -> list[dict[str, Any]]:
    results = []
    for entry in targets:
        queue_id = client.trigger_build(entry.url)
        build_number = client.wait_for_build_number(
            queue_id,
            poll_interval_seconds=int(config["defaults"].get("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS)),
        )
        result: dict[str, Any] = {
            "queue_id": queue_id,
            "run_id": format_run_id(entry.full_name, build_number),
            "job": entry.full_name,
            "build_number": build_number,
            "url": f"{entry.url}/{build_number}/",
        }
        if follow:
            result.update(maybe_follow_build(client, config, entry, build_number))
        results.append(result)
    return results


def cmd_build(args: argparse.Namespace) -> None:
    if args.job is None:
        require_tty()
    config, client, entries = create_client_and_entries(job_name=args.job)
    entry = resolve_job_name(args.job, entries) if args.job is not None else interactive_select_job(entries)
    branch = args.branch
    if args.job is None and branch is None:
        branch = prompt_branch(client, entry, optional=True)
    if branch is not None:
        update_branch_specifier(client, entry, branch)

    results = _trigger_and_collect(client, config, [entry], follow=args.follow)
    if args.json:
        print_json(results[0])
        return
    print("构建已触发:")
    print(yaml_dump(results[0]))


def cmd_runs_list(args: argparse.Namespace) -> None:
    config = load_config(required=True)
    client = JenkinsClient(config)
    runs = client.list_running_builds()
    if args.json:
        print_json(
            [
                {
                    "run_id": run.run_id,
                    "job": run.full_name,
                    "build_number": run.build_number,
                    "url": run.url,
                    "node": run.node_name,
                    "display_name": run.display_name,
                    "timestamp_ms": run.timestamp_ms,
                }
                for run in runs
            ]
        )
        return
    if not runs:
        print("当前没有运行中的构建。")
        return
    rows = [
        [run.run_id, run.node_name or "-", run.display_name or "-", run.url]
        for run in runs
    ]
    print(build_cards(rows, ["RUN ID", "NODE", "DISPLAY", "URL"]))


def cmd_runs_stop(args: argparse.Namespace) -> None:
    config = load_config(required=True)
    client = JenkinsClient(config)
    full_name, build_number = parse_run_id(args.run_id)
    job_url = canonical_job_url(client.base_url, full_name)
    client.stop_build(job_url, build_number)
    payload = {"stopped": args.run_id}
    if args.json:
        print_json(payload)
        return
    print(f"已发送停止请求: {args.run_id}")


def cmd_runs_status(args: argparse.Namespace) -> None:
    config = load_config(required=True)
    client = JenkinsClient(config)
    full_name, build_number = parse_run_id(args.run_id)
    job_url = canonical_job_url(client.base_url, full_name)
    info = client.build_info(job_url, build_number)
    payload = build_status_payload(full_name, build_number, job_url, info)
    if args.json:
        print_json(payload)
        return
    print(yaml_dump(payload))


def cmd_logs(args: argparse.Namespace) -> None:
    config = load_config(required=True)
    client = JenkinsClient(config)
    full_name, build_number = parse_run_id(args.run_id)
    job_url = canonical_job_url(client.base_url, full_name)

    if args.json:
        if args.follow:
            info = client.wait_for_build_result(
                job_url,
                build_number,
                timeout_seconds=int(config["defaults"].get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
                poll_interval_seconds=int(config["defaults"].get("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS)),
            )
        else:
            info = client.build_info(job_url, build_number)
        text = client.console_text(job_url, build_number)
        payload = build_status_payload(full_name, build_number, job_url, info)
        payload["text"] = text
        print_json(payload)
        return

    if not args.follow:
        text = client.console_text(job_url, build_number)
        emit_log_text(text, args.tail)
        return

    start = 0
    catching_up = True
    initial_tail = LogTailBuffer(args.tail) if args.tail and args.tail > 0 else None
    poll_interval = int(config["defaults"].get("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS))
    while True:
        previous_start = start
        text, start, more = client.progressive_console(job_url, build_number, start)
        if initial_tail is not None:
            if start < previous_start:
                initial_tail.clear()
            initial_tail.append(text)
            if not text or not more:
                emit_log_text(initial_tail.text())
                initial_tail = None
        else:
            emit_log_text(text)
        if catching_up:
            # Running logs may be paginated. Drain the initial backlog without
            # a poll delay, whether printing every page or buffering its tail.
            if text and more:
                continue
            catching_up = False
        if not more:
            break
        time.sleep(poll_interval)


class LogTailBuffer:
    """Retain only the last N lines while draining initial log pages."""

    def __init__(self, lines: int):
        self.lines: deque[str] = deque(maxlen=lines)
        self.pending = ""
        self.after_cr = False

    def clear(self) -> None:
        self.lines.clear()
        self.pending = ""
        self.after_cr = False

    def append(self, text: str) -> None:
        if not text:
            return
        if self.after_cr and text.startswith("\n"):
            text = text[1:]
        self.after_cr = text.endswith("\r")
        for line in io.StringIO(text, newline=None):
            if line.endswith("\n"):
                self.lines.append(self.pending + line[:-1])
                self.pending = ""
            else:
                self.pending += line

    def text(self) -> str:
        lines = deque(self.lines, maxlen=self.lines.maxlen)
        if self.pending:
            lines.append(self.pending)
        return "\n".join(lines)


def emit_log_text(text: str, tail: int | None = None) -> None:
    if tail and tail > 0:
        # Keep only N lines instead of materializing a second copy of every line.
        text = "\n".join(deque((line.rstrip("\r\n") for line in io.StringIO(text, newline=None)), maxlen=tail))
    if text:
        print(text, end="" if text.endswith("\n") else "\n", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="管理 Jenkins jobs、分支与构建。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="管理本地配置")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)

    config_init = config_subparsers.add_parser("init", help="初始化 Jenkins 配置")
    config_init.add_argument("--url", help="Jenkins URL")
    config_init.add_argument("--username", help="用户名")
    config_init.add_argument("--token", help="API token")
    config_init.add_argument("--verify-ssl", type=bool_value, help="是否校验证书（true/false）")
    config_init.set_defaults(func=cmd_config_init)

    config_show = config_subparsers.add_parser("show", help="查看配置")
    config_show.add_argument("--json", action="store_true", help="输出 JSON")
    config_show.set_defaults(func=cmd_config_show)

    config_path = config_subparsers.add_parser("path", help="显示配置文件路径")
    config_path.set_defaults(func=cmd_config_path)

    doctor_parser = subparsers.add_parser("doctor", help="检查配置和连接，同步 jobs 并提醒缺少的描述")
    doctor_parser.add_argument("--json", action="store_true", help="输出 JSON")
    doctor_parser.set_defaults(func=cmd_doctor)

    jobs_parser = subparsers.add_parser("jobs", help="列出和管理 jobs（自动同步本地配置）")
    jobs_parser.add_argument("--query", help="按 job 名称、标签或描述过滤")
    jobs_parser.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_parser.set_defaults(func=cmd_jobs_list)
    jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command")

    jobs_list = jobs_subparsers.add_parser("list", help="列出可构建 jobs")
    jobs_list.add_argument("--query", help="按 job 名称、标签或描述过滤")
    jobs_list.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_list.set_defaults(func=cmd_jobs_list)

    jobs_label = jobs_subparsers.add_parser("label", help="标注 job 为测试服或正式服")
    jobs_label.add_argument("job_name", help="完整 Jenkins job 名称（支持中文）")
    jobs_label.add_argument("label", choices=["test", "prod"], help="标签")
    jobs_label.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_label.set_defaults(func=cmd_jobs_label)

    jobs_unlabel = jobs_subparsers.add_parser("unlabel", help="移除 job 标签")
    jobs_unlabel.add_argument("job_name", help="完整 Jenkins job 名称（支持中文）")
    jobs_unlabel.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_unlabel.set_defaults(func=cmd_jobs_unlabel)

    jobs_desc = jobs_subparsers.add_parser("desc", help="设置 job 描述（空字符串清除）")
    jobs_desc.add_argument("job_name", help="完整 Jenkins job 名称（支持中文）")
    jobs_desc.add_argument("description", help="自然语言描述；传入空字符串清除")
    jobs_desc.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_desc.set_defaults(func=cmd_jobs_desc)

    build_parser_ = subparsers.add_parser("build", help="触发构建")
    build_parser_.add_argument("--job", type=nonempty_value, help="完整 Jenkins job 名称；省略时交互选择")
    build_parser_.add_argument("--branch", type=nonempty_value, help="先持久修改分支再构建；指定 --job 时省略则使用当前分支")
    build_parser_.add_argument("--follow", action="store_true", help="等待构建完成")
    build_parser_.add_argument("--json", action="store_true", help="输出 JSON")
    build_parser_.set_defaults(func=cmd_build)

    set_branch_parser = subparsers.add_parser("set-branch", help="修改 Jenkins Git Branch Specifier")
    set_branch_parser.add_argument("--job", type=nonempty_value, help="完整 Jenkins job 名称；省略时交互选择")
    set_branch_parser.add_argument("--branch", type=nonempty_value, help="目标分支名称；省略时交互输入")
    set_branch_parser.add_argument("--json", action="store_true", help="输出 JSON")
    set_branch_parser.set_defaults(func=cmd_set_branch)

    runs_parser = subparsers.add_parser("runs", help="查看运行中的构建")
    runs_subparsers = runs_parser.add_subparsers(dest="runs_command", required=True)

    runs_list = runs_subparsers.add_parser("list", help="列出运行中的构建")
    runs_list.add_argument("--json", action="store_true", help="输出 JSON")
    runs_list.set_defaults(func=cmd_runs_list)

    runs_status = runs_subparsers.add_parser("status", help="查询某次构建的状态")
    runs_status.add_argument("run_id", help="格式: <full-job-name>#<build-number>")
    runs_status.add_argument("--json", action="store_true", help="输出 JSON")
    runs_status.set_defaults(func=cmd_runs_status)

    runs_stop = runs_subparsers.add_parser("stop", help="停止运行中的构建")
    runs_stop.add_argument("run_id", help="格式: <full-job-name>#<build-number>")
    runs_stop.add_argument("--json", action="store_true", help="输出 JSON")
    runs_stop.set_defaults(func=cmd_runs_stop)

    logs_parser = subparsers.add_parser("logs", help="查看 console output")
    logs_parser.add_argument("run_id", help="格式: <full-job-name>#<build-number>")
    logs_parser.add_argument("--tail", type=int, help="仅展示最后 N 行")
    logs_parser.add_argument("--follow", action="store_true", help="持续输出直到构建结束")
    logs_parser.add_argument("--json", action="store_true", help="输出 JSON")
    logs_parser.set_defaults(func=cmd_logs)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except CLIError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("已取消", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

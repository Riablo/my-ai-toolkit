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
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
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
    def aliases(self) -> list[str]:
        raw = self.metadata.get("aliases")
        if not isinstance(raw, list):
            return []
        return [str(alias) for alias in raw if str(alias).strip()]

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
        return merged

    jenkins = data.get("jenkins")
    if isinstance(jenkins, dict):
        merged["jenkins"].update({k: v for k, v in jenkins.items() if v is not None})

    defaults = data.get("defaults")
    if isinstance(defaults, dict):
        merged["defaults"].update({k: v for k, v in defaults.items() if v is not None})

    jobs = data.get("jobs")
    if isinstance(jobs, dict):
        merged["jobs"] = {
            str(name): normalize_job_meta(meta)
            for name, meta in jobs.items()
            if isinstance(name, str) and isinstance(meta, dict)
        }

    return merged


def normalize_job_meta(meta: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    label = meta.get("label", meta.get("env"))
    if label in LABEL_DISPLAY:
        normalized["label"] = label

    aliases: list[str] = []
    raw_aliases = meta.get("aliases")
    if isinstance(raw_aliases, list):
        aliases.extend(str(alias).strip() for alias in raw_aliases if str(alias).strip())
    elif isinstance(raw_aliases, str) and raw_aliases.strip():
        aliases.extend(part.strip() for part in raw_aliases.split(",") if part.strip())

    legacy_keywords = meta.get("keywords")
    if isinstance(legacy_keywords, str) and legacy_keywords.strip():
        aliases.extend(part.strip() for part in legacy_keywords.split(",") if part.strip())

    deduped_aliases = list(dict.fromkeys(aliases))
    if deduped_aliases:
        normalized["aliases"] = deduped_aliases

    return normalized


def load_config(required: bool = True) -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        if required:
            raise CLIError(
                f"配置文件不存在: {CONFIG_PATH}\n请先运行: {APP_NAME} config init"
            )
        return default_config()

    with CONFIG_PATH.open() as handle:
        data = yaml.safe_load(handle) or {}

    config = ensure_config_shape(data)

    if required:
        missing = []
        if not config["jenkins"].get("url"):
            missing.append("jenkins.url")
        if not config["jenkins"].get("username"):
            missing.append("jenkins.username")
        if not config["jenkins"].get("token"):
            missing.append("jenkins.token")
        if missing:
            raise CLIError(
                f"配置文件缺少必填字段: {', '.join(missing)}\n请运行: {APP_NAME} config init"
            )

    return config


def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w") as handle:
        yaml.safe_dump(config, handle, allow_unicode=True, sort_keys=False)
    os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)


def masked_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return "*" * len(token)
    return f"{token[:2]}{'*' * (len(token) - 4)}{token[-2:]}"


def bool_value(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"无法识别布尔值: {value}")


def ci_equals(left: str, right: str) -> bool:
    return left.casefold() == right.casefold()


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
        return response.json()

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
            return CLIError(f"HTTP {response.status_code}: {url}\n{message}")
        return CLIError(f"HTTP {response.status_code}: {url}")

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        def walk(container_url: str) -> None:
            data = self.get_json(
                f"{container_url.rstrip('/')}/api/json",
                params={"tree": "jobs[name,fullName,url,color,_class,buildable]"},
            )
            for item in data.get("jobs", []):
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
                except CLIError:
                    continue
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
        endpoint = f"{job_url.rstrip('/')}/build"
        response = self.post(
            endpoint,
            expected_codes=(200, 201, 202, 302),
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
    *,
    client: JenkinsClient | None = None,
    with_live_branch_specs: bool = False,
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
    if with_live_branch_specs:
        if client is None:
            raise CLIError("获取实时分支信息时缺少 Jenkins client")
        for entry in entries:
            entry.live_branch_specifier = fetch_live_branch_specifier(client, entry.url)
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
    haystacks = [entry.full_name, entry.label_display, *(entry.aliases)]
    return any(contains_ci(haystack, query) for haystack in haystacks if haystack)


def resolve_job_ref(ref: str, entries: list[JobEntry]) -> JobEntry:
    for entry in entries:
        if entry.full_name == ref:
            return entry

    alias_candidates = [
        entry
        for entry in entries
        if any(ci_equals(alias, ref) for alias in entry.aliases)
    ]
    if len(alias_candidates) == 1:
        return alias_candidates[0]
    if len(alias_candidates) > 1:
        raise CLIError(
            f"别称不唯一: {ref}\n"
            "匹配到这些 job:\n"
            + "\n".join(f"- {entry.full_name}" for entry in alias_candidates[:20])
        )

    candidates = [entry for entry in entries if contains_ci(entry.full_name, ref)]
    if candidates:
        raise CLIError(
            "命令行参数只接受完整 Jenkins job name 或唯一别称。\n"
            "可能的 job name 候选:\n"
            + "\n".join(f"- {entry.full_name}" for entry in candidates[:20])
        )
    raise CLIError(
        f"找不到 job 或别称: {ref}\n"
        f"可以先运行: {APP_NAME} jobs list --query \"{ref}\""
    )


def save_job_meta(config: dict[str, Any], full_name: str, meta: dict[str, Any]) -> None:
    jobs = config.setdefault("jobs", {})
    normalized = normalize_job_meta(meta)
    if normalized:
        jobs[full_name] = normalized
    else:
        jobs.pop(full_name, None)


def render_jobs(entries: list[JobEntry]) -> str:
    rows = []
    for index, entry in enumerate(entries, start=1):
        rows.append(
            [
                f"{index}. {entry.full_name}",
                entry.label_display,
                entry.branch_display,
                ", ".join(entry.aliases) or "-",
            ]
        )
    if not rows:
        return "没有找到任何 job。"
    return build_cards(rows, ["JOB", "LABEL", "BRANCH", "ALIASES"])


def interactive_select_job(entries: list[JobEntry]) -> JobEntry:
    require_tty()
    if not entries:
        raise CLIError("当前没有可供选择的 job")
    while True:
        answer = input("请输入要构建的序号（1 开始）: ").strip()
        if not answer:
            continue
        try:
            index = int(answer)
        except ValueError:
            print("请输入数字序号。", file=sys.stderr)
            continue
        if 1 <= index <= len(entries):
            return entries[index - 1]
        print("序号超出范围。", file=sys.stderr)


def numbered_jobs(entries: list[JobEntry]) -> str:
    rows = []
    for index, entry in enumerate(entries, start=1):
        rows.append(
            [
                f"{index}. {entry.full_name}",
                entry.label_display,
                entry.branch_display,
                ", ".join(entry.aliases) or "-",
            ]
        )
    return build_cards(rows, ["", "LABEL", "BRANCH", "ALIASES"])


def parse_branch_specifier(xml_text: str) -> tuple[str, ET.ElementTree, ET.Element]:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(xml_text, parser=parser)
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
        "aliases": entry.aliases,
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


def create_client_and_entries(*, with_live_branch_specs: bool = False) -> tuple[dict[str, Any], JenkinsClient, list[JobEntry]]:
    config = load_config(required=True)
    client = JenkinsClient(config)
    entries = job_entries_from_live_jobs(
        config,
        client.list_jobs(),
        client=client,
        with_live_branch_specs=with_live_branch_specs,
    )
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


def cmd_config_edit(args: argparse.Namespace) -> None:
    editor = os.environ.get("EDITOR", "vi")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        save_config(default_config())
    try:
        subprocess.run([editor, str(CONFIG_PATH)], check=True)
    except FileNotFoundError as exc:
        raise CLIError(f"找不到编辑器: {editor}") from exc
    except subprocess.CalledProcessError as exc:
        raise CLIError(f"编辑器退出失败: {exc.returncode}") from exc


def cmd_config_path(args: argparse.Namespace) -> None:
    print(CONFIG_PATH)


def cmd_config_check(args: argparse.Namespace) -> None:
    config = load_config(required=True)
    payload = {
        "status": "ok",
        "configPath": str(CONFIG_PATH),
        "jenkins": {
            "url": normalize_base_url(str(config["jenkins"].get("url") or "")),
            "username": str(config["jenkins"].get("username") or ""),
            "token": masked_token(str(config["jenkins"].get("token") or "")),
            "verify_ssl": bool(config["jenkins"].get("verify_ssl", DEFAULT_VERIFY_SSL)),
        },
        "jobsCount": len(config.get("jobs") or {}),
    }
    print_json(payload)


def cmd_jobs_list(args: argparse.Namespace) -> None:
    config, client, entries = create_client_and_entries(with_live_branch_specs=True)
    _ = client
    filtered = filter_jobs(entries, query=args.query)
    if args.json:
        print_json([job_info_payload(entry) for entry in filtered])
        return
    print(render_jobs(filtered))


def cmd_jobs_label(args: argparse.Namespace) -> None:
    config, _, entries = create_client_and_entries()
    entry = resolve_job_ref(args.job_ref, entries)
    meta = normalize_job_meta(config.setdefault("jobs", {}).get(entry.full_name) or {})
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
    config, _, entries = create_client_and_entries()
    entry = resolve_job_ref(args.job_ref, entries)
    meta = normalize_job_meta(config.setdefault("jobs", {}).get(entry.full_name) or {})
    meta.pop("label", None)
    save_job_meta(config, entry.full_name, meta)
    save_config(config)

    payload = {"job": entry.full_name, "label": None}
    if args.json:
        print_json(payload)
        return
    print(f"已移除 job 标签: {entry.full_name}")


def alias_owners(config: dict[str, Any], alias: str) -> list[str]:
    owners = []
    for full_name, meta in (config.get("jobs") or {}).items():
        normalized = normalize_job_meta(meta)
        if any(ci_equals(existing, alias) for existing in normalized.get("aliases", [])):
            owners.append(full_name)
    return owners


def cmd_jobs_alias_list(args: argparse.Namespace) -> None:
    config = load_config(required=False)
    items = []
    for full_name, meta in sorted((config.get("jobs") or {}).items()):
        normalized = normalize_job_meta(meta)
        aliases = normalized.get("aliases") or []
        if aliases:
            items.append({"job": full_name, "aliases": aliases})

    if args.json:
        print_json(items)
        return
    if not items:
        print("没有配置任何 job 别称。")
        return
    print(build_cards([[item["job"], ", ".join(item["aliases"])] for item in items], ["JOB", "ALIASES"]))


def cmd_jobs_alias_add(args: argparse.Namespace) -> None:
    config, _, entries = create_client_and_entries()
    entry = resolve_job_ref(args.job_ref, entries)
    alias = args.alias.strip()
    if not alias:
        raise CLIError("别称不能为空")

    owners = [owner for owner in alias_owners(config, alias) if owner != entry.full_name]
    if owners:
        raise CLIError(
            f"别称已被其他 job 使用: {alias}\n"
            + "\n".join(f"- {owner}" for owner in owners[:20])
        )

    meta = normalize_job_meta(config.setdefault("jobs", {}).get(entry.full_name) or {})
    aliases = meta.setdefault("aliases", [])
    if not any(ci_equals(existing, alias) for existing in aliases):
        aliases.append(alias)
    save_job_meta(config, entry.full_name, meta)
    save_config(config)

    payload = {"job": entry.full_name, **normalize_job_meta(config["jobs"][entry.full_name])}
    if args.json:
        print_json(payload)
        return
    print("已添加 job 别称:")
    print(yaml_dump(payload))


def cmd_jobs_alias_rm(args: argparse.Namespace) -> None:
    config, _, entries = create_client_and_entries()
    entry = resolve_job_ref(args.job_ref, entries)
    alias = args.alias.strip()
    meta = normalize_job_meta(config.setdefault("jobs", {}).get(entry.full_name) or {})
    aliases = [existing for existing in meta.get("aliases", []) if not ci_equals(existing, alias)]
    if aliases:
        meta["aliases"] = aliases
    else:
        meta.pop("aliases", None)
    save_job_meta(config, entry.full_name, meta)
    save_config(config)

    payload = {"job": entry.full_name, "removed_alias": alias}
    if args.json:
        print_json(payload)
        return
    print(f"已删除 job 别称: {entry.full_name} -> {alias}")


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
    config, client, entries = create_client_and_entries()
    _ = config
    entry = resolve_job_ref(args.ref, entries)

    payload = update_branch_specifier(client, entry, args.branch)

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
    config, client, entries = create_client_and_entries(with_live_branch_specs=args.ref is None)

    if args.ref:
        targets = [resolve_job_ref(args.ref, entries)]
    else:
        print(numbered_jobs(entries))
        print("")
        targets = [interactive_select_job(entries)]

    results = _trigger_and_collect(client, config, targets, follow=args.follow)

    if args.json:
        print_json(results if len(results) > 1 else results[0])
        return
    for r in results:
        print("构建已触发:")
        print(yaml_dump(r))


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

    last_text = ""
    first_iteration = True
    poll_interval = int(config["defaults"].get("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS))
    while True:
        text = client.console_text(job_url, build_number)
        if first_iteration and args.tail and args.tail > 0:
            lines = text.splitlines()
            text_to_print = "\n".join(lines[-args.tail :])
            if text_to_print:
                print(text_to_print)
        else:
            delta = text[len(last_text) :] if text.startswith(last_text) else text
            if delta:
                print(delta, end="" if delta.endswith("\n") else "\n")
        last_text = text
        info = client.build_info(job_url, build_number)
        if not args.follow or not info.get("building", False):
            break
        first_iteration = False
        time.sleep(poll_interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Trigger Jenkins builds from the command line.")
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

    config_edit = config_subparsers.add_parser("edit", help="编辑配置文件")
    config_edit.set_defaults(func=cmd_config_edit)

    config_path = config_subparsers.add_parser("path", help="显示配置文件路径")
    config_path.set_defaults(func=cmd_config_path)

    config_check = config_subparsers.add_parser("check", help="检查配置是否可用")
    config_check.set_defaults(func=cmd_config_check)

    jobs_parser = subparsers.add_parser("jobs", help="列出和管理 jobs")
    jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command", required=True)

    jobs_list = jobs_subparsers.add_parser("list", help="列出可构建 jobs")
    jobs_list.add_argument("--query", help="按 job 名称、标签或别称过滤")
    jobs_list.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_list.set_defaults(func=cmd_jobs_list)

    jobs_label = jobs_subparsers.add_parser("label", help="标注 job 为测试服或正式服")
    jobs_label.add_argument("job_ref", help="Jenkins job 名称或唯一别称")
    jobs_label.add_argument("label", choices=["test", "prod"], help="标签")
    jobs_label.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_label.set_defaults(func=cmd_jobs_label)

    jobs_unlabel = jobs_subparsers.add_parser("unlabel", help="移除 job 标签")
    jobs_unlabel.add_argument("job_ref", help="Jenkins job 名称或唯一别称")
    jobs_unlabel.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_unlabel.set_defaults(func=cmd_jobs_unlabel)

    jobs_alias = jobs_subparsers.add_parser("alias", help="管理 job 别称")
    jobs_alias_subparsers = jobs_alias.add_subparsers(dest="jobs_alias_command", required=True)

    jobs_alias_list = jobs_alias_subparsers.add_parser("list", help="列出 job 别称")
    jobs_alias_list.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_alias_list.set_defaults(func=cmd_jobs_alias_list)

    jobs_alias_add = jobs_alias_subparsers.add_parser("add", help="添加 job 别称")
    jobs_alias_add.add_argument("job_ref", help="Jenkins job 名称或唯一别称")
    jobs_alias_add.add_argument("alias", help="别称")
    jobs_alias_add.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_alias_add.set_defaults(func=cmd_jobs_alias_add)

    jobs_alias_rm = jobs_alias_subparsers.add_parser("rm", help="删除 job 别称")
    jobs_alias_rm.add_argument("job_ref", help="Jenkins job 名称或唯一别称")
    jobs_alias_rm.add_argument("alias", help="别称")
    jobs_alias_rm.add_argument("--json", action="store_true", help="输出 JSON")
    jobs_alias_rm.set_defaults(func=cmd_jobs_alias_rm)

    build_parser_ = subparsers.add_parser("build", help="触发构建")
    build_parser_.add_argument("ref", nargs="?", help="Jenkins job 名称或唯一别称")
    build_parser_.add_argument("--follow", action="store_true", help="等待构建完成")
    build_parser_.add_argument("--json", action="store_true", help="输出 JSON")
    build_parser_.set_defaults(func=cmd_build)

    set_branch_parser = subparsers.add_parser("set-branch", help="修改 Jenkins Git Branch Specifier")
    set_branch_parser.add_argument("ref", help="Jenkins job 名称或唯一别称")
    set_branch_parser.add_argument("branch", help="目标分支名称")
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
    except KeyboardInterrupt:
        print("已取消", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

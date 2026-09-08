#!/usr/bin/env python3
"""A tiny read-it-later metadata fetcher."""

from __future__ import annotations

import argparse
import html
import http.client
import json
import re
import shutil
import socket
import ssl
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, NoReturn


APP_NAME = "readlater-cli"
DEFAULT_TIMEOUT = 10
DEFAULT_SUMMARY_LENGTH = 280
DEFAULT_RETRIES = 1
MAX_DOWNLOAD_BYTES = 4 * 1024 * 1024
MAX_DECODED_BYTES = 8 * 1024 * 1024
MAX_BODY_TEXT_CHARS = 64 * 1024
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    f"{APP_NAME}/1.0"
)
X_HOSTS = {
    "x.com",
    "twitter.com",
    "mobile.twitter.com",
    "www.x.com",
    "www.twitter.com",
}
BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "main",
    "nav",
    "p",
    "section",
    "td",
    "th",
    "tr",
}


class CliError(Exception):
    """User-facing CLI error."""


@dataclass
class HttpResponse:
    url: str
    status: int
    headers: Any
    body: bytes


@dataclass
class XStatusInfo:
    handle: str | None
    status_id: str


@dataclass
class ReadLaterItem:
    url: str
    title: str | None
    summary: str | None
    source: str
    canonical_url: str | None = None
    author_name: str | None = None
    author_url: str | None = None
    site_name: str | None = None
    fetched_at: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def die(message: str) -> NoReturn:
    raise CliError(message)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = html.unescape(value)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def truncate_text(value: str | None, limit: int) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if limit <= 0 or len(text) <= limit:
        return text

    cut_at = text.rfind(" ", 0, max(1, limit - 3))
    if cut_at < max(20, limit // 2):
        cut_at = max(1, limit - 3)
    return text[:cut_at].rstrip() + "..."


def normalize_input_url(raw_url: str) -> str:
    value = raw_url.strip()
    if not value:
        die("URL 不能为空")

    parsed = urllib.parse.urlparse(value)
    if not parsed.scheme:
        value = f"https://{value}"
        parsed = urllib.parse.urlparse(value)

    if parsed.scheme not in {"http", "https"}:
        die(f"只支持 http/https URL: {raw_url}")
    if not parsed.netloc:
        die(f"URL 格式不正确: {raw_url}")
    return value


def normalize_host(netloc: str) -> str:
    return netloc.split("@")[-1].split(":")[0].lower()


def parse_x_status_url(url: str) -> XStatusInfo | None:
    parsed = urllib.parse.urlparse(url)
    host = normalize_host(parsed.netloc)
    if host not in X_HOSTS:
        return None

    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) >= 3 and parts[1] in {"status", "statuses"}:
        status_id = parts[2]
        if status_id.isdigit():
            return XStatusInfo(handle=parts[0], status_id=status_id)

    if len(parts) >= 4 and parts[:3] == ["i", "web", "status"]:
        status_id = parts[3]
        if status_id.isdigit():
            return XStatusInfo(handle=None, status_id=status_id)

    return None


def handle_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None
    handle = urllib.parse.unquote(parts[0]).strip("@ ")
    return handle or None


def decode_response_body(body: bytes, headers: Any, max_bytes: int = MAX_DECODED_BYTES) -> bytes:
    encoding = str(headers.get("Content-Encoding", "")).lower()
    if "gzip" not in encoding and "deflate" not in encoding:
        if len(body) > max_bytes:
            raise CliError(f"响应正文超过 {max_bytes // 1024} KiB 限制")
        return body

    def decompress(wbits: int) -> bytes:
        remaining = body
        chunks = []
        size = 0
        while remaining:
            decoder = zlib.decompressobj(wbits)
            chunk = decoder.decompress(remaining, max_bytes - size + 1)
            size += len(chunk)
            if size > max_bytes:
                raise CliError(f"解压后的正文超过 {max_bytes // 1024} KiB 限制")
            if not decoder.eof:
                # A raw-deflate stream may happen to start with a valid zlib
                # header. An incomplete candidate must still try the raw form.
                raise zlib.error("压缩响应不完整")
            chunks.append(chunk)
            # gzip permits concatenated members and trailing zero padding.
            remaining = decoder.unused_data.lstrip(b"\x00") if "gzip" in encoding else b""
        return b"".join(chunks)

    try:
        if "gzip" in encoding:
            return decompress(zlib.MAX_WBITS | 16)
        try:
            return decompress(zlib.MAX_WBITS)
        except zlib.error:
            return decompress(-zlib.MAX_WBITS)
    except zlib.error as exc:
        raise CliError("无法解压响应正文") from exc


def read_response_body(response: Any) -> bytes:
    body = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(body) > MAX_DOWNLOAD_BYTES:
        raise CliError(f"响应下载超过 {MAX_DOWNLOAD_BYTES // 1024} KiB 限制")
    return decode_response_body(body, response.headers)


def request_bytes(url: str, timeout: int, accept: str, *, html_only: bool = False) -> HttpResponse:
    return request_bytes_with_retries(url, timeout, accept, retries=DEFAULT_RETRIES, html_only=html_only)


def compact_error_body(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None

    if re.search(r"<(?:!doctype\s+html|html|body|title|h1)\b", text, re.I):
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)

    return truncate_text(text, 300)


def make_request(url: str, accept: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": USER_AGENT,
        },
    )


def is_retryable_url_error(exc: urllib.error.URLError) -> bool:
    return isinstance(
        exc.reason,
        (
            TimeoutError,
            socket.timeout,
            ssl.SSLError,
            http.client.HTTPException,
            OSError,
        ),
    )


def format_network_error(exc: BaseException) -> str:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "请求超时"
    if isinstance(exc, http.client.RemoteDisconnected):
        return "请求失败: 远端在响应前关闭连接"
    return f"请求失败: {exc}"


def request_bytes_with_retries(
    url: str,
    timeout: int,
    accept: str,
    retries: int,
    *,
    html_only: bool = False,
) -> HttpResponse:
    last_error: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(make_request(url, accept), timeout=timeout) as resp:
                body = b"" if html_only and not is_probably_html(resp.headers) else read_response_body(resp)
                return HttpResponse(
                    url=resp.geturl(),
                    status=resp.status,
                    headers=resp.headers,
                    body=body,
                )
        except urllib.error.HTTPError as exc:
            body = read_response_body(exc)
            message = compact_error_body(body.decode("utf-8", errors="replace"))
            raise CliError(f"HTTP {exc.code}: {message or exc.reason}") from exc
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt < retries and is_retryable_url_error(exc):
                continue
            raise CliError(format_network_error(exc.reason)) from exc
        except (
            TimeoutError,
            socket.timeout,
            ssl.SSLError,
            http.client.HTTPException,
            OSError,
        ) as exc:
            last_error = exc
            if attempt < retries:
                continue
            raise CliError(format_network_error(exc)) from exc

    raise CliError(format_network_error(last_error or RuntimeError("unknown error")))


def request_json(url: str, timeout: int) -> dict[str, Any]:
    response = request_bytes(url, timeout, "application/json")
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError("响应不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise CliError("响应 JSON 格式不正确")
    return payload


class TweetOEmbedParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_p = 0
        self.paragraph_parts: list[str] = []
        self.all_parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() == "p":
            self.in_p += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "p" and self.in_p > 0:
            self.in_p -= 1

    def handle_data(self, data: str) -> None:
        if data:
            self.all_parts.append(data)
            if self.in_p:
                self.paragraph_parts.append(data)


def extract_text_from_oembed_html(raw_html: str) -> str | None:
    parser = TweetOEmbedParser()
    parser.feed(raw_html)
    text = clean_text(" ".join(parser.paragraph_parts))
    if not text:
        text = clean_text(" ".join(parser.all_parts))
    if not text:
        return None

    # X oEmbed often leaves trailing media links in the fallback text. They are
    # useful for rendering, but noisy in a read-it-later one-line summary.
    text = re.sub(r"\s+pic\.(?:twitter|x)\.com/\S+$", "", text)
    return clean_text(text)


def build_x_title(author_name: str | None, handle: str | None) -> str:
    author = clean_text(author_name)
    if author and handle:
        return f"{author} (@{handle}) on X"
    if author:
        return f"{author} on X"
    if handle:
        return f"@{handle} on X"
    return "X Post"


def fetch_x_oembed(
    url: str,
    info: XStatusInfo,
    timeout: int,
    summary_length: int,
) -> ReadLaterItem:
    query = urllib.parse.urlencode(
        {
            "url": url,
            "omit_script": "true",
            "hide_media": "true",
            "hide_thread": "true",
            "dnt": "true",
        }
    )
    payload = request_json(f"https://publish.x.com/oembed?{query}", timeout)

    raw_html = str(payload.get("html") or "")
    summary = truncate_text(extract_text_from_oembed_html(raw_html), summary_length)
    if not summary:
        raise CliError("X oEmbed 响应中没有可读正文")

    author_name = clean_text(str(payload.get("author_name") or "")) or None
    author_url = clean_text(str(payload.get("author_url") or "")) or None
    handle = handle_from_url(author_url) or info.handle

    return ReadLaterItem(
        url=url,
        canonical_url=clean_text(str(payload.get("url") or "")) or None,
        title=build_x_title(author_name, handle),
        summary=summary,
        source="x-oembed",
        author_name=author_name,
        author_url=author_url,
        site_name="X",
        fetched_at=utc_now_iso(),
    )


class _MetadataComplete(Exception):
    """Stop parsing after every output field has its highest-priority value."""


class MetadataHTMLParser(HTMLParser):
    def __init__(self, max_text_parts: int = 800, *, stop_when_complete: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.links: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self.in_title = False
        self.in_body = False
        self.skip_depth = 0
        self.max_text_parts = max_text_parts
        self.body_text_chars = 0
        self.stop_when_complete = stop_when_complete

    def append_body(self, text: str) -> None:
        if len(self.body_parts) >= self.max_text_parts or self.body_text_chars >= MAX_BODY_TEXT_CHARS:
            return
        text = text[: MAX_BODY_TEXT_CHARS - self.body_text_chars]
        self.body_parts.append(text)
        self.body_text_chars += len(text)

    @property
    def has_complete_metadata(self) -> bool:
        # These are the highest-priority fields. Stop only once later tags cannot
        # improve the output, including the optional canonical URL and site name.
        return all(self.meta.get(key) for key in ("og:title", "og:description", "og:url", "og:site_name"))

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        attr_map = {key.lower(): value or "" for key, value in attrs}

        if tag in {"script", "style", "noscript", "template", "svg"}:
            self.skip_depth += 1
            return

        if tag == "title":
            self.in_title = True
        elif tag == "body":
            self.in_body = True
        elif tag == "meta":
            key = (
                attr_map.get("property")
                or attr_map.get("name")
                or attr_map.get("itemprop")
                or ""
            ).strip().lower()
            content = clean_text(attr_map.get("content"))
            if key and content and key not in self.meta:
                self.meta[key] = content
                if self.stop_when_complete and self.has_complete_metadata:
                    raise _MetadataComplete
        elif tag == "link":
            rel = attr_map.get("rel", "").lower()
            href = clean_text(attr_map.get("href"))
            if href and "canonical" in rel:
                self.links["canonical"] = href

        if tag in BLOCK_TAGS and self.in_body:
            self.append_body("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "template", "svg"}:
            if self.skip_depth > 0:
                self.skip_depth -= 1
            return

        if tag == "title":
            self.in_title = False
        elif tag == "body":
            self.in_body = False

        if tag in BLOCK_TAGS and self.in_body:
            self.append_body("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self.in_title:
            self.title_parts.append(data)
            return
        if self.in_body:
            self.append_body(data)

    @property
    def title(self) -> str | None:
        return clean_text(" ".join(self.title_parts))

    @property
    def body_text(self) -> str | None:
        return clean_text(" ".join(self.body_parts))


def decode_html(body: bytes, headers: Any) -> str:
    charset = None
    if hasattr(headers, "get_content_charset"):
        charset = headers.get_content_charset()

    if not charset:
        head = body[:4096].decode("ascii", errors="ignore")
        match = re.search(r"charset=[\"']?([A-Za-z0-9._-]+)", head, re.I)
        if match:
            charset = match.group(1)

    for candidate in [charset, "utf-8", "gb18030", "latin-1"]:
        if not candidate:
            continue
        try:
            return body.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def first_meta(meta: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        value = clean_text(meta.get(key.lower()))
        if value:
            return value
    return None


def remove_title_prefix(summary: str | None, title: str | None) -> str | None:
    clean_summary = clean_text(summary)
    clean_title = clean_text(title)
    if not clean_summary or not clean_title:
        return clean_summary

    if clean_summary.lower().startswith(clean_title.lower()):
        rest = clean_summary[len(clean_title) :].strip(" -:|")
        return rest or clean_summary
    return clean_summary


def readable_title_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.path and parsed.path != "/":
        name = urllib.parse.unquote(parsed.path.rstrip("/").split("/")[-1])
        name = re.sub(r"[-_]+", " ", name).strip()
        if name:
            return name
    return parsed.netloc or url


def is_probably_html(headers: Any) -> bool:
    content_type = str(headers.get("Content-Type", "")).lower()
    return not content_type or "html" in content_type or "text/" in content_type


def fetch_generic_url(url: str, timeout: int, summary_length: int) -> ReadLaterItem:
    response = request_bytes(url, timeout, "text/html,application/xhtml+xml,*/*;q=0.8", html_only=True)

    if not is_probably_html(response.headers):
        content_type = clean_text(str(response.headers.get("Content-Type", "")))
        return ReadLaterItem(
            url=url,
            canonical_url=response.url if response.url != url else None,
            title=readable_title_from_url(response.url),
            summary=f"非 HTML 内容: {content_type}" if content_type else None,
            source="url",
            fetched_at=utc_now_iso(),
        )

    raw_html = decode_html(response.body, response.headers)
    parser = MetadataHTMLParser(stop_when_complete=True)
    try:
        # One feed preserves continuous text: HTMLParser otherwise emits data
        # at each chunk boundary, which would insert spaces into text/title.
        parser.feed(raw_html)
    except _MetadataComplete:
        pass

    title = (
        first_meta(parser.meta, ["og:title", "twitter:title"])
        or parser.title
        or readable_title_from_url(response.url)
    )
    summary = first_meta(
        parser.meta,
        ["og:description", "description", "twitter:description"],
    )
    if not summary:
        summary = parser.body_text
    summary = remove_title_prefix(summary, title)

    canonical_url = first_meta(parser.meta, ["og:url"]) or parser.links.get("canonical")
    if canonical_url:
        canonical_url = urllib.parse.urljoin(response.url, canonical_url)

    return ReadLaterItem(
        url=url,
        canonical_url=canonical_url or (response.url if response.url != url else None),
        title=truncate_text(title, 160),
        summary=truncate_text(summary, summary_length),
        source="html",
        site_name=first_meta(parser.meta, ["og:site_name", "application-name"]),
        fetched_at=utc_now_iso(),
    )


def is_unhelpful_x_item(item: ReadLaterItem) -> bool:
    title = (item.title or "").strip().lower()
    summary = (item.summary or "").strip().lower()
    if title in {"x", "x / ?", "nothing to see here"}:
        return True
    if title.startswith("x /") and not item.summary:
        return True
    if "something went wrong" in summary or "nothing to see here" in summary:
        return True
    return False


def build_x_url_fallback(url: str, info: XStatusInfo) -> ReadLaterItem:
    return ReadLaterItem(
        url=url,
        title=build_x_title(None, info.handle),
        summary=None,
        source="x-url",
        site_name="X",
        fetched_at=utc_now_iso(),
    )


def fetch_readlater_item(
    raw_url: str,
    timeout: int,
    summary_length: int,
) -> ReadLaterItem:
    url = normalize_input_url(raw_url)
    x_info = parse_x_status_url(url)

    if x_info:
        try:
            return fetch_x_oembed(url, x_info, timeout, summary_length)
        except CliError:
            try:
                item = fetch_generic_url(url, timeout, summary_length)
            except CliError:
                return build_x_url_fallback(url, x_info)
            if is_unhelpful_x_item(item):
                return build_x_url_fallback(url, x_info)
            return item

    return fetch_generic_url(url, timeout, summary_length)


def emit_json(item: ReadLaterItem) -> None:
    json.dump(item.to_payload(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def emit_human(item: ReadLaterItem) -> None:
    columns = shutil.get_terminal_size((88, 20)).columns
    summary = item.summary or "-"
    wrapped_summary = textwrap.wrap(
        summary,
        width=max(24, columns - 4),
        break_long_words=False,
        break_on_hyphens=False,
    ) or ["-"]

    print(f"标题：{item.title or '-'}")
    print(f"概要：{wrapped_summary[0]}")
    for line in wrapped_summary[1:]:
        print(f"      {line}")
    print(f"URL：{item.url}")


def add_fetch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("url", help="要抓取的网页或 X/Twitter 帖子 URL")
    parser.add_argument("-j", "--json", action="store_true", help="输出 JSON")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"请求超时时间（秒，默认 {DEFAULT_TIMEOUT}）",
    )
    parser.add_argument(
        "--summary-length",
        type=int,
        default=DEFAULT_SUMMARY_LENGTH,
        help=f"概要最大长度（默认 {DEFAULT_SUMMARY_LENGTH}）",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="抓取一个链接的标题、简单概要和 URL。",
    )
    subparsers = parser.add_subparsers(dest="command")

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="抓取一个链接摘要",
        description="抓取一个链接的标题、简单概要和 URL。",
    )
    add_fetch_args(fetch_parser)

    return parser


def normalize_argv(argv: list[str]) -> list[str]:
    if not argv or argv[0] in {"-h", "--help"}:
        return argv
    if argv[0] == "fetch":
        return argv
    return ["fetch", *argv]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_argv(list(sys.argv[1:] if argv is None else argv)))

    if args.command != "fetch":
        parser.print_help()
        return 0

    if args.timeout <= 0:
        die("`--timeout` 必须大于 0")

    item = fetch_readlater_item(args.url, args.timeout, args.summary_length)
    if args.json:
        emit_json(item)
    else:
        emit_human(item)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CliError as exc:
        eprint(f"错误：{exc}")
        raise SystemExit(1)

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Add or update supported personal Notion records through the official Notion API."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("~/.config/my-notion/config.json").expanduser()
NOTION_BASE_URL = "https://api.notion.com/v1"
DEFAULT_NOTION_VERSION = "2026-03-11"
USER_AGENT = "my-notion/1.0 (my-ai-toolkit)"
ALLOWED_RATINGS = {"💎💎", "💎", "⭐⭐⭐", "⭐⭐", "⭐"}

DEFAULT_CONFIG: dict[str, Any] = {
    "notion_version": DEFAULT_NOTION_VERSION,
    "notion_token": "",
    "data_sources": {
        "music_logs": "463f650e-e366-49d0-b74f-9fdd0dc862be",
        "movie_logs": "98d35d39-5c09-4a0c-932a-e8ad7be8f33b",
        "tv_series_logs": "695d1775-5f82-43d9-9e2e-4d88b06bc906",
    },
    "omdb_api_key": "",
    "media": {
        "music": {
            "data_source": "music_logs",
            "properties": {
                "name": "Name",
                "artists": "Artists",
                "artwork": "Artwork",
                "released_year": "Released Year",
                "rating": "Rating",
                "logged_date": "Logged Date",
            },
        },
        "movie": {
            "data_source": "movie_logs",
            "properties": {
                "name": "Name",
                "director": "Director",
                "imdb": "IMDB",
                "poster": "Poster",
                "released_year": "Released Year",
                "rating": "Rating",
                "logged_date": "Logged Date",
            },
        },
        "tv": {
            "data_source": "tv_series_logs",
            "properties": {
                "name": "Name",
                "creator": "Creator",
                "imdb": "IMDB",
                "poster": "Poster",
                "released_year": "Released Year",
                "seasons": "Seasons",
                "rating": "Rating",
                "logged_date": "Logged Date",
            },
        },
    },
}


class MyNotionError(RuntimeError):
    pass


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise MyNotionError(
            f"配置不存在: {path}\n"
            "先运行: uv run SKILL_DIR/scripts/my_notion.py config-template > ~/.config/my-notion/config.json"
        )
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise MyNotionError(f"配置 JSON 无效: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise MyNotionError(f"配置必须是 JSON object: {path}")
    return deep_merge(DEFAULT_CONFIG, data)


def get_token(config: dict[str, Any], required: bool = True) -> str:
    token = (
        os.environ.get("NOTION_API_KEY", "").strip()
        or os.environ.get("NOTION_TOKEN", "").strip()
        or str(config.get("notion_token", "")).strip()
    )
    if required and not token:
        raise MyNotionError(
            "未找到 Notion token。请设置 NOTION_API_KEY / NOTION_TOKEN，"
            "或在 ~/.config/my-notion/config.json 写入 notion_token。"
        )
    return token


def get_omdb_key(config: dict[str, Any]) -> str:
    key = os.environ.get("OMDB_API_KEY", "").strip() or str(config.get("omdb_api_key", "")).strip()
    if not key:
        raise MyNotionError(
            "Movie/TV 需要 OMDB API key。请设置 OMDB_API_KEY，"
            "或在 ~/.config/my-notion/config.json 写入 omdb_api_key。"
        )
    return key


def resolve_data_source(config: dict[str, Any], value: str) -> str:
    data_sources = config.get("data_sources", {})
    if isinstance(data_sources, dict) and value in data_sources:
        value = data_sources[value]
    data_source_id = str(value).strip().removeprefix("collection://")
    if not data_source_id:
        raise MyNotionError("data source id 不能为空")
    return data_source_id


def request_json(
    method: str,
    path_or_url: str,
    *,
    token: str | None = None,
    notion_version: str | None = None,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    url = path_or_url if path_or_url.startswith("http") else f"{NOTION_BASE_URL}{path_or_url}"
    body = None
    request_headers = {"User-Agent": USER_AGENT}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    if notion_version:
        request_headers["Notion-Version"] = notion_version
    if headers:
        request_headers.update(headers)

    for attempt in range(3):
        req = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < 2:
                retry_after = exc.headers.get("Retry-After", "1")
                try:
                    delay = max(1.0, float(retry_after))
                except ValueError:
                    delay = 1.0
                time.sleep(delay)
                continue
            raise MyNotionError(f"HTTP {exc.code} {method} {url}\n{raw}") from exc
        except urllib.error.URLError as exc:
            raise MyNotionError(f"请求失败 {method} {url}: {exc}") from exc
    raise MyNotionError(f"请求重试后仍失败: {method} {url}")


def fetch_musicbrainz_album(album_name: str, artist_name: str) -> dict[str, Any]:
    query = f"{album_name} {artist_name}"
    url = "https://musicbrainz.org/ws/2/release-group?" + urllib.parse.urlencode(
        {"query": query, "fmt": "json"}
    )
    data = request_json("GET", url, headers={"User-Agent": USER_AGENT})
    release_groups = data.get("release-groups", [])
    if not release_groups:
        raise MyNotionError(f"MusicBrainz 未找到专辑: {album_name} / {artist_name}")

    item = release_groups[0]
    mbid = item.get("id", "")
    raw_date = item.get("first-release-date", "")
    artists = [
        credit["name"]
        for credit in item.get("artist-credit", [])
        if isinstance(credit, dict) and credit.get("name")
    ]
    return {
        "album": item.get("title", album_name),
        "release_year": parse_year(raw_date),
        "artists": artists or [artist_name],
        "artwork": fetch_cover_art(mbid) if mbid else "",
        "mbid": mbid,
    }


def fetch_cover_art(mbid: str) -> str:
    url = f"https://coverartarchive.org/release-group/{mbid}"
    try:
        data = request_json("GET", url, headers={"User-Agent": USER_AGENT}, timeout=15)
    except MyNotionError:
        return ""
    images = data.get("images", [])
    if not images:
        return ""
    first = images[0]
    return first.get("thumbnails", {}).get("large") or first.get("image", "")


def fetch_omdb(title: str, media_type: str, api_key: str) -> dict[str, Any]:
    url = "https://www.omdbapi.com/?" + urllib.parse.urlencode(
        {"apikey": api_key, "t": title, "type": media_type}
    )
    data = request_json("GET", url)
    if data.get("Response") == "False":
        raise MyNotionError(f"OMDB 未找到: {title} (type={media_type}) - {data.get('Error', '')}")

    year = parse_year(data.get("Year", ""))
    result: dict[str, Any] = {
        "title": data.get("Title", title),
        "year": year,
        "poster": "" if data.get("Poster") == "N/A" else data.get("Poster", ""),
        "imdb_id": data.get("imdbID", ""),
        "type": media_type,
    }
    if media_type == "movie":
        result["directors"] = split_people(data.get("Director", ""))
    else:
        result["creators"] = split_people(data.get("Writer", ""))
        result["total_seasons"] = parse_int(data.get("totalSeasons", ""))
    return result


def split_people(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip() and part.strip() != "N/A"]


def parse_year(value: Any) -> int | None:
    match = re.search(r"\d{4}", str(value or ""))
    return int(match.group(0)) if match else None


def parse_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def text_obj(content: str) -> dict[str, Any]:
    return {"text": {"content": content}}


def title_property(value: str) -> dict[str, Any]:
    return {"title": [text_obj(value)]}


def rich_text_property(value: str | list[str]) -> dict[str, Any]:
    if isinstance(value, list):
        value = ", ".join(item for item in value if item)
    return {"rich_text": [text_obj(value)]} if value else {"rich_text": []}


def number_property(value: int | float | None) -> dict[str, Any] | None:
    return {"number": value} if value is not None else None


def date_property(value: str) -> dict[str, Any]:
    return {"date": {"start": value}}


def select_property(value: str) -> dict[str, Any]:
    return {"select": {"name": value}}


def url_property(value: str) -> dict[str, Any] | None:
    return {"url": value} if value else None


def files_property(name: str, url: str) -> dict[str, Any] | None:
    url = clean_url(url)
    if not url:
        return None
    return {"files": [{"name": name, "external": {"url": url}}]}


def clean_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url or url == "N/A":
        return ""
    if url.startswith("http://"):
        return "https://" + url.removeprefix("http://")
    return url


def add_property(properties: dict[str, Any], notion_name: str | None, value: dict[str, Any] | None) -> None:
    if notion_name and value is not None:
        properties[notion_name] = value


def build_media_metadata(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    if args.metadata_json:
        try:
            data = json.loads(args.metadata_json)
        except json.JSONDecodeError as exc:
            raise MyNotionError(f"--metadata-json 不是有效 JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise MyNotionError("--metadata-json 必须是 JSON object")
        return data

    if args.metadata_file:
        with Path(args.metadata_file).expanduser().open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise MyNotionError("--metadata-file 必须包含 JSON object")
        return data

    if args.kind == "music":
        if not args.artist:
            raise MyNotionError("记录 Music Logs 必须提供 --artist")
        return fetch_musicbrainz_album(args.title, args.artist)

    media_type = "movie" if args.kind == "movie" else "series"
    return fetch_omdb(args.title, media_type, get_omdb_key(config))


def build_media_properties(
    kind: str,
    metadata: dict[str, Any],
    rating: str,
    logged_date: str,
    property_map: dict[str, str],
) -> tuple[str, int | None, dict[str, Any]]:
    if rating not in ALLOWED_RATINGS:
        allowed = " / ".join(sorted(ALLOWED_RATINGS))
        raise MyNotionError(f"Rating 必须是已有 Notion 选项之一: {allowed}")

    properties: dict[str, Any] = {}
    if kind == "music":
        title = str(metadata.get("album") or metadata.get("title") or "")
        year = parse_year(metadata.get("release_year") or metadata.get("year"))
        add_property(properties, property_map.get("name"), title_property(title))
        add_property(properties, property_map.get("artists"), rich_text_property(metadata.get("artists", [])))
        add_property(properties, property_map.get("artwork"), files_property("Artwork", metadata.get("artwork", "")))
    elif kind == "movie":
        title = str(metadata.get("title") or "")
        year = parse_year(metadata.get("year") or metadata.get("release_year"))
        imdb_id = str(metadata.get("imdb_id", ""))
        imdb_url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else str(metadata.get("imdb", ""))
        add_property(properties, property_map.get("name"), title_property(title))
        add_property(properties, property_map.get("director"), rich_text_property(metadata.get("directors", [])))
        add_property(properties, property_map.get("imdb"), url_property(imdb_url))
        add_property(properties, property_map.get("poster"), files_property("Poster", metadata.get("poster", "")))
    else:
        title = str(metadata.get("title") or "")
        year = parse_year(metadata.get("year") or metadata.get("release_year"))
        imdb_id = str(metadata.get("imdb_id", ""))
        imdb_url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else str(metadata.get("imdb", ""))
        seasons = parse_int(metadata.get("total_seasons") or metadata.get("seasons"))
        add_property(properties, property_map.get("name"), title_property(title))
        add_property(properties, property_map.get("creator"), rich_text_property(metadata.get("creators", [])))
        add_property(properties, property_map.get("imdb"), url_property(imdb_url))
        add_property(properties, property_map.get("poster"), files_property("Poster", metadata.get("poster", "")))
        add_property(properties, property_map.get("seasons"), number_property(seasons))

    if not title:
        raise MyNotionError("metadata 中缺少标题，无法写入 Notion title 字段")
    add_property(properties, property_map.get("released_year"), number_property(year))
    add_property(properties, property_map.get("rating"), select_property(rating))
    add_property(properties, property_map.get("logged_date"), date_property(logged_date))
    return title, year, properties


def query_existing_page(
    *,
    token: str,
    notion_version: str,
    data_source_id: str,
    title_property_name: str,
    title: str,
    year_property_name: str | None = None,
    year: int | None = None,
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"property": title_property_name, "title": {"equals": title}},
    ]
    if year_property_name and year is not None:
        filters.append({"property": year_property_name, "number": {"equals": year}})
    payload = {"filter": filters[0] if len(filters) == 1 else {"and": filters}, "page_size": 10}
    result = request_json(
        "POST",
        f"/data_sources/{data_source_id}/query",
        token=token,
        notion_version=notion_version,
        payload=payload,
    )
    return list(result.get("results", []))


def create_page(
    *,
    token: str,
    notion_version: str,
    data_source_id: str,
    properties: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "parent": {"type": "data_source_id", "data_source_id": data_source_id},
        "properties": properties,
    }
    return request_json("POST", "/pages", token=token, notion_version=notion_version, payload=payload)


def update_page(
    *,
    token: str,
    notion_version: str,
    page_id: str,
    properties: dict[str, Any],
) -> dict[str, Any]:
    return request_json(
        "PATCH",
        f"/pages/{page_id}",
        token=token,
        notion_version=notion_version,
        payload={"properties": properties},
    )


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def command_config_template(_: argparse.Namespace) -> int:
    print_json(DEFAULT_CONFIG)
    return 0


def command_schema(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    token = get_token(config)
    data_source_id = resolve_data_source(config, args.data_source)
    result = request_json(
        "GET",
        f"/data_sources/{data_source_id}",
        token=token,
        notion_version=str(config.get("notion_version") or DEFAULT_NOTION_VERSION),
    )
    print_json(result)
    return 0


def command_media(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    media_config = config.get("media", {}).get(args.kind)
    if not isinstance(media_config, dict):
        raise MyNotionError(f"配置缺少 media.{args.kind}")
    property_map = media_config.get("properties", {})
    if not isinstance(property_map, dict):
        raise MyNotionError(f"配置 media.{args.kind}.properties 必须是 object")

    metadata = build_media_metadata(args, config)
    logged_date = args.logged_date or dt.date.today().isoformat()
    title, year, properties = build_media_properties(args.kind, metadata, args.rating, logged_date, property_map)
    data_source_id = resolve_data_source(config, str(media_config.get("data_source", "")))
    notion_version = str(config.get("notion_version") or DEFAULT_NOTION_VERSION)

    if args.dry_run:
        print_json(
            {
                "dry_run": True,
                "mode": args.mode,
                "data_source_id": data_source_id,
                "title": title,
                "year": year,
                "properties": properties,
                "metadata": metadata,
            }
        )
        return 0

    token = get_token(config)
    action = args.mode
    page_id = args.page_id
    if args.mode == "upsert":
        matches = query_existing_page(
            token=token,
            notion_version=notion_version,
            data_source_id=data_source_id,
            title_property_name=property_map.get("name", "Name"),
            title=title,
            year_property_name=property_map.get("released_year"),
            year=year,
        )
        if len(matches) > 1:
            urls = [match.get("url", match.get("id", "")) for match in matches]
            raise MyNotionError(f"匹配到多个 Notion 条目，请改用 --page-id 指定: {urls}")
        if matches:
            page_id = matches[0]["id"]
            action = "update"
        else:
            action = "create"

    if action == "update":
        if not page_id:
            raise MyNotionError("--mode update 必须提供 --page-id，或使用 --mode upsert 自动查找")
        result = update_page(token=token, notion_version=notion_version, page_id=page_id, properties=properties)
    elif action == "create":
        result = create_page(token=token, notion_version=notion_version, data_source_id=data_source_id, properties=properties)
    else:
        raise MyNotionError(f"未知 action: {action}")

    print_json({"action": action, "id": result.get("id"), "url": result.get("url"), "metadata": metadata})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage supported personal Notion records through the Notion API.")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="配置文件路径，默认 ~/.config/my-notion/config.json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_template = subparsers.add_parser("config-template", help="输出配置模板")
    config_template.set_defaults(func=command_config_template)

    schema = subparsers.add_parser("schema", help="读取 Notion data source schema")
    schema.add_argument("--data-source", required=True, help="data source alias 或真实 id")
    schema.set_defaults(func=command_schema)

    media = subparsers.add_parser("media", help="新增或编辑 Music/Movie/TV Series Logs")
    media.add_argument("--kind", required=True, choices=["music", "movie", "tv"])
    media.add_argument("--title", required=True, help="专辑名、电影名或剧集名")
    media.add_argument("--artist", help="Music Logs 必填：艺术家名")
    media.add_argument("--rating", required=True, help="Notion Rating 选项，如 💎、⭐⭐⭐")
    media.add_argument("--logged-date", help="YYYY-MM-DD，默认今天")
    media.add_argument("--mode", choices=["upsert", "create", "update"], default="upsert")
    media.add_argument("--page-id", help="明确更新某个 Notion page 时使用")
    media.add_argument("--metadata-json", help="跳过外部查询，直接使用 JSON metadata")
    media.add_argument("--metadata-file", help="跳过外部查询，从 JSON 文件读取 metadata")
    media.add_argument("--dry-run", action="store_true", help="只输出 Notion payload，不写入")
    media.set_defaults(func=command_media)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MyNotionError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

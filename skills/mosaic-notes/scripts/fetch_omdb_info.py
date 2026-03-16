#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
fetch_omdb_info.py - 从 OMDB API 获取电影/剧集信息
用法: uv run fetch_omdb_info.py "<片名>" --type movie|series

API key 读取顺序:
1. 环境变量 OMDB_API_KEY
2. ~/.config/mosaic-notes/config.json 中的 omdb_api_key 字段
"""

import sys
import json
import os
import re
import urllib.request
import urllib.parse


def sanitize_filename(name):
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    sanitized = sanitized.strip().strip(".")
    sanitized = re.sub(r"[\s.]+$", "", sanitized)
    if not sanitized or sanitized.startswith("."):
        sanitized = "unnamed" + sanitized
    return sanitized[:255]


def get_api_key():
    key = os.environ.get("OMDB_API_KEY", "").strip()
    if key:
        return key
    config_file = os.path.expanduser("~/.config/mosaic-notes/config.json")
    if os.path.exists(config_file):
        with open(config_file) as f:
            config = json.load(f)
        key = config.get("omdb_api_key", "").strip()
        if key:
            return key
    print("错误: 未找到 OMDB API key。请设置 OMDB_API_KEY 环境变量或在 ~/.config/mosaic-notes/config.json 中配置 omdb_api_key。", file=sys.stderr)
    sys.exit(1)


def search_omdb(title, media_type, api_key):
    url = "http://www.omdbapi.com/?" + urllib.parse.urlencode({
        "apikey": api_key,
        "t": title,
        "type": media_type,
    })
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)

    if data.get("Response") == "False":
        raise ValueError(f"OMDB 未找到: {title} (type={media_type}) - {data.get('Error', '')}")

    return data


def is_chinese_text(text):
    return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))


def get_chinese_title_from_wikipedia(title, media_type):
    try:
        search_query = title
        if media_type == "movie":
            search_query += " film"

        headers = {"User-Agent": "fetch_omdb_info/1.0 (mosaic-notes)"}

        search_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query",
            "list": "search",
            "srsearch": search_query,
            "format": "json",
            "srlimit": 1,
            "utf8": 1,
        })

        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)

        results = data.get("query", {}).get("search", [])
        if not results:
            return None

        page_id = results[0]["pageid"]

        langlinks_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query",
            "pageids": page_id,
            "prop": "langlinks",
            "lllang": "zh",
            "format": "json",
            "utf8": 1,
        })

        req = urllib.request.Request(langlinks_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            for link in page.get("langlinks", []):
                if link.get("lang") == "zh":
                    return link.get("*", "").strip()

        return None

    except Exception as e:
        print(f"警告: 无法从 Wikipedia 获取中文标题: {e}", file=sys.stderr)
        return None


def main():
    if len(sys.argv) < 3:
        print('用法: uv run fetch_omdb_info.py "<片名>" --type movie|series', file=sys.stderr)
        sys.exit(1)

    title = sys.argv[1]
    media_type = "movie"

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--type" and i + 1 < len(sys.argv):
            media_type = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    if media_type not in ("movie", "series"):
        print("错误: --type 必须是 movie 或 series", file=sys.stderr)
        sys.exit(1)

    api_key = get_api_key()
    data = search_omdb(title, media_type, api_key)

    year = data.get("Year", "Unknown")
    if "–" in year or "-" in year:
        year = re.split(r"[–\-]", year)[0]

    omdb_title = data.get("Title", title)

    aliases = []
    if not is_chinese_text(omdb_title):
        zh_title = get_chinese_title_from_wikipedia(omdb_title, media_type)
        if zh_title:
            aliases.append(zh_title)

    result = {
        "title": omdb_title,
        "year": year,
        "poster": data.get("Poster", "N/A"),
        "imdb_id": data.get("imdbID", ""),
        "type": media_type,
        "aliases": aliases,
    }

    if media_type == "movie":
        directors = [d.strip() for d in data.get("Director", "").split(",") if d.strip() and d.strip() != "N/A"]
        result["directors"] = directors
    else:
        creators = [c.strip() for c in data.get("Writer", "").split(",") if c.strip() and c.strip() != "N/A"]
        result["creators"] = creators
        result["total_seasons"] = data.get("totalSeasons", "")

    result["filename"] = sanitize_filename(f"{result['title']} ({year}).md")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

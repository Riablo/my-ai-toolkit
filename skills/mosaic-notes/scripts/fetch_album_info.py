#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""
fetch_album_info.py - 从 MusicBrainz 和 Cover Art Archive 获取专辑信息
用法: uv run fetch_album_info.py "<专辑名>" "<艺术家>"
"""

import sys
import json
import re
import urllib.request
import urllib.parse

USER_AGENT = "MosaicObsidian/1.0 (mosaic-notes)"


def sanitize_filename(name):
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    sanitized = sanitized.strip().strip(".")
    sanitized = re.sub(r"[\s.]+$", "", sanitized)
    if not sanitized or sanitized.startswith("."):
        sanitized = "unnamed" + sanitized
    return sanitized[:255]


def search_album(album_name, artist_name):
    query = f"{album_name} {artist_name}"
    url = "https://musicbrainz.org/ws/2/release-group?" + urllib.parse.urlencode({
        "query": query,
        "fmt": "json"
    })
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)

    release_groups = data.get("release-groups", [])
    if not release_groups:
        raise ValueError(f"MusicBrainz 未找到专辑: {album_name} / {artist_name}")

    return release_groups[0]


def fetch_artwork(mbid):
    url = f"https://coverartarchive.org/release-group/{mbid}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
        images = data.get("images", [])
        if images:
            return images[0]["thumbnails"].get("large", images[0].get("image", ""))
    except Exception:
        pass
    return ""


def main():
    if len(sys.argv) < 3:
        print("用法: uv run fetch_album_info.py \"<专辑名>\" \"<艺术家>\"", file=sys.stderr)
        sys.exit(1)

    album_name = sys.argv[1]
    artist_name = sys.argv[2]

    item = search_album(album_name, artist_name)

    title = item["title"]
    raw_date = item.get("first-release-date", "")
    release_year = raw_date[:4] if raw_date else "Unknown"
    mbid = item["id"]
    artists = [
        c["name"]
        for c in item.get("artist-credit", [])
        if isinstance(c, dict) and "name" in c
    ]

    artwork = fetch_artwork(mbid)

    artists_str = ", ".join(artists)
    filename = sanitize_filename(f"{artists_str} - {title} ({release_year}).md")

    result = {
        "album": title,
        "release_year": release_year,
        "artists": artists,
        "artwork": artwork,
        "filename": filename,
        "mbid": mbid
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

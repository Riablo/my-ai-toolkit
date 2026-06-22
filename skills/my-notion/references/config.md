# My Notion 配置

配置文件固定为：

```text
~/.config/my-notion/config.json
```

最小配置示例：

```json
{
  "notion_version": "2026-03-11",
  "notion_token": "",
  "data_sources": {
    "music_logs": "463f650e-e366-49d0-b74f-9fdd0dc862be",
    "movie_logs": "98d35d39-5c09-4a0c-932a-e8ad7be8f33b",
    "tv_series_logs": "695d1775-5f82-43d9-9e2e-4d88b06bc906"
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
        "logged_date": "Logged Date"
      }
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
        "logged_date": "Logged Date"
      }
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
        "logged_date": "Logged Date"
      }
    }
  }
}
```

## Token 规则

优先使用环境变量：

```bash
export NOTION_API_KEY="<notion-token>"
```

也支持 `NOTION_TOKEN` 或配置里的 `notion_token`。不要把真实 token 提交进仓库。

## 初始化建议

如果用户没有配置文件：

```bash
mkdir -p ~/.config/my-notion
uv run SKILL_DIR/scripts/my_notion.py config-template > ~/.config/my-notion/config.json
```

然后让用户把 `notion_token` 或环境变量补上，并确认对应数据库已经分享给 Notion integration。

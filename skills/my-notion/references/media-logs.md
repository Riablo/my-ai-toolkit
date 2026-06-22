# Media Logs

本 workflow 把 Mosaic Obsidian 的 Music/Movie/TV metadata 流程改成 Notion database page add/update。

## 数据源

默认数据源来自用户当前 Notion 页面：

| Kind | Database | Data Source |
| --- | --- | --- |
| `music` | Music Logs | `463f650e-e366-49d0-b74f-9fdd0dc862be` |
| `movie` | Movie Logs | `98d35d39-5c09-4a0c-932a-e8ad7be8f33b` |
| `tv` | TV Series Logs | `695d1775-5f82-43d9-9e2e-4d88b06bc906` |

## 字段映射

### Music

| Notion 字段 | 类型 | 来源 |
| --- | --- | --- |
| `Name` | title | MusicBrainz release-group title |
| `Artists` | rich text | MusicBrainz artist-credit names, 逗号连接 |
| `Artwork` | files | Cover Art Archive external URL |
| `Released Year` | number | first-release-date 的年份 |
| `Rating` | select | 用户评分 |
| `Logged Date` | date | 今天或用户给定日期 |

### Movie

| Notion 字段 | 类型 | 来源 |
| --- | --- | --- |
| `Name` | title | OMDB Title |
| `Director` | rich text | OMDB Director, 逗号连接 |
| `IMDB` | url | `https://www.imdb.com/title/<imdb_id>/` |
| `Poster` | files | OMDB Poster external URL |
| `Released Year` | number | OMDB Year 起始年份 |
| `Rating` | select | 用户评分 |
| `Logged Date` | date | 今天或用户给定日期 |

### TV Series

| Notion 字段 | 类型 | 来源 |
| --- | --- | --- |
| `Name` | title | OMDB Title |
| `Creator` | rich text | OMDB Writer, 逗号连接 |
| `IMDB` | url | `https://www.imdb.com/title/<imdb_id>/` |
| `Poster` | files | OMDB Poster external URL |
| `Released Year` | number | OMDB Year 起始年份 |
| `Seasons` | number | OMDB totalSeasons |
| `Rating` | select | 用户评分 |
| `Logged Date` | date | 今天或用户给定日期 |

## 命令

```bash
uv run SKILL_DIR/scripts/my_notion.py media --kind music --title "An Evening With Silk Sonic" --artist "Silk Sonic" --rating "⭐⭐⭐"
uv run SKILL_DIR/scripts/my_notion.py media --kind movie --title "The Shawshank Redemption" --rating "💎"
uv run SKILL_DIR/scripts/my_notion.py media --kind tv --title "Breaking Bad" --rating "💎💎"
```

## 查询与编辑

- 默认 `--mode upsert`：用 `Name` 加 `Released Year` 匹配已有条目。
- 明确新增：`--mode create`。
- 明确编辑：`--mode update --page-id <page_id>`。
- 字段不确定时：加 `--dry-run`。

## 注意

- 用户给中文片名/剧名且不确定英文原名时，先用 WebSearch 确认，再把英文原名交给 OMDB。
- OMDB 查询失败时，不要编造导演、主创、年份、海报或 IMDB ID。
- 当前 Notion schema 没有 aliases 字段，所以中文译名只作为人工确认线索，不写入 Notion。

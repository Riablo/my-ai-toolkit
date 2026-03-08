# TV Series Logs 工作流

当用户要记录一部剧集时，执行以下流程：

## 所需信息

- 剧集名称（必须）
- 评分（必须，未提供时询问用户）

评分标准参见 SKILL.md 的评分系统。

## Step 1：确认剧名

用户给出的剧名可能是中文翻译。若不确定对应的原剧名，先用 WebSearch 搜索确认英文原名，再用原名查询 OMDB。

## Step 2：运行脚本获取剧集数据

```bash
uv run SKILL_DIR/scripts/fetch_omdb_info.py "<剧名>" --type series
```

输出 JSON 示例：
```json
{
  "title": "Breaking Bad",
  "year": "2008",
  "poster": "https://m.media-amazon.com/images/...",
  "imdb_id": "tt0903747",
  "type": "series",
  "aliases": ["绝命毒师"],
  "creators": ["Vince Gilligan"],
  "total_seasons": "5",
  "filename": "Breaking Bad (2008).md"
}
```

`aliases` 字段规则：
- 原剧名为非中文 → 脚本自动查询 Wikipedia 获取中文译名，填入 aliases
- 原剧名为中文 → aliases 为空数组 `[]`

**注意**：API key 读取顺序：(1) 环境变量 `OMDB_API_KEY` (2) `~/.config/mosaic-notes/config.json` 中的 `omdb_api_key` 字段。

## Step 3：创建笔记

### 文件名格式

```
剧名 (年份).md
```

### 创建笔记文件

使用 create_from_template.py 创建（模板名 `TV Series Logs`），在 `Inbox/<filename>` 创建。然后用 Read + Edit 工具编辑 frontmatter，最终文件内容如下：

```yaml
---
aliases:
  - "<中文译名>"
categories: TV Series Logs
title: <剧名>
creators:
  - "[[主创1]]"
  - "[[主创2]]"
release_year: "[[Year <年份>|<年份>]]"
poster: <海报URL>
seasons: <总季数>
rating: <评分>
imdb: https://www.imdb.com/title/<imdb_id>/
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---
```

### 示例输出（英文原剧）

以 "Breaking Bad" 为例：

```yaml
---
aliases:
  - "绝命毒师"
categories: TV Series Logs
title: Breaking Bad
creators:
  - "[[Vince Gilligan]]"
release_year: "[[Year 2008|2008]]"
poster: https://m.media-amazon.com/images/...
seasons: 5
rating: 💎💎
imdb: https://www.imdb.com/title/tt0903747/
created: 2026-02-18
updated: 2026-02-18
---
```

## 存放位置

`Inbox/` 目录，文件名按上述格式生成。

## 注意事项

- `categories` 使用字符串格式（非数组），值为 `TV Series Logs`
- `release_year` 使用 wiki 链接格式 `"[[Year YYYY|YYYY]]"`
- `creators` 每个主创用 `"[[...]]"` 包裹，多行格式；来源于 OMDB 的 Writer 字段
- `seasons` 为数字（非字符串），来源于 OMDB 的 totalSeasons
- `imdb` 格式为 `https://www.imdb.com/title/<imdb_id>/`
- `poster` 使用 OMDB 返回的海报 URL，若为 `N/A` 则留空
- `aliases` 默认为空数组 `[]`，用户可提供中文别名
- `created` 和 `updated` 值相同，均为今天日期
- 正文部分留空（frontmatter only）

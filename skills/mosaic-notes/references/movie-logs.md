# Movie Logs 工作流

当用户要记录一部电影时，执行以下流程：

## 所需信息

- 电影名称（必须）
- 评分（必须，未提供时询问用户）

评分标准参见 SKILL.md 的评分系统。

## Step 1：确认片名

用户给出的片名可能是中文翻译。若不确定对应的原片名，先用 WebSearch 搜索确认英文原名，再用原名查询 OMDB。

## Step 2：运行脚本获取电影数据

```bash
uv run SKILL_DIR/scripts/fetch_omdb_info.py "<片名>" --type movie
```

输出 JSON 示例：
```json
{
  "title": "The Shawshank Redemption",
  "year": "1994",
  "poster": "https://m.media-amazon.com/images/...",
  "imdb_id": "tt0111161",
  "type": "movie",
  "aliases": ["肖申克的救赎"],
  "directors": ["Frank Darabont"],
  "filename": "The Shawshank Redemption (1994).md"
}
```

`aliases` 字段规则：
- 原片名为非中文 → 脚本自动查询 Wikipedia 获取中文译名，填入 aliases
- 原片名为中文 → aliases 为空数组 `[]`

**注意**：API key 读取顺序：(1) 环境变量 `OMDB_API_KEY` (2) `~/.config/mosaic-notes/.omdb_api_key` 文件。

## Step 3：创建笔记并设置属性

### 文件名格式

```
电影名 (年份).md
```

### 3a. 创建笔记

```bash
obsidian vault=VAULT_NAME create name="<filename_no_ext>" template="TPL - Movie Logs" path="Inbox/<filename>" silent
```

### 3b. 设置属性

```bash
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="title" value="<片名>"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="directors" type=list value='["[[导演1]]", "[[导演2]]"]'
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="release_year" value="[[Year <年份>|<年份>]]"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="poster" value="<海报URL>"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="rating" value="<评分>"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="imdb" value="https://www.imdb.com/title/<imdb_id>/"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="created" value="<YYYY-MM-DD>"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="updated" value="<YYYY-MM-DD>"
```

**aliases 设置：**
- 脚本返回的 `aliases` 数组不为空时（非中文原片）：
  ```bash
  obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="aliases" type=list value='["中文译名"]'
  ```
- 脚本返回的 `aliases` 数组为空时（中文原片）：
  ```bash
  obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="aliases" type=list value='[]'
  ```

### 示例输出（英文原片）

以 "The Shawshank Redemption" 为例，最终 frontmatter：

```yaml
---
aliases:
  - "肖申克的救赎"
categories: Movie Logs
title: The Shawshank Redemption
directors:
  - "[[Frank Darabont]]"
release_year: "[[Year 1994|1994]]"
poster: https://m.media-amazon.com/images/...
rating: 💎
imdb: https://www.imdb.com/title/tt0111161/
created: 2026-02-18
updated: 2026-02-18
---
```

## 存放位置

`Inbox/` 目录，文件名按上述格式生成。

## 注意事项

- `categories` 使用字符串格式（非数组），值为 `Movie Logs`
- `release_year` 使用 wiki 链接格式 `"[[Year YYYY|YYYY]]"`
- `directors` 每个导演用 `"[[...]]"` 包裹，多行格式
- `imdb` 格式为 `https://www.imdb.com/title/<imdb_id>/`
- `poster` 使用 OMDB 返回的海报 URL，若为 `N/A` 则留空
- `aliases` 默认为空数组 `[]`，用户可提供中文别名
- `created` 和 `updated` 值相同，均为今天日期
- 正文部分留空（frontmatter only）

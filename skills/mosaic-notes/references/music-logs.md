# Music Logs 工作流

当用户要记录一张专辑时，执行以下流程：

## 所需信息

- 专辑名称（必须）
- 艺术家名称（必须）
- 评分（必须，未提供时询问用户）

评分标准参见 SKILL.md 的评分系统。

## Step 1 & 2：运行脚本获取专辑数据

使用 `SKILL_DIR/scripts/fetch_album_info.py`（SKILL_DIR 见 SKILL.md 初始化部分）：

```bash
uv run SKILL_DIR/scripts/fetch_album_info.py "<专辑名>" "<艺术家>"
```

输出 JSON 示例：
```json
{
  "album": "An Evening With Silk Sonic",
  "release_year": "2021",
  "artists": ["Silk Sonic"],
  "artwork": "http://coverartarchive.org/.../30922850185-500.jpg",
  "filename": "Silk Sonic - An Evening With Silk Sonic (2021).md",
  "mbid": "97a8636b-af26-46b9-a3f4-4ed57c75a2da"
}
```

**注意**：MusicBrainz 按信用名显示艺术家（如合唱团只显示团名，不展开成员）。若需要列出个人成员，用户需额外指定。

## Step 3：创建笔记并设置属性

### 文件名格式

```
艺术家1, 艺术家2 - 专辑名 (年份).md
```

文件名清理规则（替换为下划线）：
- 非法字符：`< > : " / \ | ? *` 以及控制字符

### 3a. 创建笔记

```bash
obsidian vault=VAULT_NAME create name="<filename_no_ext>" template="TPL - Music Logs" path="Inbox/<filename>" silent
```

### 3b. 设置属性

```bash
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="album" value="<专辑名>"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="artists" type=list value='["[[艺术家1]]", "[[艺术家2]]"]'
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="release_year" value="[[Year <年份>|<年份>]]"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="artwork" value="<封面URL>"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="rating" value="<评分>"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="created" value="<YYYY-MM-DD>"
obsidian vault=VAULT_NAME property:set file="<filename_no_ext>" name="updated" value="<YYYY-MM-DD>"
```

### 示例输出

以专辑 "An Evening With Silk Sonic" 为例，最终 frontmatter：

```yaml
---
categories: Music Logs
album: An Evening With Silk Sonic
artists:
  - "[[Bruno Mars]]"
  - "[[Anderson .Paak]]"
  - "[[Silk Sonic]]"
release_year: "[[Year 2021|2021]]"
artwork: https://archive.org/...
rating: ⭐⭐⭐
created: 2024-01-15
updated: 2024-01-15
---
```

## 存放位置

`Inbox/` 目录，文件名按上述格式生成。

## 注意事项

- `categories` 使用字符串格式（非数组），值为 `Music Logs`
- `release_year` 使用 wiki 链接格式 `"[[Year YYYY|YYYY]]"`
- `artists` 每个艺术家用 `"[[...]]"` 包裹，多行格式
- `created` 和 `updated` 值相同，均为今天日期
- 正文部分留空（frontmatter only）

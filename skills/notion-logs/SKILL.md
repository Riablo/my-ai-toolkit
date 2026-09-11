---
name: notion-logs
description: 添加或编辑个人 Notion Music、Movie、TV Series Logs 中的专辑、电影和剧集记录；长期知识笔记使用独立的 notion-notes。
disable-model-invocation: true
---

# Notion Logs

使用 Notion 官方 API 记录专辑、电影和剧集，支持 Music、Movie、TV Series Logs。

## 先读配置

每次执行前读取并校验 `~/.config/notion-logs/config.json`：JSON 必须有效，API 版本、当前操作所需的 data source 和字段映射必须完整且值有效，并能取得对应 API token；Movie/TV 还需 OMDB key。

配置不存在、缺字段或值无效时，读取 [references/config.md](references/config.md)，引导用户创建或修复配置；不要猜 token、写入示例 token，或用脚本默认值掩盖配置问题。

配置通过后，定义：

- `SKILL_DIR` = 当前 skill 目录
- `CONFIG` = `~/.config/notion-logs/config.json`

## 写入规则

- 实际 Notion 写入只用 `SKILL_DIR/scripts/notion_logs.py` 调 Notion API；不要用 Notion MCP、Notion 插件或其他 Notion skill 来创建/更新条目。
- 只写入本 skill 已显式支持的数据库和子命令；不要临时拼一个任意 Notion database payload 来写入新库。
- 缺少评分、标题、必要数据源或 API token 时先补齐，不要静默写入不完整记录。
- 用户没有明确要删除时绝不删除；用户明确要求删除时说明本 skill 不处理删除，让用户到 Notion 项目里手动删。
- 字段不确定或用户请求含糊时先跑 `--dry-run` 看 payload。

## Media Logs

当用户要记录专辑、电影或剧集时，读取 [references/media-logs.md](references/media-logs.md)。

常用命令：

```bash
uv run SKILL_DIR/scripts/notion_logs.py media --kind music --title "<专辑名>" --artist "<艺术家>" --rating "<评分>"
uv run SKILL_DIR/scripts/notion_logs.py media --kind movie --title "<电影名>" --rating "<评分>"
uv run SKILL_DIR/scripts/notion_logs.py media --kind tv --title "<剧集名>" --rating "<评分>"
```

默认行为是 `upsert`：先按 `Name` 和 `Released Year` 查找，找到则更新，找不到则创建。明确只想新增时加 `--mode create`；明确编辑某条页面时加 `--mode update --page-id <page_id>`。

## 新数据库维护

只有当用户明确要求“给 notion-logs 添加某个新数据库支持”时，才读取 [references/extending.md](references/extending.md) 并修改 skill。不要在日常记录任务中自动扩展数据库或使用通用写入。

## Gotchas

- Notion API 现在应优先使用 `data_source_id`，不是旧的 database parent。
- `Created`、`created_time`、rollup、formula 等系统/计算字段不可写。
- `files` 字段传外部图片 URL 会覆盖该字段现有文件列表；脚本只有拿到非空图片 URL 时才写 Poster/Artwork。
- Movie/TV 需要 OMDB key；Music 不需要 OMDB。
- `Rating` 必须匹配目标数据库已有选项：`💎💎`、`💎`、`⭐⭐⭐`、`⭐⭐`、`⭐`。
- 这个 skill 没有通用 Notion 写入入口；用户没有先要求维护 skill 时，不要添加新 data source alias、新子命令或新字段映射。

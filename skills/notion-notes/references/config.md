# 配置

配置文件：`~/.config/notion-notes/config.json`。

```json
{
  "notion_version": "2026-03-11",
  "notion_token": "",
  "database_id": "303479a0-f3d6-400b-ac86-ae87f881cd8e",
  "data_source_id": "b7219e33-652d-4e19-9ae7-7c93dc677973"
}
```

Token 按 `NOTION_API_KEY`、`NOTION_TOKEN`、配置中的 `notion_token` 顺序取第一个非空字符串。可复用本机 `~/.config/notion-logs/config.json` 中的 Notion Token，初始化时复制到此配置；不要复制 OMDB key 或影音数据库映射。

文件不存在时协助创建上述配置并补全 Token；已有文件缺字段或值无效时修复对应项，保留其它配置。JSON 顶层须为对象，`notion_version` 须为有效的 `YYYY-MM-DD` API 版本，两个 ID 须为非空 UUID。Token 不得为空或示例占位符，不输出配置中的真实凭据；配置文件权限设为 `600`。

用 `GET /databases/{database_id}` 确认目标是 Notes、列出的 data source 包含配置 ID，再用 `GET /data_sources/{data_source_id}` 核对字段类型和选项。遇到认证、访问权限或版本错误时说明原因并协助修复，不改写为其它数据库。

# 配置

配置文件：`~/.config/notion-ai-tools/config.json`。

```json
{
  "notion_version": "2026-03-11",
  "notion_token": "",
  "database_id": "7dfa635e-3f46-406b-b697-318e824ad9b8",
  "data_source_id": "d53ecff7-c7a0-4520-ba3b-72c934c453ed"
}
```

Token 按 `NOTION_API_KEY`、`NOTION_TOKEN`、配置中的 `notion_token` 顺序取第一个非空字符串。可复用本机 `~/.config/notion-notes/config.json` 或 `~/.config/notion-logs/config.json` 中的 Notion Token，初始化时只复制凭据，不复制其它数据库 ID 或字段映射。

文件不存在时协助创建上述配置并补全 Token；已有文件缺字段或值无效时修复对应项，保留其它配置。JSON 顶层须为对象，`notion_version` 须为有效的 `YYYY-MM-DD` API 版本，两个 ID 须为非空 UUID。Token 不得为空或示例占位符，不输出配置中的真实凭据；配置文件权限设为 `600`。

用 `GET /databases/{database_id}` 确认目标是 AI Tools、列出的 data source 包含配置 ID，再用 `GET /data_sources/{data_source_id}` 核对字段类型和选项。遇到认证、访问权限或版本错误时说明原因并协助修复，不改写为其它数据库。

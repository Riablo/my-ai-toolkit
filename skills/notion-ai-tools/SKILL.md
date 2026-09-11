---
name: notion-ai-tools
description: 将当前或曾经使用的 AI Skills、MCPs 和 Plugins 记录到个人 Notion AI Tools 数据库，维护用途、使用状态、适用 Agent 和安装范围；用于工具清单维护，不负责安装或配置工具。
disable-model-invocation: true
---

# Notion AI Tools

维护 [AI Tools](https://app.notion.com/p/riablo/7dfa635e3f46406bb697318e824ad9b8) 清单，方便查看有哪些工具、是否还在使用、用在哪里以及基本用途。

## 配置

每次执行前读取并校验 `~/.config/notion-ai-tools/config.json`，格式见 [references/config.md](references/config.md)。检查 JSON、API 版本、两个 ID 和有效 token；缺失或值无效时协助初始化或修复，不静默跳过。

使用配置中的 Token 调用 Notion 官方 API。先读取目标 data source，确认它属于配置中的 database，并核对字段和已有选项；实际结构有变化时先处理差异，不猜字段写入。

## 记录方式

- 用户要求记录或更新时直接执行，从对话、指定文件、配置或官方来源整理信息。新增至少填写 `Name`、`Type`、`Status`、`Purpose`；缺少且无法确定的 `Name`、`Type`、`Purpose` 再询问。
- 新增或补全空字段时，`Status`、`Used In`、`Scope` 缺省则直接使用下表默认值，不再询问用户。用户或上下文已明确的值优先；更新已有记录时，不用默认值覆盖已有值。
- 保存前按名称或来源地址查找已有记录，结合安装范围、Agent 和正文确认是否为同一使用场景，优先更新相关条目。不同项目或安装方式按实际情况区分，必要差异写在正文；更新时保留未涉及的字段和仍有价值的内容。
- 暂时不用时将状态改为 `暂停`，明确不再使用时标为 `已弃用`，保留历史记录。
- 安装方法、配置示例、命令、心得和已知问题按需写入页面正文，自由组织，不强制模板。保持字段简单，不为每类细节增加属性；只有用户需要频繁筛选、排序或查看时，再考虑增加字段。
- 完成后简短返回新增或更新的工具名称和链接。写入结果不明时先查询核实，避免直接重试创建出重复条目。

## 字段

| 字段 | 写法 |
| --- | --- |
| `Name`（title） | 工具名称 |
| `Type`（multi_select） | `Skill`、`MCP`、`Plugin`，可同时选择多个 |
| `Status`（select） | 默认 `使用中`；可选 `使用中`、`暂停`、`已弃用` |
| `Used In`（multi_select） | 默认同时选择 `Codex`、`Pi`；已有 `Codex`、`Claude Code`、`Pi`、`OMP`，有新 Agent 时可新增 |
| `Scope`（select） | 默认 `Global`（全局）；项目级使用 `Project` |
| `Purpose`（rich_text） | 一句话说明主要用途，保持简短 |
| `Source`（url） | 优先官方 GitHub，其次官网、官方文档；来源不明确时留空，不编造链接 |

## API 提示

请求基址为 `https://api.notion.com/v1`，携带 `Authorization: Bearer <token>`、配置中的 `Notion-Version`，JSON 请求使用 `Content-Type: application/json`。Token 从环境或配置在进程内读取，不回显、不写入条目或仓库；临时 Python 脚本用 `uv run` 执行。

- 查询用 `POST /data_sources/{data_source_id}/query`，按需处理分页；编辑指定页面前确认它属于 AI Tools。
- [创建页面](https://developers.notion.com/reference/post-page)使用 `parent.data_source_id`、`properties` 和可选的 `markdown` 正文；链接中的 database ID 和 view ID 不能当作 data source ID。
- 属性用 `PATCH /pages/{page_id}` 更新；正文先[读取 Markdown](https://developers.notion.com/reference/retrieve-page-markdown)，再用 [Markdown 更新接口](https://developers.notion.com/reference/update-page-markdown)按需修改。读取结果被截断或有未加载块时，补读相关内容后再编辑，不据残缺正文整页覆盖。

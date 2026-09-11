---
name: notion-notes
description: 将用户希望长期保留的个人配置、实际踩坑、已验证方案、决策和其它笔记保存或更新到个人 Notion Notes 数据库；影音记录使用 notion-logs。
disable-model-invocation: true
---

# Notion Notes

把值得保留的信息存进 [Notes](https://app.notion.com/p/riablo/303479a0f3d6400bac86ae87f881cd8e)。优先保留个人环境、实际经验和决策依据，少写随时能重新查到的通用知识；用户明确要保存的内容按其意图处理。

## 配置

每次执行前读取并校验 `~/.config/notion-notes/config.json`，格式见 [references/config.md](references/config.md)。检查 JSON、API 版本、两个 ID 和有效 token；缺失或值无效时协助初始化或修复，不静默跳过。

使用配置中的 Token 调用 Notion 官方 API。先读取目标 data source，确认它属于配置中的 database，并核对字段和已有 Topics；实际结构有变化时先处理差异，不猜字段写入。

## 保存方式

- 用户要求保存或更新时直接执行，从当前对话、指定文件或链接提炼内容。保留关键配置、命令、适用环境、结论和有用的来源，区分已验证事实与尚未确认的推测。
- 保存前按标题关键词、Topics 查找相关笔记并阅读候选正文。同一事项优先补充或更新，保留仍有价值的原文；仅主题相近不必合并。无法确定要更新哪篇时再询问。
- 正文直接写在数据库条目的页面中，按内容自由组织，不强制模板、章节数量或复杂分类，也不额外创建目录和数据库。
- 完成后简短返回新增或更新的笔记标题和链接。写入结果不明时先查询核实，避免直接重试创建出重复条目。

## 字段

| 字段 | 写法 |
| --- | --- |
| `Name`（title） | 简洁、方便日后查找的标题 |
| `Type`（select） | 自动选最合适的一个：`Config` 配置、`Fix` 问题解决、`Decision` 决策、`Note` 其它 |
| `Topics`（multi_select） | 少量有意义的主题、技术、设备或项目；优先复用已有相同或相近标签，确有需要时新增，避免大小写和同义重复 |
| `Created` / `Updated` | Notion 自动维护，不写入 |

## API 提示

请求基址为 `https://api.notion.com/v1`，携带 `Authorization: Bearer <token>`、配置中的 `Notion-Version`，JSON 请求使用 `Content-Type: application/json`。Token 从环境或配置在进程内读取，不回显、不写入笔记或仓库；临时 Python 脚本用 `uv run` 执行。

- 查询用 `POST /data_sources/{data_source_id}/query`，按需处理分页；编辑指定页面前确认它属于 Notes。
- [创建页面](https://developers.notion.com/reference/post-page)使用 `parent.data_source_id`、`properties` 和 `markdown` 正文；链接中的 database ID 和 view ID 不能当作 data source ID。
- 属性用 `PATCH /pages/{page_id}` 更新；正文先[读取 Markdown](https://developers.notion.com/reference/retrieve-page-markdown)，再用 [Markdown 更新接口](https://developers.notion.com/reference/update-page-markdown)按需修改。读取结果被截断或有未加载块时，补读相关内容后再编辑，不据残缺正文整页覆盖。

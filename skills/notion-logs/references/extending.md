# 添加已知数据库支持

只有当用户明确要求“把某个已知 Notion 数据库加入 notion-logs”时，才使用本文件维护 skill。日常记录任务中不要自动扩展数据库，也不要临时写入未登记的 data source。

## 维护流程

1. 确认用户给出的目标数据库名称、data source id 或页面 URL，以及要支持的动作是添加、编辑，还是二者都要。

2. 读取 schema。若配置里已经有 alias，可用：

```bash
uv run SKILL_DIR/scripts/notion_logs.py schema --data-source <alias>
```

若尚未写入配置，先用 Notion 页面或 API 确认 data source id；不要猜字段名。

3. 在 `scripts/notion_logs.py` 的 `DEFAULT_CONFIG["data_sources"]` 中添加明确 alias，并同步更新 `references/config.md` 的配置示例：

```json
{
  "data_sources": {
    "shopping_records": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  }
}
```

4. 为该数据库新增专用字段映射和专用构造逻辑。优先使用明确子命令或明确 kind，不要新增通用 `page` / `properties-json` 写入入口。

5. 新增或更新 reference，写清楚：

- 必填用户输入
- Notion 字段名和类型
- 数据来源
- upsert 匹配键
- 不可写字段

6. 更新 `SKILL.md`，只暴露新数据库的专用工作流和命令。

7. 更新 `README.md` 的 skill 说明；若用户要求，也更新 `agents/openai.yaml` 的默认提示。

8. 验证。`SKILL_DIR` 为正在维护的 skill 目录；从当前环境的 skill 列表定位 `skill-creator`，将其实际目录记为 `SKILL_CREATOR_DIR`，不要写死某台机器的路径：

```bash
uv run python -m py_compile "<SKILL_DIR>/scripts/notion_logs.py"
uv run --with pyyaml "<SKILL_CREATOR_DIR>/scripts/quick_validate.py" "<SKILL_DIR>"
uv run "<SKILL_DIR>/scripts/notion_logs.py" <new-command> --dry-run ...
```

若验证器不可用，明确报告该项未运行并协助定位或安装，不把缺失当作通过。检查 dry-run 中的目标、必填字段和不可写字段；dry-run 通过不代表真实写入成功，也不构成真实写入的授权。

部分旧版 `quick_validate.py` 不识别 `disable-model-invocation`。保留原文件中的字段，先独立检查它是布尔值且与 `agents/openai.yaml` 的调用策略一致，再用仅去掉该字段的临时副本运行其余校验，并报告此兼容处理；其他错误仍按验证失败处理。

## Property Builder 参考

- title: `{"title":[{"text":{"content":"..."}}]}`
- rich text: `{"rich_text":[{"text":{"content":"..."}}]}`
- number: `{"number": 123}`
- select: `{"select":{"name":"..."}}`
- date: `{"date":{"start":"YYYY-MM-DD"}}`
- url: `{"url":"https://..."}`
- files external: `{"files":[{"name":"Poster","external":{"url":"https://..."}}]}`

不要写 `created_time`、`last_edited_time`、formula、rollup、created_by、last_edited_by。

## 禁止事项

- 不要为了快速完成一次记录而新增通用 Notion 写入命令。
- 不要让脚本接受任意 data source + 任意 properties JSON 并执行写入。
- 不要自动创建 Notion 数据库或 data source。
- 不要把真实 Notion token 写进 skill、README 或示例配置。

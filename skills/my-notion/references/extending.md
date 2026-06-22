# 添加已知数据库支持

只有当用户明确要求“把某个已知 Notion 数据库加入 my-notion”时，才使用本文件维护 skill。日常记录任务中不要自动扩展数据库，也不要临时写入未登记的 data source。

## 维护流程

1. 确认用户给出的目标数据库名称、data source id 或页面 URL，以及要支持的动作是添加、编辑，还是二者都要。

2. 读取 schema。若配置里已经有 alias，可用：

```bash
uv run SKILL_DIR/scripts/my_notion.py schema --data-source <alias>
```

若尚未写入配置，先用 Notion 页面或 API 确认 data source id；不要猜字段名。

3. 在 `scripts/my_notion.py` 的 `DEFAULT_CONFIG["data_sources"]` 中添加明确 alias，并同步更新 `references/config.md` 的配置示例：

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

8. 验证：

```bash
python3 -m py_compile skills/my-notion/scripts/my_notion.py
uv run --with pyyaml /Users/cz/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/my-notion
uv run skills/my-notion/scripts/my_notion.py <new-command> --dry-run ...
```

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

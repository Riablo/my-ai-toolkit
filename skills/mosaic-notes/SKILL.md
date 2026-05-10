---
name: mosaic-notes
description: 当用户要在 Obsidian Mosaic 知识库里记笔记、搜笔记、改属性、写 daily note、添加任务、记录专辑/电影/剧集，或说“记一下”“加个待办”“把昨天任务移过来”时使用。
---

# Mosaic Notes

直接读写 Obsidian Mosaic vault，不依赖 Obsidian CLI。主文件只保留入口规则、配置校验和常用工作流；分类、格式和维护细则按需读取 reference。

## 先读配置

每次执行前先读取：

```bash
cat ~/.config/mosaic-notes/config.json
```

配置至少包含：

- `vault_path`
- `headless`
- `omdb_api_key`（仅 Movie / TV Series Logs 需要）

## 配置校验

配置不存在时，先让用户明确提供真实的 vault 路径，再初始化；不要把示例路径写进去。

配置存在时，至少检查：

- `vault_path` 存在且是目录
- `vault_path/Templates/` 存在
- 若要写 Movie / TV Series Logs，`omdb_api_key` 已配置，或环境变量 `OMDB_API_KEY` 可用
- `headless` 缺失时按 `false` 处理，但提醒用户补上

校验通过后，定义：

- `VAULT_PATH` = `vault_path`
- `SKILL_DIR` = 当前 skill 目录
- `HEADLESS` = `headless`

## Headless 同步

当 `headless = true` 时，每次操作前后都必须同步：

```bash
ob sync --path VAULT_PATH
# ... 文件操作 ...
ob sync --path VAULT_PATH
```

当 `headless = false` 时，不需要额外同步。

## 常用工作流

### 创建普通笔记

使用模板脚本创建，新笔记默认放 `Inbox/`：

```bash
uv run SKILL_DIR/scripts/create_from_template.py --vault VAULT_PATH --template "{类别}" --name "标题" --path "Inbox/标题.md"
```

然后直接修改 frontmatter 和正文。

### 读取 / 搜索 / 追加

- 读取：直接读 `VAULT_PATH/` 下对应文件
- 搜索：优先按文件名或内容搜索
- 追加：直接编辑目标文件

### Daily Notes

- 路径固定为 `VAULT_PATH/Library/YYYY-MM-DD.md`
- 文件不存在时，用 `Daily Notes` 模板创建
- 用户要加任务 / 待办 / todo 时，写到 `## ✅ Tasks` 区块

### 完成任务

把 `- [ ]` 改成 `- [x]`。

### 任务顺延

用户提到“任务转移”“任务顺延”“把昨天的任务移过来”“rollover”时，运行：

```bash
uv run SKILL_DIR/scripts/rollover_tasks.py --vault VAULT_PATH
```

这个脚本会移动昨天 Daily Note 中未完成的顶层任务及其子任务树，而不是复制。

### 记录类笔记

按需读取对应 reference：

- 专辑 / 音乐记录：`references/music-logs.md`
- 电影记录：`references/movie-logs.md`
- 剧集记录：`references/tv-series-logs.md`

相关脚本统一用 `uv run`：

```bash
uv run SKILL_DIR/scripts/fetch_album_info.py "<专辑名>" "<艺术家>"
uv run SKILL_DIR/scripts/fetch_omdb_info.py "<片名>" --type movie|series
```

## 核心 gotchas

- 新笔记默认进 `Inbox/`；只有 Daily Notes 直接进 `Library/`
- 必须显式给 `--path`，不要依赖隐式默认
- 文件名就是标题，正文不需要再写 H1
- 任务必须插在 `## ✅ Tasks` 与下一个区块之间
- 记录类工作流才需要 OMDB API key；普通记笔记不该因为缺 OMDB 而阻塞

## 何时读 reference

- 需要类别清单、评分规则、YAML/frontmatter 约定、vault 目录结构时：读 [references/vault-rules.md](/Users/cz/Projects/my-ai-toolkit/skills/mosaic-notes/references/vault-rules.md)
- 需要新增类别、修改模板、调整框架规则时：读 [references/framework-maintenance.md](/Users/cz/Projects/my-ai-toolkit/skills/mosaic-notes/references/framework-maintenance.md)

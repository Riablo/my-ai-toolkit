---
name: mosaic-notes
description: 管理 Obsidian Mosaic 知识库的笔记，使用 Obsidian 官方 CLI 操作 vault。当用户要创建笔记、修改笔记属性、搜索笔记、记录专辑/电影/剧集、添加备忘、写 daily note、添加任务/待办/todo，或任何涉及 Mosaic 知识库内容管理的操作时使用此技能。即使用户只是随口提到"记一下"、"加个笔记"、"帮我记录"、"加个任务"、"提醒我"、"待办"，也应触发。包含记录类工作流：(1) Music Logs - 当用户提到记录专辑、听了什么音乐时，查阅 references/music-logs.md；(2) Movie Logs - 当用户提到记录电影、看了什么电影时，查阅 references/movie-logs.md；(3) TV Series Logs - 当用户提到记录剧集、追了什么剧时，查阅 references/tv-series-logs.md。电影和剧集使用 OMDB API，音乐使用 MusicBrainz API。当用户需要新增类别、修改模板、调整规则时，也使用此技能，参照"框架维护"章节。
---

# Mosaic Notes

独立操作 Obsidian Mosaic 知识库的技能。所有规则和约定都包含在本文件中。

## 初始化

每次执行前，读取配置文件：

```bash
cat ~/.config/mosaic-notes/config.json
```

如果文件不存在，引导用户完成初始化：

1. 询问 vault 路径（Obsidian vault 在文件系统中的绝对路径）
2. 询问 vault 名称（Obsidian 中的 vault 名称，用于 CLI 的 `vault=` 参数）
3. 询问 OMDB API key（可选，用于 Movie/TV Series Logs；没有的话跳过）
4. 创建配置文件：

```json
{
  "vault_path": "/Users/cz/Vaults/Mosaic",
  "vault_name": "Mosaic",
  "omdb_api_key": ""
}
```

配置就绪后，定义以下变量供后续使用：
- **VAULT_PATH** = `vault_path`（文件读写的绝对路径）
- **VAULT_NAME** = `vault_name`（obsidian CLI 的 `vault=` 参数）
- **SKILL_DIR** = `~/.claude/skills/mosaic-notes`

## Obsidian 官方 CLI

这是 Obsidian 1.12+ 官方提供的 CLI（非第三方 npm 包 `obsidian-cli`），需要 Obsidian 应用正在运行。

所有命令必须加 `vault=VAULT_NAME` 参数：

```bash
obsidian vault=VAULT_NAME create name="标题" template="TPL - {类别}" path="Inbox/标题.md" silent
obsidian vault=VAULT_NAME property:set name="key" value="val" file="标题"
obsidian vault=VAULT_NAME property:set name="artists" type=list value='["[[A]]", "[[B]]"]' file="标题"
obsidian vault=VAULT_NAME read file="标题"
obsidian vault=VAULT_NAME search query="关键词"
obsidian vault=VAULT_NAME append file="标题" content="内容"
obsidian vault=VAULT_NAME daily:read
obsidian vault=VAULT_NAME daily:append content="内容"
```

直接读写文件时使用绝对路径：`VAULT_PATH/Library/xxx.md`、`VAULT_PATH/Inbox/xxx.md`

### 脚本执行

所有 Python 脚本使用 uv 执行，脚本内含 PEP 723 内联元数据，无需额外安装依赖：

```bash
uv run SKILL_DIR/scripts/fetch_album_info.py "<专辑名>" "<艺术家>"
uv run SKILL_DIR/scripts/fetch_omdb_info.py "<片名>" --type movie|series
```

### 命令参考

运行 `obsidian help` 查看所有可用命令和用法。遇到不确定的命令时，优先通过此命令获取最新信息。

### 注意

- `create` 默认在 vault 根目录创建，**必须显式设置 `path="Inbox/文件名.md"`**
- Daily Notes 使用 `daily:*` 系列命令
- wiki 链接值无需额外转义：`value="[[Year 2021|2021]]"`

## 核心规则

1. **使用 categories 属性** - 不使用 Obsidian 标签系统
2. **大写开头格式** - 类别值如 `Dev Notes`、`AI Prompts`
3. **模板驱动** - 使用 `VAULT_PATH/Templates/` 中的模板
4. **新建到 Inbox** - 新笔记存放在 `Inbox/`；**Daily Notes 例外**，直接创建到 `Library/`
5. **文件名即标题** - 正文不需要 H1，正文内最高 H2
6. **日期格式** - 统一 `YYYY-MM-DD`
7. **YAML 数组格式** - 使用多行格式，每项单独一行

## 笔记类别

所有笔记必须属于至少一个类别：

### 随手记

快速记录，无需过度组织。

- **Ideas** - 胡思乱想、灵感记录
- **Issues** - 待解决的问题清单（status: `Open` / `Closed`）
- **Memos** - 简单备忘录
- **Daily Notes** - 每日日记，包含当日任务和随手记录

### 笔记类

系统性的知识和经验记录。

- **Dev Notes** - 开发相关的技术笔记
- **Life Hacks** - 生活相关的技巧和经验
- **Config Notes** - 硬件、软件设置和配置记录
- **AI Prompts** - 可复用的 AI 提示词库
- **Gaming Notes** - 游戏相关的攻略和笔记
- **Prompting Logs** - 一次性使用过的提示词记录
- **Articles** - 从网络摘录的优质文章

### 项目类

- **Repos** - Git 仓库（自己维护的 GitHub 仓库等）
- **Projects** - 个人项目，含任务列表（status: `Not Started` / `In Progress` / `Completed`）
- **Releases** - 工作项目的版本迭代，关联 Repos（status 同 Projects）

### 记录类

- **Music Logs** - 音乐欣赏记录（→ references/music-logs.md）
- **Movie Logs** - 电影观看记录（→ references/movie-logs.md）
- **TV Series Logs** - 电视剧观看记录（→ references/tv-series-logs.md）
- **Purchase Logs** - 购买记录

### Things

- **Games** - 游戏
- **Apps** - 应用程序
- **Dev Libs** - 开发库和命令行工具
- **Services** - SaaS 服务（附加属性：pricing `Free` / `One Time Purchase` / `Usage Based` / `Subscription`）
- **Online Tools** - 在线工具（无需注册、免费使用的网页工具）
- **Devices** - 硬件设备
- **Plugins** - 各类工具的插件
- **Operating Systems** - 操作系统

### 实体

- **People** - 人物
- **Groups** - 组织/团体（如乐队、公司，关联多个 People）

### 其它

- **Topics** - 话题、概念、讨论主题
- **Years** - 年份，关联涉及特定年份的笔记

## 评分系统

用于记录类笔记（Music/Movie/TV Series Logs）的 `rating` 属性：

- 💎💎 - 完美
- 💎 - 极佳
- ⭐⭐⭐ - 不错
- ⭐⭐ - 普通
- ⭐ - 无感
- 👎 - 非常差

## 文件组织

```
VAULT_PATH/
├── Attachments/     # 媒体文件
├── Bases/           # 汇总内容
├── Inbox/           # 新建笔记默认位置
├── Library/         # 已整理的笔记主库
└── Templates/       # 笔记模板
```

## 创建笔记工作流

### 普通笔记

```bash
obsidian vault=VAULT_NAME create name="标题" template="TPL - {类别}" path="Inbox/标题.md" silent
obsidian vault=VAULT_NAME property:set name="key" value="val" file="标题"
```

### 添加任务 / TODO

当用户要添加任务、待办、todo 时，写入今天的 Daily Note 的 `## ✅ Tasks` 区块下：

1. 读取今天的 Daily Note：
   ```bash
   obsidian vault=VAULT_NAME daily:read
   ```

2. 如果今天的 Daily Note 不存在，创建：
   ```bash
   obsidian vault=VAULT_NAME create name="YYYY-MM-DD" template="TPL - Daily Notes" path="Library/YYYY-MM-DD.md" silent
   ```

3. 在 `## ✅ Tasks` 下追加任务（使用 Edit 工具编辑 `VAULT_PATH/Library/YYYY-MM-DD.md`）：
   ```markdown
   - [ ] 任务内容
   ```

Daily Note 模板结构：
```markdown
## ✅ Tasks

## 📝 Notes
```

任务插入在 `## ✅ Tasks` 和 `## 📝 Notes` 之间。

### 记录类笔记

参阅 SKILL_DIR 下对应文档：

- **references/music-logs.md** - Music Logs（MusicBrainz + Cover Art Archive）
- **references/movie-logs.md** - Movie Logs（OMDB API）
- **references/tv-series-logs.md** - TV Series Logs（OMDB API）

## 框架维护

当需要新增/修改类别、模板或规则时，需要同步更新以下文件：

### 新增类别

1. **`VAULT_PATH/README.md`** - 在对应分组下添加说明
2. **本技能 SKILL.md** - 在笔记类别清单中添加
3. **`VAULT_PATH/Templates/TPL - {类别名}.md`** - 创建模板
4. 使用大写开头的英文命名

### 修改通用规则

- 评分系统 / 日期格式 / YAML 格式 → 更新本 SKILL.md + `VAULT_PATH/README.md`
- 文件组织规则 → 同上

### 修改类别（重命名/删除）

同新增类别的文件范围。删除时检查 `VAULT_PATH/Library/` 中是否有使用该类别的笔记。

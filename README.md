# my-ai-toolkit

我自己用的 AI 工具箱，收录两类内容：

- **skills/** — 给 AI 用的 Skills（Claude Code Skill 格式）
- **cli/** — 命令行小工具

## 安装

```bash
# 将所有 CLI 工具软链接到 ~/.local/bin/，同时安装 Fish completions
bash scripts/install.sh
```

首次安装后确保 `~/.local/bin` 在 PATH 中：

```fish
# fish
fish_add_path ~/.local/bin

# bash/zsh
export PATH="$HOME/.local/bin:$PATH"
```

安装脚本会自动：
- 将 `cli/` 下所有工具软链接到 `~/.local/bin/`
- 检测 Fish Shell 并安装补全到 `~/.config/fish/completions/`

## skills/

Claude Code 的 [Custom Skills](https://docs.anthropic.com/en/docs/claude-code/skills)，使用 `myskills` 命令管理。

| Skill | 说明 |
| --- | --- |
| [cli-skill-creator](skills/cli-skill-creator/) | 为 `cli/` 下的命令行工具生成 AI skill（先探测 help/README/配置，再写轻量 skill） |
| [cloudsaver-cli](skills/cloudsaver-cli/) | 使用 `cloudsaver-cli` 搜索网盘资源、检查配置并转存 115 分享链接 |
| [freecurrency-cli](skills/freecurrency-cli/) | 使用 `freecurrency-cli` 查询汇率、做金额换算，并检查配置与缓存 |
| [mosaic-notes](skills/mosaic-notes/) | 管理 Obsidian Mosaic 知识库的笔记 |
| [qweather-cli](skills/qweather-cli/) | 使用 `qweather-cli` 查询实时天气、每日预报、逐小时预报，并检查 QWeather 配置 |

## cli/

命令行工具，各自有独立的说明。

| 工具 | 说明 |
| --- | --- |
| [cloudsaver-cli](cli/cloudsaver-cli/) | 网盘资源搜索与 115 转存工具（Telegram 搜索 / 115 转存） |
| [freecurrency-cli](cli/freecurrency-cli/) | Open Exchange Rates 汇率工具（金额换算 / 最新汇率 / 本地缓存） |
| [myskills](cli/myskills/) | 管理 AI Skills 的链接、安装与卸载（list / link / install / unlink / uninstall / status） |
| [pingcode-cli](cli/pingcode-cli/) | PingCode 命令行工具（bugs 列表等） |
| [qweather-cli](cli/qweather-cli/) | QWeather 命令行工具（实时天气 / 每日预报 / 逐小时预报） |
| [jenkins-builder-cli](cli/jenkins-builder-cli/) | Jenkins 构建命令行工具（列出 jobs / 触发构建 / 改分支 / 日志 / 停止） |

### myskills 用法

```bash
myskills list                                  # 列出可用 skills
myskills link mosaic-notes                     # 链接到 ~/.agents/ 和 ~/.claude/（默认）
myskills install mosaic-notes                  # 复制到 ~/.agents/ 和 ~/.claude/（默认，覆盖已有内容）
myskills link mosaic-notes --claude             # 只链接到 ~/.claude/
myskills install mosaic-notes --local-agents    # 覆盖安装到当前目录的 .agents
myskills link mosaic-notes --agents --local-claude  # 多选目标
myskills unlink mosaic-notes                   # 移除所有位置的软链接
myskills uninstall mosaic-notes                # 移除所有位置已复制安装的目录
myskills status                                # 查看状态（软链接或已安装）
```

目标参数（`link` / `install` / `unlink` / `uninstall` 可用，可多选）：

| 参数 | 目录 |
| --- | --- |
| `--agents` | `~/.agents/skills/` |
| `--claude` | `~/.claude/skills/` |
| `--local-agents` | `./.agents/skills/`（当前目录） |
| `--local-claude` | `./.claude/skills/`（当前目录） |

## License

MIT

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
| [mosaic-notes](skills/mosaic-notes/) | 管理 Obsidian Mosaic 知识库的笔记 |

## cli/

命令行工具，各自有独立的说明。

| 工具 | 说明 |
| --- | --- |
| [freecurrency-cli](cli/freecurrency-cli/) | freecurrencyapi 汇率工具（金额换算 / 最新汇率 / 本地缓存） |
| [myskills](cli/myskills/) | 管理 AI Skills 的软链接（list / link / unlink / status） |
| [pingcode-cli](cli/pingcode-cli/) | PingCode 命令行工具（bugs 列表等） |
| [qweather-cli](cli/qweather-cli/) | QWeather 命令行工具（实时天气 / 每日预报 / 逐小时预报） |

### myskills 用法

```bash
myskills list                                  # 列出可用 skills
myskills link mosaic-notes                     # 链接到 ~/.agents/ 和 ~/.claude/（默认）
myskills link mosaic-notes --claude             # 只链接到 ~/.claude/
myskills link mosaic-notes --agents --local-claude  # 多选目标
myskills unlink mosaic-notes                   # 移除所有位置的软链接
myskills status                                # 查看链接状态
```

目标参数（`link` / `unlink` 可用，可多选）：

| 参数 | 目录 |
| --- | --- |
| `--agents` | `~/.agents/skills/` |
| `--claude` | `~/.claude/skills/` |
| `--local-agents` | `./.agents/skills/`（当前目录） |
| `--local-claude` | `./.claude/skills/`（当前目录） |

## License

MIT

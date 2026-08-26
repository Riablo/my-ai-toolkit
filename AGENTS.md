# AGENTS.md

## 项目概述

个人 AI 工具箱，收录两类内容：
- `skills/` — Codex Skills（每个 skill 一个子目录，包含 `SKILL.md`）
- `cli/` — 命令行工具（每个工具一个子目录，包含同名可执行文件）

## 项目结构

```
skills/<skill-name>/SKILL.md     # skill 主文件（必需）
skills/<skill-name>/agents/openai.yaml # Codex 调用策略（必需）
skills/<skill-name>/references/  # 参考文档（可选）
skills/<skill-name>/scripts/     # 辅助脚本（可选）
cli/<tool-name>/<tool-name>      # CLI 可执行文件（必需，bash 脚本）
cli/<tool-name>/_<tool-name>     # zsh 补全（推荐）
cli/<tool-name>/<tool-name>.fish # Fish Shell 补全（兼容）
scripts/install.sh               # 安装脚本，软链 CLI 工具 + zsh/Fish 补全
```

## 约定

- CLI 工具用 bash 编写，帮助信息用中文
- 需要 bash 5.0+，可自由使用 nameref、readarray、关联数组等现代语法。macOS 自带 bash 3.2 不够用，需通过 Homebrew 升级（`brew install bash`）
- 避免在 `set -e` 下用 `((expr)) && ((expr))` 模式，算术结果为 0 时退出码非零会导致脚本退出
- 不要在 bash 脚本中做交互式 TUI（raw 模式按键监听），macOS/Fish 下兼容性差
- Skill 目录必须包含 `SKILL.md`，install.sh 和 myskills 通过此文件识别 skill
- Skill 默认只能由用户显式调用：`SKILL.md` frontmatter 必须设置 `disable-model-invocation: true`（Claude Code / Pi），`agents/openai.yaml` 必须设置 `policy.allow_implicit_invocation: false`（Codex）
- 只有用户明确要求某个 skill 可被自动调用时，才移除或反转上述两项配置；两端配置必须保持一致
- 更新已有 `agents/openai.yaml` 时保留其 `interface`、`dependencies` 等其他字段，只修改 `policy.allow_implicit_invocation`
- CLI 工具目录下的同名文件即为入口（如 `cli/myskills/myskills`）
- 安装方式：`bash scripts/install.sh`，软链接到 `~/.local/bin/`
- 用户主要使用 zsh，CLI 工具应优先提供 zsh 补全文件 `_tool-name`
- 兼顾 Fish Shell，已有或适合补充的 CLI 可继续提供 `.fish` 补全文件
- zsh 补全安装到 `~/.zsh/completions/`，Fish 补全安装到 `~/.config/fish/completions/`（install.sh 自动判断或通过 `--shell` 指定）
- Skill 中的 Python 脚本统一使用 uv 执行（PEP 723 内联元数据，无需 requirements.txt）
- Skill 的配置文件统一存放在 `~/.config/<skill-name>/` 目录下
- Skill 若依赖配置文件，必须在每次执行前校验：文件不存在时引导用户初始化，文件存在但缺少必要字段或值无效时提醒用户并协助修复，不得静默跳过或使用未经校验的配置

## 维护规则

添加新 skill 或 CLI 工具时，同步更新 `README.md` 中对应表格；新 skill 默认按上述规则禁用自动调用。
如果改动影响项目结构或约定，也需更新本文件。

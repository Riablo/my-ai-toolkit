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
cli/<tool-name>/<tool-name>      # CLI 可执行入口（必需）
cli/<tool-name>/_<tool-name>     # zsh 补全（推荐）
cli/<tool-name>/<tool-name>.fish # Fish Shell 补全（兼容）
scripts/install.sh               # 安装脚本，软链 CLI 工具 + zsh/Fish 补全
```

## 约定

- 简单 CLI 直接通过工具帮助或 README 使用，不为其创建仅转述命令用法的 skill；只有需要额外的可复用工作流或任务约定时才考虑 skill
- 新 CLI 默认用 Bash 编写；已有 Python 入口或 Bash 包装的 Python/Node 实现沿用其结构，帮助信息用中文
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
- Skill 若依赖配置文件，必须在每次执行时完成配置校验。已核实主命令在请求或写入前执行等价校验时，可直接调用主命令；否则先用自检入口或只读校验。配置不存在、必要字段缺失或值无效时，停止依赖该配置的操作并协助初始化或修复，不用默认值掩盖问题
- 初始化、登录或写配置时，所用参数必须由用户明确提供或已获同意；不从示例推断路径、账号或可选值，不回显真实凭据。已有明确授权可沿用，但不扩大操作范围

## 执行与验收

- 在用户授权范围内持续完成到约定验收点；只读检查、修复本次改动造成的失败及重跑相关本地测试无需逐步确认。发布、覆盖、删除等操作仍遵守具体任务和 skill 的确认边界
- 按改动范围运行现有测试和必要检查，报告结果及未运行项。通过后仅在新改动、失败或未解决疑点出现时扩大或重复验证；不以模型能力为由跳过规定检查
- 精简 skill 前对照旧版本，保留必要命令、验收条件、失败处理和授权边界；移到 reference 的内容要保留明确入口。改变这些行为时检查对应的成功、失败或未授权场景，缺少行为证据时明确说明
- 发布的 skill 使用相对目录引用内部资源，写清外部工具的定位方式；不能依赖使用它的项目同时加载本仓库 `AGENTS.md`

下列命令从仓库根目录执行，按改动选择。Bash 测试需使用 Bash 5+：

| 改动范围 | 回归测试入口 |
| --- | --- |
| myskills / skill 分发 | `bash cli/myskills/test_myskills.bash` |
| skill-auto / 调用策略 | `bash cli/skill-auto/test_skill_auto.bash` |
| wt-land | `bash cli/wt-land/test_wt_land.bash` |
| testpage-cli | `bash cli/testpage-cli/test_testpage_cli.bash` |
| pingcode-cli | `bash cli/pingcode-cli/test_pingcode_cli.bash`、`bash cli/pingcode-cli/test_pingcode_performance.bash` |
| jenkins-builder-cli | `uv run cli/jenkins-builder-cli/test_main.py` |
| readlater-cli | `python3 cli/readlater-cli/test_main.py` |
| cloudsaver-cli | `npm --prefix cli/cloudsaver-cli test` |
| cos-cli | `uv run --with cos-python-sdk-v5==1.9.44 python -m unittest discover -s cli/cos-cli -p 'test_*.py' -v` |

Skill 的改动还需检查 frontmatter、两端调用策略、引用和文档中的命令是否有效；涉及脚本或产物时完成该 skill 的专用验证。以上本地回归入口不代表授权执行真实发布或写入服务。

## 维护规则

添加、删除或更名 skill / CLI 时，同步更新 `README.md` 表格、示例和相关引用，并清理仓库内失效的 skill 软链接；新 skill 默认按上述规则禁用自动调用。
如果改动影响项目结构或约定，也需更新本文件。

---
name: cli-skill-creator
description: 为本仓库 `cli/` 下的命令行工具创建或更新 AI skill。当用户提到“给某个 CLI 写一个 skill”、“让 AI 能用自然语言调用某个命令行工具”、“基于 help/README 为 qweather-cli、freecurrency-cli、myskills 等工具制作 skill”或“把 CLI 包装成可安装的 skill”时使用。联用通用 `skill-creator` 的原则，但优先遵循本技能里的仓库路径、CLI 探测、配置校验、结果转述和 README 同步规则。
---

# CLI Skill Creator

为 `my-ai-toolkit` 中的 CLI 工具生成 skill。保持生成结果轻量、可安装、可维护；不要把 CLI 的整份帮助信息抄进 skill，优先让后续 AI 在运行时调用 `-h` 获取最新能力。

## 联用方式

把通用 `skill-creator` 当作技能设计总规范，把本技能当作这个仓库的 CLI 专用补丁。

若两者冲突，优先遵循仓库内的 `AGENTS.md`、CLI 实际行为和本技能。

## 目标产物

默认在 `skills/<skill-name>/` 下创建 skill，并至少包含 `SKILL.md`。

若目标环境依赖技能列表的 UI 元数据，再补一个最小的 `agents/openai.yaml`。

只有在确实需要额外模板、复杂说明或示例时再增加 `references/`、`scripts/` 或 `assets/`。不要额外创建 `README.md`、`CHANGELOG.md` 一类文件。

新增 skill 后，同步更新仓库根目录的 `README.md` 表格。

## 先确认 CLI 事实

先读取这些位置：

- `cli/<tool-name>/<tool-name>`
- `cli/<tool-name>/README.md`（若存在）
- 仓库根目录 `AGENTS.md`

然后按下面顺序探测 CLI：

1. 先看入口文件的 shebang、扩展名和可执行方式，不要假设它一定是 bash。
2. 优先运行 `<tool-name> -h`；若工具未安装到 PATH，则改用仓库内入口文件。
3. 若直接执行失败，按入口类型切换解释器，例如 Python 入口用 `python3 cli/<tool-name>/<tool-name> -h`。
4. 若存在子命令，再运行 `<tool-name> <subcommand> -h` 收集各子命令职责和关键参数。
5. 再读源码，补充这些 `-h` 不一定会完整暴露的信息：配置文件路径、环境变量、初始化命令、缓存路径、输出格式、典型报错。

若 `-h` 本身就失败，不要臆造功能；先从源码和 README 判断真实调用方式。若工具当前损坏，也要在生成的 skill 中写明限制或初始化要求。

## 生成 skill 时必须覆盖的内容

为每个基于 CLI 的 skill 至少写清楚这些内容：

1. frontmatter：说明这个 skill 做什么，以及用户用什么自然语言表达时应该触发。
2. 初始化：说明 CLI 是否需要 `init`、配置文件、环境变量、登录态或 API key。
3. 配置校验：每次执行前都检查配置是否存在且关键字段有效；缺失时引导用户初始化或修复，不能静默跳过。
4. 命令选择：把用户语义映射到 CLI 的子命令或参数类别。
5. 帮助探测：提醒后续 AI 遇到细节不确定时，先跑 `-h` 或子命令 `-h`。
6. 输出转述：先给人类可读的结论，再按需要附上原始输出或关键字段。
7. 维护约定：CLI 新增子命令、参数或配置规则时，要同步更新 skill 和仓库 `README.md`。

## 路径与安装约定

假定 skill 与 CLI 同在这个仓库内，即：

- skill 位于 `skills/<skill-name>/`
- CLI 位于 `cli/<tool-name>/`

即使 skill 之后通过 `myskills` 软链接到 `~/.agents/skills/` 或 `~/.claude/skills/`，也优先把 `SKILL.md` 所在目录当作真实源目录，再回到仓库根目录定位对应 CLI。

默认把 `PROJECT_ROOT` 视为 `skills/` 的上一级目录，把 `TOOL_DIR` 视为 `PROJECT_ROOT/cli/<tool-name>`。

## 生成内容要保持轻量

不要把整份 `-h` 输出搬进 skill。只保留后续 AI 反复需要、但仅靠常识推不出来的内容，例如：

- 工具需要哪些初始化步骤
- 配置文件或环境变量叫什么
- 用户语义到子命令的大致映射
- 输出应该怎样翻译成人类语言
- 哪些子命令值得优先查看 `-h`

参数细节、枚举值、帮助文本示例留给运行时的 CLI 自己回答。

## 命令选择与结果转述

写生成的 skill 时，明确要求后续 AI：

- 先理解用户意图，再选择最接近的子命令
- 需要歧义消解时，结合 `-h`、README 和源代码决定
- 执行后先总结结论，再补地点、时间、金额、状态、错误原因等关键信息
- 默认不要原样倾倒 JSON；除非用户明确要求原始输出、调试信息或需要完整字段

如果 CLI 返回结构化数据，要求后续 AI 把字段翻译成自然语言，而不是机械复读字段名。

## 命名建议

生成 skill 时，默认让 skill 名与 CLI 工具名保持一致，除非去掉 `-cli` 会明显提升可读性且不会引起歧义。

frontmatter 的 `description` 要覆盖两类信息：

- 工具能力范围
- 用户可能说出的自然语言触发方式

## 输出模板

需要快速起草时，先查看 [references/cli-skill-template.md](references/cli-skill-template.md)。

若目标 CLI 已有现成 README 和稳定 `-h`，通常只需要一个简洁的 `SKILL.md`；不必为了“完整”而增加多余文件。

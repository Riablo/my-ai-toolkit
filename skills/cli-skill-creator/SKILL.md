---
name: cli-skill-creator
description: 为本仓库 `cli/` 下的命令行工具创建或更新 skill 时使用。用户提到“给某个 CLI 写 skill”“让 AI 用自然语言调用某个命令行工具”“把仓库里的 CLI 包装成可安装 skill”时触发。
---

# CLI Skill Creator

为 `my-ai-toolkit` 中的 CLI 生成轻量、可维护的 skill。把通用 skill 设计原则当底座，把本技能当成仓库内 CLI 的专用补丁。

## 目标

- 产出默认放在 `skills/<skill-name>/`
- 至少包含 `SKILL.md`
- 只有确实需要时才增加 `references/`、`scripts/`、`assets/` 或 `agents/openai.yaml`
- 新增 skill 后同步更新仓库根目录 `README.md`

## 先确认 CLI 事实

先读：

- `cli/<tool-name>/<tool-name>`
- `cli/<tool-name>/README.md`（若存在）
- 仓库根目录 `AGENTS.md`

再探测 CLI：

1. 先确认入口类型，不要默认它一定是 Bash。
2. 优先运行顶层 `-h`；若未安装到 PATH，改用仓库内入口。
3. 若直接执行失败，再按入口类型切换解释器。
4. 若有子命令，再看相关子命令 `-h`。
5. 最后读源码，补 `-h` 不会直接暴露的事实：配置文件、环境变量、自检入口、缓存路径、输出格式、典型报错。

若 `-h` 本身失败，不要臆造功能；先从源码和 README 判断真实调用方式。

## 写 skill 时只保留高价值信息

不要把 help 文档搬进 skill。只保留后续 AI 反复需要、但靠常识推不出来的内容：

- 什么时候触发这个 skill
- CLI 是否需要初始化、配置文件、登录态或 API key
- 默认应该直接执行主命令，还是先做某种轻量检查
- 用户语义如何映射到子命令类别
- 哪些失败最常见、最容易踩坑
- 输出应怎样转述成人话

参数细节、枚举值、完整示例留给运行时 `-h`。

## 正文结构建议

优先把每个 CLI skill 写成这几个部分：

1. `description`：只写触发场景，不写实现细节
2. 核心原则：默认动作、什么时候看 `-h`、什么时候不要自动执行初始化
3. 路由规则：用户意图到子命令的大致映射
4. Gotchas：配置坑、交互坑、危险操作、输出陷阱
5. 输出转述：先结论，后关键字段

如果某个工具有很多分支，再把重内容拆到 `references/`。

## 仓库约定

- 默认把 `PROJECT_ROOT` 视为 `skills/` 的上一级目录
- 对应 CLI 默认位于 `PROJECT_ROOT/cli/<tool-name>`
- 如果 CLI 涉及配置，自检入口要优先写清楚，但不要要求每次执行前都先跑一遍
- 对 `init`、登录、写配置这类会修改本机状态的命令，只有在用户明确给出必要参数或明确同意时才执行
- 输出默认先给自然语言结论，不要机械倾倒 JSON

## 维护

当 CLI 新增子命令、配置规则、输出格式或关键 gotcha 时，优先更新 skill 的路由与 gotcha；不要为了“完整”把正文重新膨胀成 README。

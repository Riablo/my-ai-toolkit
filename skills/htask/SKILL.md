---
name: htask
description: 在 Herdr 中用 htask 创建 Git worktree 任务，协调 Pi/Codex、PingCode bug 与本地开发或 PR/MR 交付。
disable-model-invocation: true
---

# Htask：委派新任务

`htask` 是任务入口：它创建 Herdr worktree、启动 agent 并发送提示词。此 skill 只补充选参、授权与结果判断；参数语法以当前安装的 `htask -h` 为准。CLI 由用户环境的 `PATH` 提供，用 `command -v htask` 定位；skill 与 CLI 可以分别安装，不能假定 CLI 在 skill 目录旁。

## 创建前

1. **确认意图与环境。** 只有用户明确要新建任务时才运行；仅讨论方案、询问用法或查看已有 pane 时直接解释或按 Herdr skill 使用读取命令。CLI 允许用户从 Herdr 外的 shell / 脚本调用已运行的 Herdr 服务，不需要 `HERDR_ENV`；但本 agent 亲自控制 Herdr 时仍须遵守 Herdr skill 的调用环境限制（先确认在 Herdr pane 中），不伪造环境变量。缺少 `htask` 或无法连接目标会话时停下，说明如何安装 CLI 或连接 Herdr。
2. **定位仓库与起点。** 用户指定仓库就用其路径；否则确认当前目录确实是目标仓库。`--base v6.1.0` 只传分支名：CLI 先查并刷新 `origin/v6.1.0`，远端没有时才用同名本地分支；省略 `--base` 则以当前检出的分支名执行同样规则。远端查询/刷新失败会停止，不回退本地旧分支；不会切换或合并源分支。目标仓库或基准有歧义时先问。
3. **收集最小输入。** 要有任务分支名，以及 bug 编号或任务提示词之一；缺分支时询问，不替用户从 bug 标题编造。AI 或外部脚本调用时一次传齐参数，避免 CLI 启动交互问答却无人回答；用户要自己逐项填写时，让用户在自己的终端运行 `htask`。多个 Herdr 会话时先确认 CLI 连接的是目标会话，外部脚本显式传 `--repo`。
4. **确认交付边界。** 创建任务只授权创建 worktree、启动 agent 和发送提示词。只有用户明确要求自动提交并发起 PR/MR 时才选 `--mode submit`；它也授权后续 agent 提交、推送和发布。仅要求本地开发才选 `--mode dev`，不把普通任务升级到任何模式。

## 选参时的联动

- **Bug 与提示词：** `--bug` 让 CLI 自行查询 `pingcode-cli bug`，把编号作为分支前缀（`编号/分支名`），并将工单文字、评论及图片地址放在用户补充要求之前；用户补充要求冲突时优先。无 bug 时，`--prompt` 就是主任务提示词。传给 `--branch` 的是**未加 bug 前缀**的名字，不要提前拼接；也不必重复查询工单再把原始 JSON/HTML 塞进 `--prompt`。CLI 对正文疑似凭据的过滤是尽力而为，**工单与图片的完整链接（包括查询参数）会交给 agent**；敏感工单应先审查再发送。
- **Agent 与模型：** 默认 agent 为 Pi；`--model` 仅接受该 agent 的 TOML 预设名（如 `sol/xhigh`），会转换为原生模型/强度参数。省略 `--model` 时沿用 Pi/Codex 自身配置；无预设的交互模式不会问模型。用户指定原生 ID 或强度时先核对配置中的预设，未经同意不替用户添加配置或猜测 ID；显式传入未配置的预设须报错。CLI 已移除 `--thinking`，也不自行重复启动 agent 或发送提示词。
- **配置与 dev：** 可选全局 `~/.config/htask/config.toml`（或 `$XDG_CONFIG_HOME/htask/config.toml`）和源仓库 `.config/htask/config.toml` 均使用 `schema_version = 1`；项目的 `init`/`dev` 各自覆盖全局同名数组，具名 `dev_profiles` 按名称整组覆盖，模型预设逐项覆盖。旧 JSON 尚存或 TOML 格式无效时 CLI 会在建树前停止，协助迁移或修复。CLI 在新 worktree 的第二个 tab 先执行 `init`；dev 模式交互选择启动方案，脚本不传 `--dev-profile` 使用默认 `dev`，传入名称则只运行该方案。未知名称在建树前报错；不从 bug 或路径猜 App。`SOURCE_DIR` 为源仓库根目录。配置含 shell 命令，先确认来源可信。命令只是异步派发；检查第二个 tab 后才能报告初始化或服务已完成。配置示例见随 CLI 发布的 README。
- **submit：** 仅支持主机名可自动识别的 GitHub/GitLab 网络 `origin`；未知自托管域名在建树前报错，应核对远端地址，不猜测平台；本地路径/file 远端不适用，不能悄悄降级。目标 PR/MR 分支由 `--base` 的分支名推导，CLI 会在建树前确认远端同名分支存在；仅本地分支无法作 submit 目标。CLI 只是给 agent 追加测试、提交、推送和用 `gh`/`glab` 创建 PR/MR 的指令，**不会自己发布或等待完成**。

## 完成与故障

- `htask` 成功表示已创建 worktree、启动 agent 并提交提示词；若项目有命令配置，也只是将命令提交到了第二个 tab。记录 agent pane 和项目命令 pane，向用户报告「任务已启动、初始化已派发」，而非「依赖已安装、服务已启动/PR 已完成」。新 worktree 仍聚焦 agent 所在 tab。若用户要求跟到交付完成，从 `PATH` 定位 `herdr`，用 `herdr agent get <pane-id>` / `herdr agent read <pane-id> --source recent-unwrapped --lines 120` 跟踪，并检查第二个 tab 的 `herdr pane read <pane-id> --source recent-unwrapped --lines 120` 及远端 PR/MR 实际结果。
- 创建前远端查询、配置校验或 PingCode 查询失败时先处理错误。缺少可选 htask 配置时沿用 agent 默认值；已存在但无效的配置须修复后再试。PingCode 鉴权失败按 `pingcode-cli` 的诊断/初始化指引协助修复；配置参数须由用户提供或同意，不从示例猜值。创建 worktree 后若命令 tab 创建失败或 agent 启动失败，worktree 会保留；若项目命令或提示词提交失败，可能已经发送。用返回的 pane ID 检查实际状态后再决定恢复方式，不直接重跑 `htask`、删除 worktree 或盲目重发命令。`submit` 发布结果不明时先查远端已有 PR/MR，避免重复创建。

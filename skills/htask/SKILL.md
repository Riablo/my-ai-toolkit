---
name: htask
description: 用户要创建 Herdr worktree 任务时，用 htask 启动 Pi/Codex 并核对任务结果。
disable-model-invocation: true
---

# Htask

用户明确要求新建任务时，用 `htask` 创建 Herdr worktree、启动 Pi/Codex 并发送任务提示词；仅询问用法或查看已有任务时不创建。

1. **先看帮助。** 用 `command -v htask` 从 `PATH` 定位命令，运行 `htask -h` 获取当前参数和默认行为；未安装就先协助安装，不假设 CLI 与本 skill 同目录。确认源仓库、起点分支和目标 Herdr 会话，不明确时询问。代理或脚本非交互调用时一次传齐必需参数；需要交互填写就让用户在自己的终端运行。
2. **守住授权边界。** 只有用户明确授权提交、推送和发 PR/MR 才选择 `--mode submit`。敏感工单先审查：`--bug` 会把工单和图片的完整 URL（可能含访问参数）发送给 agent。配置或认证无效时按报错协助修复，账号、路径和凭据由用户提供或同意。项目迭代背景只是定位线索，具体任务优先。
3. **按实际结果报告。** `htask` 成功表示任务启动、提示词送达；第二个 tab 的初始化/开发命令只是派发，不能据此声称服务已启动。需要跟到交付时，用输出的 pane ID 和 `PATH` 中的 `herdr` 核查 agent 与项目命令 tab；PR/MR 须核查远端实际结果。
4. **失败先核查再恢复。** 若已经建树或启动后报错，先查 pane 和外部状态，不直接重跑 `htask`。PingCode 状态更新失败时，任务可能已经启动；先核对工单状态，必要时仅用 `PATH` 中的 `pingcode-cli` 重试 `pingcode-cli set-state <编号> --state 处理中`。发布结果不明时先查已有 PR/MR，避免重复创建。

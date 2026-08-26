---
name: wt-land
description: 当用户要把当前 worktree 的已提交功能分支线性落到另一个本地 worktree 分支，或明确要求执行、排查 `wt-land` 时使用。
disable-model-invocation: true
---

# wt-land

使用 `wt-land` 把当前功能分支 rebase 到目标分支，再让目标分支所在 worktree fast-forward 到当前分支。

## 核心原则

- 用户明确给出目标分支并要求落地时，执行 `wt-land <目标分支>`
- 参数或行为不确定时先运行 `wt-land -h`
- 不要额外执行 `fetch`、`pull`、`push`、强制更新分支或删除 worktree；这些都不属于该命令的职责
- 命令会改写当前分支提交并移动目标分支，执行前应向用户清楚说明这两个 Git 副作用

## CLI 入口

- 优先使用 PATH 中的 `wt-land`
- 若未安装，再使用仓库里的 `cli/wt-land/wt-land`
- 入口是 Bash 脚本，需要 Bash 5+

## 执行前提

- 当前与目标都必须是本地分支，且不能是同一分支
- 目标分支必须已在另一个 worktree 中检出
- 两个 worktree 都必须干净，包括没有未跟踪文件
- 当前功能改动必须已经提交；不要替用户自动提交、stash 或清理文件

## 高价值 gotchas

- 命令先 rebase，出现冲突时目标分支尚未移动；让用户选择解决后 `git rebase --continue`，或用 `git rebase --abort` 撤销 rebase
- rebase 成功后，目标 worktree 只接受 `--ff-only`；不要用普通 merge 或强推绕过失败
- 命令只使用本地引用，不会同步远端；目标分支是否需要先 pull、最终是否要 push，应由用户另行决定
- 多个功能分支依次落到同一目标分支时，每次都基于目标分支当时的最新提交重新 rebase

## 输出转述

- 成功时说明当前功能分支已 rebase，并且目标分支已 fast-forward 到哪个提交
- 失败时指出是前置检查、rebase 冲突还是 fast-forward 失败，并保留 Git 给出的恢复命令

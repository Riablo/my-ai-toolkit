# wt-land

把当前功能分支 rebase 到一个本地目标分支，再让目标分支所在 worktree 通过 `--ff-only` 前进到功能分支，用于保持目标分支提交历史线性。

```bash
wt-land foo
```

典型场景是从 `foo` 建出多个 worktree 功能分支 `a`、`b`、`c`。每个功能完成并提交后，在对应 worktree 中执行 `wt-land foo`，逐个把功能分支线性落到 `foo`。

## 前提

- 当前分支与目标分支均为本地分支
- 目标分支已在另一个 worktree 中检出
- 当前与目标 worktree 均无未提交改动（包括未跟踪文件）

命令只操作本地 Git 状态，不会自动 `fetch`、`pull`、`push` 或删除 worktree。发生 rebase 冲突时，按 Git 的提示解决后执行 `git rebase --continue`，或者执行 `git rebase --abort`。

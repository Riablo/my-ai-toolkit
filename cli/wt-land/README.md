# wt-land

把当前功能分支 rebase 到一个本地目标分支，再让目标分支通过 `--ff-only` 前进到功能分支，用于保持目标分支提交历史线性。

```bash
wt-land foo
```

典型场景是从 `foo` 建出多个 worktree 功能分支 `a`、`b`、`c`。每个功能完成并提交后，在对应 worktree 中执行 `wt-land foo`，逐个把功能分支线性落到 `foo`。

也支持同一个工作目录内的不同分支，命令不变：

- 目标分支已在另一个 worktree 中检出：在该 worktree 合并，当前目录保持原分支。
- 目标分支未被检出：在当前目录 rebase，然后切到目标分支合并，成功后切回原分支。

## 前提

- 当前分支与目标分支均为本地分支
- 当前 worktree 无未提交改动（包括未跟踪文件）；目标分支若在另一个 worktree 检出，该 worktree 也必须干净

命令只操作本地 Git 状态，不会自动 `fetch`、`pull`、`push` 或删除 worktree。

## 失败处理

- rebase 冲突：按 Git 的提示解决后执行 `git rebase --continue`，完成后重新运行 `wt-land foo` 以完成合并；或者执行 `git rebase --abort` 撤销此次 rebase。
- rebase 成功后，后续步骤失败不会自动撤销 rebase。同目录模式若在快进合并时失败，会停留在目标分支；处理失败原因后，切回原功能分支再重试。
- 合并成功但切回原分支失败：目标分支已经更新，按错误提示用 `git status` 检查状态后手动切回。

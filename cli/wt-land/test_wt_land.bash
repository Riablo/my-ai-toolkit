#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp_dir="$(mktemp -d)"
tmp_dir="$(cd "$tmp_dir" && pwd -P)"
trap 'rm -rf "$tmp_dir"' EXIT

# 隔离用户配置与 hooks，所有写入仅发生在临时仓库。
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_EDITOR=true

for mode in worktree local; do
  repo="$tmp_dir/$mode repo"
  feature_worktree="$repo"

  git init -q -b foo "$repo"
  git -C "$repo" config user.email test@example.com
  git -C "$repo" config user.name Test
  printf 'base\n' >"$repo/base.txt"
  git -C "$repo" add base.txt
  git -C "$repo" commit -q -m base

  if [ "$mode" = worktree ]; then
    feature_worktree="$tmp_dir/feature a"
    git -C "$repo" worktree add -q -b a "$feature_worktree" foo
  else
    git -C "$repo" switch -qc a
  fi
  mkdir "$feature_worktree/feature-dir"
  printf 'feature\n' >"$feature_worktree/feature-dir/feature.txt"
  git -C "$feature_worktree" add feature-dir
  git -C "$feature_worktree" commit -q -m feature

  git -C "$repo" switch -q foo
  printf 'foo advanced\n' >"$repo/foo.txt"
  git -C "$repo" add foo.txt
  git -C "$repo" commit -q -m 'advance foo'
  if [ "$mode" = local ]; then
    git -C "$repo" switch -q a
  fi
  before_a="$(git -C "$repo" rev-parse a)"
  before_foo="$(git -C "$repo" rev-parse foo)"

  git -C "$repo" branch idle foo
  target_description='本地分支'
  if [ "$mode" = worktree ]; then
    target_description="$repo"
  fi
  if command -v zsh >/dev/null 2>&1; then
    completion="$(cd "$feature_worktree" && zsh -fc '
      _describe() { print -rl -- "${targets[@]}"; }
      CURRENT=2
      source "$1"
    ' -- "$script_dir/_wt-land")"
    test "$completion" = "foo:$target_description"$'\nidle:本地分支'
  else
    echo '跳过 zsh 补全验证：未安装 zsh'
  fi

  printf 'dirty\n' >"$feature_worktree/untracked.txt"
  if (cd "$feature_worktree" && "$script_dir/wt-land" foo >"$tmp_dir/out" 2>"$tmp_dir/err"); then
    echo "expected dirty current worktree to fail ($mode)" >&2
    exit 1
  fi
  grep -q '当前 worktree 有未提交改动' "$tmp_dir/err"
  rm "$feature_worktree/untracked.txt"

  if [ "$mode" = worktree ]; then
    printf 'dirty\n' >"$repo/untracked.txt"
    if (cd "$feature_worktree" && "$script_dir/wt-land" foo >"$tmp_dir/out" 2>"$tmp_dir/err"); then
      echo 'expected dirty target worktree to fail' >&2
      exit 1
    fi
    grep -q '目标 worktree 有未提交改动' "$tmp_dir/err"
    rm "$repo/untracked.txt"
  fi
  test "$(git -C "$repo" rev-parse a)" = "$before_a"
  test "$(git -C "$repo" rev-parse foo)" = "$before_foo"

  # foo 不包含 feature-dir，验证切分支移除当前子目录时仍能完成后续操作。
  (cd "$feature_worktree/feature-dir" && "$script_dir/wt-land" foo >/dev/null)
  test "$(git -C "$feature_worktree" symbolic-ref --short HEAD)" = a
  if [ "$mode" = worktree ]; then
    test "$(git -C "$repo" symbolic-ref --short HEAD)" = foo
  fi
  test "$(git -C "$repo" rev-parse foo)" = "$(git -C "$repo" rev-parse a)"
  test "$(git -C "$repo" rev-list --count foo)" -eq 3
  test "$(git -C "$repo" log --format=%s --reverse foo)" = $'base\nadvance foo\nfeature'
  git -C "$repo" merge-base --is-ancestor foo a
  git -C "$repo" diff --quiet foo a
  test -z "$(git -C "$feature_worktree" status --porcelain)"

  printf 'feature conflict\n' >"$feature_worktree/base.txt"
  git -C "$feature_worktree" commit -qam 'feature conflict'
  git -C "$repo" switch -q foo
  printf 'target conflict\n' >"$repo/base.txt"
  git -C "$repo" commit -qam 'target conflict'
  if [ "$mode" = local ]; then
    git -C "$repo" switch -q a
  fi
  before_a="$(git -C "$repo" rev-parse a)"
  before_foo="$(git -C "$repo" rev-parse foo)"
  if (cd "$feature_worktree" && "$script_dir/wt-land" foo >"$tmp_dir/out" 2>"$tmp_dir/err"); then
    echo "expected rebase conflict to fail ($mode)" >&2
    exit 1
  fi
  test -n "$(git -C "$feature_worktree" diff --name-only --diff-filter=U)"
  test "$(git -C "$repo" rev-parse foo)" = "$before_foo"
  git -C "$feature_worktree" rebase --abort
  test "$(git -C "$feature_worktree" symbolic-ref --short HEAD)" = a
  test "$(git -C "$repo" rev-parse a)" = "$before_a"

  # 解决冲突并 continue 后，再次运行命令才能完成目标分支的快进。
  if (cd "$feature_worktree" && "$script_dir/wt-land" foo >"$tmp_dir/out" 2>"$tmp_dir/err"); then
    echo "expected repeated rebase conflict to fail ($mode)" >&2
    exit 1
  fi
  printf 'resolved\n' >"$feature_worktree/base.txt"
  git -C "$feature_worktree" add base.txt
  git -C "$feature_worktree" rebase --continue >/dev/null
  test "$(git -C "$repo" rev-parse foo)" = "$before_foo"
  (cd "$feature_worktree" && "$script_dir/wt-land" foo >/dev/null)
  test "$(git -C "$feature_worktree" symbolic-ref --short HEAD)" = a
  test "$(git -C "$repo" rev-parse foo)" = "$(git -C "$repo" rev-parse a)"
done

# 同目录模式：用 hook 模拟 rebase 后目标分支又前进，必须拒绝非快进合并。
printf 'next feature\n' >"$repo/feature-dir/feature.txt"
git -C "$repo" commit -qam 'next feature'
before_a="$(git -C "$repo" rev-parse a)"
cat >"$repo/.git/hooks/post-checkout" <<'EOF'
#!/usr/bin/env bash
if [ "$(git symbolic-ref --short HEAD)" = foo ]; then
  git commit --allow-empty -qm 'target moved'
fi
EOF
chmod +x "$repo/.git/hooks/post-checkout"
if (cd "$repo" && "$script_dir/wt-land" foo >"$tmp_dir/out" 2>"$tmp_dir/err"); then
  echo 'expected non-fast-forward merge to fail' >&2
  exit 1
fi
grep -q 'fast-forward 合并失败，当前停留在目标分支：foo' "$tmp_dir/err" || {
  cat "$tmp_dir/err" >&2
  exit 1
}
test "$(git -C "$repo" symbolic-ref --short HEAD)" = foo
test "$(git -C "$repo" rev-parse a)" = "$before_a"
test "$(git -C "$repo" log -1 --format=%s foo)" = 'target moved'
test "$(git -C "$repo" rev-parse foo)" != "$before_a"

"$script_dir/wt-land" --help | grep -q 'wt-land <目标分支>'

echo "ok: wt-land 支持多 worktree 和同目录分支，保留干净检查、冲突恢复与 ff-only 保护"

#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

repo="$tmp_dir/repo"
feature_worktree="$tmp_dir/feature-a"

git init -q -b foo "$repo"
git -C "$repo" config user.email test@example.com
git -C "$repo" config user.name Test
printf 'base\n' >"$repo/base.txt"
git -C "$repo" add base.txt
git -C "$repo" commit -q -m base

git -C "$repo" worktree add -q -b a "$feature_worktree" foo
printf 'feature\n' >"$feature_worktree/feature.txt"
git -C "$feature_worktree" add feature.txt
git -C "$feature_worktree" commit -q -m feature

printf 'foo advanced\n' >"$repo/foo.txt"
git -C "$repo" add foo.txt
git -C "$repo" commit -q -m 'advance foo'

(cd "$feature_worktree" && "$script_dir/wt-land" foo >/dev/null)

test "$(git -C "$repo" rev-parse foo)" = "$(git -C "$repo" rev-parse a)"
test "$(git -C "$repo" rev-list --count foo)" -eq 3
test "$(git -C "$repo" log --format=%s --reverse foo)" = $'base\nadvance foo\nfeature'
git -C "$repo" merge-base --is-ancestor foo a
git -C "$repo" diff --quiet foo a

printf 'dirty\n' >"$feature_worktree/untracked.txt"
if (cd "$feature_worktree" && "$script_dir/wt-land" foo >"$tmp_dir/out" 2>"$tmp_dir/err"); then
  echo "expected dirty worktree to fail" >&2
  exit 1
fi
grep -q '当前 worktree 有未提交改动' "$tmp_dir/err"

"$script_dir/wt-land" --help | grep -q 'wt-land <目标分支>'

echo "ok: wt-land 会 rebase 功能分支并让目标分支 fast-forward"

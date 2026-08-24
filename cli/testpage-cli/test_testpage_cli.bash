#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

git init --bare -q "$tmp_dir/remote.git"
git init -q -b main "$tmp_dir/repo"
git -C "$tmp_dir/repo" config user.email test@example.com
git -C "$tmp_dir/repo" config user.name Test
git -C "$tmp_dir/repo" commit -q --allow-empty -m init
git -C "$tmp_dir/repo" remote add origin "$tmp_dir/remote.git"
git -C "$tmp_dir/repo" push -q -u origin main

mkdir -p "$tmp_dir/home/.config/testpage-cli" "$tmp_dir/source"
printf 'project_root=%s\nbase_url=https://example.com/\n' "$tmp_dir/repo" >"$tmp_dir/home/.config/testpage-cli/config.conf"
printf 'old\n' >"$tmp_dir/source/index.html"
printf 'old\n' >"$tmp_dir/source/old.js"

HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/source" >/dev/null
rm "$tmp_dir/source/old.js"
printf 'new\n' >"$tmp_dir/source/index.html"
printf 'new\n' >"$tmp_dir/source/new.js"
printf '%s\n' "$tmp_dir/source" | HOME="$tmp_dir/home" "$script_dir/testpage-cli" push >/dev/null

test ! -e "$tmp_dir/repo/source/old.js"
test -e "$tmp_dir/repo/source/new.js"
! git --git-dir="$tmp_dir/remote.git" cat-file -e main:source/old.js 2>/dev/null
test "$(git --git-dir="$tmp_dir/remote.git" show main:source/index.html)" = new
echo "ok: 交互路径输入会完整覆盖同名目录"

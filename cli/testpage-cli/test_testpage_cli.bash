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
ln -s old.js "$tmp_dir/source/linked.js"

export TESTPAGE_TEST_DIR="$tmp_dir"
git() {
  case " $* " in
    *' fetch '*) printf 'unexpected explicit fetch\n' >&2; return 98 ;;
    *' pull '*) printf 'pull\n' >> "$TESTPAGE_TEST_DIR/pulls.log" ;;
  esac
  command git "$@"
}
rsync() {
  case " $* " in
    *' --dry-run '*) ;;
    *) printf 'copy\n' >> "$TESTPAGE_TEST_DIR/copies.log" ;;
  esac
  command rsync "$@"
}
export -f git rsync

HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/source" >/dev/null
first_head="$(git -C "$tmp_dir/repo" rev-parse HEAD)"
ln "$tmp_dir/repo/source/index.html" "$tmp_dir/original-index.html"
# Modification times alone do not require rewriting or publishing the tree.
touch -t 200001010000 "$tmp_dir/source/index.html"
HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/source" >/dev/null
test "$tmp_dir/repo/source/index.html" -ef "$tmp_dir/original-index.html"
test "$(git -C "$tmp_dir/repo" rev-parse HEAD)" = "$first_head"
test "$(wc -l < "$tmp_dir/copies.log")" -eq 1
test "$(wc -l < "$tmp_dir/pulls.log")" -eq 2

# Executable-bit and symlink-only edits must also bypass the no-change path.
chmod +x "$tmp_dir/source/old.js"
HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/source" >/dev/null
test -x "$tmp_dir/repo/source/old.js"
rm "$tmp_dir/source/linked.js"
ln -s index.html "$tmp_dir/source/linked.js"
HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/source" >/dev/null
test "$(readlink "$tmp_dir/repo/source/linked.js")" = index.html

# Equal sizes and mtimes must not hide a changed file.
printf 'new\n' > "$tmp_dir/source/index.html"
touch -r "$tmp_dir/repo/source/index.html" "$tmp_dir/source/index.html"
HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/source" >/dev/null
test "$(git --git-dir="$tmp_dir/remote.git" show main:source/index.html)" = new
test "$(wc -l < "$tmp_dir/copies.log")" -eq 4

rm "$tmp_dir/source/old.js"
printf 'new\n' >"$tmp_dir/source/index.html"
printf 'new\n' >"$tmp_dir/source/new.js"
printf '%s\n' "$tmp_dir/source" | HOME="$tmp_dir/home" "$script_dir/testpage-cli" push >/dev/null

test ! -e "$tmp_dir/repo/source/old.js"
test -e "$tmp_dir/repo/source/new.js"
! git --git-dir="$tmp_dir/remote.git" cat-file -e main:source/old.js 2>/dev/null
test "$(git --git-dir="$tmp_dir/remote.git" show main:source/index.html)" = new

# A single HTML file is published as a file, without a wrapping directory.
printf 'page\n' >"$tmp_dir/page.html"
printf 'asset\n' >"$tmp_dir/asset.js"
url="$(HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/page.html" | tail -n 1)"
test "$url" = "https://example.com/page.html"
test "$(git --git-dir="$tmp_dir/remote.git" show main:page.html)" = page
! git --git-dir="$tmp_dir/remote.git" cat-file -e main:asset.js 2>/dev/null
file_head="$(git -C "$tmp_dir/repo" rev-parse HEAD)"
HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/page.html" >/dev/null
test "$(git -C "$tmp_dir/repo" rev-parse HEAD)" = "$file_head"
printf 'page2\n' >"$tmp_dir/page.html"
url="$(HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/page.html" --subdir sub --name demo | tail -n 1)"
test "$url" = "https://example.com/sub/demo.html"
test "$(git --git-dir="$tmp_dir/remote.git" show main:sub/demo.html)" = page2
test "$(git --git-dir="$tmp_dir/remote.git" show main:page.html)" = page
# Non-HTML files and targets that are existing directories are refused.
if HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/asset.js" >/dev/null 2>&1; then
  printf 'expected non-html file to be rejected\n' >&2; exit 1
fi
if HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/page.html" --name source.html --subdir source/.. >/dev/null 2>&1; then
  printf 'expected invalid subdir to be rejected\n' >&2; exit 1
fi
mkdir "$tmp_dir/source/nested.html"
printf 'nested\n' >"$tmp_dir/source/nested.html/index.html"
HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/source" >/dev/null
if HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/page.html" --subdir source --name nested.html >/dev/null 2>&1; then
  printf 'expected existing directory target to be rejected\n' >&2; exit 1
fi
test -d "$tmp_dir/repo/source/nested.html"
test -z "$(git -C "$tmp_dir/repo" status --porcelain)"
# The one remaining pull still refuses divergent branches before deployment.
git -C "$tmp_dir/repo" commit -q --allow-empty -m local-only
git clone -q -b main "$tmp_dir/remote.git" "$tmp_dir/other"
git -C "$tmp_dir/other" config user.email test@example.com
git -C "$tmp_dir/other" config user.name Test
git -C "$tmp_dir/other" commit -q --allow-empty -m remote-only
git -C "$tmp_dir/other" push -q origin main
copies_before="$(wc -l < "$tmp_dir/copies.log")"
printf 'blocked\n' > "$tmp_dir/source/index.html"
if HOME="$tmp_dir/home" "$script_dir/testpage-cli" push "$tmp_dir/source" > /dev/null 2> "$tmp_dir/error"; then
  printf 'expected ff-only failure\n' >&2; exit 1
fi
test "$(wc -l < "$tmp_dir/copies.log")" -eq "$copies_before"
test "$(cat "$tmp_dir/repo/source/index.html")" = new
echo "ok: 无变化不复制、内容比较、完整覆盖、单文件发布和 ff-only 均通过"

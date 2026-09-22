#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

# 复制到临时仓库，安装器的 chmod、软链接和 rc 写入均与真实环境隔离。
repo="$tmp_dir/toolkit repo"
mkdir -p "$repo/scripts" "$repo/cli/demo"
cp "$script_dir/install.sh" "$repo/scripts/install.sh"
printf '#!/usr/bin/env bash\nexit 0\n' > "$repo/cli/demo/demo"
printf '#compdef demo\n' > "$repo/cli/demo/_demo"
test_home="$tmp_dir/user home"
mkdir -p "$test_home"
installer="$repo/scripts/install.sh"
run_install() {
  env HOME="$test_home" SHELL=/bin/bash bash "$installer" "$@" > "$tmp_dir/output" 2>&1
}

run_install
test "$(readlink "$test_home/.local/bin/demo")" = "$repo/cli/demo/demo"
test "$(readlink "$test_home/.zsh/completions/_demo")" = "$repo/cli/demo/_demo"
test -x "$test_home/.local/bin/demo"
grep -q '^compinit -i$' "$test_home/.zshrc"
zsh -n "$test_home/.zshrc"
cp "$test_home/.zshrc" "$tmp_dir/expected-rc"
run_install
cmp "$test_home/.zshrc" "$tmp_dir/expected-rc"

# 集成模式把补全路径放到已有 compinit 前；再次安装保留模式和位置。
printf 'autoload -Uz compinit\ncompinit -i\n' > "$test_home/.zshrc"
run_install --zsh-rc-mode integrated
test "$(head -n 1 "$test_home/.zshrc")" = '# >>> my-ai-toolkit >>>'
test "$(grep -c '^compinit -i$' "$test_home/.zshrc")" -eq 1
zsh -n "$test_home/.zshrc"
cp "$test_home/.zshrc" "$tmp_dir/expected-rc"
run_install
cmp "$test_home/.zshrc" "$tmp_dir/expected-rc"

# 自定义目录可用；--no-rc 保留用户配置，普通文件不会被链接覆盖。
mkdir -p "$test_home/custom bin"
printf 'keep\n' > "$test_home/custom bin/demo"
run_install --no-rc --bin-dir "$test_home/custom bin" \
  --zsh-completion-dir "$test_home/custom completions"
test "$(cat "$test_home/custom bin/demo")" = keep
test ! -L "$test_home/custom bin/demo"
test "$(readlink "$test_home/custom completions/_demo")" = "$repo/cli/demo/_demo"
cmp "$test_home/.zshrc" "$tmp_dir/expected-rc"

test_home="$tmp_dir/untouched"
run_install --help
for option in --shell --bin-dir --zsh-completion-dir --zsh-rc-mode; do
  if run_install "$option"; then
    echo "expected invalid arguments to fail: $option" >&2
    exit 1
  fi
done
if run_install --zsh-rc-mode invalid; then
  echo 'expected invalid rc mode to fail' >&2
  exit 1
fi
test ! -e "$test_home"

echo '安装脚本回归测试通过'

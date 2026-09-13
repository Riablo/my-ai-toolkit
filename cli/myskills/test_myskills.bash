#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

mkdir -p "$tmp_dir/cli/myskills" "$tmp_dir/skills"
cp "$script_dir/myskills" "$tmp_dir/cli/myskills/myskills"
tool="$tmp_dir/cli/myskills/myskills"
cd "$tmp_dir"

# 纯名称模式在空目录不输出展示文案；默认展示保持原样。
test -z "$("$tool" list --names)"
test "$("$tool" list)" = '没有找到任何 skill。'

mkdir -p skills/{alpha,long,missing,utf8,without,not-a-skill}
printf 'description:   first description\ndescription: ignored\n' > skills/alpha/SKILL.md
printf 'description: 1234567890123456789012345678901234567890123456789012345678901234567890\n' > skills/long/SKILL.md
printf '%s\n' '---' 'name: missing' '---' 'body' > skills/missing/SKILL.md
printf 'description: 中文描述🙂保留原样\n' > skills/utf8/SKILL.md
printf 'description: no final newline' > skills/without/SKILL.md

test "$("$tool" list --names)" = $'alpha\nlong\nmissing\nutf8\nwithout'
expected=$'\033[1m可用的 Skills：\033[0m\n\n'
expected+=$'  \033[0;36malpha\033[0m  \033[2mfirst description\033[0m\n'
expected+=$'  \033[0;36mlong\033[0m  \033[2m123456789012345678901234567890123456789012345678901234567890\033[0m\n'
expected+=$'  \033[0;36mmissing\033[0m  \033[2m\033[0m\n'
expected+=$'  \033[0;36mutf8\033[0m  \033[2m中文描述🙂保留原样\033[0m\n'
expected+=$'  \033[0;36mwithout\033[0m  \033[2mno final newline\033[0m'
test "$("$tool" list)" = "$expected"

# 名称中的空格不能被列表/status 拆开；不读取缺少 SKILL.md 的目录。
mkdir -p 'skills/space skill' .agents/skills
printf 'description: spaces\n' > 'skills/space skill/SKILL.md'
ln -s "$tmp_dir/skills/space skill" '.agents/skills/space skill'
test "$("$tool" list --names)" = $'alpha\nlong\nmissing\nspace skill\nutf8\nwithout'
status_output="$("$tool" status)"
[[ "$status_output" == *"./.agents/skills/space skill → $tmp_dir/skills/space skill"* ]]
# 先完整读取帮助，避免 grep -q 提前关闭管道导致工具收到 SIGPIPE。
help_output="$("$tool" --help)"
[[ "$help_output" == *'list [--names]'* ]]

if command -v fish >/dev/null 2>&1; then
  fish --no-config -c '
    set -g test_tool $argv[1]
    set -g calls_file $argv[3]
    function myskills
        printf "%s\n" "$argv" >> "$calls_file"
        command "$test_tool" $argv
    end
    source $argv[2]
    set -l matches (complete -C "myskills link a")
    contains -- alpha $matches; or exit 1
    test (string join " " < "$calls_file") = "list --names"; or exit 1
    printf "" > "$calls_file"
    complete -C "myskills link alpha " >/dev/null
    test ! -s "$calls_file"; or exit 1
    complete -C "myskills link --h" >/dev/null
    test ! -s "$calls_file"; or exit 1
    set matches (complete -C "myskills link alpha --a")
    string match -q -- "--agents*" $matches; or exit 1
    set matches (complete -C "myskills list --n")
    string match -q -- "--names*" $matches; or exit 1
  ' -- "$tool" "$script_dir/myskills.fish" "$tmp_dir/fish-calls"
else
  printf '跳过 Fish 补全验证：未安装 fish\n'
fi

if command -v zsh >/dev/null 2>&1; then
  zsh -f -c '
    test_tool=$1
    calls_file=$3
    names_file=$4
    myskills() {
      print -rl -- "$@" >> "$calls_file"
      command "$test_tool" "$@"
    }
    _describe() {
      if [[ "$1" == -t && "$2" == skills ]]; then
        print -rl -- "${skills[@]}" > "$names_file"
      fi
      return 0
    }
    _arguments() { return 0; }
    CURRENT=2
    PREFIX=""
    words=(myskills link)
    source "$2"
    CURRENT=3
    words=(myskills link "")
    _myskills
    [[ "$(< "$calls_file")" == $'"'"'list\n--names'"'"' ]] || exit 1
    [[ "$(< "$names_file")" == *$'"'"'\nspace skill\n'"'"'* ]] || exit 1
    : > "$calls_file"
    CURRENT=4
    words=(myskills link alpha "")
    _myskills
    [[ ! -s "$calls_file" ]] || exit 1
    CURRENT=3
    PREFIX=--h
    words=(myskills link --h)
    _myskills
    [[ ! -s "$calls_file" ]] || exit 1
  ' -- "$tool" "$script_dir/_myskills" "$tmp_dir/zsh-calls" "$tmp_dir/zsh-names"
else
  printf '跳过 zsh 补全验证：未安装 zsh\n'
fi

printf 'myskills 回归测试通过\n'

#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp="$(mktemp -d)"
trap 'if [ "${HTASK_KEEP_TMP:-0}" = 1 ]; then printf "测试目录：%s\n" "$tmp" >&2; else rm -rf "$tmp"; fi' EXIT
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_EDITOR=true
export HERDR_ENV=1
export HTASK_TEST_LOG="$tmp/calls.jsonl" HTASK_TEST_EVENTS="$tmp/events.log" XDG_CONFIG_HOME="$tmp/config"
mkdir -p "$tmp/bin" "$tmp/repo with spaces" "$XDG_CONFIG_HOME/htask"
repo="$(cd "$tmp/repo with spaces" && pwd -P)"
git init -q -b main "$repo"
git -C "$repo" config user.email test@example.com
git -C "$repo" config user.name Test
git -C "$repo" commit -q --allow-empty -m base
git -C "$repo" remote add origin 'git@gitlab-t.example.com:org/demo.git'
git init --bare -q "$tmp/remote.git"
git -C "$repo" push -q "$tmp/remote.git" main
export HTASK_REAL_GIT="$(command -v git)" HTASK_TEST_REMOTE="$tmp/remote.git" HTASK_GIT_LOG="$tmp/git.log"
# 保留网络 origin URL 供平台校验；只将 ls-remote/fetch 重定向到本地 bare 仓库。
cat > "$tmp/bin/git" <<'EOF'
#!/usr/bin/env bash
prefix=()
if [ "${1:-}" = -C ]; then prefix=(-C "$2"); shift 2; fi
case "${1:-}" in
  ls-remote)
    printf 'ls-remote %s\n' "$5" >> "$HTASK_GIT_LOG"
    [ "${HTASK_GIT_FAIL:-}" != query ] || exit 128
    exec "$HTASK_REAL_GIT" "${prefix[@]}" ls-remote --exit-code --heads "$HTASK_TEST_REMOTE" "$5" ;;
  fetch)
    printf 'fetch %s\n' "$4" >> "$HTASK_GIT_LOG"
    [ "${HTASK_GIT_FAIL:-}" != fetch ] || exit 128
    exec "$HTASK_REAL_GIT" "${prefix[@]}" fetch --no-tags "$HTASK_TEST_REMOTE" "$4" ;;
esac
exec "$HTASK_REAL_GIT" "${prefix[@]}" "$@"
EOF
chmod +x "$tmp/bin/git"

# 用 stub 隔离全部 Herdr/PingCode 调用；本测试不创建真实 worktree、agent 或 PR/MR。
cat > "$tmp/bin/herdr" <<'EOF'
#!/usr/bin/env bash
jq -cn --args '$ARGS.positional' -- "$@" >> "$HTASK_TEST_LOG"
printf 'herdr %s %s\n' "$1" "$2" >> "$HTASK_TEST_EVENTS"
case "$1 $2" in
  'worktree create') [ "${HTASK_FAIL:-}" != create ] || exit 1
    if [ -f "$HTASK_TEST_REPO/.config/htask/config.toml" ] && [ "${HTASK_FAIL:-}" != missing-pane ]; then
      branch="" base=""
      while [ "$#" -gt 0 ]; do
        case "$1" in --branch) branch="$2"; shift ;; --base) base="$2"; shift ;; esac
        shift
      done
      mkdir -p "$(dirname "$HTASK_TEST_WORKTREES/$branch")"
      git -C "$HTASK_TEST_REPO" worktree add -qb "$branch" "$HTASK_TEST_WORKTREES/$branch" "$base"
    fi
    if [ "${HTASK_FAIL:-}" = missing-pane ]; then printf '{"result":{}}\n'; else
      jq -cn --arg path "$HTASK_TEST_WORKTREES/$branch" '{result:{workspace:{workspace_id:"w9"},root_pane:{pane_id:"w9:p8"},worktree:{path:$path}}}'
    fi ;;
  'tab create') [ "${HTASK_FAIL:-}" != tab ] || exit 1
    printf '{"result":{"tab":{"tab_id":"w9:t2"},"root_pane":{"pane_id":"w9:p9"}}}\n' ;;
  'pane run') [ "${HTASK_FAIL:-}" != run ] || exit 1 ;;
  'agent start') [ "${HTASK_FAIL:-}" != start ] || exit 1 ;;
  'agent prompt') [ "${HTASK_FAIL:-}" != prompt ] || exit 1 ;;
  *) exit 1 ;;
esac
EOF
cat > "$tmp/bin/pingcode-cli" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$HTASK_BUG_LOG"
printf 'pingcode %s\n' "$*" >> "$HTASK_TEST_EVENTS"
if [ "$1" = set-state ]; then
  if [ "${HTASK_SET_STATE_FAIL:-}" = 1 ]; then printf '模拟状态更新失败\n' >&2; exit 1; fi
  printf '{"state":"处理中"}\n'
  exit 0
fi
[ "$1" = bug ] || exit 1
[ "${HTASK_BUG_FAIL:-}" != 1 ] || exit 1
cat <<'JSON' | jq -c --arg id "$2" '.identifier = $id'
{"identifier":"720YUN-4764","title":"热点不能拖动","html_url":"https://example.com/bug?view=full&access_token=necessary",  "description":"<p>账号密码: demo secretpass</p><img src=\"https://image.example/origin-url?view=full\" src=\"https://image.example/?access_token=leak\"><p>拖动被遮挡热点失败</p>","comments":[{"content":"已知问题，继续排查"}]}
JSON
EOF
chmod +x "$tmp/bin/herdr" "$tmp/bin/pingcode-cli"
export PATH="$tmp/bin:$PATH" HTASK_BUG_LOG="$tmp/bug.log"
mkdir -p "$tmp/worktrees"
export HTASK_TEST_REPO="$repo" HTASK_TEST_WORKTREES="$(cd "$tmp/worktrees" && pwd -P)" HTASK_SETUP_LOG="$tmp/setup.log"
cat > "$tmp/bin/codegraph" <<'EOF'
#!/usr/bin/env bash
printf 'codegraph %s\n' "$*" >> "$HTASK_SETUP_LOG"
[ "${HTASK_SETUP_FAIL:-}" != codegraph ]
EOF
cat > "$tmp/bin/pnpm" <<'EOF'
#!/usr/bin/env bash
printf 'pnpm %s\n' "$*" >> "$HTASK_SETUP_LOG"
EOF
chmod +x "$tmp/bin/codegraph" "$tmp/bin/pnpm"
cli="$script_dir/htask"

reset_logs() { : > "$HTASK_TEST_LOG"; : > "$HTASK_TEST_EVENTS"; : > "$HTASK_BUG_LOG"; : > "$HTASK_GIT_LOG"; }
run() { (cd "$repo" && bash "$cli" "$@") > "$tmp/out" 2> "$tmp/err"; }
assert_failure() {
  if run "$@"; then echo "预期失败：$*" >&2; exit 1; fi
  [ ! -s "$HTASK_TEST_LOG" ] || { echo '失败前不应调用 Herdr' >&2; exit 1; }
}

bash "$cli" --help | grep -q -- '--mode dev|submit'
reset_logs
run --branch basic --prompt '你好'
jq -se --arg repo "$repo" 'length == 3 and
  .[0] == ["worktree","create","--cwd",$repo,"--branch","basic","--base","refs/remotes/origin/main","--focus"] and
  .[1][0:2] == ["agent","start"] and .[1][3:] == ["--kind","pi","--pane","w9:p8"] and
  .[2] == ["agent","prompt","w9:p8","你好"]' "$HTASK_TEST_LOG" >/dev/null
[ "$(< "$HTASK_GIT_LOG")" = $'ls-remote refs/heads/main\nfetch +refs/heads/main:refs/remotes/origin/main' ]
[ ! -s "$HTASK_BUG_LOG" ]
reset_logs
assert_failure --branch no-dev-profile --mode dev --dev-profile c2v-editor --prompt 'hi'
grep -q '没有 Dev 启动方案' "$tmp/err"
reset_logs
assert_failure --branch no-preset --model sol/xhigh --prompt 'hi'
grep -q '没有模型预设' "$tmp/err"
cat > "$XDG_CONFIG_HOME/htask/config.toml" <<'TOML'
schema_version = 1
[models.pi."sol/xhigh"]
model = "openai-codex/gpt-6-sol"
thinking = "xhigh"
[models.pi."deepseek/max"]
model = "deepseek/deepseek-flash"
thinking = "max"
[models.codex."luna/max"]
model = "gpt-6-luna"
thinking = "max"
TOML
reset_logs
run --branch explicit --model sol/xhigh --prompt '你好'
jq -se '.[1][3:] == ["--kind","pi","--pane","w9:p8","--","--provider","openai-codex","--model","gpt-6-sol","--thinking","xhigh"]' "$HTASK_TEST_LOG" >/dev/null

reset_logs
run --branch codex --agent codex --model luna/max --prompt '你好'
jq -se '.[1][3:] == ["--kind","codex","--pane","w9:p8","--","-m","gpt-6-luna","-c","model_reasoning_effort=\"max\""]' "$HTASK_TEST_LOG" >/dev/null
if grep -q dangerously "$HTASK_TEST_LOG"; then echo '不可默认绕过审批和沙箱' >&2; exit 1; fi
# 交互只列出所选 agent 的预设，选择序号后转换为原生参数。
reset_logs
python3 - "$cli" "$repo" <<'PY'
import os, pty, select, subprocess, sys, time
master, slave = pty.openpty()
p = subprocess.Popen(['bash', sys.argv[1], '--branch', 'listed', '--agent', 'codex'],
                     cwd=sys.argv[2], stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
try:
    for expected, answer in [('仓库路径'.encode(), b'\n'), (b'--base', b'\n'),
                             (b'--bug', b'\n'), (b'1) luna/max', b'1\n'), (b'--mode', b'\n'),
                             (b'--prompt', b'hello\n')]:
        output = b''
        end = time.monotonic() + 10
        while expected not in output:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f'missing {expected!r}: {output!r}')
            ready, _, _ = select.select([master], [], [], remaining)
            if ready:
                output += os.read(master, 4096)
        if expected == b'1) luna/max':
            assert b'--model' in output and b'sol/xhigh' not in output, output
        os.write(master, answer)
    assert p.wait(timeout=10) == 0
finally:
    if p.poll() is None:
        p.kill()
    os.close(master)
PY
jq -se '.[1][3:] == ["--kind","codex","--pane","w9:p8","--","-m","gpt-6-luna","-c","model_reasoning_effort=\"max\""]' "$HTASK_TEST_LOG" >/dev/null
reset_logs
assert_failure --branch unknown-alias --agent codex --model sol/xhigh --prompt 'hi'
reset_logs
assert_failure --branch removed-flag --thinking xhigh --prompt 'hi'
rm "$XDG_CONFIG_HOME/htask/config.toml"

# 本地 main 故意落后；远端同名分支必须先刷新。远端没有时只用真正的本地分支。
git -C "$repo" checkout -qb remote-tip
git -C "$repo" commit -q --allow-empty -m 'new remote tip'
git -C "$repo" push -q "$HTASK_TEST_REMOTE" HEAD:main
git -C "$repo" checkout -q main
reset_logs
run --branch fresh --base main --prompt 'hi'
[ "$(git -C "$repo" rev-parse refs/remotes/origin/main)" = "$(git -C "$repo" rev-parse remote-tip)" ]
[ "$(git -C "$repo" rev-parse main)" != "$(git -C "$repo" rev-parse remote-tip)" ]
jq -se '.[0][7] == "refs/remotes/origin/main"' "$HTASK_TEST_LOG" >/dev/null
git -C "$repo" branch local-only
reset_logs
run --branch local-fallback --base local-only --prompt 'hi'
jq -se '.[0][7] == "refs/heads/local-only"' "$HTASK_TEST_LOG" >/dev/null
[ "$(< "$HTASK_GIT_LOG")" = 'ls-remote refs/heads/local-only' ]
reset_logs
assert_failure --branch no-remote-ref --base origin/local-only --prompt 'hi'
reset_logs
assert_failure --branch no-target --base local-only --mode submit --prompt 'hi'
grep -q '目标分支 origin/local-only 不存在' "$tmp/err"
git -C "$repo" update-ref refs/remotes/origin/old-cached HEAD
reset_logs
assert_failure --branch no-stale --base old-cached --prompt 'hi'
git -C "$repo" tag tag-only
git -C "$repo" push -q "$HTASK_TEST_REMOTE" tag-only
reset_logs
assert_failure --branch no-tag --base tag-only --prompt 'hi'
git -C "$repo" remote remove origin
reset_logs
run --branch no-origin --base local-only --prompt 'hi'
jq -se '.[0][7] == "refs/heads/local-only"' "$HTASK_TEST_LOG" >/dev/null
[ ! -s "$HTASK_GIT_LOG" ]
git -C "$repo" remote add origin 'git@gitlab-t.example.com:org/demo.git'

# 精确按起点分支名匹配迭代背景；bug 和用户要求顺序保留，不猜同名前缀。
mkdir -p "$repo/.config/htask"
git -C "$repo" push -q "$HTASK_TEST_REMOTE" main:v6.1.0
git -C "$repo" push -q "$HTASK_TEST_REMOTE" main:v6.1.1
cat > "$repo/.config/htask/config.toml" <<'TOML'
schema_version = 1
[iteration_prompts]
"v6.1.0" = "示例背景：优先在 apps/sample-app/ 查找；具体任务优先。"
"v6.2.0" = "另一个版本的背景"
TOML
reset_logs
run --branch ctx-bug --base v6.1.0 --bug 720YUN-4764 --prompt '用户要求：修复主项目'
jq -se '.[2][3] as $p |
  ($p | startswith("项目迭代背景（起点分支：v6.1.0；仅供定位，具体工单或用户要求优先）：\n示例背景：优先在 apps/sample-app/ 查找；具体任务优先。")) and
  (($p | index("请修复以下 PingCode Bug：")) > ($p | index("示例背景："))) and
  (($p | index("用户补充要求")) > ($p | index("描述："))) and
  ($p | contains("用户要求：修复主项目")) and
  ($p | contains("https://example.com/bug?view=full&access_token=necessary")) and
  ($p | contains("另一个版本的背景") | not)' "$HTASK_TEST_LOG" >/dev/null
reset_logs
run --branch ctx-origin --base origin/v6.1.0 --prompt '只修某个问题'
jq -se '.[2][3] == "项目迭代背景（起点分支：v6.1.0；仅供定位，具体工单或用户要求优先）：\n示例背景：优先在 apps/sample-app/ 查找；具体任务优先。\n\n只修某个问题"' "$HTASK_TEST_LOG" >/dev/null
reset_logs
run --branch ctx-other --base v6.1.1 --prompt '只执行原任务'
jq -se '.[2][3] == "只执行原任务"' "$HTASK_TEST_LOG" >/dev/null
reset_logs
run --branch ctx-main --base main --prompt '修主项目'
jq -se '.[2][3] == "修主项目"' "$HTASK_TEST_LOG" >/dev/null
reset_logs
run --branch ctx-submit --base v6.1.0 --mode submit --prompt '交付当前任务'
jq -se '.[2][3] as $p |
  ($p | startswith("项目迭代背景（起点分支：v6.1.0")) and
  (($p | index("交付要求：")) > ($p | index("交付当前任务")))' "$HTASK_TEST_LOG" >/dev/null
git -C "$repo" checkout -qb v6.1.0
reset_logs
run --branch ctx-default --prompt '默认 base'
jq -se '.[2][3] | startswith("项目迭代背景（起点分支：v6.1.0")' "$HTASK_TEST_LOG" >/dev/null
git -C "$repo" checkout -q main
rm "$repo/.config/htask/config.toml"

reset_logs
HTASK_GIT_FAIL=query assert_failure --branch offline --base main --prompt 'hi'
grep -q '未回退' "$tmp/err"
reset_logs
HTASK_GIT_FAIL=fetch assert_failure --branch fetch-fail --base main --prompt 'hi'
grep -q '未使用本地旧版本' "$tmp/err"

reset_logs
run --branch fix --bug 720YUN-4764 --prompt '优先我的要求' --mode dev
[ "$(< "$HTASK_BUG_LOG")" = $'bug 720YUN-4764\nset-state 720YUN-4764 --state 处理中' ]
[ "$(< "$HTASK_TEST_EVENTS")" = $'pingcode bug 720YUN-4764\nherdr worktree create\nherdr agent start\nherdr agent prompt\npingcode set-state 720YUN-4764 --state 处理中' ]
grep -q 'PingCode Bug 720YUN-4764 已更新为处理中' "$tmp/out"
jq -se '.[0][5] == "720YUN-4764/fix" and
  (.[2][3] | startswith("请修复以下 PingCode Bug：") and
   contains("热点不能拖动") and contains("拖动被遮挡热点失败") and
   contains("链接：https://example.com/bug?view=full&access_token=necessary") and
   contains("图片地址：") and contains("https://image.example/origin-url?view=full") and
   contains("用户补充要求") and contains("优先我的要求") and
   (contains("（基础描述；") | not) and (contains("（PingCode 转换后的公开地址）") | not) and
   (contains("secretpass") | not) and (contains("access_token=leak") | not) and (contains("leak") | not))' "$HTASK_TEST_LOG" >/dev/null
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 3 ] # dev 暂不创建额外 pane
jq -se '(.[2][3] | index("用户补充要求")) > (.[2][3] | index("拖动被遮挡热点失败"))' "$HTASK_TEST_LOG" >/dev/null

reset_logs
run --branch onlybug --bug 720YUN-4764
jq -se '.[0][5] == "720YUN-4764/onlybug" and (.[2][3] | contains("热点不能拖动"))' "$HTASK_TEST_LOG" >/dev/null
[ "$(< "$HTASK_BUG_LOG")" = $'bug 720YUN-4764\nset-state 720YUN-4764 --state 处理中' ]

reset_logs
run --branch foo-bar --bug 720YUN-11380 --prompt 'hi'
jq -se '.[0][5] == "720YUN-11380/foo-bar" and
  (.[2][3] | contains("编号：720YUN-11380"))' "$HTASK_TEST_LOG" >/dev/null
[ "$(< "$HTASK_BUG_LOG")" = $'bug 720YUN-11380\nset-state 720YUN-11380 --state 处理中' ]

reset_logs
run --branch submit --bug 720YUN-4764 --base main --mode submit
[ "$(< "$HTASK_BUG_LOG")" = $'bug 720YUN-4764\nset-state 720YUN-4764 --state 处理中' ]
jq -se '.[0][5] == "720YUN-4764/submit" and
  (.[2][3] | contains("glab mr create --source-branch") and contains("--target-branch") and contains("720YUN-4764") and contains("main") and (contains("（submit 模式）") | not))' "$HTASK_TEST_LOG" >/dev/null

# submit 的交互问答自动识别 GitLab，不再显示平台选择。
reset_logs
python3 - "$cli" "$repo" <<'PY'
import os, pty, select, subprocess, sys, time
master, slave = pty.openpty()
p = subprocess.Popen(['bash', sys.argv[1], '--branch', 'tty-submit', '--mode', 'submit'],
                     cwd=sys.argv[2], stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
try:
    for expected, answer in [('仓库路径'.encode(), b'\n'), (b'--base', b'\n'),
                             (b'--bug', b'\n'), (b'--agent', b'\n'), (b'--prompt', b'hi\n')]:
        output = b''
        end = time.monotonic() + 10
        while expected not in output:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f'missing {expected!r}: {output!r}')
            ready, _, _ = select.select([master], [], [], remaining)
            if ready:
                output += os.read(master, 4096)
                assert b'--forge' not in output, output
        os.write(master, answer)
    assert p.wait(timeout=10) == 0
finally:
    if p.poll() is None:
        p.kill()
    os.close(master)
PY
jq -se '.[0][5] == "tty-submit" and (.[2][3] | contains("glab mr create"))' "$HTASK_TEST_LOG" >/dev/null

git -C "$repo" push -q "$HTASK_TEST_REMOTE" main:release
git -C "$repo" update-ref refs/remotes/origin/release HEAD
git -C "$repo" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/release
reset_logs
assert_failure --branch ambiguous --base origin --mode submit --prompt 'done'
grep -q '具体分支名' "$tmp/err"
reset_logs
run --branch release-fix --base origin/release --mode submit --prompt 'done'
jq -se '.[0][7] == "refs/remotes/origin/release" and (.[2][3] | contains("目标分支：release。"))' "$HTASK_TEST_LOG" >/dev/null

git -C "$repo" remote set-url origin 'https://github.com/org/demo.git'
reset_logs
run --branch gh --mode submit --prompt 'done'
jq -se '.[2][3] | contains("gh pr create --base") and contains("--head") and contains("main")' "$HTASK_TEST_LOG" >/dev/null

git -C "$repo" remote set-url origin 'https://forge.example.com/org/demo.git'
reset_logs
assert_failure --branch unknown --mode submit --prompt 'done'
grep -q '无法从 origin 主机 forge.example.com 识别' "$tmp/err"
reset_logs
assert_failure --branch custom --mode submit --forge gitlab --prompt 'done'
grep -q '未知选项：--forge' "$tmp/err"

git -C "$repo" remote set-url origin "$tmp/remote.git"
reset_logs
assert_failure --branch local --mode submit --prompt 'done'
grep -q '本地路径' "$tmp/err"

reset_logs
assert_failure --branch invalid --bug INVALID --prompt 'hi'
reset_logs
assert_failure --branch bad --agent none --prompt 'hi'
reset_logs
assert_failure --branch bad --mode other --prompt 'hi'
reset_logs
assert_failure --branch bad --agent pi --model no-provider --prompt 'hi'
reset_logs
assert_failure --branch bad --prompt 'hi' --base missing-ref
reset_logs
assert_failure --branch 'bad..branch' --prompt 'hi'
reset_logs
assert_failure --branch incomplete

# 完整参数可由 Herdr 外的脚本调用；不依赖 pane 注入的 HERDR_* 上下文。
reset_logs
(cd "$repo" && env -u HERDR_ENV -u HERDR_SOCKET_PATH -u HERDR_WORKSPACE_ID \
  -u HERDR_TAB_ID -u HERDR_PANE_ID -u HERDR_STARTUP_CWD -u HERDR_BIN_PATH \
  bash "$cli" --branch external --prompt 'hi') > "$tmp/out" 2> "$tmp/err"
jq -se 'length == 3 and .[0][0:2] == ["worktree","create"] and
  .[0][5] == "external" and .[1][0:2] == ["agent","start"] and
  .[2] == ["agent","prompt","w9:p8","hi"]' "$HTASK_TEST_LOG" >/dev/null

reset_logs
if HTASK_BUG_FAIL=1 run --branch no-bug --bug 720YUN-4764; then
  echo '查询失败不能创建 worktree' >&2; exit 1
fi
[ ! -s "$HTASK_TEST_LOG" ]
[ "$(< "$HTASK_BUG_LOG")" = 'bug 720YUN-4764' ]

# 只有 agent 提示词成功送达才更新状态；更新失败也不能重建已启动的任务。
for stage in create start prompt; do
  reset_logs
  if HTASK_FAIL="$stage" run --branch "bug-${stage}-fail" --bug 720YUN-4764 --prompt 'hi'; then
    echo "Herdr ${stage} 失败不应更新 bug 状态" >&2; exit 1
  fi
  [ "$(< "$HTASK_BUG_LOG")" = 'bug 720YUN-4764' ]
done
reset_logs
if HTASK_SET_STATE_FAIL=1 run --branch bug-state-fail --bug 720YUN-4764 --prompt 'hi'; then
  echo '更新 bug 失败应报告部分成功' >&2; exit 1
fi
[ "$(< "$HTASK_BUG_LOG")" = $'bug 720YUN-4764\nset-state 720YUN-4764 --state 处理中' ]
[ "$(< "$HTASK_TEST_EVENTS")" = $'pingcode bug 720YUN-4764\nherdr worktree create\nherdr agent start\nherdr agent prompt\npingcode set-state 720YUN-4764 --state 处理中' ]
grep -q '任务已启动' "$tmp/out"
! grep -q 'PingCode Bug.*已更新为处理中' "$tmp/out"
grep -q '任务已启动.*PingCode Bug.*状态更新失败' "$tmp/err"
grep -q '不要重新执行 htask' "$tmp/err"

# 各阶段失败后不误启 agent、不删除 worktree，也不重复提交提示词。
reset_logs
if HTASK_FAIL=create run --branch create-fail --prompt 'hi'; then exit 1; fi
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 1 ]
reset_logs
if HTASK_FAIL=missing-pane run --branch missing-pane --prompt 'hi'; then exit 1; fi
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 1 ]
grep -q 'root_pane.pane_id' "$tmp/err"
reset_logs
if HTASK_FAIL=start run --branch start-fail --prompt 'hi'; then exit 1; fi
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 2 ]
grep -q 'worktree 已创建' "$tmp/err"
reset_logs
if HTASK_FAIL=prompt run --branch prompt-fail --prompt 'hi'; then exit 1; fi
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 3 ]
grep -q '勿盲目重发' "$tmp/err"

# 通过伪终端验证 Herdr 外部直接运行 htask 的逐项交互；空回车接受默认值。
reset_logs
python3 - "$cli" "$repo" <<'PY'
import os, pty, select, subprocess, sys, time
master, slave = pty.openpty()
external_env = {key: value for key, value in os.environ.items() if not key.startswith('HERDR_')}
p = subprocess.Popen(['bash', sys.argv[1]], cwd=sys.argv[2], stdin=slave,
                     stdout=slave, stderr=slave, env=external_env)
os.close(slave)
answers = [b'\n', b'\n', b'\n', b'from-tty\n', b'\n', b'\n', b'\n', b'hello tty\n']
output = b''
try:
    for expected, answer in zip(['仓库路径'.encode(), b'--base', b'--bug', b'--branch', b'--agent', b'--mode', b'--prompt', b'--prompt'], answers):
        end = time.monotonic() + 10
        while expected not in output:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f'missing prompt {expected!r}: {output!r}')
            ready, _, _ = select.select([master], [], [], remaining)
            if ready:
                try:
                    output += os.read(master, 4096)
                except OSError:
                    break
        if expected == b'--prompt':
            assert '可留空'.encode() not in output and '任务补充提示词'.encode() not in output
        os.write(master, answer)
        output = b''
    assert p.wait(timeout=10) == 0
finally:
    if p.poll() is None:
        p.kill()
    os.close(master)
PY
jq -se '.[0][5] == "from-tty" and .[1][3:] == ["--kind","pi","--pane","w9:p8"] and .[2][3] == "hello tty"' "$HTASK_TEST_LOG" >/dev/null

# 必填分支首次直接回车要重复询问，提示文字也不得声称可以留空。
reset_logs
python3 - "$cli" "$repo" <<'PY'
import os, pty, select, subprocess, sys, time
master, slave = pty.openpty()
p = subprocess.Popen(['bash', sys.argv[1], '--prompt', 'only task'], cwd=sys.argv[2],
                     stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
transcript = b''
try:
    for expected, answer in [('仓库路径'.encode(), b'\n'), (b'--base', b'\n'), (b'--bug', b'\n'),
                             (b'--branch', b'\n'), (b'--branch', b'retry\n'),
                             (b'--agent', b'\n'), (b'--mode', b'\n')]:
        end = time.monotonic() + 10
        output = b''
        while expected not in output:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f'missing prompt {expected!r}: {output!r}')
            ready, _, _ = select.select([master], [], [], remaining)
            if ready:
                output += os.read(master, 4096)
        if expected == b'--branch':
            assert '可留空'.encode() not in output, output
        transcript += output
        os.write(master, answer)
    assert p.wait(timeout=10) == 0
    assert transcript.count(b'--branch') == 2
finally:
    if p.poll() is None:
        p.kill()
    os.close(master)
PY
jq -se '.[0][5] == "retry" and .[2][3] == "only task"' "$HTASK_TEST_LOG" >/dev/null

# 配置仅从源仓库读取，所有命令在新 worktree 的第二个 tab 顺序执行。
mkdir -p "$repo/.config/htask"
printf 'test-only local env\n' > "$repo/.env.development.local"
cat > "$repo/.config/htask/config.toml" <<'TOML'
schema_version = 1
init = ['cp "$SOURCE_DIR/.env.development.local" ./.env.development.local', 'codegraph index -f', 'pnpm install']
dev = ['pnpm run start']
[dev_profiles]
"c2v-editor" = ['pnpm run start:c2v-editor']
TOML
setup_command() { jq -sr 'map(select(.[0:2] == ["pane","run"]))[-1][3]' "$HTASK_TEST_LOG"; }
run_setup_in_worktree() {
  (cd "$HTASK_TEST_WORKTREES/$1" &&
    if command -v zsh >/dev/null; then zsh -fc "$(setup_command)"; else bash -c "$(setup_command)"; fi
  ) > "$tmp/setup-out" 2> "$tmp/setup-err"
}

reset_logs
run --branch nested --bug 720YUN-4764 --prompt 'hi'
jq -se '.[0][5] == "720YUN-4764/nested" and
  (.[1] | index("--cwd")) != null' "$HTASK_TEST_LOG" >/dev/null
[ -d "$HTASK_TEST_WORKTREES/720YUN-4764/nested" ]
[ "$(git -C "$repo" rev-parse 720YUN-4764/nested)" = "$(git -C "$repo" rev-parse refs/remotes/origin/main)" ]
reset_logs
run --branch init-only --prompt 'hi'
jq -se --arg wt "$HTASK_TEST_WORKTREES/init-only" 'length == 5 and
  .[1] == ["tab","create","--workspace","w9","--cwd",$wt,"--label","Setup","--no-focus"] and
  .[2][0:3] == ["pane","run","w9:p9"] and
  .[3][0:2] == ["agent","start"] and .[4][0:3] == ["agent","prompt","w9:p8"]' "$HTASK_TEST_LOG" >/dev/null
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree init-only || { printf 'setup stderr: %s\n' "$(< "$tmp/setup-err")" >&2; exit 1; }
cmp "$repo/.env.development.local" "$HTASK_TEST_WORKTREES/init-only/.env.development.local"
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph index -f\npnpm install' ]
grep -q '初始化完成' "$tmp/setup-out"

git -C "$repo" remote set-url origin 'git@gitlab-t.example.com:org/demo.git'
reset_logs
run --branch submit-init --mode submit --base main --prompt 'hi'
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 5 ]
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree submit-init
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph index -f\npnpm install' ]

reset_logs
run --branch dev-task --mode dev --prompt 'hi'
jq -se --arg wt "$HTASK_TEST_WORKTREES/dev-task" 'length == 5 and
  .[1] == ["tab","create","--workspace","w9","--cwd",$wt,"--label","Dev","--no-focus"] and
  (.[4][3] | contains("环境初始化正在另一个 tab") and (contains("（dev 模式）") | not))' "$HTASK_TEST_LOG" >/dev/null
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree dev-task
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph index -f\npnpm install\npnpm run start' ]

reset_logs
run --branch c2v-task --mode dev --dev-profile c2v-editor --prompt 'hi'
jq -se 'length == 5 and .[1][7] == "Dev" and (.[4][3] | startswith("hi"))' "$HTASK_TEST_LOG" >/dev/null
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree c2v-task
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph index -f\npnpm install\npnpm run start:c2v-editor' ]

# 交互 dev 模式列出默认命令与具名方案；通过序号选择 C2V。
reset_logs
python3 - "$cli" "$repo" <<'PY'
import os, pty, select, subprocess, sys, time
master, slave = pty.openpty()
p = subprocess.Popen(['bash', sys.argv[1], '--branch', 'c2v-tty', '--mode', 'dev'],
                     cwd=sys.argv[2], stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
try:
    for expected, answer in [('仓库路径'.encode(), b'\n'), (b'--base', b'\n'),
                             (b'--bug', b'\n'), (b'--agent', b'\n'),
                             (b'1) c2v-editor', b'1\n'), (b'--prompt', b'hi\n')]:
        output = b''
        end = time.monotonic() + 10
        while expected not in output:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f'missing {expected!r}: {output!r}')
            ready, _, _ = select.select([master], [], [], remaining)
            if ready:
                output += os.read(master, 4096)
        os.write(master, answer)
    assert p.wait(timeout=10) == 0
finally:
    if p.poll() is None:
        p.kill()
    os.close(master)
PY
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree c2v-tty
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph index -f\npnpm install\npnpm run start:c2v-editor' ]
reset_logs
assert_failure --branch invalid-profile --mode dev --dev-profile unknown --prompt 'hi'
grep -q '没有 Dev 启动方案' "$tmp/err"
reset_logs
assert_failure --branch wrong-mode --mode submit --dev-profile c2v-editor --prompt 'hi'
grep -q '仅适用于 --mode dev' "$tmp/err"
reset_logs
assert_failure --branch no-mode --dev-profile c2v-editor --prompt 'hi'

reset_logs
run --branch failed-init --mode dev --prompt 'hi'
: > "$HTASK_SETUP_LOG"
if HTASK_SETUP_FAIL=codegraph run_setup_in_worktree failed-init; then
  echo '初始化失败时不应继续安装或启动服务' >&2; exit 1
fi
[ "$(< "$HTASK_SETUP_LOG")" = 'codegraph index -f' ]
grep -q '项目命令失败' "$tmp/setup-err"

printf 'schema_version = 1\ninit = []\ndev = ["pnpm run start"]\n' > "$repo/.config/htask/config.toml"
reset_logs
run --branch only-dev-default --prompt 'hi'
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 3 ]
reset_logs
run --branch only-dev-mode --mode dev --prompt 'hi'
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 5 ]
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree only-dev-mode
[ "$(< "$HTASK_SETUP_LOG")" = 'pnpm run start' ]
cat > "$repo/.config/htask/config.toml" <<'TOML'
schema_version = 1
init = ['cp "$SOURCE_DIR/.env.development.local" ./.env.development.local', 'codegraph index -f', 'pnpm install']
dev = ['pnpm run start']
[dev_profiles]
"c2v-editor" = ['pnpm run start:c2v-editor']
TOML

reset_logs
run --branch bug-with-init --bug 720YUN-4764 --prompt 'hi'
[ "$(< "$HTASK_TEST_EVENTS")" = $'pingcode bug 720YUN-4764\nherdr worktree create\nherdr tab create\nherdr pane run\nherdr agent start\nherdr agent prompt\npingcode set-state 720YUN-4764 --state 处理中' ]
reset_logs
if HTASK_FAIL=tab run --branch tab-fail --prompt 'hi'; then exit 1; fi
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 2 ]
reset_logs
if HTASK_FAIL=tab run --branch bug-tab-fail --bug 720YUN-4764 --prompt 'hi'; then exit 1; fi
[ "$(< "$HTASK_BUG_LOG")" = 'bug 720YUN-4764' ]
reset_logs
if HTASK_FAIL=run run --branch run-fail --prompt 'hi'; then exit 1; fi
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 3 ]

printf 'schema_version = 1\ninit = [42]\n' > "$repo/.config/htask/config.toml"
reset_logs
assert_failure --branch bad-config --prompt 'hi'
grep -q '配置无效' "$tmp/err"
printf 'schema_version = 1\n[dev_profiles]\nc2v-editor = [""]\n' > "$repo/.config/htask/config.toml"
reset_logs
assert_failure --branch bad-profile-config --prompt 'hi'
grep -q 'dev_profiles.c2v-editor' "$tmp/err"
printf 'schema_version = 1\n[iteration_prompts]\n"v6.1.0" = ["wrong type"]\n' > "$repo/.config/htask/config.toml"
reset_logs
assert_failure --branch bad-iteration-config --prompt 'hi'
grep -q 'iteration_prompts.v6.1.0' "$tmp/err"
printf 'schema_version = 1\n[iteration_prompts]\n"v6.1.0" = "  "\n' > "$repo/.config/htask/config.toml"
reset_logs
assert_failure --branch empty-iteration-config --prompt 'hi'
rm "$repo/.config/htask/config.toml"
reset_logs
run --branch no-config --mode dev --prompt 'hi'
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 3 ]

# 项目数组覆盖全局，未声明的数组继承；同名预设只覆盖声明的字段。
cat > "$XDG_CONFIG_HOME/htask/config.toml" <<'TOML'
schema_version = 1
init = ['codegraph global']
dev = ['pnpm run start']
[dev_profiles]
"c2v-editor" = ['pnpm run start:global-c2v']
extension = ['pnpm run start:extension']
[iteration_prompts]
"v6.1.0" = "全局迭代背景"
"v6.2.0" = "全局第二版本"
[models.pi."sol/xhigh"]
model = 'openai-codex/gpt-6-sol'
thinking = 'xhigh'
TOML
cat > "$repo/.config/htask/config.toml" <<'TOML'
schema_version = 1
init = ['codegraph project']
[dev_profiles]
"c2v-editor" = ['pnpm run start:project-c2v']
[iteration_prompts]
"v6.1.0" = "项目迭代背景"
[models.pi."sol/xhigh"]
thinking = 'low'
TOML
reset_logs
run --branch layered --mode dev --model sol/xhigh --prompt 'hi'
jq -se '.[3][3:] == ["--kind","pi","--pane","w9:p8","--","--provider","openai-codex","--model","gpt-6-sol","--thinking","low"]' "$HTASK_TEST_LOG" >/dev/null
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree layered
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph project\npnpm run start' ]
python3 "$script_dir/config.py" "$XDG_CONFIG_HOME/htask/config.toml" "$repo/.config/htask/config.toml" |
  jq -e '.iteration_prompts["v6.1.0"] == "项目迭代背景" and .iteration_prompts["v6.2.0"] == "全局第二版本"' >/dev/null
reset_logs
run --branch override-profile --mode dev --dev-profile c2v-editor --prompt 'hi'
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree override-profile
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph project\npnpm run start:project-c2v' ]
reset_logs
run --branch inherited-profile --mode dev --dev-profile extension --prompt 'hi'
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree inherited-profile
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph project\npnpm run start:extension' ]
printf 'schema_version = 1\ninit = []\ndev = []\n' > "$repo/.config/htask/config.toml"
reset_logs
run --branch cleared --mode dev --prompt 'hi'
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 3 ]

# 旧 JSON、错误格式与未定义的新预设，都必须在建树前停止。
printf '{"schemaVersion":1,"init":[]}\n' > "$repo/.config/htask/config.json"
reset_logs
assert_failure --branch legacy --prompt 'hi'
grep -q '旧版 JSON' "$tmp/err"
rm "$repo/.config/htask/config.json"
printf 'schema_version = 1\n[models.pi."new"]\nthinking = "low"\n' > "$repo/.config/htask/config.toml"
reset_logs
assert_failure --branch incomplete-model --prompt 'hi'
grep -q '缺少 model' "$tmp/err"
rm "$repo/.config/htask/config.toml"
printf 'schema_version = [broken\n' > "$XDG_CONFIG_HOME/htask/config.toml"
reset_logs
assert_failure --branch invalid-global --prompt 'hi'
grep -q 'TOML 语法错误' "$tmp/err"
rm "$XDG_CONFIG_HOME/htask/config.toml"

# 安装后为软链入口，辅助解析器须从软链目标旁加载。
ln -s "$cli" "$tmp/bin/htask-link"
reset_logs
(cd "$repo" && bash "$tmp/bin/htask-link" --branch via-link --prompt 'hi') > "$tmp/out" 2> "$tmp/err"
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 3 ]

echo 'htask 回归测试通过'

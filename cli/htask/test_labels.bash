#!/usr/bin/env bash
# 由 test_htask.bash source，复用隔离的 Git/Herdr stub；不连接真实服务。
# 失败清单：默认值误追加、清空失效、重复 init、串行阻塞服务、init 失败仍启动、
# 单服务失败连带取消、submit 漏 Label/越权发布、无 Label 项目被要求配置、旧配置静默忽略。
cat > "$repo/.config/htask/config.toml" <<'TOML'
schema_version = 2
init = ['codegraph common']
dev = ['pnpm run default']
[labels.editor]
init = ['codegraph editor']
dev = ['pnpm run editor']
[labels.c2v]
init = ['codegraph c2v']
dev = ['pnpm run c2v']
[labels.documentation]
[labels."area::中文 空格"]
[iterations."v6.1.0"]
prompt = '迭代说明'
labels = ['c2v']
TOML
cp "$repo/.config/htask/config.toml" "$tmp/labels.toml"

reset_logs
run --branch labels-default --base origin/v6.1.0 --mode dev --prompt hi
jq -se 'map(select(.[0:2] == ["agent","prompt"]))[0][3] | contains("[\"c2v\"]")' "$HTASK_TEST_LOG" >/dev/null
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree labels-default
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph common\ncodegraph c2v\npnpm run c2v' ]

reset_logs
run --branch labels-override --base v6.1.0 --label editor --label editor --mode dev --prompt hi
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree labels-override
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph common\ncodegraph editor\npnpm run editor' ]

reset_logs
run --branch labels-none --base v6.1.0 --no-labels --mode dev --prompt hi
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree labels-none
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph common\npnpm run default' ]

reset_logs
run --branch labels-many --mode dev --label editor --label c2v --label editor --prompt hi
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree labels-many
[ "$(head -3 "$HTASK_SETUP_LOG")" = $'codegraph common\ncodegraph editor\ncodegraph c2v' ]
[ "$(grep -c '^pnpm run' "$HTASK_SETUP_LOG")" -eq 2 ]
jq -se 'map(select(.[0:2] == ["tab","create"])) | map(.[7]) == ["Setup","Dev: editor","Dev: c2v"]' "$HTASK_TEST_LOG" >/dev/null

reset_logs
run --branch labels-no-dev --mode dev --label documentation --prompt hi
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree labels-no-dev
[ "$(< "$HTASK_SETUP_LOG")" = 'codegraph common' ]

# 选择 Label 不等于授权发布；普通模式仍执行专属 init，但不启动开发服务。
reset_logs
run --branch labels-normal --label editor --prompt hi
jq -se 'map(select(.[0:2] == ["agent","prompt"]))[0][3] | contains("[\"editor\"]") and (contains("交付要求：") | not)' "$HTASK_TEST_LOG" >/dev/null
: > "$HTASK_SETUP_LOG"
run_setup_in_worktree labels-normal
[ "$(< "$HTASK_SETUP_LOG")" = $'codegraph common\ncodegraph editor' ]

for forge in gitlab github; do
  git -C "$repo" remote set-url origin "git@$forge.example.com:org/demo.git"
  reset_logs
  run --branch "labels-submit-$forge" --label editor --label 'area::中文 空格' --mode submit --prompt hi
  jq -se 'map(select(.[0:2] == ["agent","prompt"]))[0][3] |
    contains("[\"editor\",\"area::中文 空格\"]") and contains("核对") and contains("不要新建") and contains("不要重复创建")' "$HTASK_TEST_LOG" >/dev/null
  : > "$HTASK_SETUP_LOG"
  run_setup_in_worktree "labels-submit-$forge"
  [ "$(< "$HTASK_SETUP_LOG")" = $'codegraph common\ncodegraph editor' ]
done
git -C "$repo" remote set-url origin 'git@gitlab-t.example.com:org/demo.git'

# 专属 init 失败，不派发任何 Dev；无论选择顺序都先完成所有 init。
cat > "$repo/.config/htask/config.toml" <<'TOML'
schema_version = 2
init = ['codegraph common']
[labels.editor]
init = ['false', 'codegraph unreachable']
dev = ['pnpm run editor']
[labels.c2v]
dev = ['pnpm run c2v']
TOML
reset_logs
run --branch label-init-fail --mode dev --label c2v --label editor --prompt hi
: > "$HTASK_SETUP_LOG"
if run_setup_in_worktree label-init-fail; then echo 'Label init 应失败' >&2; exit 1; fi
[ "$(< "$HTASK_SETUP_LOG")" = 'codegraph common' ]
[ "$(wc -l < "$HTASK_TEST_LOG")" -eq 5 ]

# 两个长期服务相互等待对方启动，验证不是串行运行；shell 特殊字符不破坏转义。
cat > "$repo/.config/htask/config.toml" <<'TOML'
schema_version = 2
[labels.editor]
dev = ['touch editor.ready; for i in {1..100}; do if [ -f c2v.ready ]; then exit 0; fi; sleep 0.05; done; exit 1']
[labels.c2v]
dev = ['touch c2v.ready; for i in {1..100}; do if [ -f editor.ready ]; then exit 0; fi; sleep 0.05; done; exit 1']
TOML
reset_logs
run --branch label-parallel --mode dev --label editor --label c2v --prompt hi
run_setup_in_worktree label-parallel

cat > "$repo/.config/htask/config.toml" <<'TOML'
schema_version = 2
[labels.editor]
dev = ['false', 'touch unreachable']
[labels.c2v]
dev = ['touch survived']
TOML
reset_logs
run --branch label-service-fail --mode dev --label editor --label c2v --prompt hi
if run_setup_in_worktree label-service-fail; then echo '服务应失败' >&2; exit 1; fi
[ -f "$HTASK_TEST_WORKTREES/label-service-fail/survived" ]
[ ! -f "$HTASK_TEST_WORKTREES/label-service-fail/unreachable" ]

# 派发一个 Dev tab 失败仍尝试其他组；协调 pane 返回失败，不谎称启动成功。
reset_logs
run --branch label-dispatch-fail --mode dev --label editor --label c2v --prompt hi
if HTASK_FAIL=tab run_setup_in_worktree label-dispatch-fail; then exit 1; fi
[ "$(jq -s 'map(select(.[0:2] == ["tab","create"])) | length' "$HTASK_TEST_LOG")" -eq 3 ]

# 缺参数、非法 schema/字段/类型/引用等均在建树前失败。
for bad in \
  'schema_version = 1' \
  $'schema_version = 2\n[dev_profiles]\nx = ["echo old"]' \
  $'schema_version = 2\n[iteration_prompts]\nmain = "old"' \
  $'schema_version = 2\nlabels = []' \
  $'schema_version = 2\n[labels.x]\ninit = [42]' \
  $'schema_version = 2\n[labels.x]\nunknown = []' \
  $'schema_version = 2\n[labels." "]' \
  $'schema_version = 2\n[iterations.main]\nlabels = ["missing"]' \
  $'schema_version = 2\n[iterations.main]\nlabels = "x"' \
  $'schema_version = 2\n[iterations.main]\nunknown = true'; do
  printf '%s\n' "$bad" > "$repo/.config/htask/config.toml"
  reset_logs
  assert_failure --branch invalid-config --prompt hi
done
cp "$tmp/labels.toml" "$repo/.config/htask/config.toml"
for section in labels iterations; do
  printf 'schema_version = 2\n[%s]\n' "$section" > "$XDG_CONFIG_HOME/htask/config.toml"
  reset_logs
  assert_failure --branch project-only --prompt hi
  grep -q '仅允许在项目配置' "$tmp/err"
done
rm "$XDG_CONFIG_HOME/htask/config.toml"
reset_logs
assert_failure --branch missing-label --prompt hi --label

# 交互：回车保留迭代默认、0 清空、逗号多选；错误序号必须重问。
for selection in default none multi; do
  reset_logs
  python3 - "$cli" "$repo" "$selection" <<'PY'
import os, pty, select, subprocess, sys, time
selection = sys.argv[3]
master, slave = pty.openpty()
p = subprocess.Popen(['bash', sys.argv[1], '--branch', 'label-tty-' + selection,
                      '--base', 'v6.1.0', '--mode', 'dev'], cwd=sys.argv[2],
                     stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
try:
    steps = [('仓库路径', '\n'), ('--bug', '\n'), ('--agent', '\n'),
             ('输入序号', '99\n'), ('输入序号', {'default': '\n', 'none': '0\n', 'multi': '1,2\n'}[selection]),
             ('--prompt', 'hi\n')]
    for expected, answer in steps:
        output = b''
        deadline = time.monotonic() + 10
        while expected.encode() not in output:
            remaining = deadline - time.monotonic()
            assert remaining > 0, output
            if select.select([master], [], [], remaining)[0]:
                output += os.read(master, 65536)
        os.write(master, answer.encode())
    assert p.wait(timeout=10) == 0
finally:
    if p.poll() is None:
        p.kill()
    os.close(master)
PY
  : > "$HTASK_SETUP_LOG"
  run_setup_in_worktree "label-tty-$selection"
  case "$selection" in
    default) [ "$(< "$HTASK_SETUP_LOG")" = $'codegraph common\ncodegraph c2v\npnpm run c2v' ] ;;
    none) [ "$(< "$HTASK_SETUP_LOG")" = $'codegraph common\npnpm run default' ] ;;
    multi) [ "$(grep -c '^pnpm run' "$HTASK_SETUP_LOG")" -eq 2 ] ;;
  esac
done

# 示例文件就是可校验的项目配置，而非过期的文档片段。
python3 "$script_dir/config.py" "$tmp/missing-global.toml" "$script_dir/config.example.toml" | jq -e '.labels.c2v and .iterations["v6.1.0"].labels == ["c2v"]' >/dev/null

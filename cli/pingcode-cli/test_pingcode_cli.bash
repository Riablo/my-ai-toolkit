#!/usr/bin/env bash
set -euo pipefail

CLI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pingcode-cli"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT
export TEST_DIR XDG_CONFIG_HOME="$TEST_DIR/config" MOCK_MODE=normal
CONFIG_FILE="$XDG_CONFIG_HOME/pingcode-cli/config.json"

curl() {
  local args=" $* " body status=200
  printf '%s\n' "${args//$'\n'/ }" >> "$TEST_DIR/requests.log"
  [[ "$MOCK_MODE" != network-failure ]] || return 7
  case "$args" in
    *'/v1/auth/token'*)
      [[ "$args" == *'grant_type=refresh_token'* ]] || return 98
      body='{"access_token":"new-access","refresh_token":"new-refresh","expires_in":3600}'
      ;;
    *'/v1/project/projects'*)
      body='{"total":2,"values":[{"id":"p1","name":"项目一","ignored":true},{"id":"p2","name":"项目二"}]}'
      case "$MOCK_MODE" in
        api-failure) status=403 ;;
        invalid-response) body='{}' ;;
      esac
      ;;
    *'--request PATCH'*'/v1/project/work_items/bug-1'*)
      [[ "$args" == *"\"state_id\":\"${EXPECTED_STATE_ID:-5f3a1c2fc2742c20e17dcbcd}\""* ]] || return 98
      body="$(jq -cn --arg name "${EXPECTED_STATE_NAME:-已修复}" \
        '{id:"bug-1",state:{name:$name},project:{id:"p1",name:"项目一"},extra:true}')"
      [[ "$MOCK_MODE" != patch-failure ]] || status=403
      ;;
    *'/v1/project/work_items'*)
      [[ "$args" == *'include_public_image_token=description'* ]] || return 98
      if [[ "$args" == *'identifier='* ]]; then
        case "$args" in
          *'identifier=P-1'*) body='{"total":1,"values":[{"id":"bug-1","identifier":"P-1","title":"第一个","html_url":"https://example.test/P-1","state":{"id":"s1","name":"新提交"},"description":"<p>one</p><img src=\"https://files.test/one.png\">","public_image_token":"single-token","project":{"id":"p1","name":"项目一"},"assignee":{"display_name":"陈峥"},"created_by":{"display_name":"朱文锦"},"is_archived":0,"is_deleted":0,"extra":true}]}' ;;
          *'identifier=P-ARCHIVED'*) body='{"total":1,"values":[{"id":"bug-archived","identifier":"P-ARCHIVED","is_archived":1}]}' ;;
          *'identifier=P-DELETED'*) body='{"total":1,"values":[{"id":"bug-deleted","identifier":"P-DELETED","is_deleted":1}]}' ;;
          *'identifier=P-UNKNOWN'*) body='{"total":0,"values":[]}' ;;
          *'identifier=P-MISMATCH'*) body='{"total":1,"values":[{"id":"bug-1","identifier":"P-1"}]}' ;;
          *'identifier=P-DUPLICATE'*) body='{"total":2,"values":[{"id":"bug-1","identifier":"P-DUPLICATE"},{"id":"bug-2","identifier":"P-DUPLICATE"}]}' ;;
          *) return 98 ;;
        esac
        case "$MOCK_MODE" in
          invalid-list) body='{}' ;;
          invalid-id) body='{"values":[{"id":"../bad","identifier":"P-1"}]}' ;;
          invalid-total) body='{"total":2,"values":[{"id":"bug-1","identifier":"P-1"}]}' ;;
        esac
        printf '%s\n200' "$body"
        return
      fi
      [[ "$args" == *'assignee_id=me'* && "$args" == *'type_id=bug'* ]] || return 98
      if [[ "$MOCK_MODE" == empty-bugs ]]; then
        printf '%s\n200' '{"total":0,"values":[]}'
        return
      fi
      case "$args" in
        *'project_id=p1'*'state_id=5f3a1c2fc2742c538a7dcbcb'*)
          body='{"total":4,"values":[{"id":"bug-1","identifier":"P-1","title":"第一个","html_url":"https://example.test/P-1","state":{"id":"s1","name":"新提交"},"project":{"name":"项目一"},"assignee":{"display_name":"陈峥"},"created_by":{"display_name":"朱文锦"},"description":"<p>one</p><img src=\"https://files.test/one.png\">","public_image_token":"list-token-1","created_at":101,"is_archived":0,"is_deleted":0,"extra":true},{"id":"old","identifier":"P-OLD","created_at":100},{"id":"archived","identifier":"P-ARCHIVED","created_at":102,"is_archived":1},{"id":"deleted","identifier":"P-DELETED","created_at":102,"is_deleted":1}]}'
          ;;
        *'project_id=p1'*'state_id=5f3a1c2fc2742c17f27dcbce'*)
          body='{"total":1,"values":[{"id":"bug-2","identifier":"P-2","state":{"name":"重新打开"},"project":{"name":"项目一"},"assignee":null,"description":"<img src=\"https://files.test/two.png?size=large\">","public_image_token":"list-token-2","created_at":102}]}'
          ;;
        *'project_id=p2'*'state_id=5f3a1c2fc2742c538a7dcbcb'*)
          body='{"total":1,"values":[{"id":"bug-3","identifier":"Q-1","state":{"name":"新提交"},"project":{"name":"项目二"},"created_at":103}]}'
          ;;
        *'project_id=p2'*'state_id=5f3a1c2fc2742c17f27dcbce'*) body='{"total":0,"values":[]}' ;;
        *'state_id=5f3a1c2fc2742c538a7dcbcb'*)
          [[ "$args" != *'project_id='* ]] || return 98
          body='{"total":2,"values":[{"id":"bug-1","identifier":"P-1","project":{"name":"项目一"},"created_at":101},{"id":"bug-3","identifier":"Q-1","project":{"name":"项目二"},"created_at":103}]}'
          ;;
        *'state_id=5f3a1c2fc2742c17f27dcbce'*)
          [[ "$args" != *'project_id='* ]] || return 98
          body='{"total":1,"values":[{"id":"bug-2","identifier":"P-2","project":{"name":"项目一"},"created_at":102}]}'
          ;;
        *) return 98 ;;
      esac
      ;;
    *'/v1/comments'*)
      [[ "$args" == *'principal_type=workitem'* && "$args" == *'page_index=0'* && "$args" == *'page_size=30'* ]] || return 98
      if [[ "$args" == *'principal_id=bug-1'* ]]; then
        body='{"total":100,"values":[{"id":"c1","content":"有稳定复现方法吗？","created_by":{"display_name":"陈峥","id":"u1"},"is_deleted":0,"attachments":[]},{"id":"c2","content":"还是没有显示","created_by":{"display_name":"朱文锦"},"is_reply_comment":1,"replied_comment":{"id":"c1"}},{"id":"c3","content":"已删除","is_deleted":1}]}'
      elif [[ "$args" == *'principal_id=bug-2'* || "$args" == *'principal_id=bug-3'* ]]; then
        body='{"values":[]}'
      else
        return 98
      fi
      case "$MOCK_MODE" in
        comments-failure) status=500 ;;
        invalid-response) body='{}' ;;
        empty-comments) body='{"values":[]}' ;;
        empty-response) body='' ;;
      esac
      ;;
    *) return 22 ;;
  esac
  printf '%s\n%s' "$body" "$status"
}
export -f curl

expect_failure() {
  if "$CLI" "$@" </dev/null > "$TEST_DIR/output" 2> "$TEST_DIR/error"; then
    printf '预期命令失败：%s\n' "$*" >&2
    exit 1
  fi
}

update_config() {
  jq "$@" "$CONFIG_FILE" > "$TEST_DIR/updated.json"
  cat "$TEST_DIR/updated.json" > "$CONFIG_FILE"
}

top_help="$("$CLI" -h)"
for command in config auth doctor projects bugs bug comments set-state; do
  command_help="$("$CLI" "$command" -h)"
  [ "$command_help" != "$top_help" ]
  [[ "$command_help" == *"pingcode-cli ${command}"* ]]
done
[[ "$("$CLI" config path)" == "$CONFIG_FILE" ]]
expect_failure config show
expect_failure doctor
[[ "$(<"$TEST_DIR/error")" == *'config init'* ]]
expect_failure init

printf 'client\nsecret\nme\ny\n100\n' | "$CLI" config init >/dev/null
permission="$(stat -c '%a' "$CONFIG_FILE" 2>/dev/null || stat -f '%Lp' "$CONFIG_FILE")"
[ "$permission" = 600 ]
update_config '.access_token = "old" | .refresh_token = "old-refresh" | .expires_in = 1 | .token_obtained_at = 0'
"$CLI" auth
jq -e '.access_token == "new-access" and .refresh_token == "new-refresh" and .expires_in == 3600' "$CONFIG_FILE" >/dev/null

shown="$("$CLI" config show)"
jq -e '.client_id == "client" and .client_secret == "***" and .access_token == "***" and .refresh_token == "***"' <<< "$shown" >/dev/null
[[ "$("$CLI" config)" == "$shown" ]]
TZ=Asia/Shanghai "$CLI" config set-created-after 2025-01-22
jq -e '.created_after == 1737475200 and .client_secret == "secret" and .access_token == "new-access"' "$CONFIG_FILE" >/dev/null
TZ=UTC "$CLI" config set-created-after 2025-01-22
jq -e '.created_after == 1737504000' "$CONFIG_FILE" >/dev/null
TZ=Asia/Shanghai "$CLI" config set-created-after 2024-02-29
cp "$CONFIG_FILE" "$TEST_DIR/before.json"
for invalid in 2025-1-22 2025-02-29 2025-02-30 2025-13-01 2025-00-01 '2025-01-22T00:00:00'; do
  expect_failure config set-created-after "$invalid"
  cmp "$CONFIG_FILE" "$TEST_DIR/before.json"
done
update_config '.created_after = 100 | .projects = [{id:"p1",name:"项目一",states:[{id:"obsolete",name:"旧状态"}]}]'

: > "$TEST_DIR/requests.log"
projects="$("$CLI" projects refresh)"
jq -e '. == [{id:"p1",name:"项目一"},{id:"p2",name:"项目二"}]' <<< "$projects" >/dev/null
jq -e 'all(.projects[]; has("states") | not)' "$CONFIG_FILE" >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 1 ]]

completion="$(zsh -fc '
  words=(pingcode-cli bugs --)
  CURRENT=3
  _arguments() { print -r -- "OPTIONS:${words[*]}:${CURRENT}:$*" }
  _describe() { : }
  source "$1"
  print -r -- "PROJECTS:$(_pingcode_projects)"
' zsh "$(dirname "$CLI")/_pingcode-cli")"
[[ "$completion" == *'OPTIONS:bugs --:2:'*'--project'* && "$completion" != *'--state'* ]]
[[ "$completion" == *'PROJECTS:项目一'*'项目二'* ]]
completion="$(zsh -fc '
  words=(pingcode-cli set-state bug-1 --state "")
  CURRENT=5
  _arguments() { print -r -- "$*" }
  source "$1"
' zsh "$(dirname "$CLI")/_pingcode-cli")"
[[ "$completion" == *'--state'*'(已拒绝 重新打开 已修复 新提交 挂起 已发布 处理中)'* ]]

: > "$TEST_DIR/requests.log"
bugs="$("$CLI" bugs --project 项目一)"
jq -e '
  map(.id) == ["bug-1", "bug-2"] and
  .[0].state == "新提交" and .[0].project == "项目一" and
  .[0].assignee == "陈峥" and .[0].created_by == "朱文锦" and
  .[1].state == "重新打开" and .[1].assignee == "" and .[1].created_by == "" and
  .[0].description == "<p>one</p><img src=\"https://files.test/one.png?access_token=list-token-1\">" and
  .[1].description == "<img src=\"https://files.test/two.png?size=large&access_token=list-token-2\">" and
  all(.[]; keys == ["assignee", "created_by", "description", "html_url", "id", "identifier", "project", "state", "title"])
' <<< "$bugs" >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 2 ]]
[[ "$(<"$TEST_DIR/requests.log")" != *'/v1/comments'* ]]
jq -e '
  .work_item_ids["P-1"].id == "bug-1" and .work_item_ids["P-2"].id == "bug-2" and
  .work_item_ids["P-OLD"].id == "old" and .work_item_ids["P-ARCHIVED"].id == "archived" and
  .work_item_ids["P-DELETED"].id == "deleted"
' "$CONFIG_FILE" >/dev/null
: > "$TEST_DIR/requests.log"
all_bugs="$("$CLI" bugs)"
jq -e 'map(.id) == ["bug-1","bug-2","bug-3"] and .[2].project == "项目二"' <<< "$all_bugs" >/dev/null
if [[ "$(wc -l < "$TEST_DIR/requests.log")" -ne 2 ]]; then
  printf 'FAIL: all-project bugs must use 2 state requests, not loop through projects\n' >&2
  exit 1
fi
[[ "$(<"$TEST_DIR/requests.log")" != *'project_id='* ]]
"$CLI" bugs --project=项目一 --created-after=101 | jq -e 'map(.id) == ["bug-2"]' >/dev/null
"$CLI" bugs --created-after 999 | jq -e '. == []' >/dev/null
jq -e '.work_item_ids["Q-1"].id == "bug-3"' "$CONFIG_FILE" >/dev/null
for identifier in P-2 Q-1; do
  : > "$TEST_DIR/requests.log"
  "$CLI" comments "$identifier" | jq -e '. == []' >/dev/null
  [[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 1 ]]
  [[ "$(<"$TEST_DIR/requests.log")" != *'/v1/project/work_items'* ]]
done
: > "$TEST_DIR/requests.log"
"$CLI" set-state P-1 --state 已修复 | jq -e '.id == "bug-1" and .state == "已修复"' >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 1 ]]
[[ "$(<"$TEST_DIR/requests.log")" == *'--request PATCH'* ]]
expect_failure bugs --state 新提交
expect_failure bugs --state=新提交
expect_failure bugs --project=
expect_failure bugs --created-after=bad
expect_failure bugs --project 不存在

: > "$TEST_DIR/requests.log"
comments="$("$CLI" comments P-1)"
jq -e '. == [{id:"c1",content:"有稳定复现方法吗？",created_by:"陈峥"},{id:"c2",content:"还是没有显示",created_by:"朱文锦"}]' <<< "$comments" >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 1 ]]
[[ "$(<"$TEST_DIR/requests.log")" != *'/v1/project/work_items'* ]]
# If the mapping is missing, the identifier list request repopulates it.
update_config 'del(.work_item_ids["P-1"])'
: > "$TEST_DIR/requests.log"
"$CLI" comments P-1 >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 2 ]]
[[ "$(grep -c 'identifier=P-1' "$TEST_DIR/requests.log")" -eq 1 ]]
jq -e '.work_item_ids["P-1"].id == "bug-1" and (.work_item_ids["P-1"].cached_at | type) == "number"' "$CONFIG_FILE" >/dev/null
: > "$TEST_DIR/requests.log"
"$CLI" comments P-1 | jq -e 'length == 2' >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 1 ]]
# A mapping just under seven days old is still usable. Cache hits must not prune;
# the next write removes expired, future-dated and malformed entries.
update_config --argjson now "$EPOCHSECONDS" '
  .work_item_ids["P-VALID"] = {id:"bug-1",cached_at:($now - 604800 + 120)} |
  .work_item_ids["P-OLD"] = {id:"bug-old",cached_at:($now - 604800 - 120)} |
  .work_item_ids["P-FUTURE"] = {id:"bug-future",cached_at:($now + 120)} |
  .work_item_ids["P-BAD"] = "invalid"
'
cp "$CONFIG_FILE" "$TEST_DIR/before-cache-hit.json"
: > "$TEST_DIR/requests.log"
"$CLI" comments P-VALID | jq -e 'length == 2' >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 1 ]]
cmp "$CONFIG_FILE" "$TEST_DIR/before-cache-hit.json"
: > "$TEST_DIR/requests.log"
bug="$("$CLI" bug P-1)"
jq -e --argjson comments "$comments" '
  .id == "bug-1" and .state == "新提交" and .project == "项目一" and
  .assignee == "陈峥" and .created_by == "朱文锦" and .comments == $comments and
  .description == "<p>one</p><img src=\"https://files.test/one.png?access_token=single-token\">" and
  keys == ["assignee","comments","created_by","description","html_url","id","identifier","project","state","title"]
' <<< "$bug" >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 2 ]]
[[ "$(grep -c 'identifier=P-1' "$TEST_DIR/requests.log")" -eq 1 ]]
jq -e '.work_item_ids | (has("P-VALID") and has("P-1") and (has("P-OLD") | not) and (has("P-FUTURE") | not) and (has("P-BAD") | not))' "$CONFIG_FILE" >/dev/null
[[ "$(stat -c '%a' "$CONFIG_FILE" 2>/dev/null || stat -f '%Lp' "$CONFIG_FILE")" = 600 ]]
for id in P-ARCHIVED P-DELETED; do
  : > "$TEST_DIR/requests.log"
  [[ "$("$CLI" bug "$id")" == null ]]
  [[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 1 ]]
done
MOCK_MODE=empty-comments "$CLI" comments P-1 | jq -e '. == []' >/dev/null
MOCK_MODE=empty-comments "$CLI" bug P-1 | jq -e '.comments == []' >/dev/null
MOCK_MODE=invalid-response expect_failure comments P-1
MOCK_MODE=empty-response expect_failure comments P-1
MOCK_MODE=comments-failure expect_failure bug P-1
[[ ! -s "$TEST_DIR/output" ]]
for identifier in P-UNKNOWN P-MISMATCH P-DUPLICATE; do
  : > "$TEST_DIR/requests.log"
  expect_failure bug "$identifier"
  expect_failure comments "$identifier"
  expect_failure set-state "$identifier" --state 已修复
  [[ "$(grep -c 'identifier=' "$TEST_DIR/requests.log")" -eq 3 ]]
  [[ "$(<"$TEST_DIR/requests.log")" != *'--request PATCH'* ]]
done
MOCK_MODE=invalid-list expect_failure bug P-1
MOCK_MODE=invalid-id expect_failure bug P-1
MOCK_MODE=invalid-total expect_failure bug P-1
expect_failure comments '../bad'
expect_failure comments

# A valid cache mapping skips the lookup; an expired one is refreshed before PATCH.
cp "$CONFIG_FILE" "$TEST_DIR/before.json"
while read -r state_name state_id; do
  : > "$TEST_DIR/requests.log"
  updated="$(EXPECTED_STATE_ID="$state_id" EXPECTED_STATE_NAME="$state_name" "$CLI" set-state P-1 --state "$state_name")"
  jq -e --arg name "$state_name" '.id == "bug-1" and .state == $name and (has("extra") | not)' <<< "$updated" >/dev/null
  [[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 1 ]]
  [[ "$(<"$TEST_DIR/requests.log")" == *'--request PATCH'* ]]
done <<'STATES'
已拒绝 5f3a1c2fc2742c0e3b7dcbd0
重新打开 5f3a1c2fc2742c17f27dcbce
已修复 5f3a1c2fc2742c20e17dcbcd
新提交 5f3a1c2fc2742c538a7dcbcb
挂起 5f3a1c2fc2742c5fc47dcbd1
已发布 5f3a1c2fc2742cacfb7dcbcf
处理中 5f3a1c2fc2742cef1d7dcbcc
STATES
"$CLI" set-state P-1 --state=已修复 | jq -e '.state == "已修复"' >/dev/null
cmp "$CONFIG_FILE" "$TEST_DIR/before.json"
update_config '.work_item_ids["P-1"].cached_at = 0'
: > "$TEST_DIR/requests.log"
"$CLI" set-state P-1 --state 已修复 | jq -e '.state == "已修复"' >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 2 ]]
[[ "$(grep -c 'identifier=P-1' "$TEST_DIR/requests.log")" -eq 1 ]]
update_config '.work_item_ids["P-1"].cached_at = 0'
: > "$TEST_DIR/requests.log"
"$CLI" comments P-1 >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 2 ]]
update_config '.work_item_ids["P-1"].id = "../bad"'
: > "$TEST_DIR/requests.log"
"$CLI" comments P-1 >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 2 ]]
jq -e '.work_item_ids["P-1"].id == "bug-1" and all(.projects[]; has("states") | not)' "$CONFIG_FILE" >/dev/null
update_config '.work_item_ids = "invalid-cache"'
: > "$TEST_DIR/requests.log"
"$CLI" comments P-1 >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 2 ]]
jq -e '.work_item_ids["P-1"].id == "bug-1"' "$CONFIG_FILE" >/dev/null

# Invalid menu entries re-prompt; only the eventual selection sends a request.
: > "$TEST_DIR/requests.log"
updated="$(printf 'bad\n0\n8\n9\n3\n' | "$CLI" set-state P-1 2> "$TEST_DIR/menu")"
jq -e '.state == "已修复"' <<< "$updated" >/dev/null
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 1 ]]
[[ "$(<"$TEST_DIR/menu")" == *'请输入 1–7'* ]]
[[ "$(head -n 7 "$TEST_DIR/menu")" == $'1) 已拒绝\n2) 重新打开\n3) 已修复\n4) 新提交\n5) 挂起\n6) 已发布\n7) 处理中' ]]
: > "$TEST_DIR/requests.log"
printf '\n' | "$CLI" set-state P-1 > "$TEST_DIR/output" 2> "$TEST_DIR/menu"
[[ ! -s "$TEST_DIR/output" && ! -s "$TEST_DIR/requests.log" ]]
[[ "$(<"$TEST_DIR/menu")" == *'回车取消'* && "$(<"$TEST_DIR/menu")" != *'8)'* ]]
expect_failure set-state P-1
expect_failure set-state
expect_failure set-state '../bad' --state 已修复
expect_failure set-state P-1 --state 不存在
[[ "$(<"$TEST_DIR/error")" == *'不支持的状态'* ]]
expect_failure set-state P-1 --state
expect_failure set-state P-1 --state=
expect_failure set-state P-1 --state 已修复 --state 挂起
expect_failure set-state P-1 --unknown
expect_failure set-state P-1 已修复
[[ ! -s "$TEST_DIR/requests.log" ]]
MOCK_MODE=patch-failure expect_failure set-state P-1 --state 已修复
[[ "$(<"$TEST_DIR/error")" == *'HTTP 403'* && ! -s "$TEST_DIR/output" ]]
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 1 ]]

# doctor is read-only even when its API probe fails or the token is expired.
cp "$CONFIG_FILE" "$TEST_DIR/before.json"
"$CLI" doctor > "$TEST_DIR/doctor"
[[ "$(<"$TEST_DIR/doctor")" == *'OK: API'* ]]
for mode in api-failure invalid-response network-failure; do
  MOCK_MODE="$mode" expect_failure doctor
  cmp "$CONFIG_FILE" "$TEST_DIR/before.json"
done
chmod 644 "$CONFIG_FILE"
expect_failure doctor
[[ "$(<"$TEST_DIR/error")" == *'配置权限'* ]]
chmod 600 "$CONFIG_FILE"
update_config '.token_obtained_at = 0'
cp "$CONFIG_FILE" "$TEST_DIR/before.json"
: > "$TEST_DIR/requests.log"
expect_failure doctor
[[ "$(<"$TEST_DIR/error")" == *'access_token 缺失或已过期'* ]]
[[ ! -s "$TEST_DIR/requests.log" ]]
cmp "$CONFIG_FILE" "$TEST_DIR/before.json"
update_config '.projects_refreshed_at = null'
expect_failure doctor
[[ "$(<"$TEST_DIR/error")" == *'项目缓存不存在或不完整'* ]]
update_config '.access_token = {}'
expect_failure doctor
[[ "$(<"$TEST_DIR/error")" == *'令牌字段格式无效'* ]]

# Global queries do not depend on a populated or refreshed project cache.
update_config --argjson now "$EPOCHSECONDS" '.access_token = "new-access" | .token_obtained_at = $now | .projects = [] | .projects_refreshed_at = null'
: > "$TEST_DIR/requests.log"
[[ "$(MOCK_MODE=empty-bugs "$CLI" bugs)" == '[]' ]]
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 2 ]]
[[ "$(<"$TEST_DIR/requests.log")" != *'/v1/project/projects'* ]]
printf 'pingcode-cli tests passed\n'

#!/usr/bin/env bash
set -euo pipefail

CLI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pingcode-cli"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT
export XDG_CONFIG_HOME="$TEST_DIR/config"

curl() {
  local args=" $* " body
  case "$args" in
    *'/v1/auth/token'*)
      [[ "$args" == *'grant_type=refresh_token'* ]]
      body='{"access_token":"new-access","refresh_token":"new-refresh","expires_in":3600}'
      ;;
    *'/v1/project/projects'*)
      body='{"page_size":100,"page_index":0,"total":1,"values":[{"id":"p1","name":"项目一","ignored":true}]}'
      ;;
    *'/v1/project/work_item/states'*)
      body='{"total":2,"values":[{"id":"s1","name":"新提交","color":"#fff"},{"id":"s2","name":"已修复","color":"#000"}]}'
      ;;
    *'--request PATCH'*'/v1/project/work_items/bug-1'*)
      [[ "$args" == *'"state_id":"s2"'* ]]
      body='{"id":"bug-1","identifier":"P-1","title":"修复后","html_url":"https://example.test/P-1","state":{"id":"s2","name":"已修复"},"description":"done","project":{"id":"p1"},"extra":true}'
      ;;
    *'/v1/project/work_items/bug-1'*)
      [[ "$args" == *'include_public_image_token=description'* ]]
      body='{"id":"bug-1","identifier":"P-1","title":"第一个","html_url":"https://example.test/P-1","state":{"id":"s1","name":"新提交"},"description":"<p>one</p><img src=\"https://files.test/one.png\">","public_image_token":"single-token","project":{"id":"p1"},"extra":true}'
      ;;
    *'/v1/project/work_items'*'state_id=s1'*)
      [[ "$args" == *'project_id=p1'* && "$args" == *'assignee_id=me'* && "$args" == *'type_id=bug'* && "$args" == *'include_public_image_token=description'* ]]
      body='{"total":1,"values":[{"id":"bug-1","identifier":"P-1","title":"第一个","html_url":"https://example.test/P-1","state":{"id":"s1","name":"新提交"},"description":"<p>one</p><img src=\"https://files.test/one.png\">","public_image_token":"list-token-1","created_at":101,"extra":true}]}'
      ;;
    *'/v1/project/work_items'*'state_id=s2'*)
      [[ "$args" == *'include_public_image_token=description'* ]]
      body='{"total":2,"values":[{"id":"bug-2","identifier":"P-2","title":"第二个","html_url":"https://example.test/P-2","state":{"id":"s2","name":"已修复"},"description":"<img src=\"https://files.test/two.png?size=large\">","public_image_token":"list-token-2","created_at":102},{"id":"bug-old","identifier":"P-0","title":"旧 bug","created_at":100}]}'
      ;;
    *) return 22 ;;
  esac
  printf '%s\n200' "$body"
}
export -f curl

top_help="$("$CLI" -h)"
for command in init auth projects bugs bug set-state; do
  command_help="$("$CLI" "$command" -h)"
  [ "$command_help" != "$top_help" ]
  [[ "$command_help" == *"pingcode-cli ${command}"* ]]
done

printf 'client\nsecret\nme\ny\n100\n' | "$CLI" init >/dev/null
CONFIG_FILE="$XDG_CONFIG_HOME/pingcode-cli/config.json"
permission="$(stat -f '%Lp' "$CONFIG_FILE" 2>/dev/null || stat -c '%a' "$CONFIG_FILE")"
[ "$permission" = "600" ]

tmp="$(mktemp "$TEST_DIR/config.XXXXXX")"
jq '.access_token = "old" | .refresh_token = "old-refresh" | .expires_in = 1 | .token_obtained_at = 0' "$CONFIG_FILE" > "$tmp"
mv "$tmp" "$CONFIG_FILE"
"$CLI" auth
jq -e '.access_token == "new-access" and .refresh_token == "new-refresh" and .expires_in == 3600' "$CONFIG_FILE" >/dev/null

projects="$("$CLI" projects refresh)"
jq -e '.[0] == {id:"p1", name:"项目一", states:[{id:"s1", name:"新提交"}, {id:"s2", name:"已修复"}]}' <<< "$projects" >/dev/null

completion="$(zsh -fc '
  words=(pingcode-cli bugs --)
  CURRENT=3
  _arguments() { print -r -- "OPTIONS:${words[*]}:${CURRENT}:$*" }
  _describe() { : }
  source "$1"
  words=(pingcode-cli bugs --project 项目一 --state "")
  print -r -- "PROJECTS:$(_pingcode_projects)"
  print -r -- "STATES:$(_pingcode_states)"
' zsh "$(dirname "$CLI")/_pingcode-cli")"
[[ "$completion" == *'OPTIONS:bugs --:2:'*'--project'*'--state'* ]]
[[ "$completion" == *'PROJECTS:项目一'* ]]
[[ "$completion" == *'STATES:'*'新提交'* ]]
[[ "$completion" == *'STATES:'*'已修复'* ]]

bugs="$("$CLI" bugs --project 项目一 --state 新提交 --state 已修复)"
jq -e '
  length == 2 and
  (map(.id) == ["bug-1", "bug-2"]) and
  .[0].description == "<p>one</p><img src=\"https://files.test/one.png?access_token=list-token-1\">" and
  .[1].description == "<img src=\"https://files.test/two.png?size=large&access_token=list-token-2\">" and
  all(.[]; (keys | sort) == ["description", "html_url", "id", "identifier", "state", "title"])
' <<< "$bugs" >/dev/null

bug="$("$CLI" bug bug-1)"
jq -e '
  .id == "bug-1" and
  .description == "<p>one</p><img src=\"https://files.test/one.png?access_token=single-token\">" and
  (has("extra") | not)
' <<< "$bug" >/dev/null

updated="$("$CLI" set-state bug-1 已修复)"
jq -e '.id == "bug-1" and .state.name == "已修复" and (has("extra") | not)' <<< "$updated" >/dev/null

printf 'pingcode-cli tests passed\n'

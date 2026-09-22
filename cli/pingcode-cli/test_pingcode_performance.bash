#!/usr/bin/env bash
set -euo pipefail

CLI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pingcode-cli"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT
export TEST_DIR XDG_CONFIG_HOME="$TEST_DIR/config"
mkdir -p "$XDG_CONFIG_HOME/pingcode-cli"
CONFIG_FILE="$XDG_CONFIG_HOME/pingcode-cli/config.json"

write_fixture_config() {
  command jq -n --argjson now "$EPOCHSECONDS" '{
    client_id:"dummy", client_secret:"dummy", my_assignee_id:"me", created_after:null,
    access_token:"old", refresh_token:"refresh", expires_in:3600, token_obtained_at:$now,
    projects_refreshed_at:$now,
    projects:[{id:"p1",name:"项目一"}]
  }' > "$CONFIG_FILE"
}

jq() {
  printf 'jq\n' >> "$TEST_DIR/jq.log"
  if [[ "$TEST_MODE" == filtered && "$*" == *'def add_image_access_token:'* ]]; then
    cat > "$TEST_DIR/image-input.json"
    command jq 'length' "$TEST_DIR/image-input.json" > "$TEST_DIR/image-count"
    command jq "$@" "$TEST_DIR/image-input.json"
    return
  fi
  command jq "$@"
}

curl() {
  local args=" $* " part page=0
  for part in "$@"; do
    case "$part" in page_index=*) page="${part#*=}";; esac
  done
  if [[ "$args" == *'/v1/auth/token'* ]]; then
    printf 'refresh\n' >> "$TEST_DIR/refresh.log"
    printf '%s\n200' '{"access_token":"new","refresh_token":"refresh-new","expires_in":3600}'
  elif [[ "$TEST_MODE" == refresh && "$args" == *'/v1/project/work_items'* ]]; then
    printf 'request\n' >> "$TEST_DIR/requests.log"
    if [[ "$args" == *'Authorization: Bearer old'* ]]; then
      printf '{}\n401'
    else
      [[ "$args" == *'Authorization: Bearer new'* ]] || return 98
      printf '%s\n200' '{"total":0,"values":[]}'
    fi
  elif [[ "$args" == *'/v1/project/work_items'* ]]; then
    printf '%s\n' "$page" >> "$TEST_DIR/pages.log"
    if [[ "$TEST_MODE" == filtered ]]; then
      if [[ "$args" == *'state_id=5f3a1c2fc2742c538a7dcbcb'* ]]; then
        printf '%s\n200' '{"total":4,"values":[
          {"id":"keep","created_at":101,"description":"<img src=\"https://files.test/a.png\">","public_image_token":"token"},
          {"id":"old","created_at":100,"description":"<img src=\"https://files.test/a.png\">","public_image_token":"token"},
          {"id":"archived","created_at":101,"is_archived":1,"description":"<img src=\"https://files.test/a.png\">","public_image_token":"token"},
          {"id":"deleted","created_at":101,"is_deleted":1,"description":"<img src=\"https://files.test/a.png\">","public_image_token":"token"}
        ]}'
      else
        printf '%s\n200' '{"total":0,"values":[]}'
      fi
      return
    fi
    if [[ "$args" == *'state_id=5f3a1c2fc2742c17f27dcbce'* ]]; then page=$((page + 5)); fi
    if [[ "$TEST_MODE" == stalled ]]; then page=0; fi
    printf '%s\n200' "$(<"$TEST_DIR/page-$page.json")"
  else
    return 22
  fi
}
export -f curl jq

write_fixture_config
for (( page=0; page<10; page++ )); do
  command jq -n --argjson page "$page" '{total:500,values:[
    range($page * 100; ($page + 1) * 100) |
    {id:("b" + tostring),identifier:("B-" + tostring),description:("x" * 2000),created_at:100}
  ]}' > "$TEST_DIR/page-$page.json"
done
export TEST_MODE=large
"$CLI" bugs --project 项目一 > "$TEST_DIR/bugs.json"
command jq -e 'length == 1000 and all(.[]; (.description | length) == 2000)' "$TEST_DIR/bugs.json" >/dev/null
[[ "$(wc -l < "$TEST_DIR/pages.log")" -eq 10 ]]
# Bound external JSON parsing independently of data volume: old code used 160+
# jq processes here, including 100 repeated config/token parses.
jq_count="$(wc -l < "$TEST_DIR/jq.log")"
[[ "$jq_count" -lt 40 ]]
printf 'ok: 10 pages / 1000 large items, %d jq calls\n' "$jq_count"

export TEST_MODE=filtered
"$CLI" bugs --project 项目一 --created-after 100 > "$TEST_DIR/filtered.json"
command jq -e 'map(.id) == ["keep"] and .[0].description == "<img src=\"https://files.test/a.png?access_token=token\">"' "$TEST_DIR/filtered.json" >/dev/null
if [[ "$(<"$TEST_DIR/image-count")" -ne 1 ]]; then
  printf 'FAIL: image processing received %s bugs; expected only the 1 retained bug\n' "$(<"$TEST_DIR/image-count")" >&2
  exit 1
fi
printf 'ok: image processing runs only after filtering\n'

export TEST_MODE=stalled
: > "$TEST_DIR/pages.log"
if "$CLI" bugs --project 项目一 > /dev/null 2> "$TEST_DIR/error"; then
  printf 'expected duplicate-page failure\n' >&2; exit 1
fi
[[ "$(wc -l < "$TEST_DIR/pages.log")" -eq 2 ]]
[[ "$(<"$TEST_DIR/error")" == *'分页没有前进'* ]]

# A 401 while fetching the first state must update the shared token snapshot
# used by the next state's request.
export TEST_MODE=refresh
write_fixture_config
"$CLI" bugs --project 项目一 > "$TEST_DIR/refreshed-bugs.json"
[[ "$(wc -l < "$TEST_DIR/refresh.log")" -eq 1 ]]
[[ "$(wc -l < "$TEST_DIR/requests.log")" -eq 3 ]]
command jq -e '. == []' "$TEST_DIR/refreshed-bugs.json" >/dev/null

# Top-level completion must not parse config. Parameter callbacks remain usable
# after _arguments shifts the command word out of the array.
zsh -fc '
  jq() { print jq >> "$TEST_DIR/completion.log"; command jq "$@"; }
  _describe() { :; }
  _arguments() { :; }
  words=(pingcode-cli "")
  CURRENT=2
  source "$1"
  [[ ! -e "$TEST_DIR/completion.log" ]]
  words=(bugs --project "")
  [[ "$(_pingcode_projects)" == 项目一 ]]
' zsh "$(dirname "$CLI")/_pingcode-cli"

# Validation still runs on every CLI invocation, including cache-only queries.
command jq '.client_secret = ""' "$CONFIG_FILE" > "$TEST_DIR/invalid.json"
mv "$TEST_DIR/invalid.json" "$CONFIG_FILE"
if "$CLI" projects > /dev/null 2> "$TEST_DIR/error"; then
  printf 'expected missing-config-field failure\n' >&2; exit 1
fi
[[ "$(<"$TEST_DIR/error")" == *'client_secret'* ]]
printf 'ok: large pagination, stalled pages, shared token refresh and lazy completion\n'

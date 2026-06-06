#!/usr/bin/env bash
set -euo pipefail

# ─── 安装脚本 ────────────────────────────────────────────────────
# 将 cli/ 下所有工具软链接到 ~/.local/bin/，并按当前 shell 安装补全。
# 默认会更新当前 shell 的 rc 文件；如需只安装文件，可传 --no-rc。
# 使用方式：bash scripts/install.sh
# ─────────────────────────────────────────────────────────────────

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
DIM='\033[2m'
RED='\033[0;31m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLI_DIR="$PROJECT_ROOT/cli"
BIN_DIR="${HOME}/.local/bin"
ZSH_COMP_DIR="${HOME}/.zsh/completions"
FISH_COMP_DIR="${HOME}/.config/fish/completions"
SHELL_MODE="auto"
UPDATE_RC=1
ZSH_RC_MODE="auto"
ZSH_START_MARKER="# >>> my-ai-toolkit >>>"
ZSH_END_MARKER="# <<< my-ai-toolkit <<<"

usage() {
  cat <<EOF
my-ai-toolkit installer

用法:
  bash scripts/install.sh [选项]

选项:
  --shell auto|zsh|fish|all   选择安装哪种 shell 的补全，默认 auto
  --bin-dir <path>            CLI 软链接目录，默认 ~/.local/bin
  --zsh-completion-dir <path> zsh 补全目录，默认 ~/.zsh/completions
  --fish-completion-dir <path> fish 补全目录，默认 ~/.config/fish/completions
  --zsh-rc-mode <mode>       zsh 配置模式：auto、standalone 或 integrated，默认 auto
  --no-rc                     不更新 ~/.zshrc 或 ~/.config/fish/config.fish
  -h, --help                  显示帮助

示例:
  bash scripts/install.sh
  bash scripts/install.sh --shell zsh
  bash scripts/install.sh --shell zsh --zsh-rc-mode integrated
  bash scripts/install.sh --shell all --no-rc
EOF
}

die() {
  echo -e "${RED}错误：$1${RESET}" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --shell)
      [ "$#" -ge 2 ] || die "--shell 需要参数"
      SHELL_MODE="$2"
      shift 2
      ;;
    --bin-dir)
      [ "$#" -ge 2 ] || die "--bin-dir 需要参数"
      BIN_DIR="$2"
      shift 2
      ;;
    --zsh-completion-dir)
      [ "$#" -ge 2 ] || die "--zsh-completion-dir 需要参数"
      ZSH_COMP_DIR="$2"
      shift 2
      ;;
    --fish-completion-dir)
      [ "$#" -ge 2 ] || die "--fish-completion-dir 需要参数"
      FISH_COMP_DIR="$2"
      shift 2
      ;;
    --zsh-rc-mode)
      [ "$#" -ge 2 ] || die "--zsh-rc-mode 需要参数"
      ZSH_RC_MODE="$2"
      shift 2
      ;;
    --no-rc)
      UPDATE_RC=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "未知选项：$1。使用 --help 查看帮助。"
      ;;
  esac
done

case "$SHELL_MODE" in
  auto|zsh|fish|all) ;;
  *) die "--shell 只支持 auto、zsh、fish、all" ;;
esac

case "$ZSH_RC_MODE" in
  auto|standalone|integrated) ;;
  *) die "--zsh-rc-mode 只支持 auto、standalone 或 integrated" ;;
esac

dedupe_words() {
  local result=()
  local item existing seen
  for item in "$@"; do
    seen=0
    for existing in "${result[@]}"; do
      if [ "$existing" = "$item" ]; then
        seen=1
        break
      fi
    done
    if [ "$seen" -eq 0 ]; then
      result+=("$item")
    fi
  done
  printf '%s\n' "${result[@]}"
}

detect_primary_shell() {
  local shell_name=""

  case "${MY_AI_TOOLKIT_SHELL:-}" in
    zsh|fish)
      printf '%s\n' "$MY_AI_TOOLKIT_SHELL"
      return
      ;;
  esac

  shell_name="$(ps -p "$$" -o comm= 2>/dev/null | awk '{print $1}' | xargs basename 2>/dev/null || true)"
  case "$shell_name" in
    zsh|fish)
      printf '%s\n' "$shell_name"
      return
      ;;
  esac

  shell_name="$(ps -p "${PPID:-0}" -o comm= 2>/dev/null | awk '{print $1}' | xargs basename 2>/dev/null || true)"
  case "$shell_name" in
    zsh|fish)
      printf '%s\n' "$shell_name"
      return
      ;;
  esac

  if [ -n "${SHELL:-}" ]; then
    shell_name="$(basename "$SHELL")"
  fi

  case "$shell_name" in
    zsh)
      printf 'zsh\n'
      ;;
    *)
      if [ -f "${ZDOTDIR:-$HOME}/.zshrc" ] || [ -d "${HOME}/.zsh" ]; then
        printf 'zsh\n'
      elif [ "$shell_name" = "fish" ]; then
        printf 'fish\n'
      elif command -v zsh >/dev/null 2>&1; then
        printf 'zsh\n'
      elif command -v fish >/dev/null 2>&1; then
        printf 'fish\n'
      else
        printf 'zsh\n'
      fi
      ;;
  esac
}

primary_shell="$(detect_primary_shell)"
completion_shells=()
rc_shells=()

case "$SHELL_MODE" in
  auto)
    completion_shells+=("$primary_shell")
    rc_shells+=("$primary_shell")
    if [ "$primary_shell" != "fish" ] && [ -d "${HOME}/.config/fish" ]; then
      completion_shells+=("fish")
    fi
    ;;
  zsh|fish)
    completion_shells+=("$SHELL_MODE")
    rc_shells+=("$SHELL_MODE")
    ;;
  all)
    completion_shells+=("zsh" "fish")
    rc_shells+=("zsh" "fish")
    ;;
esac

deduped_completion_shells=()
while IFS= read -r shell_name; do
  [ -n "$shell_name" ] && deduped_completion_shells+=("$shell_name")
done < <(dedupe_words "${completion_shells[@]}")
completion_shells=("${deduped_completion_shells[@]}")

deduped_rc_shells=()
while IFS= read -r shell_name; do
  [ -n "$shell_name" ] && deduped_rc_shells+=("$shell_name")
done < <(dedupe_words "${rc_shells[@]}")
rc_shells=("${deduped_rc_shells[@]}")

has_shell() {
  local needle="$1"
  local shell_name
  for shell_name in "${completion_shells[@]}"; do
    [ "$shell_name" = "$needle" ] && return 0
  done
  return 1
}

has_rc_shell() {
  local needle="$1"
  local shell_name
  for shell_name in "${rc_shells[@]}"; do
    [ "$shell_name" = "$needle" ] && return 0
  done
  return 1
}

install_symlink() {
  local source="$1"
  local target="$2"
  local label="$3"

  if [ -L "$target" ]; then
    local existing
    existing="$(readlink "$target")"
    if [ "$existing" = "$source" ]; then
      echo -e "  ${DIM}$label — 已是最新${RESET}"
      return 0
    fi
    echo -e "  ${YELLOW}$label — 已存在链接到 ${existing}，覆盖${RESET}"
    rm "$target"
  elif [ -e "$target" ]; then
    echo -e "  ${YELLOW}$label — $target 已存在且不是软链接，跳过${RESET}"
    return 1
  fi

  ln -s "$source" "$target"
  echo -e "  ${GREEN}$label — 已安装${RESET}"
  return 0
}

has_managed_block() {
  local target="$1"
  local start_marker="$2"
  local end_marker="$3"

  [ -f "$target" ] && grep -Fxq "$start_marker" "$target" && grep -Fxq "$end_marker" "$target"
}

replace_managed_block_in_place() {
  local target="$1"
  local start_marker="$2"
  local end_marker="$3"
  local block="$4"
  local block_file
  local tmp

  block_file="$(mktemp "${target}.block.XXXXXX")"
  tmp="$(mktemp "${target}.tmp.XXXXXX")"
  printf '%s\n' "$block" > "$block_file"

  awk -v start="$start_marker" -v end="$end_marker" -v block_file="$block_file" '
    $0 == start {
      print start
      while ((getline line < block_file) > 0) {
        print line
      }
      close(block_file)
      print end
      skip = 1
      next
    }
    $0 == end {
      skip = 0
      next
    }
    skip != 1 { print }
  ' "$target" > "$tmp"

  rm "$block_file"
  mv "$tmp" "$target"
}

write_managed_block() {
  local target="$1"
  local start_marker="$2"
  local end_marker="$3"
  local block="$4"
  local tmp

  mkdir -p "$(dirname "$target")"
  touch "$target"

  if has_managed_block "$target" "$start_marker" "$end_marker"; then
    replace_managed_block_in_place "$target" "$start_marker" "$end_marker" "$block"
    return
  fi

  tmp="$(mktemp "${target}.tmp.XXXXXX")"

  awk -v start="$start_marker" -v end="$end_marker" '
    $0 == start { skip = 1; next }
    $0 == end { skip = 0; next }
    skip != 1 { print }
  ' "$target" > "$tmp"

  {
    printf '\n%s\n' "$start_marker"
    printf '%s\n' "$block"
    printf '%s\n' "$end_marker"
  } >> "$tmp"

  mv "$tmp" "$target"
}

write_managed_block_at_start() {
  local target="$1"
  local start_marker="$2"
  local end_marker="$3"
  local block="$4"
  local stripped
  local tmp

  mkdir -p "$(dirname "$target")"
  touch "$target"

  if has_managed_block "$target" "$start_marker" "$end_marker"; then
    replace_managed_block_in_place "$target" "$start_marker" "$end_marker" "$block"
    return
  fi

  stripped="$(mktemp "${target}.stripped.XXXXXX")"
  tmp="$(mktemp "${target}.tmp.XXXXXX")"

  awk -v start="$start_marker" -v end="$end_marker" '
    $0 == start { skip = 1; next }
    $0 == end { skip = 0; next }
    skip != 1 { print }
  ' "$target" > "$stripped"

  {
    printf '%s\n' "$start_marker"
    printf '%s\n' "$block"
    printf '%s\n\n' "$end_marker"
    awk 'NR == 1 && $0 == "" { next } { print }' "$stripped"
  } > "$tmp"

  rm "$stripped"
  mv "$tmp" "$target"
}

detect_existing_zsh_rc_mode() {
  local target="$1"
  local block

  if [ ! -f "$target" ] || ! grep -Fxq "$ZSH_START_MARKER" "$target" || ! grep -Fxq "$ZSH_END_MARKER" "$target"; then
    printf 'standalone\n'
    return
  fi

  block="$(awk -v start="$ZSH_START_MARKER" -v end="$ZSH_END_MARKER" '
    $0 == start { in_block = 1; next }
    $0 == end { exit }
    in_block == 1 { print }
  ' "$target")"

  case "$block" in
    *"(integrated)"*)
      printf 'integrated\n'
      ;;
    *"(standalone)"*)
      printf 'standalone\n'
      ;;
    *compinit*)
      printf 'standalone\n'
      ;;
    *)
      printf 'integrated\n'
      ;;
  esac
}

ZSH_RC_EFFECTIVE_MODE="$ZSH_RC_MODE"
if [ "$ZSH_RC_MODE" = "auto" ]; then
  ZSH_RC_EFFECTIVE_MODE="$(detect_existing_zsh_rc_mode "${HOME}/.zshrc")"
fi

mkdir -p "$BIN_DIR"

echo -e "${BOLD}安装 CLI 工具到 $BIN_DIR${RESET}"
echo ""

installed=0

for tool_dir in "$CLI_DIR"/*/; do
  [ -d "$tool_dir" ] || continue
  tool_dir="${tool_dir%/}"
  tool_name="$(basename "$tool_dir")"
  tool_bin="$tool_dir/$tool_name"
  [ -f "$tool_bin" ] || continue

  chmod +x "$tool_bin"
  if install_symlink "$tool_bin" "$BIN_DIR/$tool_name" "$tool_name"; then
    installed=$((installed + 1))
  fi
done

zsh_installed=0
fish_installed=0

if has_shell zsh; then
  mkdir -p "$ZSH_COMP_DIR"
  echo ""
  echo -e "${BOLD}安装 zsh completions 到 $ZSH_COMP_DIR${RESET}"
  echo ""

  for tool_dir in "$CLI_DIR"/*/; do
    [ -d "$tool_dir" ] || continue
    tool_dir="${tool_dir%/}"
    tool_name="$(basename "$tool_dir")"
    comp_file="$tool_dir/_${tool_name}"
    [ -f "$comp_file" ] || continue

    if install_symlink "$comp_file" "$ZSH_COMP_DIR/_${tool_name}" "_${tool_name}"; then
      zsh_installed=$((zsh_installed + 1))
    fi
  done
fi

if has_shell fish; then
  mkdir -p "$FISH_COMP_DIR"
  echo ""
  echo -e "${BOLD}安装 Fish completions 到 $FISH_COMP_DIR${RESET}"
  echo ""

  for tool_dir in "$CLI_DIR"/*/; do
    [ -d "$tool_dir" ] || continue
    tool_dir="${tool_dir%/}"
    tool_name="$(basename "$tool_dir")"
    comp_file="$tool_dir/${tool_name}.fish"
    [ -f "$comp_file" ] || continue

    if install_symlink "$comp_file" "$FISH_COMP_DIR/${tool_name}.fish" "${tool_name}.fish"; then
      fish_installed=$((fish_installed + 1))
    fi
  done
fi

if [ "$UPDATE_RC" -eq 1 ]; then
  if has_rc_shell zsh; then
    if [ "$ZSH_RC_EFFECTIVE_MODE" = "standalone" ]; then
      zsh_block="$(cat <<EOF
# my-ai-toolkit: CLI tools and zsh completions (standalone)
case ":\$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) export PATH="$BIN_DIR:\$PATH" ;;
esac

if [[ -d "$ZSH_COMP_DIR" ]]; then
  fpath=("$ZSH_COMP_DIR" \$fpath)
fi

autoload -Uz compinit
compinit -i
EOF
)"
      write_managed_block "${HOME}/.zshrc" "$ZSH_START_MARKER" "$ZSH_END_MARKER" "$zsh_block"
    else
      zsh_block="$(cat <<EOF
# my-ai-toolkit: CLI tools and zsh completions (integrated)
case ":\$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) export PATH="$BIN_DIR:\$PATH" ;;
esac

if [[ -d "$ZSH_COMP_DIR" ]]; then
  fpath=("$ZSH_COMP_DIR" \$fpath)
fi
EOF
)"
      write_managed_block_at_start "${HOME}/.zshrc" "$ZSH_START_MARKER" "$ZSH_END_MARKER" "$zsh_block"
    fi
  fi

  if has_rc_shell fish; then
    fish_block="$(cat <<EOF
# my-ai-toolkit: CLI tools
if test -d "$BIN_DIR"
    fish_add_path "$BIN_DIR"
end
EOF
)"
    write_managed_block "${HOME}/.config/fish/config.fish" "# >>> my-ai-toolkit >>>" "# <<< my-ai-toolkit <<<" "$fish_block"
  fi
fi

echo ""
if [ "$installed" -eq 0 ] && [ "$zsh_installed" -eq 0 ] && [ "$fish_installed" -eq 0 ]; then
  echo "没有找到可安装的工具。"
else
  msg="$installed 个工具"
  if [ "$zsh_installed" -gt 0 ]; then
    msg="$msg, $zsh_installed 个 zsh 补全"
  fi
  if [ "$fish_installed" -gt 0 ]; then
    msg="$msg, $fish_installed 个 Fish 补全"
  fi
  echo -e "${GREEN}完成! 共安装 ${msg}.${RESET}"
fi

echo ""
echo -e "${DIM}检测到主 shell：${primary_shell}；补全模式：${SHELL_MODE}；zsh rc 模式：${ZSH_RC_EFFECTIVE_MODE}。${RESET}"

if [ "$UPDATE_RC" -eq 1 ]; then
  if has_rc_shell zsh; then
    echo -e "${GREEN}已更新 ~/.zshrc。新开一个 zsh 终端后 PATH 和补全会生效。${RESET}"
  fi
  if has_rc_shell fish; then
    echo -e "${GREEN}已更新 ~/.config/fish/config.fish。新开一个 fish 终端后 PATH 会生效。${RESET}"
  fi
else
  echo -e "${YELLOW}已按 --no-rc 跳过 shell 配置文件更新。${RESET}"
  echo "请自行确保 $BIN_DIR 在 PATH 中。"
  if has_shell zsh; then
    if [ "$ZSH_RC_EFFECTIVE_MODE" = "standalone" ]; then
      echo "zsh 还需要把 $ZSH_COMP_DIR 加入 fpath 并启用 compinit。"
    else
      echo "zsh 还需要在现有 compinit 之前把 $ZSH_COMP_DIR 加入 fpath。"
    fi
  fi
fi

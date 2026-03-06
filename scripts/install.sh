#!/usr/bin/env bash
set -euo pipefail

# ─── 安装脚本 ────────────────────────────────────────────────────
# 将 cli/ 下所有工具软链接到 ~/.local/bin/
# 使用方式：bash scripts/install.sh
# ─────────────────────────────────────────────────────────────────

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
DIM='\033[2m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLI_DIR="$PROJECT_ROOT/cli"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "$BIN_DIR"

echo -e "${BOLD}安装 CLI 工具到 $BIN_DIR${RESET}"
echo ""

installed=0

for tool_dir in "$CLI_DIR"/*/; do
  [ -d "$tool_dir" ] || continue
  tool_name="$(basename "$tool_dir")"

  # 查找同名可执行文件
  tool_bin="$tool_dir/$tool_name"
  [ -f "$tool_bin" ] || continue

  target="$BIN_DIR/$tool_name"

  if [ -L "$target" ]; then
    existing="$(readlink "$target")"
    if [ "$existing" = "$tool_bin" ]; then
      echo -e "  ${DIM}$tool_name — 已安装，跳过${RESET}"
      ((installed++))
      continue
    fi
    echo -e "  ${YELLOW}$tool_name — 已存在链接到 $existing，覆盖${RESET}"
    rm "$target"
  elif [ -f "$target" ]; then
    echo -e "  ${YELLOW}$tool_name — $target 已存在且不是软链接，跳过${RESET}"
    continue
  fi

  chmod +x "$tool_bin"
  ln -s "$tool_bin" "$target"
  echo -e "  ${GREEN}$tool_name — 已安装${RESET}"
  ((installed++))
done

# ─── 安装 Fish completions ──────────────────────────────────────
FISH_COMP_DIR="${HOME}/.config/fish/completions"
fish_installed=0

if command -v fish &>/dev/null; then
  mkdir -p "$FISH_COMP_DIR"
  echo -e "${BOLD}安装 Fish completions 到 $FISH_COMP_DIR${RESET}"
  echo ""

  for tool_dir in "$CLI_DIR"/*/; do
    [ -d "$tool_dir" ] || continue
    tool_name="$(basename "$tool_dir")"
    comp_file="$tool_dir/${tool_name}.fish"
    [ -f "$comp_file" ] || continue

    target="$FISH_COMP_DIR/${tool_name}.fish"

    if [ -L "$target" ]; then
      existing="$(readlink "$target")"
      if [ "$existing" = "$comp_file" ]; then
        echo -e "  ${DIM}${tool_name}.fish — 已安装，跳过${RESET}"
        ((fish_installed++))
        continue
      fi
      rm "$target"
    elif [ -f "$target" ]; then
      echo -e "  ${YELLOW}${tool_name}.fish — 已存在且不是软链接，跳过${RESET}"
      continue
    fi

    ln -s "$comp_file" "$target"
    echo -e "  ${GREEN}${tool_name}.fish — 已安装${RESET}"
    ((fish_installed++))
  done
  echo ""
fi

# ─── 汇总 ───────────────────────────────────────────────────────
echo ""
if [ "$installed" -eq 0 ] && [ "$fish_installed" -eq 0 ]; then
  echo "没有找到可安装的工具。"
else
  msg="$installed 个工具"
  if [ "$fish_installed" -gt 0 ]; then
    msg="$msg, $fish_installed 个 Fish 补全"
  fi
  echo -e "${GREEN}完成! 共安装 ${msg}.${RESET}"
fi

# ─── 检查 PATH ──────────────────────────────────────────────────
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo ""
  echo -e "${YELLOW}提示：$BIN_DIR 不在 PATH 中。${RESET}"
  echo -e "请添加以下内容到你的 shell 配置文件："
  echo ""
  echo "  # fish"
  echo "  fish_add_path $BIN_DIR"
  echo ""
  echo "  # bash/zsh"
  echo "  export PATH=\"$BIN_DIR:\$PATH\""
fi

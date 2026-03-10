# pingcode-cli

PingCode 命令行工具，无需打开浏览器即可查看和管理缺陷。

## 环境要求

- macOS 或 Linux
- bash 5.0+（macOS 自带 3.2 不够用，需 `brew install bash`）
- curl
- python3（macOS 自带）

## 安装

```bash
# 1. 将 pingcode-cli 复制到 PATH 中的任意目录
cp pingcode-cli ~/.local/bin/

# 2.（可选）安装 Fish Shell 补全
cp pingcode-cli.fish ~/.config/fish/completions/
```

确保 `~/.local/bin` 在 PATH 中：

```fish
# fish
fish_add_path ~/.local/bin

# bash / zsh
export PATH="$HOME/.local/bin:$PATH"
```

## 初始化配置

首次运行时会引导你完成配置：

```bash
pingcode-cli bugs
```

按照提示操作：

1. 打开 PingCode 缺陷列表页面
2. 按 F12 打开开发者工具 → Network 标签
3. 刷新页面，找到 `content` 请求
4. 右键该请求 → Copy → Copy as cURL
5. 粘贴到终端，按回车

工具会自动从 cURL 命令中解析出所有必要配置（URL、Cookie、项目 ID 等），保存到 `~/.config/pingcode-cli/config`。

## 使用

```bash
# 列出我的未解决缺陷
pingcode-cli bugs

# 修改缺陷状态
pingcode-cli set-state 720YUN-10515 已修复
pingcode-cli set-state 720YUN-10515 处理中

# 可用状态：待处理、处理中、已修复、重新打开、挂起

# 查看 / 编辑配置
pingcode-cli config show
pingcode-cli config edit

# Cookie 过期后重新初始化
pingcode-cli config init
```

## 注意事项

- 会话 Cookie 会过期，过期后重新运行 `pingcode-cli config init`，从浏览器复制新的 cURL 即可
- 配置文件权限为 600（仅本人可读写）
- `set-state` 依赖 `bugs` 命令缓存的数据来查找缺陷 ID，如果报错找不到缺陷，先运行一次 `pingcode-cli bugs`

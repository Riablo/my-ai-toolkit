# cloudsaver-cli

从旧 `CloudSaver` 项目迁移过来的 CLI，保留原来的两个核心能力：

- 从 Telegram 频道搜索网盘资源
- 将 115 分享资源转存到自己的 115 网盘

这次迁移主要做了仓库规范整理，没有主动改功能边界。当前仓库里的命令名统一为 `cloudsaver-cli`，并补上了标准入口、Fish 补全、README 以及配置兼容逻辑。

## 环境要求

- macOS 或 Linux
- `bash`
- `node` 18+
- 可访问 Telegram 网页搜索结果与 115 网盘接口的网络环境

## 安装

```bash
# 安装本仓库所有 CLI 到 ~/.local/bin
bash scripts/install.sh
```

或者手动复制：

```bash
cp cli/cloudsaver-cli/cloudsaver-cli ~/.local/bin/
cp cli/cloudsaver-cli/cloudsaver-cli.fish ~/.config/fish/completions/
chmod +x ~/.local/bin/cloudsaver-cli
```

## 配置位置

当前仓库规范下的主配置文件是：

```text
~/.config/cloudsaver-cli/config.json
```

为了兼容旧项目，运行时也会自动读取旧位置中的配置：

- `~/.config/cloudsaver/config.json`
- `~/.config/cloudsaver/local.json`

如果你后续通过 `cloudsaver-cli config ...` 修改配置，新配置会写回到 `~/.config/cloudsaver-cli/config.json`。

## 用法

### 配置搜索频道

```bash
cloudsaver-cli config --add-channel
cloudsaver-cli config --show
```

### 设置 115 Cookie

```bash
cloudsaver-cli config --set-cookie
```

获取 Cookie 的方式与旧项目保持一致：

1. 登录 `115.com`
2. 打开浏览器开发者工具
3. 找到任意请求
4. 复制请求头里的 `Cookie`

### 搜索资源

```bash
cloudsaver-cli search "电影名称"
cloudsaver-cli s "电影名称"
cloudsaver-cli search "电影名称" --limit 10
cloudsaver-cli search "电影名称" --no-table
```

### 转存资源

```bash
cloudsaver-cli save
cloudsaver-cli save "https://115.com/s/xxxxx"
cloudsaver-cli save "https://115.com/s/xxxxx" --folder "folder_id"
```

说明：

- 不传 `--folder` 时，会自动使用根目录下的“转存”文件夹；如果不存在就自动创建
- 传了 `--folder` 时，会直接转存到指定文件夹 ID，不再额外询问确认

## 命令一览

| 命令 | 简写 | 说明 |
| --- | --- | --- |
| `search <keyword>` | `s` | 搜索网盘资源 |
| `save [url]` | `sv` | 转存 115 网盘资源 |
| `config` | - | 配置管理 |
| `--version` | - | 显示版本 |
| `--help` | - | 显示帮助 |

## 说明

- 搜索结果按网盘类型分类展示，优先展示 115 和阿里云盘链接
- 当前只支持 115 网盘转存；其他网盘仍然只展示链接
- 配置文件保存时权限会设为 `600`

## 来源

此工具迁移自你之前的 `CloudSaver` CLI 版本，原项目 README 中也注明其源自开源的 CloudSaver 项目。当前仓库继续沿用 MIT License。

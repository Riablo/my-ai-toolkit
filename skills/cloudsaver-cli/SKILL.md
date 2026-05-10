---
name: cloudsaver-cli
description: 当用户想搜索 Telegram 频道里的网盘资源、找 115 或阿里云盘链接、把 115 分享链接转存到自己的网盘，或排查 `cloudsaver-cli` 的频道、Cookie、代理配置时使用。
---

# CloudSaver CLI

用 `cloudsaver-cli` 做两件事：搜索资源，或把 115 分享转存到自己的网盘。

## 核心原则

- 默认直接执行 `search` 或 `save`，不要每次先跑配置检查。
- 只有当用户主动要排查，或主命令失败且像配置问题时，才运行 `config --check`。
- 写配置的命令如 `config --add-channel`、`config --set-cookie`、`config --set-proxy`，只有在用户明确要求初始化或修改时才执行。
- `config` 不带选项会进入交互菜单；AI 默认不要走这个入口。

## CLI 入口

- 优先使用 PATH 中的 `cloudsaver-cli`
- 若未安装，再回到仓库里的 `cli/cloudsaver-cli/cloudsaver-cli`
- 这是 Bash 包装脚本，实际依赖 Node；若入口本身失败，优先检查 `node` 是否可用且版本不少于 18

## 初始化与检查

- 主配置：`~/.config/cloudsaver-cli/config.json`
- 兼容旧配置：`~/.config/cloudsaver/config.json`、`~/.config/cloudsaver/local.json`
- 代理环境变量：`HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY`
- 查看配置：`cloudsaver-cli config --show`
- 自检：`cloudsaver-cli config --check`

若用户还没初始化，通常需要两步：

```bash
cloudsaver-cli config --add-channel
cloudsaver-cli config --set-cookie
```

但不要因为 skill 里写了这两条就自动执行；频道、Cookie、代理都属于显式用户输入。

## 帮助探测

先看顶层帮助；参数不确定时再看对应子命令：

```bash
cloudsaver-cli -h
cloudsaver-cli search -h
cloudsaver-cli save -h
cloudsaver-cli config -h
```

## 路由规则

- 搜索片源、网盘资源、115/阿里云盘链接：用 `search`
- 明确给出片名、年份、清晰度时，直接把这些词拼进搜索词
- 转存 115 分享链接：用 `save`
- 用户给了目标文件夹 ID：加 `--folder`
- 排查频道、Cookie、代理或配置状态：用 `config --show` 或 `config --check`

## 高价值 gotchas

- `search` 默认表格输出；如果需要更容易复述的终端结果，优先加 `--no-table`
- 搜索结果会优先把 115 资源排前，再到阿里云和其他网盘；同层里通常优先清晰度更高的结果
- `save` 在未提供 URL 时会进入交互式输入；用户已经给了链接时，直接把 URL 作为参数传入
- 用户没给目标文件夹 ID 时，`save <url>` 可直接执行；CLI 会使用默认“转存”目录
- 常见配置缺失是“还没加搜索频道”或“115 Cookie 已过期”

## 输出转述

- `search`：先说有没有找到，优先推荐前几条 115 / 阿里云结果，再补频道、时间、清晰度关键词
- `save`：先说是否转存成功，再补目标文件夹、文件数量、失败项和失败原因
- `config --show`：先总结频道、代理、Cookie 是否已配置，再补配置路径

除非用户明确要原始输出，否则不要整段照抄终端表格或日志。

## 常见错误

- `请先配置搜索频道`：还没添加 Telegram 频道
- `请先设置115网盘Cookie`：还没配置登录态或 Cookie 已过期
- `无效的115分享链接`：链接格式不对
- `分享已取消` / `分享中没有文件`：链接解析正常，但服务端资源不可用
- 配置文件非法或字段缺失：先修配置，再继续执行

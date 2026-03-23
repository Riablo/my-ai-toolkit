---
name: cloudsaver-cli
description: 使用 `cloudsaver-cli` 搜索 Telegram 频道里的网盘资源，并将 115 分享资源转存到自己的 115 网盘。当用户提到“帮我搜片源/资源”“找 115 或阿里云盘链接”“看看有没有 4K/1080P 资源”“把这个 115 链接转存到网盘”“检查 cloudsaver-cli 的频道、Cookie 或代理配置”等，或希望 AI 通过命令行完成这些任务时使用此技能。
---

# CloudSaver CLI

使用 `cloudsaver-cli` 完成资源搜索和 115 转存。先确认配置，再查看帮助选择子命令；不要凭印象猜参数。

## CLI 定位

- 优先使用 PATH 中的 `cloudsaver-cli`
- 若未安装，则回到仓库里的 `cli/cloudsaver-cli/cloudsaver-cli`
- 这个入口是 Bash 包装脚本，实际会调用同目录下的 Node bundle；若直接执行失败，再先检查 `node` 是否可用且版本不少于 18

定位仓库内 CLI 时，使用下面的约定：

- `SKILL_DIR` = 当前 `SKILL.md` 所在目录
- `PROJECT_ROOT` = `SKILL_DIR` 的上上级目录
- `TOOL_PATH` = `PROJECT_ROOT/cli/cloudsaver-cli/cloudsaver-cli`

## 初始化

每次执行前先确认配置就绪：

- 主配置文件：`~/.config/cloudsaver-cli/config.json`
- 兼容旧配置：`~/.config/cloudsaver/config.json`、`~/.config/cloudsaver/local.json`
- 可选代理环境变量：`HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY`
- Cookie 初始化：`cloudsaver-cli config --set-cookie`
- 搜索频道初始化：`cloudsaver-cli config --add-channel`
- 配置检查：`cloudsaver-cli config --show`

若用户还没初始化，优先引导他：

```bash
cloudsaver-cli config --add-channel
cloudsaver-cli config --set-cookie
```

如果只是想确认当前 CLI 读到的配置，优先运行：

```bash
cloudsaver-cli config --show
```

## 配置校验

每次执行真实搜索或转存前都要校验，不能静默跳过：

1. 先确认 `node` 18+ 可用，且 `cloudsaver-cli -h` 能正常执行。
2. 若没有环境变量覆盖，则配置文件或兼容旧配置至少要有一份可读取的有效 JSON。
3. 做搜索前，必须存在至少一个搜索频道；若 `config --show` 里 `频道数量: 0`，先引导用户添加频道。
4. 做 115 转存前，必须已经设置 `Cookie`；若 `config --show` 里显示 `Cookie: 未设置`，先引导用户执行 `cloudsaver-cli config --set-cookie`。
5. 若启用了代理，确保代理主机非空、端口是有效整数；配置异常时先修复，不要继续请求。

若任一条件不满足，先提醒用户初始化或修复配置，不要继续执行真实请求。

## 帮助探测

先运行：

```bash
cloudsaver-cli -h
```

遇到参数细节不确定时，再查看对应子命令：

```bash
cloudsaver-cli search -h
cloudsaver-cli save -h
cloudsaver-cli config -h
```

如果 PATH 中没有命令，就把上面的 `cloudsaver-cli` 替换成仓库内入口或 `bash TOOL_PATH`。

## 命令路由

- 用户要搜索片源、网盘资源、115/阿里云盘链接时，用 `search`
- 用户明确给出关键词、片名、剧名、年份、清晰度时，把这些词直接作为 `search <keyword>` 输入
- 用户要把某个 115 分享链接转存到自己的网盘时，用 `save`
- 用户给了目标文件夹 ID 时，用 `save <url> --folder <id>`
- 用户没有给目标文件夹 ID 时，直接用 `save <url>`；CLI 会默认使用根目录下的“转存”文件夹，不需要再次确认
- 用户要检查频道、Cookie、代理或配置状态时，用 `config --show`
- 用户要设置 Cookie、添加/删除频道、配置代理时，优先用显式选项：`config --set-cookie`、`config --add-channel`、`config --remove-channel`、`config --set-proxy`

常用映射：

- “帮我搜《完美的日子》115 资源” -> `cloudsaver-cli search "完美的日子 115"`
- “找阿里云盘的 4K 版本” -> `cloudsaver-cli search "<关键词> 4K"`
- “把这个 115 链接转存到网盘” -> `cloudsaver-cli save "<url>"`
- “把这个 115 链接转存到某个文件夹” -> `cloudsaver-cli save "<url>" --folder "<folder_id>"`
- “看看 cloudsaver-cli 配置好了没” -> `cloudsaver-cli config --show`

补充约定：

- `search` 默认是表格输出；若需要更容易解析的终端输出，优先加 `--no-table`
- `search` 结果会优先把 115 资源排前，再到阿里云和其他网盘；同层里优先清晰度更高的结果
- `save` 在未提供 URL 时会进入交互式输入；若用户已经给了链接，优先把 URL 直接作为参数传入
- `config` 不带选项会进入交互菜单；AI 默认不要走这个交互入口，优先使用显式选项

## 输出转述

执行 CLI 后，先给人类可读的结论，再补关键细节：

- `search`：先总结是否找到资源、优先推荐前几条 115 / 阿里云结果，再补频道、时间、链接类型、清晰度关键词
- `save`：先总结是否转存成功，再补目标文件夹、文件数量、失败项和失败原因
- `config --show`：先总结频道是否已配置、代理是否启用、Cookie 是否已设置，再补配置路径

除非用户明确要原始输出、调试日志或完整表格，否则不要整段照抄终端输出。

## 常见错误

- `请先配置搜索频道`：说明还没有添加 Telegram 频道，先执行 `cloudsaver-cli config --add-channel`
- `请先设置115网盘Cookie`：说明还没有登录态，先执行 `cloudsaver-cli config --set-cookie`
- `无效的115分享链接`：说明链接格式不对，检查是否真的是 `115.com` / `115cdn.com` / `anxia.com` 的分享链接
- `分享已取消`：链接解析正常，但 115 服务端认为该分享已失效
- `分享中没有文件`：分享还在，但当前列表为空
- `Cookie可能已过期`：重新设置 Cookie 再试
- `配置文件不是合法 JSON` / 配置字段缺失：先修复配置文件，再继续执行

## 维护约定

当 `cloudsaver-cli` 新增子命令、参数、配置规则、搜索排序规则或转存行为时，同步更新这个 skill 和仓库根目录 `README.md`。

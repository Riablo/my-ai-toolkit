# CLI Skill Template

用这个参考文件快速起草基于 CLI 的 skill。保留框架，替换成目标工具的真实信息；不要把占位文字原样提交。

## 最小结构

```md
---
name: <skill-name>
description: 使用 `<tool-name>` 这个 CLI 处理 <能力范围>。当用户提到 <自然语言触发词>，或希望 AI 通过命令行完成 <任务类型> 时使用此技能。
---

# <Skill Title>

使用 `<tool-name>` 完成任务。先查看帮助，再选择子命令；不要凭印象猜参数。

## 初始化

每次执行前先确认配置是否就绪：

- 配置文件路径：`<config-path>`
- 环境变量：`<ENV_A>`、`<ENV_B>`
- 初始化命令：`<tool-name> init ...`

若配置不存在、字段缺失或值无效，先提示用户初始化或修复，不要继续执行真实请求。

## CLI 定位

- 优先使用 PATH 中的 `<tool-name>`
- 若未安装，则回到仓库里的 `cli/<tool-name>/<tool-name>`
- 若 `-h` 执行失败，先确认入口实际是 bash、python3 还是别的解释器

## 帮助探测

先运行：

```bash
<tool-name> -h
```

若需要具体参数，再运行：

```bash
<tool-name> <subcommand> -h
```

## 命令路由

- <意图 A> -> `<tool-name> <subcommand-a>`
- <意图 B> -> `<tool-name> <subcommand-b>`
- <意图 C> -> `<tool-name> <subcommand-c>`

若用户给出过滤条件、范围、语言、输出格式或时间跨度，结合子命令帮助补充参数。

## 结果转述

执行 CLI 后，先用自然语言总结结果，再补充关键细节。除非用户要求原始输出，否则不要整段照抄 JSON。
```

## 起草检查清单

- frontmatter 是否写清触发语义，而不只是工具名
- 是否写明初始化命令、配置路径、环境变量和关键字段
- 是否要求“每次执行前校验配置”
- 是否明确“遇到参数细节先跑 `-h`”
- 是否把用户语义映射到子命令，而不是单纯列命令名
- 是否要求把 CLI 输出翻译成自然语言
- 是否避免把完整帮助文本塞进 skill
- 是否在新增 skill 后同步更新仓库根目录 `README.md`

## qweather-cli 示例

`qweather-cli` 是一个很适合这种写法的例子：

- 顶层命令：`init`、`config`、`now`、`daily`、`hourly`
- 初始化要求：需要 `api_host` 和 `api_key`
- 配置文件：`~/.config/qweather-cli/config.json`
- 环境变量：`QWEATHER_API_HOST`、`QWEATHER_API_KEY`
- 语义路由：
  - “现在天气怎样” -> `now`
  - “未来几天天气” -> `daily`
  - “未来几小时天气” -> `hourly`
- 结果转述：先总结天气，再补充温度、体感、降水、风力、预报时间等关键信息

这个例子里，不需要把 `--days`、`--hours`、`--unit`、`--location-id` 的全部细节提前写死到 skill 中；只要提醒后续 AI 在执行时查看对应子命令的 `-h` 即可。

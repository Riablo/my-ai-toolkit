---
name: freecurrency-cli
description: 使用 `freecurrency-cli` 查询最新汇率、做金额换算、检查 Open Exchange Rates 配置和本地缓存。当用户提到“汇率”“换汇”“金额换算”“100 人民币是多少美元”“查一下最新 USD/EUR/CNY/TWD 汇率”“看看 Open Exchange Rates 配置”“清理汇率缓存”等，或希望 AI 通过命令行完成这些任务时使用此技能。
---

# Freecurrency CLI

使用 `freecurrency-cli` 完成汇率查询与金额换算。默认直接执行查询命令；只有用户明确要排查配置，或执行因配置问题失败时，再使用 `config` 相关命令。

## CLI 定位

- 优先使用 PATH 中的 `freecurrency-cli`
- 若未安装，则回到仓库里的 `cli/freecurrency-cli/freecurrency-cli`
- 这个入口是 Python 脚本；若直接执行失败，再改用 `python3 cli/freecurrency-cli/freecurrency-cli -h`

定位仓库内 CLI 时，使用下面的约定：

- `SKILL_DIR` = 当前 `SKILL.md` 所在目录
- `PROJECT_ROOT` = `SKILL_DIR` 的上上级目录
- `TOOL_PATH` = `PROJECT_ROOT/cli/freecurrency-cli/freecurrency-cli`

## 初始化

首次使用时需要初始化：

- 配置文件：`~/.config/freecurrency-cli/config.json`
- 缓存目录：`~/.cache/freecurrency-cli/`
- 环境变量：`OPENEXCHANGERATES_APP_ID`、`OPENEXCHANGERATES_API_BASE_URL`
- 初始化命令：`freecurrency-cli init --app-id <APP_ID>`

若用户还没初始化，引导他先执行：

```bash
freecurrency-cli init --app-id YOUR_APP_ID
```

需要确认当前实际生效的配置时，运行：

```bash
freecurrency-cli config show
```

它会返回掩码后的 App ID 和当前 `baseUrl`，适合直接转述给用户。

需要快速检查配置是否可用时，运行：

```bash
freecurrency-cli config check
```

正常查询时不要额外先做一轮手工检查；直接执行 `convert` 或 `latest`。只有当用户主动要求排查，或执行失败且看起来像配置问题时，再跑 `config check`。

## 帮助探测

先运行：

```bash
freecurrency-cli -h
```

遇到参数细节不确定时，再查看对应子命令：

```bash
freecurrency-cli convert -h
freecurrency-cli latest -h
freecurrency-cli config -h
freecurrency-cli cache -h
```

如果 PATH 中没有命令，就把上面的 `freecurrency-cli` 替换成仓库内入口或 `python3 TOOL_PATH`。

## 命令路由

- 用户要做金额换算、问“100 CNY 是多少 USD”这类问题时，用 `convert`
- 用户给的是自然语言式表达时，也可以用 `convert <amount> <FROM> to <TO>`
- 用户要看最新汇率、某个基准货币相对多个币种的价格时，用 `latest`
- 用户要看配置路径、当前 App ID 是否生效、当前 base URL，或快速检查配置是否可用时，用 `config show`、`config path` 或 `config check`
- 用户要看缓存目录、缓存条数、缓存是否需要清理时，用 `cache info`
- 用户明确要求清空缓存时，用 `cache clear`

常用映射：

- “把 100 人民币换成美元” -> `freecurrency-cli convert 100 CNY USD`
- “把 100 人民币换成美元，按自然语言格式” -> `freecurrency-cli convert 100 CNY to USD`
- “查 CNY 对 USD、EUR、JPY 的最新汇率” -> `freecurrency-cli latest --base CNY --currencies USD EUR JPY`

补充约定：

- `latest --currencies` 同时支持空格分隔和逗号分隔
- Open Exchange Rates 免费层上游基准货币是 `USD`；CLI 会在本地重算任意 `--base` 的交叉汇率
- `convert` 默认只输出换算结果；只有在需要汇率、缓存来源、过期时间等细节时才加 `--json`
- 若源货币和目标货币相同，`convert` 会直接返回原金额，不会请求 API

## 输出转述

执行后先给人类可读的结论，再补关键细节：

- `convert` 默认转述成“`100 CNY` 约等于 `13.8 USD`”
- 使用 `convert --json` 时，再补充 `rate`、`source`（`api` / `cache` / `identity`）、`lastUpdatedAt`、`expiresAt`
- `latest` 会输出 JSON；先总结基准货币和目标币种汇率，再按需补 `lastUpdatedAt`、缓存来源、缓存过期时间
- `config show` 只转述掩码后的 App ID、配置路径和 base URL
- `cache info` 重点转述缓存目录、TTL（当前实现是 1800 秒）、有效缓存数量和过期缓存数量

除非用户明确要原始输出、调试信息或完整 JSON，否则不要整段照抄 JSON。

## 常见错误

- `非法货币代码`：货币代码必须是 3 位英文字母，例如 `USD`、`CNY`
- `非法金额`：金额不是合法数字
- `未找到配置文件` / `配置文件缺少 app_id`：先引导用户初始化或修复 `config.json`
- `HTTP xxx`：API 返回错误，优先转述 HTTP 状态码和 message
- `请求失败`：通常是网络不可达或自定义 `OPENEXCHANGERATES_API_BASE_URL` 有问题

## 维护约定

当 `freecurrency-cli` 新增子命令、参数、配置字段、缓存规则或输出格式时，同步更新这个 skill 和仓库根目录 `README.md`。

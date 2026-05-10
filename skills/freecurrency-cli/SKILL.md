---
name: freecurrency-cli
description: 当用户要查汇率、做金额换算、看最新 USD/EUR/CNY/TWD 汇率、检查 Open Exchange Rates 配置，或排查 `freecurrency-cli` 缓存与配置时使用。
---

# Freecurrency CLI

用 `freecurrency-cli` 做汇率查询、金额换算和少量配置排查。

## 核心原则

- 默认直接执行 `convert` 或 `latest`，不要先跑一轮手工检查。
- 只有当用户主动要排查，或主命令失败且像配置问题时，才运行 `config check`。
- `init` 会写本机配置；没有真实 `app_id` 时不要自动执行。

## CLI 入口

- 优先使用 PATH 中的 `freecurrency-cli`
- 若未安装，再回到仓库里的 `cli/freecurrency-cli/freecurrency-cli`
- 这是 Python 入口；若直接执行失败，再改用 `python3`

## 初始化与检查

- 配置文件：`~/.config/freecurrency-cli/config.json`
- 缓存目录：`~/.cache/freecurrency-cli/`
- 环境变量：`OPENEXCHANGERATES_APP_ID`、`OPENEXCHANGERATES_API_BASE_URL`
- 初始化：`freecurrency-cli init --app-id <APP_ID>`
- 查看配置：`freecurrency-cli config show`
- 自检：`freecurrency-cli config check`
- 缓存信息：`freecurrency-cli cache info`

## 帮助探测

```bash
freecurrency-cli -h
freecurrency-cli convert -h
freecurrency-cli latest -h
freecurrency-cli config -h
freecurrency-cli cache -h
```

## 路由规则

- “100 CNY 是多少 USD” 这类金额换算：用 `convert`
- 查询一组最新汇率：用 `latest`
- 查看配置路径、当前 App ID 是否生效、base URL 是否正确：用 `config show` / `config path` / `config check`
- 查看或清理缓存：用 `cache info` / `cache clear`

## 高价值 gotchas

- Open Exchange Rates 免费层上游基准货币是 `USD`；CLI 会在本地重算任意 `--base` 的交叉汇率
- `latest --currencies` 同时支持空格分隔和逗号分隔
- `convert` 默认只输出结果；只有在需要汇率、来源、过期时间等细节时才加 `--json`
- 若源货币和目标货币相同，`convert` 会直接返回原金额，不会请求 API

## 输出转述

- `convert`：先用自然语言给结果，再按需补 `rate`、`source`、`lastUpdatedAt`、`expiresAt`
- `latest`：先总结基准货币和目标币种汇率，再补缓存来源和时间
- `config show`：只转述掩码后的 App ID、配置路径和 base URL
- `cache info`：重点转述缓存目录、TTL、有效缓存数量和过期缓存数量

默认不要整段倾倒 JSON。

## 常见错误

- `非法货币代码`：货币代码必须是 3 位英文字母
- `非法金额`：金额不是合法数字
- `未找到配置文件` / `配置文件缺少 app_id`：先初始化或修配置
- `HTTP xxx` / `请求失败`：通常是 API 错误、网络问题或自定义 `API_BASE_URL` 有误

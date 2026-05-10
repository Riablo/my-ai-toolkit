---
name: qweather-cli
description: 当用户要查当前天气、未来几天预报、未来几小时降雨或温度变化，按城市 / LocationID / 经纬度查天气，或排查 `qweather-cli` 配置时使用。
---

# QWeather CLI

用 `qweather-cli` 查实时天气、逐日预报和逐小时预报。

## 核心原则

- 默认直接执行 `now`、`daily` 或 `hourly`，不要每次先跑配置检查
- 只有当用户主动要排查，或查询失败且像配置问题时，才运行 `config check`
- `init` 会写本机配置；没有真实 `api_host` 和 `api_key` 时不要自动执行

## CLI 入口

- 优先使用 PATH 中的 `qweather-cli`
- 若未安装，再回到仓库里的 `cli/qweather-cli/qweather-cli`
- 这是 Python 入口；若直接执行失败，再改用 `python3`

## 初始化与检查

- 配置文件：`~/.config/qweather-cli/config.json`
- 环境变量：`QWEATHER_API_HOST`、`QWEATHER_API_KEY`
- 初始化：`qweather-cli init --api-host <HOST> --api-key <KEY>`
- 查看配置：`qweather-cli config show`
- 查看配置路径：`qweather-cli config path`
- 自检：`qweather-cli config check`

## 帮助探测

```bash
qweather-cli -h
qweather-cli now -h
qweather-cli daily -h
qweather-cli hourly -h
qweather-cli config -h
```

## 路由规则

- 当前天气、体感、风力：`now`
- 未来几天、本周、7/15/30 天：`daily`
- 接下来几小时、今晚到明天、24/72/168 小时：`hourly`
- 排查配置是否生效：`config show` / `config path` / `config check`

## 高价值 gotchas

- 这个 CLI 一次只接受一种定位方式：城市名、`--location-id`、或 `--lon` + `--lat`
- `--lon` 和 `--lat` 必须同时提供
- 城市名命中多个位置时，CLI 默认取第 1 个；需要时可改 `--location-index`
- 若用户知道省/州或国家范围，可用 `--adm`、`--range` 缩小搜索范围
- 用户明确要原始 QWeather 响应时，再加 `--raw`

## 输出转述

- `now`：先总结天气现象与温度，再补体感、风力、湿度、能见度、观测时间
- `daily`：先总结整体趋势，再补每天最高/最低温和天气现象
- `hourly`：先总结关键时段变化，再补温度、降水、风力和小时点
- 若城市名有歧义，顺手说明最终命中的 `resolvedLocation`

默认不要整段倾倒包装后的 JSON。

## 常见错误

- `未找到配置文件` / `配置文件缺少 api_host 或 api_key`：先初始化或修配置
- `请提供且只提供一种定位方式`：城市名、LocationID、经纬度三选一
- `--lon` 和 `--lat` 必须同时提供：坐标参数不完整
- `--location-index` 超出范围：候选位置数量不足
- `未找到城市或地区`：地名太模糊，建议加限定范围
- `HTTP xxx` / `请求失败`：通常是 Host、Key 或网络问题

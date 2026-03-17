---
name: qweather-cli
description: 使用 `qweather-cli` 查询 QWeather 实时天气、每日预报、逐小时预报，并检查 API Host / API Key 配置。当用户提到“现在天气怎么样”“北京未来 7 天天气”“接下来 72 小时会下雨吗”“按城市/LocationID/经纬度查天气”“看看 qweather-cli 配置是否生效”等，或希望 AI 通过命令行完成天气查询时使用此技能。
---

# QWeather CLI

使用 `qweather-cli` 完成天气查询。先确认配置，再查看帮助选择子命令；不要凭印象猜参数。

## CLI 定位

- 优先使用 PATH 中的 `qweather-cli`
- 若未安装，则回到仓库里的 `cli/qweather-cli/qweather-cli`
- 这个入口是 Python 脚本；若直接执行失败，再改用 `python3 cli/qweather-cli/qweather-cli -h`

定位仓库内 CLI 时，使用下面的约定：

- `SKILL_DIR` = 当前 `SKILL.md` 所在目录
- `PROJECT_ROOT` = `SKILL_DIR` 的上上级目录
- `TOOL_PATH` = `PROJECT_ROOT/cli/qweather-cli/qweather-cli`

## 初始化

每次执行前先确认配置就绪：

- 配置文件：`~/.config/qweather-cli/config.json`
- 环境变量：`QWEATHER_API_HOST`、`QWEATHER_API_KEY`
- 初始化命令：`qweather-cli init --api-host <HOST> --api-key <KEY>`

若用户还没初始化，引导他先执行：

```bash
qweather-cli init --api-host YOUR_API_HOST --api-key YOUR_API_KEY
```

若只是想确认当前 CLI 读到的配置，优先运行：

```bash
qweather-cli config show
```

它会返回配置文件路径、当前 `apiHost` 和掩码后的 `apiKey`，适合直接转述给用户。

## 配置校验

每次执行真实请求前都要校验，不能静默跳过：

1. 若设置了环境变量，`QWEATHER_API_HOST` 和 `QWEATHER_API_KEY` 必须同时提供，不能只配一个。
2. 两个环境变量去掉首尾空白后都必须非空。
3. 若使用环境变量，`api_host` 必须是可解析的 Host 或 URL；明显非法的值会直接报错。
4. 若没有环境变量，则必须存在 `~/.config/qweather-cli/config.json`。
5. 配置文件存在时，必须是合法 JSON，且 `api_host`、`api_key` 两个字段都非空。

若任一条件不满足，先提醒用户初始化或修复配置，不要继续查询天气。

需要确认配置文件位置时，运行：

```bash
qweather-cli config path
```

## 帮助探测

先运行：

```bash
qweather-cli -h
```

遇到参数细节不确定时，再查看对应子命令：

```bash
qweather-cli now -h
qweather-cli daily -h
qweather-cli hourly -h
qweather-cli init -h
qweather-cli config -h
```

如果 PATH 中没有命令，就把上面的 `qweather-cli` 替换成仓库内入口或 `python3 TOOL_PATH`。

## 命令路由

- 用户要看“现在天气”“当前温度”“此刻体感和风力”时，用 `now`
- 用户要看“未来几天”“本周天气”“未来 7 天/15 天/30 天预报”时，用 `daily`
- 用户要看“未来几小时”“今晚到明天的小时级变化”“未来 24/72/168 小时预报”时，用 `hourly`
- 用户要确认配置是否已初始化、当前 Host 是否生效、配置文件放在哪里时，用 `config show` 或 `config path`
- 用户明确要设置或重置 API Host / API Key 时，用 `init`

常用映射：

- “北京现在天气怎样” -> `qweather-cli now 北京`
- “上海未来 7 天天气” -> `qweather-cli daily 上海 --days 7`
- “深圳未来 72 小时会下雨吗” -> `qweather-cli hourly 深圳 --hours 72`
- “用经纬度查当前天气” -> `qweather-cli now --lon <LON> --lat <LAT>`
- “看看 qweather-cli 配置” -> `qweather-cli config show`

如果用户给出了语言、单位、时间跨度或输出格式要求，再结合子命令帮助补充参数。

## 位置解析

这个 CLI 只接受一种定位方式；执行前先确认用户输入属于哪一类：

- 城市名或地区名：默认走 GeoAPI 城市搜索，再取 LocationID 请求天气
- `--location-id`：直接使用 QWeather LocationID，跳过 GeoAPI
- `--lon` + `--lat`：直接按经纬度查询

补充约定：

- `--lon` 和 `--lat` 必须同时提供
- 位置参数城市名和 `--city` 不能同时使用
- 城市名命中多个位置时，CLI 默认取第 1 个，可用 `--location-index` 改
- 若用户知道省/州或国家范围，可用 `--adm`、`--range` 缩小城市搜索范围
- 若返回多个候选位置，CLI 会在 stderr 提示命中了多少结果以及当前选择了哪个位置

## 输出转述

默认输出是包装后的 JSON，通常包含：

- `query`：这次查询用的是城市名、LocationID 还是经纬度
- `resolvedLocation`：城市名模式下 GeoAPI 选中的位置
- `data`：QWeather API 返回的数据

除非用户明确要原始输出、调试信息或完整 JSON，否则不要整段照抄 JSON。

执行后先给人类可读的结论，再补关键细节：

- `now`：先总结当前天气现象与温度，再补体感、风向风力、湿度、能见度、降水、观测时间
- `daily`：先总结未来几天的整体趋势，再补每天的最高/最低温、天气现象、降水概率或风况
- `hourly`：先总结接下来几个关键时段的变化，再补温度、天气现象、降水、风力和小时点
- 若城市名有歧义，顺手说明最终命中的 `resolvedLocation`

用户明确要求 QWeather 原始响应时，再加 `--raw`。

## 常见错误

- `未找到配置文件` / `配置文件缺少 api_host 或 api_key`：先引导用户初始化或修复 `config.json`
- `环境变量 QWEATHER_API_HOST 和 QWEATHER_API_KEY 必须同时提供`：说明两个变量需要成对设置
- `配置文件不是合法 JSON`：提示修复配置文件格式
- `请提供且只提供一种定位方式`：城市名、`--location-id`、`--lon/--lat` 三选一
- `--lon` 和 `--lat` 必须同时提供：补齐缺失的坐标参数
- `--location-index` 超出范围：GeoAPI 返回的候选数量比用户指定的索引少
- `未找到城市或地区`：说明 GeoAPI 没找到匹配位置，建议换更精确的地名或加 `--adm` / `--range`
- `HTTP xxx` / `QWeather API 返回错误代码` / `请求失败`：优先转述状态码或错误消息，并结合 Host、Key、网络环境排查

## 维护约定

当 `qweather-cli` 新增子命令、参数、配置字段、定位规则或输出格式时，同步更新这个 skill 和仓库根目录 `README.md`。

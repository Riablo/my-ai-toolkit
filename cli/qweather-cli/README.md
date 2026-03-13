# qweather-cli

QWeather 命令行工具，基于和风天气开发服务的官方 HTTP API，支持：

- 实时天气 `now`
- 每日天气预报 `daily`
- 逐小时天气预报 `hourly`

默认按城市名查询；也支持直接传 `LocationID` 或经纬度。

## 环境要求

- macOS 或 Linux
- `python3`
- 可访问 QWeather API 的网络环境
- 你自己的 `API Host` 和 `API Key`

## 安装

```bash
# 安装本仓库所有 CLI 到 ~/.local/bin
bash scripts/install.sh
```

或者手动复制：

```bash
cp cli/qweather-cli/qweather-cli ~/.local/bin/
cp cli/qweather-cli/qweather-cli.fish ~/.config/fish/completions/
chmod +x ~/.local/bin/qweather-cli
```

## 初始化配置

QWeather 现在是每个账户独立的 API Host，所以初始化时需要同时保存 `api_host` 和 `api_key`：

```bash
qweather-cli init \
  --api-host abcxyz.qweatherapi.com \
  --api-key YOUR_API_KEY
```

配置保存到 `~/.config/qweather-cli/config.json`。

也支持用环境变量临时覆盖：

```bash
export QWEATHER_API_HOST=abcxyz.qweatherapi.com
export QWEATHER_API_KEY=YOUR_API_KEY
```

## 用法

### 实时天气

```bash
qweather-cli now 北京
qweather-cli now --city 上海 --lang zh --unit m
qweather-cli now --lon 116.41 --lat 39.92
qweather-cli now --location-id 101010100
```

### 每日天气预报

```bash
qweather-cli daily 北京
qweather-cli daily 北京 --days 7
qweather-cli daily --city 深圳 --adm 广东 --range cn --days 15
```

### 逐小时天气预报

```bash
qweather-cli hourly 北京
qweather-cli hourly 北京 --hours 72
qweather-cli hourly --lon 121.47 --lat 31.23 --hours 168
```

## 位置查询规则

- 默认把位置参数当作城市名，先调用 GeoAPI `/geo/v2/city/lookup`
- 如果一个城市名命中多个位置，默认取第 1 个，可用 `--location-index` 改
- 可用 `--adm` 和 `--range` 缩小城市查询范围
- 也可以绕过 GeoAPI，直接传 `--location-id` 或 `--lon/--lat`

## 输出

默认输出 JSON：

```json
{
  "query": {
    "type": "city",
    "city": "北京",
    "location_index": 1
  },
  "resolvedLocation": {
    "name": "北京",
    "id": "101010100"
  },
  "data": {
    "code": "200"
  }
}
```

如果希望看到 QWeather 原始响应，使用 `--raw`：

```bash
qweather-cli now 北京 --raw
```

## 配置命令

```bash
qweather-cli config show
qweather-cli config path
```

## 文档依据

当前实现对照了 QWeather 官方文档的这些页面：

- [API 配置 / 构建完整请求](https://dev.qweather.com/docs/configuration/api-config/)
- [认证方式](https://dev.qweather.com/docs/configuration/authentication/)
- [实时天气](https://dev.qweather.com/docs/api/weather/weather-now/)
- [每日天气预报](https://dev.qweather.com/docs/api/weather/weather-daily-forecast/)
- [逐小时天气预报](https://dev.qweather.com/docs/api/weather/weather-hourly-forecast/)
- [城市搜索 GeoAPI](https://dev.qweather.com/docs/api/geoapi/city-lookup/)

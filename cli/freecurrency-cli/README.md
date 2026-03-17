# freecurrency-cli

基于 [Open Exchange Rates](https://openexchangerates.org/) 的汇率 CLI，核心目标是做简单的金额换算，同时尽量节省免费额度。

## 环境要求

- macOS 或 Linux
- `python3`
- 可访问 `https://openexchangerates.org`
- 你自己的 Open Exchange Rates App ID

## 安装

```bash
# 安装本仓库所有 CLI 到 ~/.local/bin
bash scripts/install.sh
```

或者手动复制：

```bash
cp cli/freecurrency-cli/freecurrency-cli ~/.local/bin/
cp cli/freecurrency-cli/freecurrency-cli.fish ~/.config/fish/completions/
chmod +x ~/.local/bin/freecurrency-cli
```

## 初始化配置

```bash
freecurrency-cli init --app-id YOUR_APP_ID
```

也兼容旧参数名：

```bash
freecurrency-cli init --api-key YOUR_APP_ID
```

配置保存到 `~/.config/freecurrency-cli/config.json`。

也支持环境变量临时覆盖：

```bash
export OPENEXCHANGERATES_APP_ID=YOUR_APP_ID
```

如果你需要指向其他地址做调试，也可以临时覆盖 API 根地址：

```bash
export OPENEXCHANGERATES_API_BASE_URL=http://127.0.0.1:8765
```

## 用法

### 金额换算

最主要的命令：

```bash
freecurrency-cli convert 100 CNY USD
```

也兼容更接近自然语言的写法：

```bash
freecurrency-cli convert 100 CNY to USD
```

默认只输出换算后的结果：

```text
13.8 USD
```

如果想看详细信息（汇率、缓存来源、过期时间）：

```bash
freecurrency-cli convert 100 CNY USD --json
```

### 查询最新汇率

```bash
freecurrency-cli latest
freecurrency-cli latest --base CNY --currencies USD EUR
freecurrency-cli latest --base CNY --currencies USD,EUR,JPY
freecurrency-cli latest --base TWD --currencies USD CNY JPY
```

说明：

- Open Exchange Rates 免费层的上游基准货币固定为 `USD`
- 这个 CLI 会先拉取 `USD` 基准的完整汇率表，再在本地换算成任意 `--base`
- 因此 `TWD`、`CNY` 这类币种之间的换算仍然可用，不依赖上游直接提供交叉汇率

### 配置与缓存

```bash
freecurrency-cli config show
freecurrency-cli config path

freecurrency-cli cache info
freecurrency-cli cache clear
```

## 缓存机制

为了减少免费额度消耗，这个 CLI 默认对 `/latest.json` 做本地缓存：

- 缓存目录：`~/.cache/freecurrency-cli/`
- 缓存时长：30 分钟
- 缓存键：`接口路径 + 参数`

对 `convert 100 CNY USD`、`convert 100 TWD JPY`、`latest --base CNY --currencies USD EUR` 这类请求，真正访问 API 时都会复用同一份最新汇率数据：

```text
/latest.json?app_id=YOUR_APP_ID
```

因此：

- `100 CNY -> USD`
- `100 TWD -> JPY`
- `latest --base CNY --currencies USD EUR`

在 30 分钟内会尽量复用同一条缓存，不需要为每个货币对单独请求一次 API。

命中规则：

1. 先检查 `/latest.json` 的缓存文件是否存在且未过期。
2. 如果缓存可用，直接读取本地缓存，不请求 API。
3. 如果缓存不存在或已过期，再请求 API，并覆盖写回缓存。

工具会在每次请求前顺手清理已过期缓存文件，避免缓存目录无限增长。

## 文档依据

当前实现主要对照了 Open Exchange Rates 官方文档中的这些页面：

- [Authentication](https://docs.openexchangerates.org/reference/authentication)
- [Latest JSON](https://docs.openexchangerates.org/reference/latest-json)
- [Currencies JSON](https://docs.openexchangerates.org/reference/currencies-json)
- [Free plan](https://openexchangerates.org/signup/free)

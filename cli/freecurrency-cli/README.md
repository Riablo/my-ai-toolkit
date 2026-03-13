# freecurrency-cli

基于 [freecurrencyapi](https://freecurrencyapi.com/) 的汇率 CLI，核心目标是做简单的金额换算，同时尽量节省免费额度。

## 环境要求

- macOS 或 Linux
- `python3`
- 可访问 `https://api.freecurrencyapi.com`
- 你自己的 freecurrencyapi API Key

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
freecurrency-cli init --api-key YOUR_API_KEY
```

配置保存到 `~/.config/freecurrency-cli/config.json`。

也支持环境变量临时覆盖：

```bash
export FREECURRENCY_API_KEY=YOUR_API_KEY
```

如果你需要指向其他地址做调试，也可以临时覆盖 API 根地址：

```bash
export FREECURRENCY_API_BASE_URL=http://127.0.0.1:8765
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
```

### 配置与缓存

```bash
freecurrency-cli config show
freecurrency-cli config path

freecurrency-cli cache info
freecurrency-cli cache clear
```

## 缓存机制

为了减少免费额度消耗，这个 CLI 默认对 `/v1/latest` 做本地缓存：

- 缓存目录：`~/.cache/freecurrency-cli/`
- 缓存时长：30 分钟
- 缓存键：`接口路径 + 规范化参数`

对 `convert 100 CNY USD` 这类请求，真正访问 API 时只会请求：

```text
/v1/latest?base_currency=CNY&currencies=USD
```

因此：

- `100 CNY -> USD`
- `200 CNY -> USD`

在 30 分钟内会复用同一条汇率缓存，因为金额不参与缓存键。

命中规则：

1. 先根据 `base_currency` 和 `currencies` 计算缓存键。
2. 如果缓存文件存在且未过期，直接读取本地缓存，不请求 API。
3. 如果缓存不存在或已过期，再请求 API，并覆盖写回缓存。

工具会在每次请求前顺手清理已过期缓存文件，避免缓存目录无限增长。

## 文档依据

当前实现对照了 freecurrencyapi 官方文档中的这些页面：

- [Latest endpoint](https://freecurrencyapi.com/docs/latest)
- [Authentication / index](https://freecurrencyapi.com/docs/index)

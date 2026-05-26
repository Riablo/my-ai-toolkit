# pano-json

下载 720 云作品页背后的原始 JSON。

工具会读取作品页源码中的 `window.json` 字段，把相对路径拼到默认前缀 `https://player-t.720static.com/` 后面，再下载得到的 JSON 文件。

## 安装

在仓库根目录执行：

```bash
bash scripts/install.sh
```

确保 `~/.local/bin` 在 `PATH` 中，然后运行：

```bash
pano-json --help
```

## 用法

最常用写法：

```bash
pano-json eb2jkrkmkf9
pano-json https://www.720yun.com/vr/361jOztwOv1
```

默认会保存到当前目录：

```text
361jOztwOv1.json
```

指定输出文件：

```bash
pano-json https://www.720yun.com/vr/361jOztwOv1 -o tour.json
```

指定输出目录：

```bash
pano-json https://www.720yun.com/vr/361jOztwOv1 -o ./downloads/
```

只查看解析出的 JSON 下载地址：

```bash
pano-json https://www.720yun.com/vr/361jOztwOv1 --print-url
```

下载并格式化：

```bash
pano-json https://www.720yun.com/vr/361jOztwOv1 --pretty
```

输出到 stdout：

```bash
pano-json https://www.720yun.com/vr/361jOztwOv1 -o -
```

## 选项

```bash
pano-json <720yun-url|tour-id> [选项]

-o, --output <file>      输出文件路径；默认保存为 <作品ID>.json
                         传入目录时保存为 <目录>/<作品ID>.json
                         传入 - 时输出 JSON 到 stdout
    --base-url <url>     JSON 相对路径的域名前缀
                         默认: https://player-t.720static.com/
    --timeout <seconds>  请求超时时间，默认 20 秒
    --pretty             保存前格式化 JSON
    --print-url          只输出解析后的 JSON 下载地址，不下载
-h, --help               显示帮助
    --version            显示版本
```

## 抓取策略

1. 接受 `https://www.720yun.com/vr/<作品ID>` 格式的公开作品地址，也接受裸作品 ID。
2. 用浏览器 User-Agent 请求作品页源码。
3. 用和 Pano Canvas Worker 相同的正则提取 `window.json`。
4. 如果 `window.json` 是相对路径，则用 `--base-url` 的值补全。
5. 带上 `Origin`、`Referer` 和 User-Agent 下载 JSON，并在保存前校验内容是合法 JSON。

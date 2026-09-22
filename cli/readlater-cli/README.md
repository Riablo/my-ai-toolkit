# readlater-cli

一个极简 read-it-later 抓取工具：输入 URL，输出标题、简单概要和原始 URL。

对 X/Twitter 帖子会优先使用 X 官方 oEmbed 接口，尽量拿到推文正文、作者和可读标题；其他网页则读取常见的 Open Graph / Twitter Card / HTML 元信息。

## 环境要求

- macOS 或 Linux
- Python 3.10+
- 可访问目标网页和 `https://publish.x.com`

## 安装

```bash
# 安装本仓库所有 CLI 到 ~/.local/bin，并安装 zsh 补全
bash scripts/install.sh
```

## 用法

最常用写法：

```bash
readlater-cli https://x.com/jack/status/20
```

等价的显式命令：

```bash
readlater-cli fetch https://x.com/jack/status/20
```

默认输出命令行友好格式：

```text
标题：jack (@jack) on X
概要：just setting up my twttr
URL：https://x.com/jack/status/20
```

输出 JSON：

```bash
readlater-cli https://x.com/jack/status/20 --json
```

```json
{
  "url": "https://x.com/jack/status/20",
  "title": "jack (@jack) on X",
  "summary": "just setting up my twttr",
  "source": "x-oembed"
}
```

普通网页也可用：

```bash
readlater-cli https://example.com
readlater-cli https://example.com --json
```

## 选项

```bash
readlater-cli <url> --json
readlater-cli <url> --timeout 5
readlater-cli <url> --summary-length 180
```

## 抓取策略

1. X/Twitter 帖子：优先请求 `https://publish.x.com/oembed`，从返回的嵌入 HTML 中提取推文正文。
2. 普通网页：优先读取 `og:title` / `twitter:title` / `<title>` 和 `og:description` / `description` / `twitter:description`。
3. 如果没有概要元信息，则从页面正文文本中截取一段作为概要。

非 HTML 链接只读取响应头，不下载文件正文。单次响应最多读取 4 MiB（另读取 1 字节判断是否超限），解压后的正文上限为 8 MiB；超过限制会显示错误。错误响应和 X oEmbed 同样受此限制。

正文摘要最多保存 800 个文本块（包含换行）和 64 KiB 字符，避免长页面占用过多内存。只有最高优先级的标题、摘要、规范链接及站点名称都已齐全时才提前停止 HTML 解析；否则继续在下载范围内查找后续元信息。

X 帖子如果已删除、私密或受限，oEmbed 可能无法返回正文；此时工具会退回到 URL 本身，至少保留标题和链接。

## 本地回归测试

```bash
python3 cli/readlater-cli/test_main.py
```

测试使用模拟响应，不请求外部网站。

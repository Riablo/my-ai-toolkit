---
name: defuddle
description: 使用 `npx defuddle` 获取 URL 或本地 HTML 的正文，并转换成 Markdown 文档。用户提到 defuddle、要求把链接转成 Markdown、抓取网页正文、读取文章内容、导出网页为 Markdown 时使用此技能。
---

# Defuddle

使用 `npx defuddle` 获取网页或本地 HTML 的正文，并输出为 Markdown。用户没有明确指定格式时，默认产出 Markdown。

## 核心命令

```bash
npx --yes defuddle parse "<URL_OR_HTML_FILE>" --markdown
```

把 `<URL_OR_HTML_FILE>` 替换成目标网址，或本地 HTML 文件路径。

## 执行步骤

1. 先确认命令可用：

```bash
npx --yes defuddle --help
```

2. 需要确认参数时查看帮助：

```bash
npx --yes defuddle parse --help
```

3. 默认将 URL 或 HTML 转成 Markdown：

```bash
npx --yes defuddle parse "<source>" --markdown
```

4. 用户明确要求其他格式时再切换：

- HTML：`npx --yes defuddle parse "<source>"`
- JSON：`npx --yes defuddle parse "<source>" --json`
- 指定属性：`npx --yes defuddle parse "<source>" --property <name>`
- 保存到文件：追加 `--output <file>`
- 需要排查问题：追加 `--debug`

## 输出约定

- 用户要“转成 Markdown”时，直接返回 Markdown 结果；内容过长时，按上下文需要做节选或保存到文件。
- 用户要“读一下这个链接”时，先基于提取结果给出简洁摘要；用户要求全文时再提供正文。
- 用户要元数据时，优先使用 `--json` 或 `--property` 获取标题、作者、站点、发布时间等字段，再用自然语言转述。

## 失败处理

- 如果 `npx`、Node.js、网络或 `defuddle` 本身不可用，直接说明无法执行的原因。
- 如果提取失败、超时、返回空内容，或结果明显不是正文，明确告诉用户这次转换未成功。
- 不要把失败说成成功；不要把无效输出冒充正文。

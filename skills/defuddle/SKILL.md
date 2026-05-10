---
name: defuddle
description: 当用户提到 defuddle、要把网页或本地 HTML 转成 Markdown、抓取正文、读取文章内容或导出网页正文时使用。
---

# Defuddle

用 `npx defuddle` 提取 URL 或本地 HTML 的正文。用户没指定格式时，默认产出 Markdown。

## 默认做法

```bash
npx --yes defuddle parse "<source>" --markdown
```

参数或格式不确定时再看帮助：

```bash
npx --yes defuddle --help
npx --yes defuddle parse --help
```

## 何时切换输出

- 用户要 HTML：去掉 `--markdown`
- 用户要结构化元数据：用 `--json` 或 `--property <name>`
- 用户要保存到文件：加 `--output <file>`
- 用户要排查提取失败：加 `--debug`

## 输出规则

- 用户要“转成 Markdown”时，直接给 Markdown 结果；太长时可节选或落文件
- 用户要“读一下这个链接”时，先基于正文给简短摘要；只有明确要求全文时再展开
- 用户要标题、作者、站点、发布时间等元数据时，优先走 `--json` 或 `--property`

## 关键 gotchas

- `defuddle` 提取失败、超时、返回空内容，或结果明显不是正文时，要明确说这次转换失败
- 不要把导航栏、评论区或乱码输出冒充正文
- 如果 `npx`、Node.js、网络或包本身不可用，直接说明卡在哪一层

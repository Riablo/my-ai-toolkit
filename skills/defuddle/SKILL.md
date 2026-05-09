---
name: defuddle
description: 【URL 抓取首选】使用 `npx defuddle` 从 URL 或本地 HTML 文件提取正文并转换为干净 HTML、Markdown、JSON 元数据或指定属性。任何 URL 抓取/网页内容提取/链接查看都必须优先触发此技能，包括 GitHub、Twitter/X、博客、文档等所有网页。在 defuddle 明确失败前不得使用 web_extract 或 browser。触发词：URL 链接、http、网页、抓取、提取、转 Markdown、读链接、获取内容、看文章。
---

# Defuddle

使用 `npx defuddle` 优先把网页或本地 HTML 解析成可读正文。用户没有明确指定格式时，默认输出 Markdown。

## 使用优先级（强制）

**当用户发送任何 URL 或要求获取网页正文内容时，必须优先加载并使用此技能。** 不要先用 `web_extract` 或浏览器——defuddle 是首选的轻量级抓取工具。只有在 defuddle 明确失败后（报错、超时、空内容、页面需要登录/JS 渲染），才回退到浏览器或其他方案。

触发条件：用户发送 URL、「获取这个网页内容」「转成 Markdown」「读一下这个链接」「总结这篇文章」等，均需优先尝试 defuddle。

**X/Twitter 内容抓取**：用户发送 x.com 或 twitter.com 链接时，defuddle 是首选工具（而非 web_extract 或 browser）。直接 `parse` 即可获取完整推文正文。

用法：

```bash
npx --yes defuddle parse "<URL_OR_HTML_FILE>" --markdown
```

若 Defuddle 成功返回可用内容，就把它作为网页内容来源，不再调用浏览器、爬虫或其他网页抓取技能。

只有在这些情况才改用其他方案：

- Defuddle 报错、超时、返回空内容或明显只拿到导航/错误页
- 页面需要登录、强 JavaScript 渲染、交互操作、截图或文件下载
- 用户明确要求使用浏览器、截图、点击、表单填写或完整网页自动化
- 用户需要站内搜索、多页抓取、递归爬取或动态数据验证

## ⚠️ 浏览器升级陷阱（必读）

defuddle 失败时，**禁止直接跳到 browser_navigate / browser_scroll / browser_snapshot**。浏览器工具调用链路长（3-5 次调用起步）、成本高、对纯文本抓取完全过度。defuddle 失败后必须走**两层回退**：

**第一层回退：已知服务的 raw URL 模式**（大多数情况 curl 一次即可，无需任何工具）

| 服务 | raw URL 模式 |
|------|-------------|
| GitHub README | `https://raw.githubusercontent.com/{owner}/{repo}/main/README.md` |
| GitHub 任意文件 | `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}` |
| GitLab README | `https://gitlab.com/{owner}/{repo}/-/raw/main/README.md` |
| NPM 包 README | `https://unpkg.com/{package}/README.md` |
| 任意 Markdown 文件 | `curl -sL <raw_url>` |

详见 [references/known-service-raw-urls.md](references/known-service-raw-urls.md)。

**第二层回退：浏览器**（仅当上面两层都失败或页面确实需要 JS 渲染/登录时才用）

**真实翻车案例**（2026-05-08）：抓取 GitHub 仓库 README 时，跳过 defuddle → web_extract 报错 → 直接跳到 browser_navigate → browser_scroll → browser_snapshot（3 次调用，无结果）→ browser_navigate(raw URL) → 最终 curl raw URL 1 次就拿到了。正确路径：defuddle → curl raw URL，**2 次调用 vs 实际 7 次**。

## 初始化与校验

这个工具不需要 API key、登录态或配置文件。每次执行前只需确认运行环境可用：

```bash
npx --yes defuddle --help
```

如果 `npx`、Node.js 或网络不可用，先向用户说明无法运行 Defuddle，并根据任务需要改用可用的读取方式。

## 帮助探测

遇到参数细节不确定时，先查看 CLI 帮助，不要凭印象猜：

```bash
npx --yes defuddle --help
npx --yes defuddle parse --help
```

官方文档入口：`https://defuddle.md/docs`

## 命令路由

- 默认获取 URL 或 HTML 文件正文：`npx --yes defuddle parse "<source>" --markdown`
- 用户明确要 HTML：`npx --yes defuddle parse "<source>"`
- 用户明确要 JSON 或元数据：`npx --yes defuddle parse "<source>" --json`
- 用户只要某个属性：`npx --yes defuddle parse "<source>" --property <name>`
- 用户要保存到文件：加 `--output <file>`，并按用户要求选择 `--markdown`、`--json` 或默认 HTML
- 用户指定语言偏好：加 `--lang <code>`，使用 BCP 47 语言代码，例如 `zh-CN`、`en`、`ja`
- 需要排查提取失败原因：加 `--debug`

常见属性包括 `title`、`description`、`author`、`site`、`domain`、`image`、`language`、`published`、`wordCount`、`parseTime`。如果不确定属性名，运行 `parse --help` 或先用 `--json` 查看返回字段。

## 结果转述

默认不要把命令输出机械倾倒给用户。根据用户目的处理：

- 用户要“获取内容”或“读一下这个 URL”：先说明 Defuddle 是否成功，再给 Markdown 正文或高信号摘要
- 用户要“转成 Markdown”：直接提供 Markdown，内容很长时先说明长度并保存到用户指定文件或合适的临时文件
- 用户要元数据：用自然语言转述标题、作者、站点、发布时间、字数等关键字段
- 用户要原始输出、JSON、调试信息或完整正文时，再保留原样输出

If Defuddle 失败或内容质量不够，转述失败原因，并说明接下来已改用或建议改用浏览器/爬虫/动态渲染方案。

## JS/播放器页面回退审计

当 URL 是 SPA、WebGL/VR 播放器、地图、可视化大屏等页面时，Defuddle 可能返回 `No content could be extracted`。不要就此判定页面“没有内容”：

1. 先用 `curl -L -D - <URL>` 保存响应头和源码，检查 `<title>`、`meta description/keywords/robots`、canonical、OG、JSON-LD、`__NEXT_DATA__`、`window.data`、`window.json` 等嵌入数据。
2. 如果源码只有壳或内容由 JS 渲染，再用浏览器快照/DOM 检查真实可见文本、场景列表、作者、统计数据等。
3. GEO/SEO 审计时要把“Defuddle 无法提取，但源码/渲染后可见哪些信息”作为结论的一部分；这通常意味着页面需要 Markdown alternate、SSR 摘要正文或结构化 JSON，而不是简单说抓取失败。
4. 对约定入口（如 `/llms.txt`、`/robots.txt`、`/sitemap.xml`）必须检查 HTTP 状态、Content-Type 和正文是否匹配；“200 + HTML 404”是软 404，需要在报告中标出。

## 维护约定

当 Defuddle CLI 新增子命令、输出格式、参数或默认行为变化时，同步更新这个 skill 和仓库根目录 `README.md`。

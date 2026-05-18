# 飞书云文档读写

从官方 `lark-doc` skill 中抽取的个人常用子集：读取已有文档、在末尾追加内容、按 block 精确编辑。不要把这个 reference 扩展成完整飞书文档手册。

## 适用范围

- 接受用户明确给出的 `/docx/<token>`、`/wiki/<token>` URL 或文档 token
- 支持读取、总结、末尾追加、小范围替换/插入/删除
- 不负责云空间搜索、表格、多维表格、评论、权限申请或批量迁移

## 必查命令

```bash
lark-cli docs +fetch --api-version v2 --help
lark-cli docs +update --api-version v2 --help
```

所有 `docs +fetch` 和 `docs +update` 都固定带 `--api-version v2`。默认 user 身份；除非用户明确要求 bot 身份，不要加 `--as bot`。

注意：当前 `lark-cli docs +update` 不支持 `--format`，不要把 `docs +fetch --format json` 的参数照搬过去。

## URL 与 token

`--doc` 可以直接接收完整 URL 或 token：

```bash
lark-cli docs +fetch --api-version v2 --doc "https://example.feishu.cn/docx/xxxx?from=copy"
lark-cli docs +fetch --api-version v2 --doc "BZEpdHcHuo5RZBxig67cHEtHnng"
```

URL 带查询参数时直接传入即可。不要手写正则拆 token，除非 CLI 明确报 URL 解析失败。

## 读取

结构未知时先看目录：

```bash
lark-cli docs +fetch --api-version v2 --doc "<doc>" --scope outline --max-depth 3
```

只读正文或总结：

```bash
lark-cli docs +fetch --api-version v2 --doc "<doc>" --doc-format markdown
```

准备精确编辑时获取 block id：

```bash
lark-cli docs +fetch --api-version v2 --doc "<doc>" --detail with-ids
```

文档很长时优先局部读取：

```bash
lark-cli docs +fetch --api-version v2 --doc "<doc>" --scope keyword --keyword "关键词1|关键词2" --detail with-ids
lark-cli docs +fetch --api-version v2 --doc "<doc>" --scope section --start-block-id "<heading_id>" --detail with-ids
lark-cli docs +fetch --api-version v2 --doc "<doc>" --scope range --start-block-id "<start_id>" --end-block-id "<end_id>" --detail with-ids
```

## 写入

末尾追加优先用 `append`，不需要先取 block id：

```bash
lark-cli docs +update --api-version v2 --doc "<doc>" --command append \
  --content '<h2>标题</h2><p>正文</p>'
```

在指定块后插入：

```bash
lark-cli docs +update --api-version v2 --doc "<doc>" --command block_insert_after \
  --block-id "<block_id>" \
  --content '<p>新段落</p>'
```

替换指定块：

```bash
lark-cli docs +update --api-version v2 --doc "<doc>" --command block_replace \
  --block-id "<block_id>" \
  --content '<p>替换后的内容</p>'
```

简单文本替换：

```bash
lark-cli docs +update --api-version v2 --doc "<doc>" --command str_replace \
  --pattern "旧文本" --content "新文本"
```

## 内容格式

默认 XML。标签保持原样，只转义标签内部文本里的特殊字符：

- `<` -> `&lt;`
- `>` -> `&gt;`
- `&` -> `&amp;`
- 换行 -> `<br/>`

常用 XML：

```xml
<h2>标题</h2>
<p>普通段落</p>
<ul><li>要点 1</li><li>要点 2</li></ul>
<blockquote>引用</blockquote>
<pre lang="bash"><code>echo hello</code></pre>
```

仅当用户提供 Markdown 文件、明确要求 Markdown，或需要 Markdown 的跨行 `str_replace` 时，才加 `--doc-format markdown`。长文本、多行或包含特殊字符时，优先用 heredoc/stdin：

```bash
lark-cli docs +update --api-version v2 --doc "<doc>" --command append --doc-format markdown --content - <<'EOF'
## 标题

正文
EOF
```

## 高风险操作

- `overwrite` 会清空后重写整篇文档，可能丢失图片、评论、画板和嵌入资源；只有用户明确要求全文重建时才用
- `block_delete` 会删除指定块；执行前必须确认 block id 来自本次读取结果
- `str_replace` 在 XML 模式下只适合行内匹配；跨段落或容器级改动优先用 block 操作
- 文档中出现 `<sheet>`、`<bitable>`、`<whiteboard>` 等资源块时，不要用文档写入命令直接改内部内容

## 验证

写入后至少做一次轻量验证：

```bash
lark-cli docs +fetch --api-version v2 --doc "<doc>" --scope keyword --keyword "刚写入的关键词"
```

若返回 `_notice.update`，当前任务完成后提醒用户 `lark-cli` 有新版本，不要中断当前写入流程去升级。

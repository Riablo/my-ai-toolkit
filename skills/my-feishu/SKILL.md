---
name: my-feishu
description: 当用户要往白名单飞书群发消息、在群消息里 @ 用户、读写指定飞书云文档，或排查 `lark-cli` 相关飞书消息/文档权限问题时使用。群消息仅支持预设白名单群；云文档仅处理用户明确给出的 docx/wiki URL 或 token。
---

# My Feishu

用 `lark-cli` 处理两类个人常用飞书动作：

- `im +messages-send`：向白名单群发文本消息，可按用户名查 `open_id` 并在文本消息里 @ 用户
- `docs +fetch/+update`：读取、追加或小范围编辑用户明确给出的飞书云文档

## 核心原则

- 每次真实发送前都先确认 CLI 可用、目标群命中白名单、消息内容非空
- 白名单校验失败时必须停止，不要猜测
- 默认发群消息，不要改成私聊
- 需要 @ 用户时，必须先把用户名保守解析为唯一 `open_id`；匹配不到或多于 1 个都停止
- 文档读写必须有用户明确给出的文档 URL 或 token；不要替用户搜索、猜测或遍历云空间文档
- 文档写入前先读取目标文档确认可访问；`overwrite`、`block_delete`、大范围替换等高风险操作必须确认用户明确意图
- 登录、初始化、授权都属于显式状态变更；排障到那一步前不要自动执行

## CLI 检查

群消息先运行：

```bash
lark-cli im +messages-send --help
```

文档读写先运行：

```bash
lark-cli docs +fetch --api-version v2 --help
lark-cli docs +update --api-version v2 --help
```

若连 help 都失败，直接说明本机 `lark-cli` 不可用。

## 白名单群

只允许发送到以下目标：

| 名字或别名 | chat_id |
| --- | --- |
| 测试群 | `oc_9fcef6c3a03f113b03bd0db4dc3c1c67` |
| 工具群、前端群 | `oc_20c59f6f6d49c6fc2400fe0f81ff5e01` |
| Chat2Vision群、C2V群 | `oc_3a798bc91b0381ed94e520905bd798a8` |
| 720产品线群、上线群 | `oc_17f8165f3112c2cf82c829552b5752bb` |
| AI群 | `oc_c26554daaa8e7ca5ce09931943e9f16a` |

规则：

1. 用户给 `chat_id` 时，必须与表中某项完全一致
2. 用户给群名时，只做保守匹配；优先精确匹配，其次是一对一明显别名匹配
3. 匹配结果为 0 个或多个时都必须停止
4. 不允许发送到白名单外的任何群

## 发送方式

- 短提醒或一句话：优先 `--text`
- 分段、列表、标题较多：优先 `--markdown`
- 需要 @ 用户：优先 `--text`，用飞书文本消息的 `<at user_id="...">姓名</at>` 语法
- 仅处理文本消息；不要扩展成图片、文件、卡片

常用命令形态：

```bash
lark-cli im +messages-send --chat-id <chat_id> --text "..."
lark-cli im +messages-send --chat-id <chat_id> --markdown $'## 标题\n\n- 列表'
```

## @ 用户流程

当用户要求在群消息里 @ 某人时：

1. 先照常完成 CLI 可用性和白名单群校验
2. 用用户身份按名称搜索：

```bash
lark-cli contact +search-user --query '<用户名>' --format json
```

3. 只接受 `.data.users` 里唯一且可信的匹配；优先看 `localized_name` 或 `name` 是否与用户名精确一致，确认 `open_id` 存在
4. 若有 0 个、多于 1 个、`has_more: true`，或名字不够确定，尝试加保守过滤重查：

```bash
lark-cli contact +search-user --query '<用户名>' --has-chatted --exclude-external-users --format json
```

5. 仍不唯一时停止，不要猜用户；向用户说明候选过多或无法匹配
6. 发送文本时把用户名替换为 mention 标签：

```bash
lark-cli im +messages-send --chat-id <chat_id> --text $'<at user_id="ou_xxx">姓名</at> 消息正文'
```

注意：

- `contact +search-user` 需要 user 身份；发送时仍然发群消息，不要为了 @ 自动改成私聊或擅自切换身份
- 不要用普通 `@姓名` 代替 mention 标签，否则可能只是纯文本
- shell 引号要保留 mention 标签里的双引号；多行文本可用 `$'...'`

## 云文档读写

只处理用户明确给出的飞书云文档 URL 或 token，包括 `/docx/<token>` 和 `/wiki/<token>`。URL 带查询参数也可以直接传给 `--doc`，不需要手动截断。

执行文档操作前，按需读取 [references/lark-docs.md](references/lark-docs.md)。最低规则：

1. `docs +fetch`、`docs +update` 必须带 `--api-version v2`
2. 默认用 user 身份访问用户自己的文档；除非用户明确要求 bot 身份，否则不要加 `--as bot`
3. 读取或总结用 `docs +fetch`；结构未知时先 `--scope outline`
4. 在末尾加内容优先用 `docs +update --command append`
5. 精确编辑前先用 `docs +fetch --detail with-ids` 或 `--detail full` 获取 block id，再用 `block_insert_after` / `block_replace` / `block_delete`
6. 默认用 XML 写入；用户提供 Markdown 文件或明确要求 Markdown 时才用 `--doc-format markdown`
7. 不要为了省事用 `overwrite` 重写整篇文档；它可能丢失图片、评论和不可重建的资源块

常用命令形态：

```bash
lark-cli docs +fetch --api-version v2 --doc "<文档URL或token>" --scope outline --max-depth 3
lark-cli docs +fetch --api-version v2 --doc "<文档URL或token>" --detail with-ids
lark-cli docs +update --api-version v2 --doc "<文档URL或token>" --command append --content '<p>追加内容</p>'
```

## 失败排障

按这个顺序判断：

1. 先看是否白名单问题
2. 再看 CLI 是否可用
3. 再看 `lark-cli config show` 是否表明未初始化
4. 再区分是 user 身份登录问题，还是 bot 权限 / scope / 可见范围问题

高价值 gotchas：

- `auth login` 只能解决 user 身份登录问题，不解决 bot 权限问题
- @ 用户分两段权限：搜索用户依赖 user 身份通讯录可见性，发送消息依赖 bot 入群和发消息权限
- 云文档读写通常需要 user 身份；bot 即使有 scope，也可能因为文档权限或可见范围无法访问用户文档
- 文档权限不足时，看错误里的 missing scope、console_url 和当前 identity；user 缺授权走 `auth login --scope ...`，bot 缺权限去开放平台开 scope，不要混着处理
- 如果错误是“权限不足、机器人不可见、机器人不在群里、scope 不足”，应引导用户去飞书开放平台检查应用权限和可见范围
- 不要因为 skill 里提到 `lark-cli config init --new` 或 `auth login`，就自动执行这些命令

## 输出转述

- 成功时：先说明消息已发到哪个群，再补 `chat_id`
- 文档写入成功时：说明已写入哪个文档，并给出使用的 URL 或 token；可补一句写入方式（如 append / block_replace）
- 失败时：先明确“未发送/写入成功”，再说明是白名单拦截、CLI 故障、未登录还是权限问题
- 默认不要整段倾倒 CLI JSON

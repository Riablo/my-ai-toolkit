---
name: my-feishu
description: 当用户要往白名单飞书群发消息，或排查 `lark-cli` 为什么发不到指定群时使用。仅支持预设群聊；目标群匹配不到、不唯一或不在白名单中时必须停止。
---

# My Feishu

用 `lark-cli im +messages-send` 向白名单群发消息。这个 skill 只处理群文本消息，不扩展到发现新群、私聊、卡片或群管理。

## 核心原则

- 每次真实发送前都先确认 CLI 可用、目标群命中白名单、消息内容非空
- 白名单校验失败时必须停止，不要猜测
- 默认发群消息，不要改成私聊
- 登录、初始化、授权都属于显式状态变更；排障到那一步前不要自动执行

## CLI 检查

先运行：

```bash
lark-cli im +messages-send --help
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
- 仅处理文本消息；不要扩展成图片、文件、卡片

常用命令形态：

```bash
lark-cli im +messages-send --chat-id <chat_id> --text "..."
lark-cli im +messages-send --chat-id <chat_id> --markdown $'## 标题\n\n- 列表'
```

## 失败排障

按这个顺序判断：

1. 先看是否白名单问题
2. 再看 CLI 是否可用
3. 再看 `lark-cli config show` 是否表明未初始化
4. 再区分是 user 身份登录问题，还是 bot 权限 / scope / 可见范围问题

高价值 gotchas：

- `auth login` 只能解决 user 身份登录问题，不解决 bot 权限问题
- 如果错误是“权限不足、机器人不可见、机器人不在群里、scope 不足”，应引导用户去飞书开放平台检查应用权限和可见范围
- 不要因为 skill 里提到 `lark-cli config init --new` 或 `auth login`，就自动执行这些命令

## 输出转述

- 成功时：先说明消息已发到哪个群，再补 `chat_id`
- 失败时：先明确“未发送成功”，再说明是白名单拦截、CLI 故障、未登录还是权限问题
- 默认不要整段倾倒 CLI JSON

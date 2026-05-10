# Vault Rules

## 核心规则

1. 使用 `categories` 属性，不使用 Obsidian 标签系统
2. 类别值使用大写开头格式，如 `Dev Notes`、`AI Prompts`
3. 新笔记优先用 `Templates/` 下模板创建
4. 新建笔记默认放 `Inbox/`；Daily Notes 例外，直接放 `Library/`
5. 文件名即标题；正文不需要 H1，正文内最高 H2
6. 日期统一 `YYYY-MM-DD`
7. YAML 数组使用多行格式，每项单独一行

## 笔记类别

### 随手记

- `Ideas`
- `Issues`
- `Memos`
- `Daily Notes`

### 笔记类

- `Dev Notes`
- `Life Hacks`
- `Config Notes`
- `AI Prompts`
- `Gaming Notes`
- `Prompting Logs`
- `Articles`

### 项目类

- `Repos`
- `Projects`
- `Releases`

### 记录类

- `Music Logs`
- `Movie Logs`
- `TV Series Logs`
- `Purchase Logs`

### Things

- `Games`
- `Apps`
- `Dev Libs`
- `Services`
- `Online Tools`
- `Devices`
- `Plugins`
- `Operating Systems`

### 实体

- `People`
- `Groups`

### 其它

- `Topics`
- `Years`

## 评分系统

记录类笔记使用：

- `💎💎` 完美
- `💎` 极佳
- `⭐⭐⭐` 不错
- `⭐⭐` 普通
- `⭐` 无感
- `👎` 非常差

## Vault 目录

```text
VAULT_PATH/
├── Attachments/
├── Bases/
├── Inbox/
├── Library/
└── Templates/
```

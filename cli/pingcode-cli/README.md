# pingcode-cli

通过 PingCode 官方 REST API 查询和更新分配给自己的 bug。

## 依赖

- bash 5.0+
- curl
- jq
- date、stat（系统自带）

## 初始化与鉴权

```bash
# 交互输入 client_id、client_secret、my_assignee_id，
# 并选择是否设置全局 created_at 起点
pingcode-cli config init

# 脱敏查看配置 / 显示配置文件路径
pingcode-cli config show
pingcode-cli config path

# 按本机时区 2025-01-22 零点转换为 Unix 秒数，保存到 created_after
pingcode-cli config set-created-after 2025-01-22

# 输出授权地址，等待手动输入 code
pingcode-cli auth

# 检查依赖、配置、项目缓存、令牌和 API
pingcode-cli doctor
```

配置保存在 `~/.config/pingcode-cli/config.json`，权限为 `600`。`access_token`
过期后会自动使用 `refresh_token` 刷新；刷新失败时重新输出授权地址并等待新的
`code`。设置 `XDG_CONFIG_HOME` 时，配置位于该目录的 `pingcode-cli/config.json`。
`config` 不带子命令等同于 `config show`，隐藏 `client_secret`、`access_token` 和
`refresh_token`；日期设置仅支持有效的 `YYYY-MM-DD`，无效输入不会改写配置。

`doctor` 检查 Bash 版本、依赖、配置字段及 `600` 权限、项目缓存和令牌本地有效期，
再用只读项目请求检查 API 连通性及项目读取权限。任一检查失败返回非零退出码；
不会自动刷新缓存、令牌或触发交互授权。首次使用先运行 `auth` 和 `projects refresh`。

## 项目缓存

```bash
# 首次使用时自动获取；输出当前缓存
pingcode-cli projects

# 手动刷新全部项目
pingcode-cli projects refresh
```

配置只缓存项目的 `id`、`name`，刷新时不请求状态。旧配置中的 `states` 不再读取，
下次 `projects refresh` 会移除它们。项目名称继续提供 zsh 与 Fish 自动补全，
仅在补全项目参数时读取缓存。

每次命令会校验一次配置并共享鉴权快照；令牌刷新后，同一命令的后续请求会
立即使用新令牌。分页响应使用临时文件累积，按 ID 检查分页是否前进，并在
最后合并去重，避免大型描述触发系统命令行参数长度限制。临时文件在命令结束时清理。

## Bug

```bash
# 跨项目查询新提交、重新打开的 bug
pingcode-cli bugs

# 只查询指定项目
pingcode-cli bugs --project '项目名称'

# 临时覆盖全局 created_at 起点
pingcode-cli bugs --project '项目名称' --created-after 1735689600

# 获取单个 bug，附带 comments（参数是 API 返回的 id）
pingcode-cli bug 5edca112b06305c524cad2fa

# 独立获取评论
pingcode-cli comments 5edca112b06305c524cad2fa

# 通过编号菜单选择状态
pingcode-cli set-state 5edca112b06305c524cad2fa

# 直接指定状态，一次完成
pingcode-cli set-state 5edca112b06305c524cad2fa --state '已修复'
```

`set-state` 使用代码内固定的七个状态：已拒绝、重新打开、已修复、新提交、挂起、
已发布、处理中。省略 `--state` 时每行显示一个状态，输入编号并回车提交；
直接回车或按 Ctrl-D 取消，不会修改状态。指定 `--state` 时无需交互选择；两种方式都直接发送更新请求，
不再先查询 bug 详情、项目或状态列表。非法状态不会发送请求。

`bugs` 固定按新提交（`5f3a1c2fc2742c538a7dcbcb`）、重新打开
（`5f3a1c2fc2742c17f27dcbce`）两个状态查询分配给自己的 bug，不再接受 `--state`。
省略 `--project` 时直接调用 API 跨项目查询，不依赖项目缓存；两个状态各请求一次，
有后续分页时再继续获取。指定项目时才从缓存解析项目名称。

`bugs` 和 `bug` 只保留 `id`、`identifier`、`title`、`html_url`、`description`，
以及字符串字段 `state`、`project`（名称）、`assignee`、`created_by`（display_name，
缺失时为空字符串）。`is_archived = 1` 或 `is_deleted = 1` 的 bug 被过滤；
单项查询被过滤时返回 `null`，也不请求评论。

列表和单项查询先过滤已归档、已删除的 bug，列表再按 `created_at > 时间戳` 过滤，
之后只为保留项的 `description` 图片 URL 拼接临时访问 token。token 随工作项 API
响应返回，本地处理不会请求或下载图片。

`comments` 只请求第一页（30 条），返回过滤掉 `is_deleted = 1` 后的数组，每条只含
`id`、`content`、`created_by`（display_name 字符串）。`bug` 将同一数组附加为
`comments` 字段；评论请求失败会使整个命令失败，`bugs` 列表不请求评论。

## API 文档

- [PingCode REST API 索引](https://pingcode.apifox.cn/llms.txt)
- [获取/刷新用户令牌](https://pingcode.apifox.cn/api-101722142.md)
- [项目与工作项 API](https://pingcode.apifox.cn/api-101826052.md)
- [获取工作项列表与可选项目过滤](https://pingcode.apifox.cn/api-115142016.md)

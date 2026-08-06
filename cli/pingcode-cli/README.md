# pingcode-cli

通过 PingCode 官方 REST API 查询和更新分配给自己的 bug。

## 依赖

- bash 5.0+
- curl
- jq

## 初始化与鉴权

```bash
# 交互输入 client_id、client_secret、my_assignee_id，
# 并选择是否设置全局 created_at 起点
pingcode-cli init

# 输出授权地址，等待手动输入 code
pingcode-cli auth
```

配置保存在 `~/.config/pingcode-cli/config.json`，权限为 `600`。`access_token`
过期后会自动使用 `refresh_token` 刷新；刷新失败时重新输出授权地址并等待新的
`code`。

## 项目缓存

```bash
# 首次使用时自动获取；输出当前缓存
pingcode-cli projects

# 手动刷新全部项目及各项目的 bug 状态
pingcode-cli projects refresh
```

配置只缓存项目和状态的 `id`、`name`。项目名称和状态名称会从这份缓存提供 zsh
与 Fish 自动补全。

## Bug

```bash
# 查询项目内全部状态
pingcode-cli bugs --project '项目名称'

# 一个或多个状态：CLI 分别请求后合并去重
pingcode-cli bugs --project '项目名称' --state '新提交' --state '处理中'

# 临时覆盖全局 created_at 起点
pingcode-cli bugs --project '项目名称' --created-after 1735689600

# 获取单个 bug（参数是 API 返回的 id）
pingcode-cli bug 5edca112b06305c524cad2fa

# 按当前项目缓存中的状态名称更新
pingcode-cli set-state 5edca112b06305c524cad2fa '已修复'
```

命令输出 JSON，只保留 `id`、`identifier`、`title`、`html_url`、`state` 和
`description`。列表的时间过滤使用 `created_at > 时间戳`。

## API 文档

- [PingCode REST API 索引](https://pingcode.apifox.cn/llms.txt)
- [获取/刷新用户令牌](https://pingcode.apifox.cn/api-101722142.md)
- [项目与工作项 API](https://pingcode.apifox.cn/api-101826052.md)

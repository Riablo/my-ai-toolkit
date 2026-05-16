# jenkins-builder-cli

Jenkins 构建命令行工具。Jenkins jobs 从接口实时获取，本地配置只保存连接信息，以及少量常用 job 的标签和别称。

支持：

- 实时列出当前账号可见且可构建的 jobs
- 给常用 job 标注“测试服”或“正式服”，未标注的显示为“未分类”
- 给常用 job 设置多个别称，方便命令行或 AI 通过约定俗成的叫法触发构建
- 直接触发构建，或不传 job 时从编号列表中交互选择
- 对经典 Git job 修改 Branch Specifier
- 查看运行中的构建、查询构建状态、停止构建、查看 console output

## 安装

本仓库根目录执行：

```bash
bash scripts/install.sh
```

确保 `~/.local/bin` 在 PATH 中，然后运行：

```bash
jenkins-builder-cli --help
```

## 依赖

- [uv](https://docs.astral.sh/uv/)
- Python 3.10+
- Jenkins API Token

## 初始化

首次配置：

```bash
jenkins-builder-cli config init
```

也可以非交互式写入：

```bash
jenkins-builder-cli config init \
  --url "https://jenkins.example.com" \
  --username "alice" \
  --token "your-token"
```

配置文件位置：

```bash
jenkins-builder-cli config path
jenkins-builder-cli config check
```

默认会写到：

```text
~/.config/jenkins-builder-cli/config.yaml
```

## 配置文件示例

```yaml
jenkins:
  url: "https://jenkins.example.com"
  username: "alice"
  token: "xxxx"
  verify_ssl: true

defaults:
  timeout_seconds: 1200
  poll_interval_seconds: 5

jobs:
  "folder/test.frontend_build":
    label: test
    aliases:
      - 前端测试
      - 测试前端
      - frontend test

  "folder/frontend_build":
    label: prod
    aliases:
      - 前端正式
      - 正式前端
      - frontend prod
```

`jobs` 是稀疏配置，不需要把所有 Jenkins jobs 手动加进去。只有需要标签或别称的常用 job 才需要配置。

## 用法

列出所有可构建 jobs：

```bash
jenkins-builder-cli jobs list
```

按 job 名称、标签或别称过滤：

```bash
jenkins-builder-cli jobs list --query frontend
jenkins-builder-cli jobs list --query 测试服
jenkins-builder-cli jobs list --query 前端正式
```

给 job 标注环境：

```bash
jenkins-builder-cli jobs label "folder/test.frontend_build" test
jenkins-builder-cli jobs label "folder/frontend_build" prod
jenkins-builder-cli jobs unlabel "folder/frontend_build"
```

管理别称：

```bash
jenkins-builder-cli jobs alias add "folder/test.frontend_build" 前端测试
jenkins-builder-cli jobs alias add "folder/test.frontend_build" "frontend test"
jenkins-builder-cli jobs alias rm "folder/test.frontend_build" 前端测试
jenkins-builder-cli jobs alias list
```

不带参数直接从列表中选并构建：

```bash
jenkins-builder-cli build
```

按 job name 或唯一别称触发构建：

```bash
jenkins-builder-cli build "folder/test.frontend_build"
jenkins-builder-cli build 前端测试
```

修改 Branch Specifier：

```bash
jenkins-builder-cli set-branch "folder/test.frontend_build" feature/login
jenkins-builder-cli set-branch 前端测试 feature/login
```

先切分支再构建：

```bash
jenkins-builder-cli set-branch 前端测试 feature/login
jenkins-builder-cli build 前端测试
```

查看运行中的构建：

```bash
jenkins-builder-cli runs list
```

查询某次构建状态：

```bash
jenkins-builder-cli runs status "folder/test.frontend_build#123"
```

停止构建：

```bash
jenkins-builder-cli runs stop "folder/test.frontend_build#123"
```

查看日志：

```bash
jenkins-builder-cli logs "folder/test.frontend_build#123" --tail 100
```

持续跟随日志：

```bash
jenkins-builder-cli logs "folder/test.frontend_build#123" --follow
```

JSON 输出：

```bash
jenkins-builder-cli jobs list --json
jenkins-builder-cli build "folder/test.frontend_build" --json
jenkins-builder-cli runs list --json
jenkins-builder-cli runs status "folder/test.frontend_build#123" --json
```

## 行为说明

- `jobs list` 每次都会实时请求 Jenkins，不使用本地 jobs 缓存
- `jobs list` 的 `BRANCH` 列显示 Jenkins 当前 job 配置里的真实 Branch Specifier；如果不是经典 Git job 或无法唯一解析，则显示 `-`
- `build <ref>` 和 `set-branch <ref>` 先精确匹配 Jenkins job name，再匹配本地 aliases
- alias 必须唯一；如果多个 job 配置了同一个 alias，命令会拒绝执行并列出候选
- 不支持 `build 12` 这种数字参数；只有 `build` 交互列表里可以输入序号
- `build` 始终调用 Jenkins 的普通 `build` 接口；如果要发布特定分支，请先用 `set-branch` 修改 Branch Specifier，再执行 `build`
- `runs status <run-id>` 适合做轮询；`status` 会统一返回这些值之一：`running`、`completed`、`failed`、`aborted`、`unstable`、`not_built`、`unknown`
- `runs status` 同时保留 Jenkins 原始 `result` 字段；常见值有 `SUCCESS`、`FAILURE`、`ABORTED`、`UNSTABLE`、`NOT_BUILT`
- `set-branch` 传入分支名时会自动补成 `*/xxx`；如果你已经自己传了 `*/` 前缀，就保持原样
- `set-branch` 是持久修改，不会在构建后自动恢复
- `set-branch` 只支持经典 Git job；遇到 Pipeline / Multibranch / 多个 Branch Specifier 时会拒绝执行

## 权限要求

至少需要 Jenkins 中的以下权限：

- `Job/Read`
- `Job/Build`
- `Job/Cancel`（停止构建）
- `Job/Configure`（修改 Branch Specifier）

# jenkins-builder-cli

Jenkins 构建命令行工具。支持：

- 实时列出当前账号可见且可构建的 jobs
- 给 job 配置测试/正式环境、自然语言描述和别名
- 直接触发构建
- 对经典 Git job 直接修改 Branch Specifier
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
    env: test
    description: "测试服前端项目"
    aliases: ["前端测试服", "frontend test"]

  "folder/frontend_build":
    env: prod
    description: "正式服前端项目"
    aliases: ["前端正式服", "frontend prod"]
```

## 用法

列出所有可构建 jobs：

```bash
jenkins-builder-cli jobs list
```

只看本地做过元数据配置的 jobs：

```bash
jenkins-builder-cli jobs list --configured
```

给 job 配置元数据：

```bash
jenkins-builder-cli jobs set-meta "folder/test.frontend_build" \
  --env test \
  --desc "测试服前端项目" \
  --alias "前端测试服" \
  --alias "frontend test"
```

删除某个 job 的本地元数据：

```bash
jenkins-builder-cli jobs rm-meta "folder/test.frontend_build"
```

不带参数直接从列表中选并构建：

```bash
jenkins-builder-cli build
```

按 job name 触发构建：

```bash
jenkins-builder-cli build "folder/test.frontend_build"
```

测试服先切分支再构建：

```bash
jenkins-builder-cli branch set "folder/test.frontend_build" feature/login
jenkins-builder-cli build "folder/test.frontend_build"
```

查看当前 Branch Specifier：

```bash
jenkins-builder-cli branch show "folder/test.frontend_build"
```

直接修改 Branch Specifier：

```bash
jenkins-builder-cli branch set "folder/test.frontend_build" feature/login
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
- 所有命令行里的 `job_ref` 都只接受唯一的 Jenkins job name；`alias` 和 `description` 只作为 AI 侧元数据保留，不参与 CLI 参数解析
- `build` 始终调用 Jenkins 的普通 `build` 接口；如果要发布特定分支，请先用 `branch set` 修改 Branch Specifier，再执行 `build`
- `runs status <run-id>` 适合做轮询；`status` 会统一返回这些值之一：`running`、`completed`、`failed`、`aborted`、`unstable`、`not_built`、`unknown`
- `runs status` 同时保留 Jenkins 原始 `result` 字段；常见值有 `SUCCESS`、`FAILURE`、`ABORTED`、`UNSTABLE`、`NOT_BUILT`
- `branch set` 传入分支名时会自动补成 `*/xxx`；如果你已经自己传了 `*/` 前缀，就保持原样
- `branch set` 是持久修改，不会在构建后自动恢复
- `branch set` 只支持经典 Git job；遇到 Pipeline / Multibranch / 多个 Branch Specifier 时会拒绝执行

## 权限要求

至少需要 Jenkins 中的以下权限：

- `Job/Read`
- `Job/Build`
- `Job/Cancel`（停止构建）
- `Job/Configure`（修改 Branch Specifier）

# jenkins-builder-cli

Jenkins 构建命令行工具。实时获取 jobs，本地配置保存连接信息及各 job 的标签、自然语言描述。

支持：

- `doctor` 检查配置与连接，同步 jobs，提醒尚未填写描述的 job
- `jobs` / `jobs list` 及管理子命令自动同步完整 job 清单，保留标签和描述
- 用“测试服”“正式服”“未分类”分组选 job，按需输入分支
- 非交互构建、持久修改经典 Git job 的 Branch Specifier
- 查看运行中的构建、查询状态、停止构建、查看 console output

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
jenkins-builder-cli doctor
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
  "720yun_tour_editer":
    label: prod
    description: "正式服编辑器 2.0，同时提供正式服工具 2.0"
  "文件夹/测试服编辑器":
    label: test
    description: "用于验证编辑器的新功能"
  "待分类任务":
    label: ""
    description: ""
```

每次执行 `jobs`（含所有子命令）或 `doctor`，都会先获取当前账号可见且可构建的完整 jobs 列表，再同步到配置文件：新增 job 的 `label` 和 `description` 都为空字符串；保留已有 job 的标签和描述；移除已不在列表中的 job。`--query` 只影响显示，不影响同步范围。请求失败或返回无效清单时不写配置。

旧配置中的 `aliases`（以及更早的 `keywords`）会去重、用中文分号合并为 `description`，同步时写回新格式。已有 `description`（含空字符串）优先保留。描述只用于展示与搜索，不能代替 job 名称执行命令。

## 配置检查

```bash
jenkins-builder-cli doctor
jenkins-builder-cli doctor --json
```

检查配置文件结构、URL、用户名、Token、证书校验开关、正整数超时/轮询间隔，以及 Jenkins 连接和 jobs 读取。检查成功后同步本地配置，只提醒缺少描述的 job，不提醒“未分类”；缺少描述不会导致失败。可选的 `defaults` 与 `verify_ssl` 省略时使用示例中的默认值，填写无效值会报错。此命令不会触发构建或修改远程 job，也不通过真实构建来验证构建/配置写权限。

`config` 仅保留 `init`、`show`、`path`。检查统一用 `doctor`（原 `config check` 已移除；不再提供 `config auth`、`config edit`）。需要手动编辑时，通过 `config path` 找到文件。

## 用法

列出所有可构建 jobs：

```bash
jenkins-builder-cli jobs list
```

按 job 名称、标签或描述过滤：

```bash
jenkins-builder-cli jobs list --query frontend
jenkins-builder-cli jobs list --query 测试服
jenkins-builder-cli jobs list --query 编辑器
```

给 job 标注环境：

```bash
jenkins-builder-cli jobs label "folder/test.frontend_build" test
jenkins-builder-cli jobs label "folder/frontend_build" prod
jenkins-builder-cli jobs unlabel "folder/frontend_build"
```

设置或清空自然语言描述：

```bash
jenkins-builder-cli jobs desc "720yun_tour_editer" "正式服编辑器 2.0，同时提供正式服工具 2.0"
jenkins-builder-cli jobs desc "720yun_tour_editer" ""
```

不带参数时，先选分组，再从每行一个 job 的编号列表中选择。只显示有 job 的分组；序号仅用于交互选择。

```bash
jenkins-builder-cli set-branch
jenkins-builder-cli build
```

选完 job 后显示当前分支并提示输入。`set-branch` 必须输入非空分支；`build` 可直接回车，沿用当前分支。无法读取分支（例如非经典 Git job 或无读取配置权限）时会明确显示，仍可回车按 job 当前配置构建。

| 参数 | `set-branch` | `build` |
| --- | --- | --- |
| 无参数 | 选分组/job，再输入分支 | 选分组/job，再输入分支；回车沿用当前分支 |
| 只有 `--job` | 显示当前分支并输入新分支 | 直接使用当前分支构建，不交互 |
| 只有 `--branch` | 选分组/job，再修改分支 | 选分组/job，再修改分支并构建 |
| `--job` 和 `--branch` 都提供 | 直接修改分支 | 直接修改分支并构建 |

```bash
jenkins-builder-cli set-branch --job "文件夹/测试服编辑器" --branch feature/login
jenkins-builder-cli set-branch --job "文件夹/测试服编辑器"
jenkins-builder-cli set-branch --branch feature/login

jenkins-builder-cli build --job "文件夹/测试服编辑器" --branch feature/login
jenkins-builder-cli build --job "文件夹/测试服编辑器"
jenkins-builder-cli build --branch feature/login
jenkins-builder-cli build --job "文件夹/测试服编辑器" --branch feature/login --follow --json
```

`--job` 接受完整 Jenkins job 名称，包括中文和文件夹路径；含空格时请加引号。旧的位置参数和别称调用已移除。需要交互却没有终端时，命令会报错；自动化调用请补齐所需参数。`--json` 不改变交互规则，交互提示写到 stderr，stdout 只输出结果 JSON。

构建时指定新分支会依次执行两次写入：先通过 `config.xml` 将 Jenkins job 的 Branch Specifier 改成实际分支（例如 `*/v6.1.0`），再触发构建。即使原值是 `${WORKFLOW_REVISION}`，也会直接替换为实际分支名，不使用构建参数传递分支。这样 `jobs list` 和 Jenkins 配置页都能看到当前配置的分支。修改失败则不触发构建；修改成功后会持久保留，即使后续构建失败也不会自动恢复。

触发前自动识别是否启用了参数化构建：普通 job 使用 `build`，参数化 job 使用 `buildWithParameters`，由 Jenkins 使用已配置的参数默认值，无需增加 CLI 参数。`buildWithParameters` 不要求 Git 分支写成变量，也不会将分支改回变量。接口区别见 [Jenkins Remote Access API](https://www.jenkins.io/doc/book/using/remote-access-api/#submitting-jobs)。

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
jenkins-builder-cli build --job "folder/test.frontend_build" --json
jenkins-builder-cli runs list --json
jenkins-builder-cli runs status "folder/test.frontend_build#123" --json
```

## 行为说明

- `jobs` 等同于 `jobs list`，每次实时请求 Jenkins 并同步本地配置
- `jobs list --query` 按名称、本地标签和描述过滤，只读取匹配 job 的分支配置
- `jobs list` 的 `BRANCH` 显示 Jenkins 当前真实 Branch Specifier；不是经典 Git job 或无法唯一解析时显示 `-`
- `build --job` 和 `set-branch --job` 精确匹配完整 job 名称，不按描述匹配；可直接定位时不枚举无关目录，找不到时列出名称候选
- 交互只读取所选 job 的分支，不为整个 job 列表读取配置
- `runs status <run-id>` 适合做轮询；`status` 会统一返回这些值之一：`running`、`completed`、`failed`、`aborted`、`unstable`、`not_built`、`unknown`
- `runs status` 同时保留 Jenkins 原始 `result` 字段；常见值有 `SUCCESS`、`FAILURE`、`ABORTED`、`UNSTABLE`、`NOT_BUILT`
- `set-branch` 传入分支名时会自动补成 `*/xxx`；如果你已经自己传了 `*/` 前缀，就保持原样
- `set-branch` 是持久修改，不会在构建后自动恢复
- `set-branch` 只支持经典 Git job；遇到 Pipeline / Multibranch / 多个 Branch Specifier 时会拒绝执行
- `logs --follow` 使用增量日志接口和服务端字节游标，后续轮询只获取新增日志，并在日志完成后退出；中文和 Jenkins 控制台注解不会导致游标错位
- `logs --tail N --follow` 启动时连续读取已有日志的分页，只缓冲最后 N 行；追到空批次或日志完成后显示这 N 行，随后显示全部新增内容。首次仍需读取已有日志，之后不会重复下载；`--json` 仍输出完整日志和构建状态
- Fish 只在 job 参数位置生成本地配置中的 job 名称候选（包括 `--job`），其他子命令位置不读取 jobs 配置

## 本地回归测试

```bash
uv run cli/jenkins-builder-cli/test_main.py
```

测试使用模拟 HTTP 响应和临时配置，不连接 Jenkins。增量协议依据 Jenkins 的 [AnnotatedLargeText](https://github.com/jenkinsci/jenkins/blob/master/core/src/main/java/hudson/console/AnnotatedLargeText.java) 与 [Stapler LargeText](https://github.com/jenkinsci/stapler/blob/master/core/src/main/java/org/kohsuke/stapler/framework/io/LargeText.java) 实现。

## 权限要求

至少需要 Jenkins 中的以下权限：

- `Job/Read`
- `Job/Build`
- `Job/Cancel`（停止构建）
- `Job/Configure`（修改 Branch Specifier）

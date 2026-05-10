---
name: testpage-cli
description: 当用户要把本地 HTML 目录发布到测试服务器、同步静态页面到 `html_test`、指定发布子目录或根目录，或排查 `testpage-cli` 配置与仓库状态时使用。
---

# Testpage CLI

用 `testpage-cli` 把本地 HTML 目录发布到测试服务器对应的 Git 项目，并返回访问 URL。

## 核心原则

- 默认直接执行 `push`，不要先做一轮手工检查
- 只有用户主动要排查，或 `push` 因配置 / 仓库状态失败时，才运行 `config check`
- `init` 会写本机配置；没有真实 `project_root` 时不要自动执行
- Git 失败时不要替用户自动绕过冲突、脏工作区或 fast-forward 限制

## CLI 入口

- 优先使用 PATH 中的 `testpage-cli`
- 若未安装，再回到仓库里的 `cli/testpage-cli/testpage-cli`
- 这是 Bash 脚本；若入口失败，先确认是否在 Bash 5+ 环境

## 初始化与检查

- 配置文件：`~/.config/testpage-cli/config.conf`
- 初始化：`testpage-cli init --project-root <html_test 仓库路径>`
- 可选参数：`--base-url`、`--default-subdir`
- 查看配置：`testpage-cli config show`
- 查看配置路径：`testpage-cli config path`
- 自检：`testpage-cli config check`

若只是发布页面，先直接 `push`；只有明确报“未初始化”或配置不可用时，才进入初始化流程。

## 帮助探测

```bash
testpage-cli -h
testpage-cli push -h
testpage-cli config -h
testpage-cli init -h
```

## 路由规则

- 发布目录：`testpage-cli push <source-dir>`
- 发布时改目录名：加 `--name`
- 发到指定子目录：加 `--subdir`
- 忽略默认子目录、强制发到根目录：加 `--root`
- 看配置或仓库状态：`config show` / `config path` / `config check`

## 高价值 gotchas

- `source-dir` 必须是目录，不接受单个 HTML 文件
- 目录里至少要有一个 `.html` 或 `.htm`
- 目标目录若已存在，CLI 会整目录删除后重建，不是增量覆盖
- 路径优先级是 `--root` > `--subdir` > `default_subdir` > 根目录
- `--root` 和 `--subdir` 互斥
- 默认目录名使用源目录名

## Git 行为

`push` 的核心流程是：

1. `git fetch --all --prune`
2. `git pull --ff-only`
3. 同步目标目录
4. `git add`
5. 无变更则直接返回 URL
6. 有变更才 `commit` 与 `push`

任一步 Git 失败都应停止并向用户解释原因。

## 输出转述

- 成功时先给最终 URL，再说明发布到了哪个目录、用了根目录还是子目录
- 无内容变化时，要明确说明“目标内容没有变化，无需提交”
- 失败时优先翻译成用户可操作的原因，而不是只贴 stderr

## 常见错误

- 配置文件不存在或字段缺失：先 `init` 或修配置
- `project_root` 不是 Git 仓库：检查本地 html_test 路径
- Git 工作区不干净：先清理或提交现有改动
- 源目录不存在或没有 HTML：换成正确的页面目录
- `--subdir` / `default_subdir` 非法：不能包含 `..`、`.` 或空路径段

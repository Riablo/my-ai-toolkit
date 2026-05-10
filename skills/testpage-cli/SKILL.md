---
name: testpage-cli
description: 使用 `testpage-cli` 将本地 HTML 目录发布到测试服务器对应的 Git 项目，并返回可访问 URL。当用户提到“发布测试页”“上传 HTML 到测试服”“把这个单页/静态页面同步到 html_test”“发到 chenzheng 子目录”“直接发到根目录”“看看 testpage-cli 配置是否正确”等，或希望 AI 通过命令行完成测试页发布时使用此技能。
---

# Testpage CLI

使用 `testpage-cli` 发布测试 HTML 页面。默认直接执行 `push`；只有用户明确要排查配置，或 `push` 因配置/仓库状态失败时，再使用 `config` 相关命令。

## CLI 定位

- 优先使用 PATH 中的 `testpage-cli`
- 若未安装，则回到仓库里的 `cli/testpage-cli/testpage-cli`
- 这个入口是 Bash 脚本；若直接执行失败，先确认是否在 Bash 5+ 环境，而不是继续猜测参数

定位仓库内 CLI 时，使用下面的约定：

- `SKILL_DIR` = 当前 `SKILL.md` 所在目录
- `PROJECT_ROOT` = `SKILL_DIR` 的上上级目录
- `TOOL_PATH` = `PROJECT_ROOT/cli/testpage-cli/testpage-cli`

## 初始化

首次使用时需要初始化：

- 配置文件：`~/.config/testpage-cli/config.conf`
- 初始化命令：`testpage-cli init --project-root <本地 html_test Git 仓库路径>`
- 可选初始化参数：`--base-url <URL>`、`--default-subdir <相对路径>`

首次配置的常见形式：

```bash
testpage-cli init --project-root /Users/cz/Work/html_test
```

如果用户平时固定发布到某个命名空间下，可建议：

```bash
testpage-cli init --project-root /Users/cz/Work/html_test --default-subdir chenzheng
```

重要约束：

- 不要因为看到 skill 里的示例命令，就自动执行 `testpage-cli init`
- 不要假设 `project_root` 一定是 `/Users/cz/Work/html_test`
- 不要假设 `default_subdir` 一定是 `chenzheng`
- 如果当前机器还没初始化，必须先让用户明确指定要用的 `project_root`，以及是否要设置 `default_subdir`
- 只有在用户已经明确给出这些值之后，才可以执行 `testpage-cli init ...`
- 如果用户没有给 `default_subdir`，就不要替用户擅自补一个

若只是想看当前 CLI 读到的配置，运行：

```bash
testpage-cli config show
```

需要确认配置文件位置时，运行：

```bash
testpage-cli config path
```

需要快速检查配置和仓库状态时，运行：

```bash
testpage-cli config check
```

正常发布时不要额外先做一轮手工检查；直接执行 `push` 即可。只有当用户主动要求排查，或 `push` 失败且看起来像配置/仓库问题时，再跑 `config check`。

初始化策略：

- 若用户只是要发布页面，先直接执行 `push`
- 只有当 `push` 失败并明确提示“未初始化”或配置不可用时，才进入初始化流程
- 进入初始化流程后，先向用户确认 `project_root` 和可选的 `default_subdir`，不要直接使用示例值

## 帮助探测

先运行：

```bash
testpage-cli -h
```

再按需要查看：

```bash
testpage-cli init -h
testpage-cli config -h
testpage-cli push -h
```

如果 `push` 的参数仍有歧义，再结合顶层 `-h`、`cli/testpage-cli/README.md` 和源码确认。

如果 PATH 中没有命令，就把上面的 `testpage-cli` 替换成仓库内入口。

## 命令路由

- 用户要“初始化 testpage-cli”“配置 html_test 仓库路径”“设置默认发布子目录”时，用 `testpage-cli init`
- 用户要“看当前配置”“确认配置文件路径”“排查是不是读到了正确仓库”“检查配置和仓库状态”时，用 `testpage-cli config show`、`testpage-cli config path` 或 `testpage-cli config check`
- 用户要“发布这个 HTML 目录”“把 dist 同步到测试服”“上传单页 HTML 应用”“返回测试链接”时，用 `testpage-cli push`

补充约束：

- 对“初始化”相关请求，只有在用户明确给出目录和子目录，或明确同意使用某个值之后，才能执行 `init`
- 不要从示例路径、仓库 README、历史常见值里推断出一个固定目录并直接执行

发布命令的语义映射：

- 默认发布：`testpage-cli push <source-dir>`
- 发布时重命名：`testpage-cli push <source-dir> --name <dir-name>`
- 发到指定子目录：`testpage-cli push <source-dir> --subdir <relative-path> [--name <dir-name>]`
- 忽略配置里的默认子目录、强制发到根目录：`testpage-cli push <source-dir> --root [--name <dir-name>]`

路径优先级要记住：

- `--root` > `--subdir` > `default_subdir` > 根目录
- `--root` 和 `--subdir` 互斥，不能同时传
- 若没有 `--name`，最终目录名默认使用源目录名

## 发布输入

- `source-dir` 必须存在，且是目录
- 源目录里至少要有一个 `.html` 或 `.htm` 文件
- 这个工具最适合“文件夹 + index.html + 静态资源”的单页应用或静态页面目录
- 目标目录若已存在，CLI 会整目录删除后重建，而不是只覆盖同名文件
- CLI 会自动排除源目录里的 `.git/`

若用户只给了一个 HTML 文件而不是目录，先说明当前 CLI 只接受目录输入。

## Git 行为

`push` 的真实流程是：

1. `git fetch --all --prune`
2. `git pull --ff-only origin <current-branch>`
3. 同步目录内容到目标位置
4. `git add --all -- <target-rel>`
5. 若没有变更，则直接返回 URL，不会 `commit` 或 `push`
6. 有变更时执行 `git commit`
7. `git push origin <current-branch>`

任一步 Git 失败都会停止，不要替用户自动绕过冲突或脏工作区。

## 输出转述

成功时，CLI 最重要的结果是最终访问 URL。转述时优先给用户：

- 发布到了哪个目录
- 是否使用了默认子目录、显式子目录或根目录
- 最终 URL 是什么

如果没有内容变化，明确说明“目标内容没有变化，无需提交”，再给 URL。

如果失败，优先翻译成用户可操作的原因，而不是只贴 stderr。必要时再建议运行 `testpage-cli config check`：

- 配置文件不存在或字段缺失：引导先 `init` 或修配置
- `project_root` 不是 Git 仓库：检查本地 html_test 路径
- Git 工作区不干净：提醒先提交或清理现有改动
- 源目录不存在或没有 HTML：提醒换成正确的页面目录
- `--subdir` / `default_subdir` 非法：说明不能包含 `..`、`.` 或空路径段

除非用户明确要原始输出或调试细节，否则不要整段照抄彩色终端输出。

## 维护约定

当 `testpage-cli` 新增子命令、参数、配置字段、路径规则、Git 流程或输出行为时，同步更新这个 skill 和仓库根目录 `README.md`。

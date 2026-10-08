# my-ai-toolkit

我自己用的 AI 工具箱，收录两类内容：

- **skills/** — 给 AI 用的 Skills（Claude Code Skill 格式）
- **cli/** — 命令行小工具

## 安装

```bash
# 安装 CLI 工具及 zsh 补全，并更新 ~/.zshrc
bash scripts/install.sh
```

安装脚本会自动：
- 将 `cli/` 下所有工具软链接到 `~/.local/bin/`
- 安装 zsh 补全到 `~/.zsh/completions/`，并在 `~/.zshrc` 的托管块中配置 `PATH`、`fpath` 和 `compinit`

只安装文件时：

```bash
bash scripts/install.sh --no-rc          # 不修改 ~/.zshrc
```

zsh 的 rc 配置默认使用 `auto` 模式：如果已有 my-ai-toolkit 托管块，会保留原来的位置以及 `standalone` 或 `integrated` 模式；如果没有旧块，则按 `standalone` 初始化，写入 `PATH`、`fpath` 并自行执行 `compinit`，适合全新机器或未知环境。如果你的 `.zshrc` 已经有统一的 `compinit`，可以首次安装时使用更轻的集成模式：

```bash
bash scripts/install.sh --zsh-rc-mode integrated
```

`integrated` 只写入 `PATH` 和 `fpath`，并把托管块放到 `.zshrc` 开头，依赖后续已有的 `compinit` 统一加载补全。

之后再执行裸命令也会保留已有模式，不会把 `integrated` 覆盖回 `standalone`：

```bash
bash scripts/install.sh
```

## skills/

Claude Code 的 [Custom Skills](https://docs.anthropic.com/en/docs/claude-code/skills)，使用 `myskills` 命令管理。

仓库中的 skill 默认只允许用户显式调用，不由 Agent 自动选择：`SKILL.md` 使用 `disable-model-invocation: true`，兼容 Claude Code 和 Pi；`agents/openai.yaml` 使用 `policy.allow_implicit_invocation: false`，兼容 Codex。以后新增 skill 也遵循这一默认项，只有明确需要自动调用时才同时调整两处配置。

Skills 用于承载可复用的工作流和任务约定。简单 CLI 直接查阅工具的帮助或 README 使用，不单独维护只转述命令用法的 skill。

| Skill | 说明 |
| --- | --- |
| [alfred-paper-icon](skills/alfred-paper-icon/) | 生成层叠纸片风格的 Alfred Workflow 图标，保持材质、层次与光照统一，配色随主题变化；附参考图和透明通道检查 |
| [image-prompt-tester](skills/image-prompt-tester/) | 生图测试：按指定方向测试图片提示词，或从参考图提取风格生成占位符模板，并行出图后保存到 `~/Downloads` |
| [htask](skills/htask/) | 配合 htask CLI 委派 Herdr worktree 任务，判断仓库基准、Bug 联动和 dev/submit 的授权与结果边界 |
| [notion-ai-tools](skills/notion-ai-tools/) | 维护 Notion AI Tools 清单，记录 Skills、MCPs、Plugins 的用途、使用状态、适用 Agent 和安装范围 |
| [notion-logs](skills/notion-logs/) | 使用 Notion API 添加或编辑 Music/Movie/TV Series Logs 中的专辑、电影和剧集记录 |
| [notion-notes](skills/notion-notes/) | 将值得长期保存的个人配置、踩坑、决策和笔记保存或更新到 Notion Notes，正文灵活组织 |
| [skill-retrospective](skills/skill-retrospective/) | 在创建、更新、重构或 review skill 时自动做反思检查，重点检查 description、README 化正文、gotcha、边界与渐进加载 |
| [web-app-dockerizer](skills/web-app-dockerizer/) | 把本地 Web App 从 Bun/npm/pnpm/yarn 或旧常驻进程迁移为 Docker Compose 长期运行 |

## cli/

命令行工具，各自有独立的说明。

| 工具 | 说明 |
| --- | --- |
| [clipfmt](cli/clipfmt/) | macOS 剪贴板格式化：Jev 分流、本地 JSON/代码/时间/URL/表格及图片转换，DeepSeek 兜底整理错乱空白与换行 |
| [cloudsaver-cli](cli/cloudsaver-cli/) | 网盘资源搜索与 115 转存工具（Telegram 搜索 / 115 转存） |
| [config-sync](cli/config-sync/) | 一条命令按 TOML 单向推送全部配置文件 / 目录到多台 SSH 主机，覆盖前备份，支持主机筛选、清理、预览和动态补全 |
| [freecurrency-cli](cli/freecurrency-cli/) | Open Exchange Rates 汇率工具（金额换算 / 最新汇率 / 本地缓存） |
| [htask](cli/htask/) | 创建 Herdr worktree 与 Pi/Codex/Claude Code 任务，支持 PingCode bug、Label 初始化/并行开发服务和带 Label 的 PR/MR 交付 |
| [myskills](cli/myskills/) | 管理 AI Skills 的链接、安装与卸载（list / link / install / unlink / uninstall / status） |
| [pano-json](cli/pano-json/) | 下载 720 云作品源码中 `window.json` 指向的原始 JSON |
| [pingcode-cli](cli/pingcode-cli/) | 使用 PingCode 官方 API 查询与更新 bugs、查看评论及诊断配置 |
| [qweather-cli](cli/qweather-cli/) | QWeather 命令行工具（实时天气 / 每日预报 / 逐小时预报） |
| [readlater-cli](cli/readlater-cli/) | 极简 read-it-later 抓取工具（URL 标题 / 简单概要 / JSON 输出，X/Twitter 优先走 oEmbed） |
| [skill-auto](cli/skill-auto/) | 同步开启或关闭 Skill 的模型自动调用与默认上下文注入 |
| [jenkins-builder-cli](cli/jenkins-builder-cli/) | Jenkins 构建命令行工具（配置检查 / jobs 同步 / 标签与描述 / 交互选分支构建 / 多 job 同分支构建 / 日志 / 停止） |
| [cos-cli](cli/cos-cli/) | 上传图片或文件夹到腾讯云 COS（配置文件 / MD5 命名 / 自定义前缀 / 预览 / URL 与 JSON 输出） |
| [testpage-cli](cli/testpage-cli/) | 测试 HTML 页面快速发布工具（同步目录 / 覆盖目标 / Git 提交并推送 / 返回访问 URL） |
| [wt-land](cli/wt-land/) | 将当前功能分支 rebase 后 fast-forward 到本地目标分支，支持同目录和多 worktree |

### clipfmt 用法

```bash
clipfmt --check  # 检查配置和依赖，不操作剪贴板
clipfmt          # 格式化当前剪贴板，成功后重新复制
```

密钥配置、内容外发和支持范围见 [clipfmt 文档](cli/clipfmt/README.md)。

### myskills 用法

```bash
myskills list                                  # 列出可用 skills
myskills list --names                          # 仅输出名称（供脚本和补全使用）
myskills link notion-notes                     # 链接到 ~/.agents/ 和 ~/.claude/（默认）
myskills link htask                            # 链接 htask 配套 skill（CLI 需单独安装）
myskills install notion-notes                  # 复制到 ~/.agents/ 和 ~/.claude/（默认，覆盖已有内容）
myskills link notion-notes --claude             # 只链接到 ~/.claude/
myskills install notion-notes --local-agents    # 覆盖安装到当前目录的 .agents
myskills link notion-notes --agents --local-claude  # 多选目标
myskills unlink notion-notes                   # 移除所有位置的软链接
myskills uninstall notion-notes                # 移除所有位置已复制安装的目录
myskills status                                # 查看状态（软链接或已安装）
```

目标参数（`link` / `install` / `unlink` / `uninstall` 可用，可多选）：

| 参数 | 目录 |
| --- | --- |
| `--agents` | `~/.agents/skills/` |
| `--claude` | `~/.claude/skills/` |
| `--local-agents` | `./.agents/skills/`（当前目录） |
| `--local-claude` | `./.claude/skills/`（当前目录） |

### htask 用法

```bash
htask                                                  # 交互式创建
htask --base v6.1.0 --branch fix-hotspot --bug 720YUN-4764 --prompt '补充要求'
```

更多选项和使用边界见 [htask 文档](cli/htask/README.md) 或 `htask --help`；配置写法见 [带注释的 TOML 示例](cli/htask/config.example.toml)。

### config-sync 用法

安装后运行 `config-sync init`，在 `~/.config/config-sync/config.toml` 创建全注释模板，不覆盖已有配置。取消所需表头与配置项的注释，修改主机 / 路径即可使用，例如：

```toml
[hosts.home.files]
htask = "~/.config/htask/config.toml"       # 两端同路径
zsh = ["~/.zshrc", "~/.config/zsh/.zshrc"]  # [本机路径, 目标路径]
[hosts.home.dirs]
nvim = "~/.config/nvim/"                   # 末尾 / 可有可无
```

```bash
config-sync --dry-run    # 校验全部来源并显示计划，不联网
config-sync              # 同步所有主机配置的全部文件和目录
config-sync --host home  # 同步 home 配置的全部内容，--host 可重复
config-sync clean        # 清理当前配置涉及的所有目标的备份
```

配置中的键只是便于阅读和日志定位的标签，不需要输入名称参数。覆盖前保存整个原文件 / 目录；**目录是完整镜像，目标多余内容会删除**。安装、备份和清理边界见 [config-sync 文档](cli/config-sync/README.md)，更多主机写法见 [TOML 示例](cli/config-sync/config.example.toml)。

## License

MIT

# htask

通过 Herdr 创建 worktree，启动 Pi / Codex 并发送任务；可在 Herdr 终端或外部 shell / 脚本中调用，无需 `HERDR_ENV`。外部调用需要 Herdr 服务已运行、CLI 能连接到目标会话；多个会话时先确认当前 `herdr` 命令连接的是目标会话（`htask` 暂无 `--session` 选项），并显式指定 `--repo`。依赖 Bash 5+、Python 3.11+（标准库 `tomllib`）、`git`、`jq`、`openssl`、`herdr`；`--bug` 还需已配置的 `pingcode-cli`，`--mode submit` 需要 `gh` 或 `glab`。安装：从本仓库根目录执行 `bash scripts/install.sh`。

```bash
htask                                            # 逐项询问，配置了预设时用列表选模型
htask --base v6.1.0 --branch fix-title --prompt '修复标题闪烁'
htask --mode dev --label c2v --branch fix-c2v --prompt '修复 C2V 编辑页'
htask --mode dev --label editor --label c2v --branch shared --prompt '调整共享逻辑'
htask --base v6.1.0 --no-labels --branch misc --prompt '不采用迭代默认 Label'
htask --base v6.1.0 --branch fix-title --bug 720YUN-11374 \
  --agent pi --model sol/xhigh --mode submit --prompt '补充验收条件'
```

- `--repo` 默认当前 Git 仓库；`--base` 默认当前检出的分支名。输入 `v6.1.0` 会先向 `origin` 查询并**刷新该远端分支**，再从 `origin/v6.1.0` 创建 worktree；远端没有时才使用同名本地分支；都没有则报错。也支持 `--base origin/v6.1.0` 强制要求远端。查询或刷新远端**失败**时会报错，不回退本地旧分支；不会切换或合并源工作目录的分支。只有明确的分支名可用，不能使用提交哈希、tag 或单独的 `origin`。
- `--branch` 必填；`--bug`、`--prompt` 至少提供一个。命令行缺少必填项时进入交互；无 TTY 的脚本须一次传齐必填参数。`--agent` 默认 `pi`；`--model` 是针对所选 agent 的**预设名**，不是原生模型 ID。省略它就不传模型及思考强度参数，使用 Pi / Codex 自身配置。交互模式下，有预设才出现列表，回车选自身默认；未配置预设则不询问。显式传入不存在的预设会报错；不再支持 `--thinking`。Codex 无论是否选模型预设，启动时都传入 `--dangerously-bypass-approvals-and-sandbox`：**跳过审批并关闭沙箱**；Pi 不受影响。只在认可此权限范围、具备外部隔离的环境中使用。
- `--bug` 把编号放在新分支名前并用 `/` 分隔：`--bug 720YUN-11380 --branch foo-bar` 创建 `720YUN-11380/foo-bar`。通过 `pingcode-cli bug <编号>` 获取标题、描述、评论和图片；`--prompt` 作为优先于工单内容的用户要求。正文疑似凭据尽力过滤，但**工单及首个图片的完整 URL（含查询参数）会原样传给 agent**；敏感工单请先审查。查询失败时不会建树。只有 worktree、agent 和提示词都成功创建/发送后，才调用 `pingcode-cli set-state <编号> --state 处理中`；不传 `--bug` 不更新状态，与 `--mode` 无关。如果状态更新失败，任务**已经启动**，CLI 返回非零并提示检查工单状态；必要时只手动重试 `set-state`，不要重跑 `htask`。
- `--mode submit` 根据网络 `origin` 的主机名自动识别 GitHub/GitLab，无法识别的平台（包括主机名不含 github/gitlab 的自托管实例）会在建树前报错。目标分支必须已在远端；本地路径 / `file://` 不可用于此模式。CLI 只要求 agent 测试、提交、推送、用 `gh pr create` 或 `glab mr create` 发 PR/MR，**不保证交付已经完成**；使用此模式即授权 agent 做远端发布。
- 建树后如果项目 tab、agent 或提示词提交失败，worktree 会保留；命令可能已送达，先查 pane 再手工恢复，不盲目重试。

## 任务 Label

`--label` 可重复，支持选一个或多个；`--no-labels` 明确不选，两者互斥。显式选择**替换**迭代默认，不做追加；重复 Label 按首次出现顺序去重。

未显式指定时，非交互使用迭代默认；交互提供编号列表（`1,2` 多选、回车接受迭代默认、`0` 不选）。没有 Label 配置的项目不询问，也不要求配置 GitLab/GitHub。

所有模式都会将最终 Label 作为任务上下文传给 agent，不从工单或文件路径猜测增减；Label 本身不授权推送或发布。`submit` 要求创建 PR/MR 时附加所选 Label，并核对实际结果：

- Label 不存在或无权限时须报告，不自动新建远端 Label，不移除已有其他 Label。
- 已创建但 Label 设置失败时修复现有 PR/MR，不重复创建。
- 空列表表示不要求添加，而不是清空已有 Label。
- CLI 不直接调用远端 Label 接口，不保证 agent 已完成交付。

## 初始化与开发服务

公共 `init` 每次建树在 Setup tab 执行一次，然后按最终 Label 顺序执行专属 `init`；所有 init 都串行，任一失败则不启动任何开发服务。所有模式都运行这些 init。

`--mode dev` 在全部 init 成功后，由 Setup tab 为每组开发服务创建独立的 `Dev: <Label>` tab，**组间并行、组内串行**：

| 最终选择 | 开发服务 |
| --- | --- |
| 无 Label | 顶层 `dev` |
| 一个或多个 Label | 仅对应 `labels.<名称>.dev`，不附加顶层 `dev` |
| 只有分类用途、没有 dev 的 Label | 不启动服务，也不回退到顶层 `dev` |

单组服务或派发失败不自动取消其他组；端口冲突由项目命令解决。

Setup / Dev 的完整脚本保存在对应 worktree 的 Git 元数据目录下（`htask.XXXXXXXX/`，目录权限 700、文件权限 600），终端只接收短的 `bash <脚本路径>` 命令，避免新 tab 就绪前长输入被截断。脚本不进入工作区或提交，保留供排查，并随 worktree 删除清理；不要盲目重跑其中的初始化或服务脚本。若路径过长导致启动命令连同回车超过 1024 字节，CLI 会停止派发并报错。

CLI 只派发 Setup 命令，**不会等待初始化、依赖安装或服务启动完成**。Setup tab 报告 init 和后续服务派发结果，各 Dev tab 提供自己的日志；无 init/dev 命令时不创建 Setup。异步失败不会追溯改变已经返回的 CLI 退出码，先检查相关 pane，不直接重跑整批。

## TOML 配置

完整带注释示例：[config.example.toml](config.example.toml)，以后可直接参考。示例使用 `720yun_tour_editer` 的命令，其他项目应按实际情况填写，不要原样执行。

全局配置：`~/.config/htask/config.toml`（若设置 `XDG_CONFIG_HOME`，则使用 `$XDG_CONFIG_HOME/htask/config.toml`）。项目配置：**源仓库根目录**的 `.config/htask/config.toml`。两个文件都可选，存在时必须带 `schema_version = 2`。

- 全局只允许 `schema_version`、`init`、`dev`、`models`；`labels`、`iterations` **仅限项目配置**，防止跨仓库继承。
- 项目的顶层 `init`、`dev` 分别整组覆盖全局；缺字段则继承，显式 `[]` 清空。模型预设仍按 agent / 名称 / 字段逐项覆盖。
- 不兼容 v1。迁移时将 `dev_profiles.<名称>` 改为 `labels.<名称>.dev`，将 `iteration_prompts.<分支>` 改为 `iterations.<分支>.prompt`，按需配置迭代 `labels`；命令行改用 `--label`，不再接受 `--dev-profile`。旧 `config.json` 需迁移并移走，否则报错。CLI 不自动改写配置。
- Label 表名就是远端真实名称，可含中文、空格和 `::`，含特殊字符的 TOML 键需加引号。不允许空名称、首尾空白、逗号、控制字符或以 `-` 开头。未知 Label、未声明的迭代引用、未知字段或错误类型都会在建树前报错。

```toml
schema_version = 2

init = [
  'cp "$SOURCE_DIR/.env.development.local" ./.env.development.local',
  'codegraph init',
  'pnpm install',
]
dev = ['pnpm run start']

[labels.editor]
dev = ['pnpm run start']

[labels.c2v]
init = [] # 可选，追加在公共 init 后；目前没有专属初始化
dev = ['pnpm run start:c2v-editor']

[iterations."v6.1.0"]
prompt = "主要是做智能体编辑器 apps/c2v-editor"
labels = ["c2v"]

[models.pi."sol/xhigh"]
model = "openai-codex/gpt-6-sol"
thinking = "xhigh"

[models.codex."sol/xhigh"]
model = "gpt-6-sol"
thinking = "xhigh"
```

`labels.<名称>.init/dev` 均可省略或为空数组；例如 `[labels.documentation]` 空表只声明分类 Label。不涉及 Label 的项目只保留顶层 init/dev/models 即可。

`iterations.<分支>.prompt/labels` 均可省略；prompt 若提供必须非空。只按起点分支名**完全匹配**（`--base origin/v6.1.0` 也匹配 `v6.1.0`），不匹配则没有迭代默认 Label。背景放在工单和用户要求之前，仅供定位，具体工单与用户要求优先。

预设的 `model` 是 Pi 的 `provider/model` 或 Codex 的原生模型 ID；`thinking` 可省略（沿用工具本身配置）。新预设需有 `model`，覆盖全局既有预设时可以只写 `thinking`。

在命令 tab 中，`SOURCE_DIR` 指源仓库根目录，`WORKTREE_DIR` 指新 worktree 根目录；初始 cwd 是新 worktree。命令数组是可信 Bash 脚本，组内失败即停止后续命令；审查配置后再运行。各 Dev tab 是独立进程，不共享彼此或 init 脚本临时修改的 cwd / shell 变量；需要的环境应在服务自己的命令中配置或从文件读取。配置无效时在建树**之前**报错。

完整参数见 `htask --help`。配套 [htask skill](../../skills/htask/SKILL.md) 用于判断授权与任务结果边界，不替代 CLI 安装。本地回归：`bash cli/htask/test_htask.bash`（包含 `test_labels.bash`，使用 stub，不创建真实 Herdr 任务或发布）。

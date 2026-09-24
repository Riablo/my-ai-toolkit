# htask

通过 Herdr 创建 worktree，启动 Pi / Codex 并发送任务；可在 Herdr 终端或外部 shell / 脚本中调用，无需 `HERDR_ENV`。外部调用需要 Herdr 服务已运行、CLI 能连接到目标会话；多个会话时先确认当前 `herdr` 命令连接的是目标会话（`htask` 暂无 `--session` 选项），并显式指定 `--repo`。依赖 Bash 5+、Python 3.11+（标准库 `tomllib`）、`git`、`jq`、`openssl`、`herdr`；`--bug` 还需已配置的 `pingcode-cli`，`--mode submit` 需要 `gh` 或 `glab`。安装：从本仓库根目录执行 `bash scripts/install.sh`。

```bash
htask                                            # 逐项询问，配置了预设时用列表选模型
htask --base v6.1.0 --branch fix-title --prompt '修复标题闪烁'
htask --mode dev --dev-profile c2v --branch fix-c2v --prompt '修复 C2V 编辑页'
htask --base v6.1.0 --branch fix-title --bug 720YUN-11374 \
  --agent pi --model sol/xhigh --mode submit --prompt '补充验收条件'
```

- `--repo` 默认当前 Git 仓库；`--base` 默认当前检出的分支名。输入 `v6.1.0` 会先向 `origin` 查询并**刷新该远端分支**，再从 `origin/v6.1.0` 创建 worktree；远端没有时才使用同名本地分支；都没有则报错。也支持 `--base origin/v6.1.0` 强制要求远端。查询或刷新远端**失败**时会报错，不回退本地旧分支；不会切换或合并源工作目录的分支。只有明确的分支名可用，不能使用提交哈希、tag 或单独的 `origin`。
- `--branch` 必填；`--bug`、`--prompt` 至少提供一个。命令行缺少必填项时进入交互；无 TTY 的脚本须一次传齐必填参数。`--agent` 默认 `pi`；`--model` 是针对所选 agent 的**预设名**，不是原生模型 ID。省略它就不传模型及思考强度参数，使用 Pi / Codex 自身配置。交互模式下，有预设才出现列表，回车选自身默认；未配置预设则不询问。显式传入不存在的预设会报错；不再支持 `--thinking`。Codex 不会被默认关闭审批或沙箱。
- `--bug` 把编号放在新分支名前并用 `/` 分隔：`--bug 720YUN-11380 --branch foo-bar` 创建 `720YUN-11380/foo-bar`。通过 `pingcode-cli bug <编号>` 获取标题、描述、评论和图片；`--prompt` 作为优先于工单内容的用户要求。正文疑似凭据尽力过滤，但**工单及首个图片的完整 URL（含查询参数）会原样传给 agent**；敏感工单请先审查。查询失败时不会建树。
- `init` 在每次建树时于第二个 tab 运行；`--mode dev` 在初始化后仅运行选中的一组启动命令。非交互模式省略 `--dev-profile` 时沿用默认 `dev`，传入名称则运行对应 `dev_profiles`；交互模式有具名方案时从列表选择（回车选默认）。未知方案或非 dev 模式传入 `--dev-profile` 会在建树前报错。CLI 仅派发命令，**不会等待初始化、依赖安装或服务启动完成**。失败请检查项目命令 pane。
- `--mode submit` 根据网络 `origin` 的主机名自动识别 GitHub/GitLab，无法识别的平台（包括主机名不含 github/gitlab 的自托管实例）会在建树前报错。目标分支必须已在远端；本地路径 / `file://` 不可用于此模式。CLI 只要求 agent 测试、提交、推送、用 `gh pr create` 或 `glab mr create` 发 PR/MR，**不保证交付已经完成**；使用此模式即授权 agent 做远端发布。
- 建树后如果项目 tab、agent 或提示词提交失败，worktree 会保留；命令可能已送达，先查 pane 再手工恢复，不盲目重试。

## TOML 配置

全局配置：`~/.config/htask/config.toml`（若设置 `XDG_CONFIG_HOME`，则使用 `$XDG_CONFIG_HOME/htask/config.toml`）。项目配置：**源仓库根目录**的 `.config/htask/config.toml`。两个文件都可选，存在时需带 `schema_version = 1`；项目的 `init`、`dev` 数组分别整组覆盖全局同名数组，模型预设按 agent / 名称 / 字段逐项覆盖全局；具名 `dev_profiles` 按名称整组覆盖全局。缺少的字段继承全局，显式 `init = []` 可清空全局初始化。旧 `config.json` 必须迁移并移走，否则报错，不会静默跳过命令。

```toml
schema_version = 1

init = [
  'cp "$SOURCE_DIR/.env.development.local" ./.env.development.local',
  'codegraph init',
  'pnpm install',
]
dev = ['pnpm run start']

[dev_profiles]
c2v = ['pnpm run start:c2v-editor']

[models.pi."sol/xhigh"]
model = "openai-codex/gpt-6-sol"
thinking = "xhigh"

[models.codex."sol/xhigh"]
model = "gpt-6-sol"
thinking = "xhigh"
```

`dev` 是默认启动命令数组，具名方案须是非空命令数组；未配置默认 `dev` 时，省略 `--dev-profile` 不会自动选择具名方案。预设的 `model` 是 Pi 的 `provider/model` 或 Codex 的原生模型 ID；`thinking` 可省略（沿用工具本身配置）。新预设需有 `model`，覆盖全局既有预设时可以只写 `thinking`。在命令 tab 中，`SOURCE_DIR` 指源仓库根目录，`WORKTREE_DIR` 指新 worktree 根目录；cwd 是新 worktree。`init` / `dev` 是按序执行的可信 Bash 命令，失败即停止后续命令；审查配置后再运行。配置无效时在建树**之前**报错。

完整参数见 `htask --help`。配套 [htask skill](../../skills/htask/SKILL.md) 用于判断授权与任务结果边界，不替代 CLI 安装。本地回归：`bash cli/htask/test_htask.bash`（stub，不创建真实 Herdr 任务或发布）。

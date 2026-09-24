# htask：多应用 Dev 启动方案迁移说明

适用于同一仓库有多个开发服务、需要按任务选择启动命令的项目。现有 `dev` 配置和 `--mode dev` 用法保持有效。

## 新增内容

| 项目 | 含义 |
| --- | --- |
| `--dev-profile <名称>` | **新增可选参数**，仅用于 `--mode dev`；选择配置中的一组具名启动命令。未知名称、用于其他模式时会在创建 worktree 前报错。 |
| `[dev_profiles]` | **新增可选 TOML 表**，名称由项目自行定义，每项为非空 Bash 命令字符串数组。 |
| `dev = [...]` | 原有配置不变，仍是默认启动方案；非交互调用未传 `--dev-profile` 时执行这一组。 |

在源仓库 `.config/htask/config.toml` 中配置。例如根项目与独立 App：

```toml
schema_version = 1

dev = ['pnpm run start']

[dev_profiles]
c2v = ['pnpm run start:c2v-editor']
```

上例的 `c2v` 是**预设名称**，由项目自行取名；`pnpm run start:c2v-editor` 才是实际命令。可以继续添加其他名称及命令数组。若项目需要公共初始化，原有 `init = [...]` 仍在每次建树时运行。全局配置也可声明 `dev_profiles`；项目配置对同名方案整组覆盖，对不同名方案继承。

## 调用方式

```bash
# 默认方案：行为与升级前相同
htask --repo /path/to/repo --mode dev --branch fix-main --prompt '修复主项目'

# 选择独立 App；名称须与该项目的 dev_profiles 键一致
htask --repo /path/to/repo --mode dev --dev-profile c2v --branch fix-app --prompt '修复 C2V 编辑页'
```

交互式选择 `dev` 模式后，如配置了具名方案，会列出默认方案和各方案；回车选择默认。非交互模式无需传 `--dev-profile`，也不会根据 bug、分支名或目录自动猜测 App。未配置默认 `dev` 时，省略此参数不会自动选一个具名方案。

一次任务只运行**选中的一组** dev 命令：在新 worktree 的第二个 Herdr tab 中，先执行 `init`，完成后再执行该组命令。`htask` 仅派发命令，不等待安装或服务启动完成；运行结果请检查该 tab。升级 CLI 后可用 `htask --help` 确认参数；项目配置仍使用 `schema_version = 1`，无需迁移已有 `dev`。

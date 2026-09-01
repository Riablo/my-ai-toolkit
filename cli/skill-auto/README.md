# skill-auto

同步控制一个 Agent Skill 是否允许模型自动调用，以及是否进入默认的 Skill discovery context。

## 用法

```bash
skill-auto on <skill 目录>
skill-auto off <skill 目录>
```

- `on`：设置 `SKILL.md` 的 `disable-model-invocation: false`，并设置 `agents/openai.yaml` 的 `policy.allow_implicit_invocation: true`
- `off`：设置 `SKILL.md` 的 `disable-model-invocation: true`，并设置 `agents/openai.yaml` 的 `policy.allow_implicit_invocation: false`

如果目录中还没有 `agents/openai.yaml`，命令会创建最小配置。已有文件中的 `interface`、`dependencies` 等字段会被保留。

```bash
skill-auto on ./skills/my-skill
skill-auto off ~/.agents/skills/my-skill
```

zsh 和 Fish 补全均支持在子命令后补全 skill 目录：

```bash
skill-auto on <Tab>
```

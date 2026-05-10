---
name: skill-retrospective
description: 当用户要创建、更新、重构、审查或复盘一个 skill，或提到“这个 skill 写得对不对”“是不是太像 README”“帮我优化 skill 的 description、gotcha、路由边界”时使用。
---

# Skill Retrospective

在 skill 的创建与修改过程中自动做一次反思和踩坑检查。这个 skill 不负责替代领域 skill；它负责检查“这个 skill 本身写得像不像一个好 skill”。

## 联用方式

- 创建或更新普通 skill 时，与 `skill-creator` 联用
- 创建或更新 CLI skill 时，与 `cli-skill-creator` 联用
- 用户明确要 review 现有 skill 时，可以单独使用本 skill

它更像一个默认介入的 reviewer，而不是脚手架。

## 先问的事

开始写或改 skill 之前，先判断两件事：

1. 这件事真的需要一个 skill 吗
2. 这次改动最主要是在修路由、修正文、补 gotcha，还是拆结构

如果只是一条全局规则、一个模型本来就知道的流程，或变化太快以至于 skill 会立刻过时，优先不要写 skill。

## 默认检查顺序

1. 检查 `description` 是否在描述“何时触发”，而不是“这个 skill 做什么”
2. 检查正文是否写了模型本来就知道的常识、完整命令手册或 README 式说明
3. 检查高价值 gotcha、边界条件、禁止事项是否缺失
4. 检查重内容是否应该拆到 `references/`、`scripts/` 或其他渐进加载位置
5. 检查这个 skill 会不会和相邻 skill 抢路由，或把边界写得过宽
6. 检查这次改动是否需要补正例、反例或至少一组路由样例

## 这个 skill 主要防什么坑

- `description` 写成功能简介，而不是路由触发器
- 主文件写得太像 README，把 help、命令示例、常识解释全抄进去
- 只写“怎么做”，没写“哪里最容易做错”
- 该拆到 `references/` 的重内容全塞进 `SKILL.md`
- 没有相邻边界意识，新增一个 skill 就顺手干扰别的 skill
- 改了路由描述，却没有补相应的正反例

详细反模式见 [references/anti-patterns.md](/Users/cz/Projects/my-ai-toolkit/skills/skill-retrospective/references/anti-patterns.md)。

## 何时读 reference

- 要做完整反思清单：读 [references/reflection-checklist.md](/Users/cz/Projects/my-ai-toolkit/skills/skill-retrospective/references/reflection-checklist.md)
- 要专门检查路由、description、gotcha：读 [references/routing-and-gotchas.md](/Users/cz/Projects/my-ai-toolkit/skills/skill-retrospective/references/routing-and-gotchas.md)
- 要识别常见反模式：读 [references/anti-patterns.md](/Users/cz/Projects/my-ai-toolkit/skills/skill-retrospective/references/anti-patterns.md)

## 输出方式

如果用户是在“review / 复盘”一个 skill：

- 先给 findings，再给简短总结
- 优先指出会导致误触发、正文失焦、gotcha 缺失、结构过胖的问题

如果用户是在“创建 / 修改”一个 skill：

- 先把明显反模式改掉
- 再补最关键的 gotcha、边界和渐进加载提示
- 最后再考虑补充说明文字

## 维护原则

- 这个 skill 记录的是反复出现的坑，不是完整 skill 教程
- 新失败案例优先追加到 gotcha 或反模式里，不要把主文件重新写成大而全指南
- 如果某条反思已经变成这个仓库所有 skill 的稳定约定，应考虑沉淀到 `AGENTS.md` 或生成器 skill，而不是无限加在这里

---
name: skill-retrospective
description: 创建、更新、重构、审查或复盘 skill 时自动联用，检查其必要性、触发边界、指令密度、gotcha 与渐进加载；不用于普通代码或文档审查。
---

# Skill Retrospective

作为 skill 工作流中的自动 reviewer，检查“这个 skill 本身写得像不像一个好 skill”。不要替代负责创建或修改内容的主 skill，也不要扩大用户原本要求的改动范围。

## 联用方式

- 创建或更新 skill 时，在内容修改完成后做检查
- 用户明确要求 review 或复盘现有 skill 时，可以单独使用

本 skill 允许自动调用，但这不代表目标 skill 也应允许自动调用。目标 skill 的调用策略应服从用户要求和目标仓库约定。

## 先问的事

开始写或改 skill 前，先判断两件事：

1. 这件事真的需要一个 skill 吗
2. 这次改动最主要是在修路由、修正文、补 gotcha，还是拆结构

如果只是重复已有全局规则、转述简单 CLI 的用法，或信息变化太快，优先复用现有规则或指向工具帮助、README。只有额外的可复用工作流或任务约定才值得维护为 skill。以任务和使用环境判断价值，不凭某个模型“应该已经知道”删掉共享要求。

## 工作方式

1. 先完成用户要求的创建、修改或审查任务；本 skill 只补充 reviewer 视角
2. 检查 `description` 是否同时说清能力、触发场景和必要边界，且不会与相邻 skill 抢路由
3. 精简重复说明和无关手册；对比旧版本，保留必要命令、验收条件、失败处理及授权边界，确认移出的内容仍有明确入口
4. 检查高价值 gotcha、授权边界和容易误判的失败场景是否缺失
5. 将条件性重内容放到 `references/`，将重复且确定的操作放到 `scripts/`
6. 检查调用策略是否符合用户要求和仓库约定；两端配置存在时应保持一致，并保留无关字段
7. 按改变的行为检查相应场景：路由看应触发/不应触发，授权看未获同意，验证和重试看失败/结果不明；缺少行为证据时明确说明，不把静态检查当作执行通过

## 这个 skill 主要防什么坑

- `description` 写成功能简介，而不是路由触发器
- 主文件写得太像 README，把 help、命令示例、常识解释全抄进去
- 只写“怎么做”，没写“哪里最容易做错”
- 该拆到 `references/` 的重内容全塞进 `SKILL.md`
- 没有相邻边界意识，新增一个 skill 就顺手干扰别的 skill
- 改了路由描述，却没有补相应的正反例
- 只配置 Claude Code / Pi 或 Codex 一侧的调用策略，导致不同 Agent 行为不一致
- 把本 skill 的自动调用策略错误地复制给目标 skill
- 为精简而删除测试、验收或确认要求，或把单个模型的表现当作所有使用者的保证

详细反模式见 [references/anti-patterns.md](references/anti-patterns.md)。

## 何时读 reference

- 要做完整反思清单：读 [references/reflection-checklist.md](references/reflection-checklist.md)
- 要专门检查路由、description、gotcha：读 [references/routing-and-gotchas.md](references/routing-and-gotchas.md)
- 要识别常见反模式：读 [references/anti-patterns.md](references/anti-patterns.md)

## 输出方式

如果用户是在“review / 复盘”一个 skill：

- 先给 findings，再给简短总结
- 优先指出会导致误触发、正文失焦、gotcha 缺失、结构过胖的问题

如果用户是在“创建 / 修改”一个 skill：

- 先把明显反模式改掉
- 再补最关键的 gotcha、边界和渐进加载提示
- 最后再考虑补充说明文字
- 将检查结果融入正常交付；除非用户要求复盘，不额外输出冗长报告

## 维护原则

- 这个 skill 记录的是反复出现的坑，不是完整 skill 教程
- 新失败案例优先追加到 gotcha 或反模式里，不要把主文件重新写成大而全指南
- 仓库维护层面的稳定约定可沉淀到 `AGENTS.md`；使用 skill 时必需的要求仍应随 skill 分发，不能依赖使用方加载本仓库规则

---
name: jenkins-builder-cli
description: 当用户用自然语言要求触发 Jenkins 构建、发布测试服/正式服、切换 Jenkins job 分支后构建、查询/停止构建或用别称查找 Jenkins job 时使用。
---

# Jenkins Builder CLI

用 `jenkins-builder-cli` 把自然语言发布/构建意图落到 Jenkins job。这个 skill 的首要目标是安全确认，避免误触发正式服或错误分支。

## 核心原则

- 项目根目录默认是 `/Users/cz/Projects/my-ai-toolkit`，CLI 入口是 `cli/jenkins-builder-cli/jenkins-builder-cli`；如果已安装到 PATH，也可以直接用 `jenkins-builder-cli`。
- 每次准备运行 CLI 前，先跑 `jenkins-builder-cli config check`。如果配置缺失或无效，停止并引导用户先修配置，不要静默继续。
- `build` 和 `set-branch` 都是有副作用的操作。任何触发 build 或修改分支前，必须先向用户确认。
- 确认信息必须包含：
  - Job name：Jenkins full job name，不是模糊描述。
  - 分支：将要构建的分支；如果无法从 Jenkins 读取或用户没有指定，就继续询问。
  - 环境：测试服、正式服或未分类；正式服尤其要明确写出来。
- 不支持用 `build 12` 这种数字参数直接构建。只有 `jenkins-builder-cli build` 进入交互式列表时才能输入序号。
- 不要自动运行 `config init`、自动改 token、自动写配置；除非用户明确要求并提供必要信息。

## 查找 job

1. 先从用户话里提取 job 线索、分支、环境词。
2. 如果用户说了“测试服”或“正式服”，先用环境过滤：
   - `jenkins-builder-cli jobs list --query "测试服"`
   - `jenkins-builder-cli jobs list --query "正式服"`
3. 如果用户还给了项目/页面/服务别称，再用这个词查：
   - `jenkins-builder-cli jobs list --query "<别称或关键词>"`
4. 如果 alias 或 query 没识别出来，列出候选 jobs 让用户选择；候选太多时优先按环境过滤后展示。
5. 用户选定 job 后，如果刚才的自然语言别称不在 config 里，可以询问是否写回：
   - `jenkins-builder-cli jobs alias add "<job-name>" "<alias>"`
   - 写 alias 是修改本地 config，也需要用户同意。

## 标签和别称

- 标签只用于区分环境：`test` 显示为“测试服”，`prod` 显示为“正式服”，未标注显示“未分类”。
- 如果用户要求“把这个标成测试服/正式服”，使用：
  - `jenkins-builder-cli jobs label "<job-ref>" test`
  - `jenkins-builder-cli jobs label "<job-ref>" prod`
- 如果用户要求“以后叫它 xxx”，使用 `jobs alias add`。
- alias 必须唯一；如果 CLI 报别称不唯一，把候选 job 列给用户，不要猜。

## Build 确认门

在真正 build 前，给用户一段明确确认，例如：

```text
请确认是否触发 Jenkins 构建：
Job name: test.720yun_js
分支: */feature/foo
环境: 测试服
将执行:
jenkins-builder-cli set-branch "test.720yun_js" "feature/foo"
jenkins-builder-cli build "test.720yun_js" --follow --json
执行方式: 派生子代理监听构建，并在完成后回报结果
```

只有用户明确同意后，才可以执行。

如果用户只是说“发布一下某项目”但没有分支，先问分支。不要默认 main/master，也不要默认 Jenkins 当前配置，除非用户明确说“用当前 Jenkins 分支”，且 `jobs list` 能显示当前分支。

## 执行 build

- 用户确认后，build 任务应交给派生子代理执行，避免占用主对话；确认文字里要明确说明这一点，让用户的确认同时覆盖派生执行。
- 子代理负责：
  - 必要时先运行 `set-branch`。
  - 运行 `build <job-name> --follow --json`。
  - 持续监听直到完成、失败、取消或超时。
  - 把最终结果通知主对话：job、分支、环境、run id、build number、status、Jenkins URL。
- 如果当前运行环境没有子代理能力，先说明限制并询问是否改为当前会话执行。
- 不要在未确认时把 build 交给子代理；确认门仍然在主对话完成。

## 任务链

用户可能会说“某个项目 build 完成后再做某事”。这时把后续操作作为任务链交给同一个子代理：

1. 先完成 build 并判断最终状态。
2. 只有 build 成功时，才继续执行后续任务，除非用户明确要求失败也继续。
3. 子代理在最终汇报里分段说明：构建结果、后续任务结果、未执行的步骤和原因。
4. 后续任务如果也有副作用或风险，仍需在派发子代理前和用户确认。

## 常见坑

- `set-branch` 是持久修改 Jenkins job 配置，不会在 build 后自动恢复。
- `set-branch` 只支持经典 Git job；Pipeline、Multibranch 或多个 Branch Specifier 可能会失败。
- `jobs list` 的 `BRANCH` 为 `-` 时，不能当作已知分支。
- `build` 默认触发 Jenkins 当前 job 配置；如果用户指定了分支，应先 `set-branch` 再 `build`。
- 正式服和测试服 job 名可能很像。用户提到环境时，确认文字必须把环境写出来。

## 输出转述

给用户汇报时先说结论，再给关键字段。不要机械倾倒完整 JSON。

成功示例：

```text
构建完成：测试服平台页面已成功构建。
Job: test.720yun_js
分支: */feature/foo
Run: test.720yun_js#123
状态: completed
URL: ...
```

失败时说明失败状态、run id、URL，并建议下一步看日志或停止/重试。

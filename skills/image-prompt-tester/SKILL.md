---
name: image-prompt-tester
description: 在 Hermes Agent 中测试图片生成提示词与参考图风格。用户要求“生图测试”“测试这个图片 prompt”“试几张图”、给出网上看到的生图提示词想看效果，或提供参考图让 agent 提取风格、生成带占位符的可复用 prompt 模板并实际出图对比时使用。默认测试 3 张/3 个版本；如果用户没有说明要测试的变化方向，先结合原提示词或参考图追问；多张图片必须用 Hermes 的 delegate_task(tasks=[...]) 按“一张图一个子任务”并行生成；保存图片、最终提示词、占位符模板和 manifest 到 ~/Downloads 的新建测试文件夹，并把结果回传当前会话。
---

# Image Prompt Tester

用于在 Hermes Agent 里快速验证图片提示词效果。保持轻量：少讲改写规则，多按用户给出的方向测试。

## 两种模式

- **提示词测试**：用户给出网上看到的 prompt 或场景描述，想实际生成几张图看效果。
- **参考图风格测试**：用户给出图片，要求提取风格，生成带占位符的可复用 prompt 模板，并用随机填充值出图验证。

## 通用规则

- 默认测试 3 张或 3 个版本，除非用户指定数量。
- 不要过度改写原 prompt；保留核心主题、构图、风格、限制条件和用户原本的语言。只有用户要求或确有必要时才翻译。
- 如果用户没有说明要测试的变化方向，先问一个简短问题，并结合原 prompt/参考图给 2-4 个可选方向。用户说“你定”“随机试”时，再自行选择。
- 多图生成必须通过 Hermes 的 `delegate_task(tasks=[...])` 批量并行：一张图一个 leaf 子任务，每个子任务只调用一次 `image_generate`，并在最终摘要返回图片路径、model/provider/quality/size 和最终 prompt。不要用 `multi_tool_use.parallel` 直接并行 `image_generate`，也不要把多张图交给单个子任务串行执行。
- 每组测试都在 `~/Downloads` 下新建目录，保存原始输入、候选 prompt/模板、生成图片、`prompts.json` 和 `manifest.md`。
- 结果要回传当前会话：图片能展示时直接展示；不能展示时给出本地路径和对应 prompt。

## 提示词测试流程

1. 提取原始 prompt/描述、用户指定的测试方向和数量。
2. 若缺少测试方向，先追问，例如：“默认测 3 张。要不要按材质、镜头、色彩这几个方向试，还是你有指定方向？”
3. 按用户确认的方向生成候选 prompt。每个候选只围绕对应方向做必要变化，避免把原 prompt 重写成另一套画面。
4. 如果用户要求对比原版，可把原 prompt 作为一个候选；否则每个候选都应体现测试方向。
5. 用 `delegate_task(tasks=[...])` 并行生成图片，保存每张图实际使用的最终 prompt。

## 参考图风格测试流程

1. 从参考图中提取可复用的风格要点：媒介、构图、光线、色彩、材质、镜头/画幅、氛围和明显限制。
2. 默认生成 3 个不同侧重点的 prompt 模板。模板必须保留占位符，例如 `{主体}`、`{场景}`、`{动作}`、`{时间}`、`{配色}`；占位符名称按画面需要调整。
3. 为了测试效果，给每个模板随机填入具体内容，记录“模板版本”和“本次填充值/最终 prompt”。
4. 用 `delegate_task(tasks=[...])` 并行生成测试图。用户选择某个版本后，最终交付保留占位符的模板，而不是只交付本次随机填充后的 prompt。
5. 生成后对每张测试图做一次简短视觉复核（优先用 `vision_analyze`）：是否贴近参考图的媒介/构图/主体/色彩/质感，指出最明显优点与问题，并把评估保存为 `evaluation.md` 或写入 `manifest.md`。这一步尤其适合参考图风格复刻，因为能发现提示词中需弱化或强化的元素。
6. 用户要求继续复刻或迭代时，沿用上一轮选中的风格要点和模板结构继续测试。

## 输出目录

目录名建议：

```text
~/Downloads/image-prompt-test-YYYYMMDD-HHMMSS-<slug>/
```

至少包含：

```text
original-input.txt
manifest.md
prompts.json
01-prompt.txt
01-image.<ext>
02-prompt.txt
02-image.<ext>
03-prompt.txt
03-image.<ext>
```

参考图风格测试还要保存每个版本的占位符模板，例如 `01-template.txt`。保存后校验本地图片存在且非空；如果图片只能以 URL 形式保留，在 manifest 中写清楚。

如果做了视觉复核，额外保存：

```text
evaluation.md
```

## 常见迭代经验

- 如果参考图包含书法、印章、招牌等文字元素，而生成模型容易乱码：不要强求精确可读文字，优先写成“subtle/decorative/blurred calligraphy-like inscription, not meant to be readable”，并限制其“小、自然融入留白、不喧宾夺主”。
- 复刻传统绘画时，如果结果偏现代插画或高清写实：加入 `flatter mineral-pigment coloring, less dimensional shading, more blank space, low contrast distant background`，并在负面提示中写 `photorealistic lighting, digital illustration look, excessive saturation, hard shadows`。

## 最终回复

简洁列出：

- 输出目录
- 每个版本的图片路径/展示图
- 每张图实际使用的最终 prompt
- 参考图风格测试时，额外列出可复用的占位符模板和本次填充值
- 失败项和失败原因，不要把失败说成成功

## 收尾检查

- 已覆盖用户指定方向；未指定方向时已先问清楚。
- 默认数量为 3，除非用户指定。
- 多张图片已通过 `delegate_task(tasks=[...])` 按“一张图一个子任务”并行发起。
- 原 prompt 没有被过度改写。
- 图片、prompt、模板和 manifest 已保存到 `~/Downloads` 新目录。
- 参考图风格测试已保存简短视觉复核（如 `evaluation.md`）或在 manifest 中记录生成图优缺点。

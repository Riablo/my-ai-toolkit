---
name: sprite-sheet
description: 生成循环动画 sprite sheet 的提示词与后处理资源。用户要制作 4x4、16 帧、可无缝循环播放的精灵图，要求用固定参考图坐标对齐不变部位、纯品红 #ff00ff 背景方便抠图，或要把生成的 sprite sheet 裁剪、逐帧去背景并导出 1 秒 MPEG-4/MP4 视频、透明视频、GIF、竖排 PNG 时使用。
---

# Sprite Sheet

用于生成 4x4、16 帧的循环动画 sprite sheet，并把生成图后处理成 1 秒 MPEG-4/MP4 视频、透明视频、GIF 或竖排 PNG。

## 核心约定

- 每次生图都必须把 `./assets/loop-sprite-anchor-1024.png` 实际附加为 image reference；这个路径相对于本 skill 目录。不要只在文字里说“参考图”或只写路径。
- 默认生成单张 `1024x1024` sprite sheet：4 列 x 4 行，共 16 帧，每帧 `256x256`。
- 帧顺序为从左到右、从上到下，第 16 帧必须能自然衔接第 1 帧。
- 背景必须是纯品红 `#ff00ff`，不要渐变、阴影、纹理、透明背景、边框、网格线、编号或文字。
- 避免在主体、道具、法术、光效、阴影、高光和轮廓中使用 `#ff00ff` 或接近品红/亮紫的颜色。
- 每个 `256x256` 小图都是独立帧，任何主体、武器、特效或残影都不能跨出当前小图进入相邻小图。
- 每个小图四周留出安全边距，主体和特效不要占满格子；默认至少留约 16-24 px 空白。
- 每一帧都以当前 `256x256` 小图中心为锚点；不变的身体部位、道具部位或物体部位要落在同一个小图局部坐标上。
- 后处理必须先裁成 16 张小图，再逐帧以最大容差去除 `#ff00ff` 背景，最后再拼接视频、GIF 或竖排 PNG。
- 保留原始带品红背景的生成图；默认交付原始 sprite sheet 和 1 秒 MPEG-4/MP4 视频。只有用户明确要求透明视频、GIF 或竖排 PNG 时，才额外交付对应格式。
- 如果运行环境支持直接发送媒体文件，例如 Telegram、Hermes 或类似聊天工具，默认直接向用户发送原始 sprite sheet 图片和 MP4 视频，而不是只给路径。

## 生图提示词

先解析 skill 目录，找到并实际附上 `./assets/loop-sprite-anchor-1024.png` 作为 image reference。不要只把路径写进 prompt；如果生图工具支持多模态输入，必须把这张 PNG 作为参考图片传入。如果当前生图工具不能附加参考图片，停止生成并说明需要换用支持 image reference 的工具。

提示词保持短而硬，避免堆太多抽象约束。最后一段 `{动画内容描述}` 保持在提示词末尾，并替换成用户给出的主体、动作、风格、视角和特殊限制。

```text
请以随消息附上的参考图片 ./assets/loop-sprite-anchor-1024.png（loop-sprite-anchor-1024.png）作为唯一坐标锚点，生成一张用于循环动画的 4x4 sprite sheet，共 16 帧。

输出规格：
1. 输出必须是一张 1024x1024 PNG 图片。
2. 图片必须分成 4 列 x 4 行，共 16 个独立小图，每个小图都是 256x256。
3. 帧顺序为从左到右、从上到下。

每格锚点和边界：
1. 每一个 256x256 小图都以自己的中心点为锚点制作动画。
2. 同一个角色或物体不动的部位，必须在每个小图的同一局部坐标上对齐。
3. 每个小图四周都要留出安全空白，主体、武器、特效和残影不要占满格子。
4. 任何像素都不能跨出当前 256x256 小图边界；不要让相邻帧的身体、武器、特效或残影出现在其他小图里。

动画要求：
1. 16 帧表现同一个连续动作，相邻帧变化要平滑。
2. 第 16 帧要自然衔接第 1 帧，适合循环播放。
3. 不要为了表现动作而移动整个人物、缩小主体、重新居中或改变每格锚点。

背景和可抠图要求：
1. 所有帧的背景必须是完全一致的纯品红 #ff00ff。
2. 不要使用透明背景、渐变、纹理、阴影投射、边框、网格线、编号、水印或文字。
3. 主体、道具、特效、阴影、高光和轮廓都不要使用 #ff00ff 或接近品红/亮紫的颜色。

动画内容描述：
{动画内容描述}
```

## 后处理脚本

所有 Python 脚本用 `uv` 执行，并已带 PEP 723 依赖声明。生成视频还需要 `ffmpeg` 在 `PATH` 中可用。

生成默认视频：

```bash
uv run skills/sprite-sheet/scripts/make_video.py /path/to/generated-sprite-sheet.png --output-dir /path/to/output-dir
```

默认视频是 Telegram 风格的 MPEG-4/MP4：16 帧、1 秒、16fps，使用 H.264、`yuv420p`、无音频、`faststart`，体积小且播放性能好。MP4/H.264 不保留 alpha；脚本仍会先抠背景并保留透明帧，再把透明区域铺成纯黑 matte 后编码 MP4。

需要保留 alpha 时再显式生成透明视频：

```bash
uv run skills/sprite-sheet/scripts/make_video.py /path/to/generated-sprite-sheet.png --output-dir /path/to/output-dir --format webm
uv run skills/sprite-sheet/scripts/make_video.py /path/to/generated-sprite-sheet.png --output-dir /path/to/output-dir --format mov
```

用户明确要求 GIF 时再生成 GIF：

```bash
uv run skills/sprite-sheet/scripts/make_gif.py /path/to/generated-sprite-sheet.png --output-dir /path/to/output-dir
```

用户明确要求竖排 PNG 时再生成竖排 PNG：

```bash
uv run skills/sprite-sheet/scripts/make_vertical_png.py /path/to/generated-sprite-sheet.png --output-dir /path/to/output-dir
```

常用参数：

- `--name <stem>`：指定输出文件名前缀。
- `--duration-seconds 1.0`：视频时长，默认 1 秒，16 帧正好 16fps。
- `--format mp4`：视频格式，默认 MP4；可选 `webm` 或 `mov` 用于透明视频。
- `--crf 30`：MP4 H.264 压缩质量，数值越高体积越小。
- `--matte-color '#000000'`：MP4 不支持 alpha 时用于填充透明区域的颜色，默认黑色。
- `--duration-ms 80`：GIF 每帧时长，默认 80ms。
- `--background '#ff00ff'`：要抠掉的背景色，默认 `#ff00ff`。
- `--tolerance 100`：背景色 RGB 容差，默认使用最大值 `100`，与 `sprite-sheet-player.html` 的抠图逻辑一致。
- `--cols 4 --rows 4`：sprite sheet 网格，默认 4x4。

脚本会输出：

- `<name>-original.png`：原始带背景 sprite sheet 副本。
- `frames-transparent/frame-01.png` 到 `frame-16.png`：先裁剪再抠背景后的透明帧。
- `<name>.mp4`、`<name>.mov`、`<name>.webm`、`<name>.gif` 或 `<name>-vertical.png`：目标格式。

## 交付检查

- 确认原始 sprite sheet 是 4x4、16 帧，且整体尺寸能被 4x4 整除。
- 确认原始图仍保留，透明帧是裁剪后逐帧抠背景得到的。
- 默认向用户返回原始 sprite sheet 和 MP4 视频；如果聊天工具支持文件/媒体发送，直接发送这两个文件。
- 同时保留输出目录路径，方便用户继续取用原图、视频和透明帧。
- 用户要求透明视频、GIF 或竖排 PNG 时，同时返回对应路径；不要把 GIF 作为默认产物。
- 如果透明边缘有品红残留，先确认使用的是默认 `--tolerance 100`，仍有问题再调高生成提示词对纯品红背景的要求；不要先拼接再抠图。

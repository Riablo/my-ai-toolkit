---
name: yun720
description: 当用户要上传全景素材到 720 云、查询 pano 制作状态、等待任务完成、创建 720 漫游作品，或先生成 2:1 全景图再创建作品时使用。
---

# yun720

使用已安装并配置好的 `yun720` CLI 操作 720 云开放平台。正文只保留工作流和高价值注意事项；参数细节以运行时帮助为准。

## 核心原则

- 不要凭记忆猜参数；执行前先看 `yun720 -h`
- 子命令或状态值不确定时，再看对应子命令帮助
- 源码仓库不是运行时依赖；不要假设某个本地源码路径长期存在
- 真实执行前先确认用户给的图片、目录、`panoId`、作品名等关键输入是否足够

## 帮助探测

```bash
yun720 -h
yun720 config -h
yun720 pano upload -h
yun720 pano status -h
yun720 pano wait -h
yun720 tour create -h
```

## 路由规则

- 看配置是否生效：`yun720 config show`
- 上传素材：`yun720 pano upload ...`
- 查询制作结果：`yun720 pano status <taskId>`
- 等素材制作完成：`yun720 pano wait <taskId>`
- 用已有 `panoId` 创建作品：`yun720 tour create --name ... --panos ...`
- 用本地图片一体化创建作品：`yun720 tour create --name ... --from ...`

## 高价值 gotchas

- 执行真实请求前先做轻量配置确认；如果 `config show` 都失败，不要继续上传或创建
- 素材要求以运行时帮助为准，但常见情况是：单张 2:1 等距柱状全景图，或按要求命名的六面体 JPG/JPEG
- 用户给的是 PNG/WebP 时，通常需要先转成 JPG/JPEG，再检查尺寸比例
- macOS 自带 Bash 3.2 可能不够；若出现 `${p,,}: bad substitution`，优先用 Homebrew Bash 运行
- 长流程可能耗时较久；执行时要保留 stdout/stderr，方便提取 `taskId`、`panoId`、作品 ID、预览链接和错误原因

## “先生成图片再创建作品”

当用户没有现成全景素材，而是要先生成图片：

1. 先生成 2:1 比例、可用于 360 播放器的 equirectangular panorama
2. 保存到本地，必要时转成 `.jpg`
3. 检查尺寸是否接近 2:1；不合格时先说明并重试或后处理
4. 再执行 `pano upload` 或 `tour create --from`

提示词重点：

- 明确要求 `equirectangular 360 panorama`
- 强调左右边缘无缝衔接
- 不要把主体放在左右边缘拼接处
- 不要出现文字、水印、边框或 UI

## 输出转述

- 上传素材：成功/失败、`taskId`、`panoId`、是否已进入制作队列
- 查询或等待：当前任务状态、失败原因、下一步建议
- 创建作品：作品 ID、`tid`、预览链接
- 若包含生成图片流程，再补本地图片路径与尺寸

默认不要整段倾倒原始 JSON；只提关键字段。

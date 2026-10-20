# img

图片压缩、格式转换与改尺寸。目标是视觉无损：几乎看不出差别的前提下尽量压小，不提供画质选项。

```bash
img compress photo.jpg shot.png         # 原地替换，原图移到废纸篓
img compress -o out *.png               # → out/*.png，原图不动
img convert -t webp IMG_0001.heic       # → IMG_0001.webp
img convert -t avif -o ~/Desktop/out *.png
img resize -w 1200 photo.jpg            # 等比缩放 → photo.1200x900.jpg
img resize -H 600 photo.webp            # 等比缩放
img resize -w 800 -H 800 avatar.png     # 强制缩放到 800x800
img resize --help                       # 各命令的选项和示例
```

- `compress` 直接替换原图，原图通过 macOS 自带的 `trash` 命令移到废纸篓，可在访达中放回；文件名和权限不变
- `convert` / `resize` 输出到原图所在目录；`-o <目录>` 指定其他目录（不存在时自动创建），`compress` 指定 `-o` 时原图不动
- 已存在的输出文件默认不覆盖，`-f` 才覆盖；`convert` / `resize` 任何情况下都不会覆盖原图
- `compress` 和 `resize` 只支持 png / jpg / webp / avif；其他格式先 `convert`
- `convert` 的输入可以是 vips 能读的任意格式（HEIC、TIFF、GIF、BMP、JPEG XL、SVG、PDF、相机 RAW 等），输出 png / jpg / webp / avif
- 不支持动图，多帧图片只取第一帧
- 去掉 EXIF / XMP 等元数据，保留 ICC 色彩配置，EXIF 方向直接应用到像素上
- `compress` 省不到 5% 时视为已是最优，不做改动，避免对有损格式白白再损失一次画质

## 依赖

全部通过 Homebrew 全局安装，缺少时 `img` 会提示安装命令；`compress` 原地替换还需要 macOS 15 及以上自带的 `trash`：

```bash
brew install vips oxipng pngquant libavif jpeg-turbo jpeg-xl
```

## 各格式的处理方式

格式识别按文件内容，不看扩展名。解码、旋转、缩放统一由 libvips 完成，编码按格式选用专门工具：

| 格式 | 工具 | 做法 |
| --- | --- | --- |
| PNG | pngquant + oxipng | pngquant 量化为调色板，结果的 SSIMULACRA2 低于 80（照片、渐变常见）时退回无损；最后 oxipng `-o 4` 无损优化 |
| JPEG | mozjpeg（vips 内置）+ jpegtran | mozjpeg Q85 重新编码；`compress` 时同时用 jpegtran 无损优化原图，取较小者 |
| WebP | libwebp（vips） | Q90 + smart subsample；源图为无损格式时额外尝试无损编码，取较小者 |
| AVIF | avifenc（libavif + libaom） | q75、speed 4，libaom 3.13+ 默认启用 `tune=iq` |

质量参数在脚本开头，按 SSIMULACRA2 约 80–88（几乎看不出差别）在照片和截图样本上校准。WebP 在高画质区间效率不如 mozjpeg 和 AVIF，所以质量档位更高。

## 测试

```bash
bash cli/img/test_img.bash
```

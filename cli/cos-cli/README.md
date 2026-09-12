# cos-cli

将图片或文件夹上传到腾讯云 COS，参考个人 Raycast 扩展 `tencent-oss` 的上传逻辑。Bash 入口通过 `uv` 运行 Python，使用腾讯云官方 SDK 处理签名、上传和大文件分块。

## 安装

需要 Bash 5.0+ 和 `uv`，Python 3.10+ 及 SDK 依赖由 `uv` 管理，首次运行会下载依赖。

```bash
# macOS 按需安装依赖
brew install bash uv

# 在 my-ai-toolkit 根目录运行，安装命令及补全
bash scripts/install.sh
```

## 配置

```bash
cos-cli config init
# 编辑 ~/.config/cos-cli/config.json，填入凭据并核对上传目标
cos-cli config check
```

`config init` 创建权限为 `600` 的模板，不覆盖已有文件。新建的配置目录权限为 `700`。Secret ID、Secret Key、临时令牌只从配置读取，不提供命令行参数。

模板如下；其中 bucket、region、domain 沿用 Raycast 插件默认值，请按实际账号修改：

```json
{
  "secret_id": "",
  "secret_key": "",
  "bucket": "static720-1347846699",
  "region": "ap-beijing",
  "domain": "https://static-t.720static.com",
  "prefix": "imgs",
  "use_md5": true,
  "security_token": "",
  "timeout": 60
}
```

| 字段 | 说明 |
| --- | --- |
| `secret_id` | 必填，腾讯云 Secret ID，对应 Raycast 的 `secret-id` |
| `secret_key` | 必填，腾讯云 Secret Key，对应 Raycast 的 `secret-key` |
| `bucket` | 必填，完整存储桶名，包含 `-APPID` |
| `region` | 必填，如 `ap-beijing` |
| `domain` | 返回链接使用的自定义域名，可带路径前缀；省略或留空时使用该存储桶的 COS 默认域名 |
| `prefix` | 对象路径前缀，默认 `imgs`；`""` 表示根目录 |
| `use_md5` | 默认 `true`，文件名加入内容 MD5 |
| `security_token` | 可选，STS 临时凭据的 Token；使用长期密钥时留空 |
| `timeout` | 每次 SDK 请求的超时时间，默认 60 秒，范围 1–3600 |

上传和预览每次都会校验配置；必填项缺失、未知字段、错误类型或无效地址会直接报错。`config check` 仅做本地校验，不验证云端权限。

```bash
cos-cli config path       # 显示路径
cos-cli config show       # 脱敏查看；三个凭据字段不会显示原值
cos-cli --config ~/.config/cos-cli/other.json config init
cos-cli --config ~/.config/cos-cli/other.json a.png
```

## 上传

```bash
cos-cli a.png                          # 单张图片
cos-cli a.png b.jpg '/tmp/截图 1.webp'  # 多张图片
cos-cli ./photos                       # 递归上传文件夹中的图片
cos-cli ./photos cover.png             # 可以混合文件夹与文件
cos-cli ./photos --prefix imgs/blog    # 临时覆盖前缀
cos-cli a.png --no-md5                 # 关闭 MD5 重命名
cos-cli a.png --md5                    # 覆盖配置，启用 MD5
cos-cli a.png --prefix ''              # 上传到存储桶根目录
cos-cli ./photos --dry-run --json      # 预览真实 Key、URL 和大小，不连接 COS
cos-cli ./assets --all-files           # 包含非图片，与 Raycast 文件夹上传一致
cos-cli -- --leading-dash.png          # 以 - 开头的文件名
```

也支持 `cos-cli upload ...`。选项可放在路径前后；与命令同名的本地路径请写成 `./config` 或 `./upload`。

目录上传保留所选文件夹名及内部层级，和原插件一致：

```text
输入：photos/旅行/海边 1.jpg
默认：imgs/photos/旅行/海边_1.<文件内容的32位MD5>.jpg
关闭 MD5：imgs/photos/旅行/海边_1.jpg

直接传入单文件 photos/旅行/海边 1.jpg：
默认：imgs/海边_1.<文件内容的32位MD5>.jpg
```

- 前缀、目录名、文件名中的空格均变成 `_`。输出 URL 对中文、`#`、`%` 等字符编码，上传 Key 保留原字符。
- 默认按扩展名识别图片，大小写不敏感：jpg、jpeg、png、gif、webp、svg、bmp、avif、heic、heif、tif、tiff、ico、apng、jxl。不会解码检查或转换图片。
- 文件夹中的非图片被跳过；直接指定非图片时报错，除非传 `--all-files`。目录遍历跳过符号链接；直接传入符号链接会提示使用实际路径。
- 所有输入、可读性和本批次 Key 冲突在上传前检查。同一个路径重复映射到同一 Key 时去重；不同文件映射到同一 Key 时拒绝整批上传。
- **已存在于 COS 的同名 Key 会按存储桶设置覆盖或产生新版本**，与 Raycast 一致。关闭 MD5 时尤其需要留意同名文件。
- 上传不改变存储桶或对象的访问权限；链接能否直接访问取决于现有 COS/CDN 配置。`domain` 只影响返回链接，文件仍上传到配置的 COS 存储桶。

## 输出

默认 stdout 每行一个成功上传的 URL，进度和错误写入 stderr，可用于管道或重定向：

```bash
cos-cli ./photos > urls.txt
cos-cli ./photos | pbcopy                 # macOS 复制全部 URL
cos-cli ./photos --format key             # 输出对象 Key
cos-cli ./photos --format markdown        # 输出 Markdown 图片引用
cos-cli ./photos --json                   # 结构化结果，等同 --format json
```

`--dry-run` 沿用所选输出格式，stderr 显示本地路径到 Key 的映射和“未发起上传”。JSON 包含 `dry_run`、`bucket`、`region`、`total`、`uploaded`、`failed`、`interrupted` 和 `results`；每个结果包含 `file`、`key`、`url`、`size`、`content_type`、`status`，上传成功后另有 `etag`，失败时有 `error`。

单文件上传失败会继续处理剩余文件；文本格式只输出成功项，JSON 保留失败项。退出码：`0` 全部成功或预览通过，`1` 配置／文件／上传错误（包括部分失败），`2` 参数错误，`130` 用户中断。已上传文件不会因后续失败或中断而回滚。

## 开发验证

```bash
uv run --with cos-python-sdk-v5==1.9.44 python -m unittest discover -s cli/cos-cli -p 'test_*.py' -v
bash -n cli/cos-cli/cos-cli
zsh -n cli/cos-cli/_cos-cli
fish -n cli/cos-cli/cos-cli.fish
```

测试使用临时配置与模拟 COS 响应，不访问真实存储桶。

接口参考：[腾讯云 COS Python SDK](https://github.com/tencentyun/cos-python-sdk-v5)、[官方示例](https://github.com/tencentyun/cos-python-sdk-v5/blob/master/demo/demo.py)。

# testpage-cli

测试 HTML 页面快速发布工具。

它会把一个包含 HTML 和静态资源的本地目录同步到配置好的 `html_test` Git 项目里，然后自动执行：

- `git fetch`
- `git pull --ff-only`
- 覆盖目标目录
- `git add`
- `git commit`
- `git push`

任一步 Git 失败都会立刻停止，不会继续往下执行。

## 安装

在仓库根目录执行：

```bash
bash scripts/install.sh
```

确保 `~/.local/bin` 在 `PATH` 中，然后运行：

```bash
testpage-cli --help
```

## 初始化

首次使用先写入配置：

```bash
testpage-cli init --project-root /Users/cz/Work/html_test
```

也可以显式指定访问前缀：

```bash
testpage-cli init \
  --project-root /Users/cz/Work/html_test \
  --base-url https://test.720yun.com/html_test/
```

配置文件位置：

```bash
testpage-cli config path
```

默认会写到：

```text
~/.config/testpage-cli/config.conf
```

配置文件示例：

```text
project_root=/Users/cz/Work/html_test
base_url=https://test.720yun.com/html_test/
```

## 用法

默认使用源目录名作为发布目录名：

```bash
testpage-cli push ./why-html-over-markdown
```

返回：

```text
https://test.720yun.com/html_test/why-html-over-markdown/
```

发布时重命名：

```bash
testpage-cli push ./dist --name T2Vision-demo
```

发布到子目录下：

```bash
testpage-cli push ./dist --subdir chenzheng --name why-html-over-markdown
```

返回：

```text
https://test.720yun.com/html_test/chenzheng/why-html-over-markdown/
```

## 行为说明

- `push` 只接受目录作为输入，目录里至少要有一个 `.html` 或 `.htm` 文件
- `--subdir` 必须是相对路径，不能包含 `..`
- `--name` 是最终目录名，不能包含 `/`
- 目标目录已存在时，会先整体删除再复制，避免旧资源残留
- 发布前会检查 `project_root` 是否是 Git 仓库，且工作区必须是干净的
- 如果复制后目标内容没有变化，就不会 commit 或 push，只直接返回 URL
- `push` 会排除源目录中的 `.git/`

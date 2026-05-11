---
name: web-app-dockerizer
description: 当用户给出一个项目目录，并要求把本地 Web App、Bun/npm/pnpm/yarn 服务、旧常驻进程或 macOS 自启动方式迁移为 Docker / Docker Compose 长期运行时使用。
---

# Web App Dockerizer

把已有本地 Web App 改造成 Docker Compose 运行方式。目标不是“加一个 Dockerfile”，而是让服务由 Docker 稳定接管，同时保留原访问方式、宿主机数据和普通 Git 工作流。

## 默认工作流

1. 先读项目，不要猜技术栈：看 README、锁文件、package scripts、源码入口、环境变量、现有 Docker 配置和本地数据文件。
2. 识别旧运行方式：LaunchAgent/LaunchDaemon、tmux/screen、pm2/forever、nohup、手写脚本、后台进程和目标端口监听者。
3. 设计最小 Docker 层：通常补 `Dockerfile`、`compose.yaml`、`.dockerignore`、README Docker 说明；有 `package.json` 时可补维护 scripts。
4. 保护数据：把 SQLite、JSON 数据、上传目录、缓存中实际属于用户数据的部分留在宿主机，用 volume 挂进容器。
5. 停用旧机制：只在确认旧启动项属于当前项目后停止和禁用，避免 Docker 与旧方式抢端口。
6. 验证：构建镜像、启动 compose、检查容器状态、访问原地址、确认数据可读、确认端口由 Docker 接管。

需要完整检查表时，读 [references/migration-checklist.md](references/migration-checklist.md)。

## Docker 化原则

- 依据真实包管理器生成运行层：Bun 用 Bun，pnpm 用 pnpm，npm 用 npm，不机械套模板。
- 默认让容器监听 `0.0.0.0` 或框架要求的容器内地址，但宿主机端口默认只绑定 `127.0.0.1`。
- 尽量保持原宿主机端口和访问 URL；除非用户明确要求，不暴露到局域网或公网。
- 不为了容器化重构业务代码；只有监听地址、数据路径、启动命令不适合容器时才做小范围调整。
- 不把 `.git`、依赖目录、日志、临时文件、本地数据和私密 `.env` 打进镜像。
- 不把 `git pull`、SSH key 或代码同步逻辑放进应用容器；保留“宿主机拉代码，再 compose build/up”的工作流。

## 高风险边界

- 数据目录不明确时先问用户，或保守挂载；不要删除、移动或只复制进镜像。
- 旧启动项名称、路径或端口归属不明确时，不要禁用；先收集证据并说明风险。
- 端口被占用不等于可以杀进程；先确认进程命令、cwd、plist、tmux 会话或 pm2 应用名确实指向当前项目。
- `.env` 可用于 compose 读取，但不要把私密值写进 Dockerfile 或提交到新文件里。
- 若 Docker/OrbStack 不可用，仍可完成文件改造，但必须明确哪些 Docker 验证没跑。

## 维护入口

如果项目有 `package.json`，优先加入清晰的 Docker 维护脚本，例如：

- `docker:up`
- `docker:update`
- `docker:logs`
- `docker:ps`
- `docker:down`

脚本只是方便用户记忆；真正的运行定义应在 Compose 配置中。

## 最终汇报

汇报先给迁移结论，再列关键事实：

- 技术栈、包管理器、启动命令和端口
- 数据目录或数据文件如何保留
- 停用了哪些旧运行方式，哪些因不明确而未动
- 新增或修改的 Docker 相关文件
- 做过的验证和结果
- 当前服务是否已由 Docker 运行
- 以后更新代码并让 Docker 生效的命令

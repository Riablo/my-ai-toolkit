# Web App Dockerization Checklist

这份 reference 在真正迁移项目时读取。它补充执行清单和验收口径，不替代项目自身 README、脚本和源码事实。

## 侦察

先确认这些事实：

- 包管理器：看 `bun.lockb`、`bun.lock`、`pnpm-lock.yaml`、`package-lock.json`、`yarn.lock`、Corepack 配置和 README。
- 启动命令：看 `package.json` scripts、README、Procfile、自定义 shell 脚本、源码入口。
- 端口：看环境变量、默认常量、框架配置、README、当前监听进程。
- 监听地址：确认应用是否能配置 host；容器内通常不能只监听 `127.0.0.1`。
- 数据：找 SQLite、JSON/NDJSON、上传目录、`data/`、`storage/`、`uploads/`、本地数据库路径、自定义 env 路径。
- 现有容器化：读已有 `Dockerfile`、`docker-compose.yml`、`compose.yaml`、`.dockerignore`，优先修补而不是重写。
- 旧运行方式：查 plist、tmux/screen、pm2/forever、nohup、后台 shell、端口占用进程。

## 旧运行方式

处理顺序：

1. 证明它属于当前项目：命令行、工作目录、plist 内容、脚本路径、服务名或端口都应能对上。
2. 优先使用项目自带 stop 脚本或进程管理器命令。
3. 对 LaunchAgent/LaunchDaemon，不只停止当前进程，还要禁用后续自动拉起。
4. 停用后再次检查端口和进程，确认旧方式不会马上重启。

不确定时不要动，向用户说明发现了什么、为什么不能确认。

## Docker 文件

常见交付物：

- `Dockerfile`：根据真实包管理器安装依赖、构建并启动。
- `compose.yaml`：构建当前项目、设置 restart 策略、绑定端口、挂载数据、传入必要环境变量。
- `.dockerignore`：排除依赖目录、Git 元数据、日志、临时文件、构建产物、本地数据和私密环境。
- `README.md`：写推荐 Docker 运行方式、启动/更新/日志/停止、默认地址、数据保留方式。
- `package.json` scripts：如存在 package.json，可补 `docker:*` 维护命令。

Compose 默认倾向：

- `restart: unless-stopped`
- 端口绑定为 `127.0.0.1:<host-port>:<container-port>`
- 数据 volume 使用宿主机相对路径或明确目录
- 环境变量中显式传 `HOST=0.0.0.0`、`PORT=<container-port>` 或框架实际需要的名称

## 数据保留

验收重点：

- 原有数据文件仍在宿主机。
- 容器读取的是同一份数据，或是明确迁移后的宿主机数据。
- 容器删除重建后数据仍在。
- 应用需要数据路径 env 时，路径应指向容器内挂载点。

不要把用户数据只 COPY 进镜像。不能确认数据归属时，宁可挂载和说明，也不要删除。

## 验证

优先执行：

- 原有测试、lint 或类型检查，如果项目已有这些入口。
- `docker compose build`
- `docker compose up -d`
- `docker compose ps`
- `docker compose logs` 或健康检查相关日志
- 用 curl 或浏览器访问原本的本机 URL。
- 检查核心页面/API 响应。
- 检查数据是否能读到。
- 检查端口监听者已变为 Docker/容器链路。
- 检查旧启动机制没有重新拉起。

如果本机没有 Docker 或 OrbStack，说明只能完成静态改造，并列出未验证项。

## 交付汇报模板

最终回复按这些字段组织，缺失项也要说明：

- 识别到的技术栈和包管理器
- 启动命令、监听地址和端口
- 数据目录/文件及 volume 挂载方式
- 旧运行方式处理结果
- 新增或修改文件
- package scripts 是否添加
- 验证命令和结果
- 当前是否已由 Docker 运行
- 以后更新流程

更新流程通常是：在宿主机项目目录 `git pull`，然后 `docker compose up -d --build` 或项目提供的 `docker:update`。

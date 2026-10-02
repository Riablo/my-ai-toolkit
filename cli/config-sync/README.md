# config-sync

直接执行命令，把配置中的所有文件和目录单向推送到所有 SSH 主机；加 `--host` 时只同步指定主机的全部内容。使用 rsync，覆盖前备份。只读取执行机器上的配置：A 配了 B 才会推送到 B；B 是否推送到 A 取决于 B 自己的配置。

依赖：本机 Bash 5+、Python 3.11+、ssh 和 rsync；目标机需要 POSIX sh、rsync、cp 等常规工具。兼容 macOS 自带的 openrsync / rsync 2.6.9。SSH 使用 `BatchMode=yes`，应提前配置密钥登录及主机指纹；端口、IdentityFile 等放在 `~/.ssh/config`。

## 配置与使用

从仓库根目录安装、创建配置：

```bash
bash scripts/install.sh
config-sync init
```

默认配置是 `~/.config/config-sync/config.toml`，支持 `XDG_CONFIG_HOME` 和 `--config 路径`，例如 `config-sync init --config /path/to/config.toml`。

`init` 自动创建父目录，以私有权限写入**全注释的配置模板**，不会启用任何主机或同步项，也不会连接 SSH。模板包含多主机、同路径 / 两端不同路径、文件 / 目录的示例和使用说明；同时取消所需表头与配置项的注释，再修改主机 / 路径即可使用。已有配置（包括空文件、目录或软链接）一律拒绝覆盖；`init` 只接受 `--config`，不接受同步项、`--host` 或 `--dry-run`。

TOML 支持 `#` 注释；完整模板见 [config.example.toml](config.example.toml)。下面是取消注释后的配置示例：

```toml
[hosts.home.files]
htask = "~/.config/htask/config.toml"         # 单路径：两端同路径
zsh = ["~/.zshrc", "~/.config/zsh/.zshrc"]    # [本机路径, 目标路径]

[hosts.home.dirs]
nvim = "~/.config/nvim/"                     # 末尾 / 可有可无

[hosts.office]
ssh = "user@workstation"                     # 可省略，默认 ssh office
[hosts.office.files]
htask = ["~/.config/htask/config.toml", "/srv/config/htask.toml"]
```

- `files` 是文件，`dirs` 是目录；键（如 `htask`）只是便于阅读和日志定位的标签，**不需要在命令中输入，也不能用于选择部分内容**。标签支持字母、数字、`_`、`-`、`.`，以字母或数字开头；同一主机的文件 / 目录标签不能重名。含 `.` 的 TOML 键须加引号。
- 单字符串表示同路径；两个字符串固定为 **[本机, 目标]**。路径只能是绝对路径或 `~/...`；`~` 分别指两台机器各自的家目录。不展开 `$变量`、通配符或 `~其他用户`，不接受根目录、家目录、`.` / `..` 路径段或专用备份路径。
- 目标文件路径是**完整文件名**；目标目录路径是**目录本身**。目录始终同步内容，不会额外嵌套一层同名目录。目标父目录不存在时自动创建。
- 同一 SSH 地址的目标路径不能重复或嵌套；也不要用不同 SSH 别名或绝对路径 / `~` 表示同一个目标来绕过此限制。

```bash
config-sync list                            # 查看当前配置
config-sync --dry-run                       # 校验全部本机来源并显示计划，不联网
config-sync                                 # 同步所有主机的全部文件和目录
config-sync --host home                     # 同步 home 配置的全部内容
config-sync -H home -H office               # 同步指定多台主机的全部内容
config-sync clean --dry-run                  # 查看备份清理范围
config-sync clean                           # 清理当前配置涉及的所有目标的备份
config-sync clean -H home                    # 只清理 home
```

省略 `--host` 时，同步所有主机各自声明的全部内容，各主机不需要配置相同的标签。显式指定主机时，只同步这些主机的全部内容；未配置文件或目录的主机自动跳过。命令不接受同步项名称参数，帮助使用 `--help` 查看。未知主机、无效配置或所选主机的本机来源不存在 / 类型不符都会报错，且在连接任何主机前检查完整配置和所选主机的全部本机来源。配置缺失 / 为空 / 没有同步项时不执行操作。zsh 补全仅提供子命令和配置中的主机名，支持 `--config`，不连接目标机器。

## 覆盖和备份边界

**目录是完整镜像，目标多余内容会被删除，包括隐藏文件。** rsync 使用校验和判断内容，即使文件大小和修改时间相同也能覆盖不同内容；保留权限、修改时间和目录内的软链接，不复制 owner / group。本机文件软链接发送实际文件内容；目标文件 / 目录本身是软链接或类型不符时拒绝覆盖。

每次推送前，已有目标整体复制到同级的 `.<目标名>.config-sync-backups/<时间戳>-<随机值>`，例如：

```text
~/.config/htask/config.toml
~/.config/htask/.config.toml.config-sync-backups/20261002T120000-a1b2c3d4e5f6
```

备份根目录以私有权限创建，内含 `.owner` 标记；每次执行不会覆盖旧快照。目标不存在时不创建备份。备份失败就不传输；传输失败保留备份并停止后续同步项。多主机推送不是事务：先前已成功的目标不会自动回滚；同步期间不要并发修改目标或同时推送到同一目标。

`clean` **无需二次确认，会不可恢复地删除备份**，但不改当前目标。它只处理当前配置路径的专用备份目录，且检查标记和目录类型；不会递归扫描目标主机或通过通配符删除其他文件。删掉 / 改名配置项后，原路径的旧备份不会再被自动清理，请保留该项执行清理，或手动处理。

需要恢复时，可从命令输出的快照路径手动复制回原路径；恢复目录时先移开现有目录，避免合并残留文件。配置和备份可能包含凭据，请只推送到你信任并有权限覆盖的机器。

## 本地回归

```bash
python3 cli/config-sync/test_config_sync.py
bash -n cli/config-sync/config-sync
zsh -n cli/config-sync/_config-sync
```

测试以本地假 SSH 执行真实 rsync 收发、备份和清理，目标全部是临时目录，不访问真实主机。

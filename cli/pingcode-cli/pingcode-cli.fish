# Fish completions for pingcode-cli

# 禁用文件补全
complete -c pingcode-cli -f

# 主命令
complete -c pingcode-cli -n '__fish_use_subcommand' -a 'bugs' -d '列出我的未解决缺陷'
complete -c pingcode-cli -n '__fish_use_subcommand' -a 'set-state' -d '修改缺陷状态'
complete -c pingcode-cli -n '__fish_use_subcommand' -a 'config' -d '管理配置'

# set-state 状态补全（第二个参数）
complete -c pingcode-cli -n '__fish_seen_subcommand_from set-state' -a '待处理 处理中 已修复 重新打开 挂起' -d '目标状态'

# config 子命令
complete -c pingcode-cli -n '__fish_seen_subcommand_from config' -a 'show' -d '查看当前配置'
complete -c pingcode-cli -n '__fish_seen_subcommand_from config' -a 'init' -d '初始化配置'
complete -c pingcode-cli -n '__fish_seen_subcommand_from config' -a 'edit' -d '编辑配置文件'
complete -c pingcode-cli -n '__fish_seen_subcommand_from config' -a 'path' -d '显示配置文件路径'

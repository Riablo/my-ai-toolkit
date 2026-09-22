# Fish completions for pingcode-cli

function __pingcode_config_file
    if set -q XDG_CONFIG_HOME
        echo "$XDG_CONFIG_HOME/pingcode-cli/config.json"
    else
        echo "$HOME/.config/pingcode-cli/config.json"
    end
end

function __pingcode_projects
    set -l file (__pingcode_config_file)
    test -r "$file"; and jq -r '.projects[]?.name' "$file" 2>/dev/null
end

complete -c pingcode-cli -f
complete -c pingcode-cli -n '__fish_use_subcommand' -a config -d '管理配置'
complete -c pingcode-cli -n '__fish_use_subcommand' -a auth -d '获取或刷新用户令牌'
complete -c pingcode-cli -n '__fish_use_subcommand' -a doctor -d '检查运行环境与 API'
complete -c pingcode-cli -n '__fish_use_subcommand' -a projects -d '查看或刷新项目缓存'
complete -c pingcode-cli -n '__fish_use_subcommand' -a bugs -d '获取 bug 列表'
complete -c pingcode-cli -n '__fish_use_subcommand' -a bug -d '获取一个 bug'
complete -c pingcode-cli -n '__fish_use_subcommand' -a comments -d '获取 bug 评论'
complete -c pingcode-cli -n '__fish_use_subcommand' -a set-state -d '修改 bug 状态'

complete -c pingcode-cli -s h -l help -d '显示帮助'
complete -c pingcode-cli -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from init show path set-created-after' -a init -d '初始化配置'
complete -c pingcode-cli -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from init show path set-created-after' -a show -d '脱敏查看配置'
complete -c pingcode-cli -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from init show path set-created-after' -a path -d '显示配置路径'
complete -c pingcode-cli -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from init show path set-created-after' -a set-created-after -d '设置日期起点（YYYY-MM-DD）'
complete -c pingcode-cli -n '__fish_seen_subcommand_from projects' -a refresh -d '刷新项目缓存'
complete -c pingcode-cli -n '__fish_seen_subcommand_from bugs' -l project -x -a '(__pingcode_projects)' -d '项目名称'
complete -c pingcode-cli -n '__fish_seen_subcommand_from bugs' -l created-after -x -d '覆盖全局 created_at 起点'
complete -c pingcode-cli -n '__fish_seen_subcommand_from set-state' -l state -x -a '已拒绝 重新打开 已修复 新提交 挂起 已发布 处理中' -d '目标状态，省略时交互选择'

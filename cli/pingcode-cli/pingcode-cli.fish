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

function __pingcode_states
    set -l file (__pingcode_config_file)
    test -r "$file"; and jq -r '[.projects[]?.states[]?.name] | unique[]' "$file" 2>/dev/null
end

complete -c pingcode-cli -f
complete -c pingcode-cli -n '__fish_use_subcommand' -a init -d '初始化配置'
complete -c pingcode-cli -n '__fish_use_subcommand' -a auth -d '获取或刷新用户令牌'
complete -c pingcode-cli -n '__fish_use_subcommand' -a projects -d '查看或刷新项目缓存'
complete -c pingcode-cli -n '__fish_use_subcommand' -a bugs -d '获取 bug 列表'
complete -c pingcode-cli -n '__fish_use_subcommand' -a bug -d '获取一个 bug'
complete -c pingcode-cli -n '__fish_use_subcommand' -a set-state -d '修改 bug 状态'

complete -c pingcode-cli -s h -l help -d '显示帮助'
complete -c pingcode-cli -n '__fish_seen_subcommand_from projects' -a refresh -d '刷新项目与状态缓存'
complete -c pingcode-cli -n '__fish_seen_subcommand_from bugs' -l project -x -a '(__pingcode_projects)' -d '项目名称'
complete -c pingcode-cli -n '__fish_seen_subcommand_from bugs' -l state -x -a '(__pingcode_states)' -d '状态名称（可重复）'
complete -c pingcode-cli -n '__fish_seen_subcommand_from bugs' -l created-after -x -d '覆盖全局 created_at 起点'
complete -c pingcode-cli -n '__fish_seen_subcommand_from set-state' -a '(__pingcode_states)' -d '目标状态'

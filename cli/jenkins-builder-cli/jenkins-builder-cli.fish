# Fish completions for jenkins-builder-cli

function __jbc_label_desc -a label
    switch "$label"
        case test
            echo "测试服"
        case prod
            echo "正式服"
        case '*'
            echo "未分类"
    end
end

function __jbc_emit_configured_jobs
    set -l cfg "$HOME/.config/jenkins-builder-cli/config.yaml"
    test -f "$cfg"; or return

    set -l in_jobs 0
    set -l key ""
    set -l label ""
    set -l aliases_mode 0
    set -l aliases

    while read -l line
        if not string match -q ' *' -- "$line"
            if test -n "$key"
                __jbc_emit_job "$key" "$label" $aliases
            end
            set key ""
            set label ""
            set aliases
            set aliases_mode 0

            if string match -q 'jobs:*' -- "$line"
                set in_jobs 1
            else if test $in_jobs -eq 1
                return
            end
            continue
        end

        test $in_jobs -eq 1; or continue

        if set -l match (string match -rg '^  "?(.+?)"?:$' -- "$line")
            if test -n "$key"
                __jbc_emit_job "$key" "$label" $aliases
            end
            set key $match
            set label ""
            set aliases
            set aliases_mode 0
        else if set -l match (string match -rg '^    label: (.+)' -- "$line")
            set label (string trim --chars='"' -- "$match")
        else if string match -q '    aliases:*' -- "$line"
            set aliases_mode 1
        else if test $aliases_mode -eq 1
            if set -l match (string match -rg '^    - (.+)' -- "$line")
                set -a aliases (string trim --chars='"' -- "$match")
            else if not string match -q '      *' -- "$line"
                set aliases_mode 0
            end
        end
    end <"$cfg"

    test -n "$key"; and __jbc_emit_job "$key" "$label" $aliases
end

function __jbc_emit_job -a key label
    set -l desc (string join '' "Job · " (__jbc_label_desc "$label"))
    printf '%s\t%s\n' "$key" "$desc"

    for alias in $argv[3..-1]
        printf '%s\tAlias -> %s\n' "$alias" "$key"
    end
end

complete -c jenkins-builder-cli -f

# top level
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'config' -d '管理本地配置'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'jobs' -d '列出和管理 jobs'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'build' -d '触发构建'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'set-branch' -d '修改分支配置'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'runs' -d '查看运行中的构建'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'logs' -d '查看 console output'

# config
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config' -a 'init show edit path check' -d 'config 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l url -d 'Jenkins URL'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l username -d '用户名'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l token -d 'API token'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l verify-ssl -d '是否校验证书'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config show' -l json -d '输出 JSON'

# jobs
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs' -a 'list label unlabel alias' -d 'jobs 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs list' -l query -d '按名称/标签/别称过滤'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs list' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs label' -ka '(__jbc_emit_configured_jobs)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs label' -a 'test prod' -d '标签'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs label' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs unlabel' -ka '(__jbc_emit_configured_jobs)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs unlabel' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs alias' -a 'list add rm' -d 'alias 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs alias list' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs alias add' -ka '(__jbc_emit_configured_jobs)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs alias add' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs alias rm' -ka '(__jbc_emit_configured_jobs)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs alias rm' -l json -d '输出 JSON'

# build / set-branch
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from build; and not __fish_seen_subcommand_from config jobs runs logs set-branch' -ka '(__jbc_emit_configured_jobs)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from build' -l follow -d '等待构建完成'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from build' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from set-branch' -ka '(__jbc_emit_configured_jobs)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from set-branch' -l json -d '输出 JSON'

# runs
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs' -a 'list status stop' -d 'runs 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs list' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs status' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs stop' -l json -d '输出 JSON'

# logs
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from logs' -l tail -d '仅展示最后 N 行'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from logs' -l follow -d '持续输出直到结束'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from logs' -l json -d '输出 JSON'

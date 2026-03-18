# Fish completions for jenkins-builder-cli

# 从 config.yaml 中提取指定 section 的 key 及其 env 字段
# 输出格式: name\tlabel · 环境  （供 Fish 补全使用）
function __jbc_completions -a section label
    set -l cfg "$HOME/.config/jenkins-builder-cli/config.yaml"
    test -f "$cfg"; or return
    set -l in_section 0
    set -l key ""
    set -l env_val ""
    while read -l line
        test -z "$line"; and continue
        if not string match -q ' *' -- "$line"
            if string match -q "$section:*" -- "$line"
                set in_section 1
            else if test $in_section -eq 1
                test -n "$key"; and __jbc_emit "$key" "$env_val" "$label"
                return
            end
            continue
        end
        if test $in_section -eq 1
            if set -l m (string match -rg '^  ([^ ].+):' -- "$line")
                test -n "$key"; and __jbc_emit "$key" "$env_val" "$label"
                set key $m
                set env_val ""
            else if set -l m (string match -rg '^    env: (.+)' -- "$line")
                set env_val $m
            end
        end
    end <"$cfg"
    test -n "$key"; and __jbc_emit "$key" "$env_val" "$label"
end

function __jbc_emit -a key env_val label
    set -l desc $label
    switch "$env_val"
        case test
            set desc "$label · 测试服"
        case prod
            set desc "$label · 正式服"
    end
    printf '%s\t%s\n' "$key" "$desc"
end

function __jbc_job_completions
    __jbc_completions jobs Job
end

function __jbc_group_completions
    __jbc_completions groups Group
end

complete -c jenkins-builder-cli -f

# top level
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'config' -d '管理本地配置'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'jobs' -d '列出和管理 jobs'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'groups' -d '管理 job 分组'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'build' -d '触发构建'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'set-branch' -d '修改分支配置'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'runs' -d '查看运行中的构建'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'logs' -d '查看 console output'

# config
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config' -a 'init show edit path' -d 'config 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l url -d 'Jenkins URL'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l username -d '用户名'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l token -d 'API token'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l verify-ssl -d '是否校验证书'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config show' -l json -d '输出 JSON'

# jobs
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs' -a 'list set-meta rm-meta' -d 'jobs 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs list' -l configured -d '仅显示已配置 jobs'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs list' -l query -d '按名称/描述过滤'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs list' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs set-meta' -ka '(__jbc_job_completions)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs set-meta' -l env -a 'test prod' -d '环境'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs set-meta' -l desc -d '描述'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs set-meta' -l keywords -d '关键词，逗号分隔'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs set-meta' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs rm-meta' -ka '(__jbc_job_completions)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs rm-meta' -l json -d '输出 JSON'

# groups
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups' -a 'list set-meta rm-meta build' -d 'groups 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups list' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups set-meta' -ka '(__jbc_group_completions)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups set-meta' -l jobs -d '包含的 job 名称'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups set-meta' -l env -a 'test prod' -d '环境'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups set-meta' -l desc -d '描述'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups set-meta' -l keywords -d '关键词，逗号分隔'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups set-meta' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups rm-meta' -ka '(__jbc_group_completions)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups rm-meta' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups build' -ka '(__jbc_group_completions)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups build' -l follow -d '等待构建完成'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from groups build' -l json -d '输出 JSON'

# build (positional: job name or group name)
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from build; and not __fish_seen_subcommand_from config jobs groups runs logs set-branch' -ka '(__jbc_job_completions)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from build; and not __fish_seen_subcommand_from config jobs groups runs logs set-branch' -ka '(__jbc_group_completions)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from build' -l follow -d '等待构建完成'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from build' -l json -d '输出 JSON'

# set-branch (positional: job name or group name)
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from set-branch' -ka '(__jbc_job_completions)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from set-branch' -ka '(__jbc_group_completions)'
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

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

    while read -l line
        if not string match -q ' *' -- "$line"
            if test -n "$key"
                __jbc_emit_job "$key" "$label"
            end
            set key ""
            set label ""

            if string match -q 'jobs:*' -- "$line"
                set in_jobs 1
            else if test $in_jobs -eq 1
                return
            end
            continue
        end

        test $in_jobs -eq 1; or continue

        if set -l match (string match -rg '^  ([^ ].*):$' -- "$line")
            if test -n "$key"
                __jbc_emit_job "$key" "$label"
            end
            set key (string trim --chars=\"\' -- "$match")
            set label ""
        else if set -l match (string match -rg '^    label: (.+)' -- "$line")
            set label (string trim --chars='"' -- "$match")
        end
    end <"$cfg"

    test -n "$key"; and __jbc_emit_job "$key" "$label"
end

function __jbc_emit_job -a key label
    set -l desc (string join '' "Job · " (__jbc_label_desc "$label"))
    printf '%s\t%s\n' "$key" "$desc"
end

complete -c jenkins-builder-cli -f

# Match the complete subcommand path and argument position. Boolean options
# may appear before the job name, but unrelated subcommands must not emit jobs.
function __jbc_at
    set -l words (commandline -opc)
    set -e words[1]
    set -l positional
    for word in $words
        contains -- "$word" --json --follow; and continue
        set -a positional "$word"
    end
    test (count $positional) -eq (count $argv); or return 1
    test (string join '\t' -- $positional) = (string join '\t' -- $argv)
end

function __jbc_after_job
    set -l words (commandline -opc)
    set -e words[1]
    set -l positional
    for word in $words
        contains -- "$word" --json --follow; and continue
        set -a positional "$word"
    end
    test (count $positional) -eq (math (count $argv) + 1); or return 1
    set -e positional[-1]
    test (string join '\t' -- $positional) = (string join '\t' -- $argv)
end

# top level
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'doctor' -d '检查配置和连接并同步 jobs'
complete -c jenkins-builder-cli -n '__jbc_at doctor' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'config' -d '管理本地配置'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'jobs' -d '列出和管理 jobs'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'build' -d '触发构建'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'set-branch' -d '修改分支配置'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'runs' -d '查看运行中的构建'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'logs' -d '查看 console output'

# config
complete -c jenkins-builder-cli -n '__jbc_at config' -a 'init show path' -d 'config 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l url -d 'Jenkins URL'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l username -d '用户名'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l token -d 'API token'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config init' -l verify-ssl -d '是否校验证书'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from config show' -l json -d '输出 JSON'

# jobs
complete -c jenkins-builder-cli -n '__jbc_at jobs' -a 'list label unlabel desc' -d 'jobs 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs list' -l query -d '按名称/标签/描述过滤'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs list' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__jbc_at jobs label' -ka '(__jbc_emit_configured_jobs)'
complete -c jenkins-builder-cli -n '__jbc_after_job jobs label' -a 'test prod' -d '标签'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs label' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__jbc_at jobs unlabel' -ka '(__jbc_emit_configured_jobs)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs unlabel' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__jbc_at jobs desc' -ka '(__jbc_emit_configured_jobs)'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs desc' -l json -d '输出 JSON'

# build / set-branch: job candidates belong only to the --job option.
for cmd in build set-branch
    complete -c jenkins-builder-cli -n "__fish_seen_subcommand_from $cmd" -l job -r -ka '(__jbc_emit_configured_jobs)' -d '完整 Jenkins job 名称'
    complete -c jenkins-builder-cli -n "__fish_seen_subcommand_from $cmd" -l branch -r -d '目标分支名称'
    complete -c jenkins-builder-cli -n "__fish_seen_subcommand_from $cmd" -l json -d '输出 JSON'
end
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from build' -l follow -d '等待构建完成'

# runs
complete -c jenkins-builder-cli -n '__jbc_at runs' -a 'list status stop' -d 'runs 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs list' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs status' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs stop' -l json -d '输出 JSON'

# logs
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from logs' -l tail -d '仅展示最后 N 行'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from logs' -l follow -d '持续输出直到结束'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from logs' -l json -d '输出 JSON'

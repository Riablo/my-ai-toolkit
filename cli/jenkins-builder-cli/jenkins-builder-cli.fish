# Fish completions for jenkins-builder-cli

complete -c jenkins-builder-cli -f

# top level
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'config' -d '管理本地配置'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'jobs' -d '列出和管理 jobs'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'build' -d '触发构建'
complete -c jenkins-builder-cli -n '__fish_use_subcommand' -a 'branch' -d '查看或修改分支配置'
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
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs set-meta' -l env -a 'test prod' -d '环境'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs set-meta' -l desc -d '描述'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs set-meta' -l alias -d '别名'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs set-meta' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from jobs rm-meta' -l json -d '输出 JSON'

# build
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from build' -l follow -d '等待构建完成'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from build' -l json -d '输出 JSON'

# branch
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from branch' -a 'show set' -d 'branch 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from branch show' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from branch set' -l json -d '输出 JSON'

# runs
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs' -a 'list status stop' -d 'runs 子命令'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs list' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs status' -l json -d '输出 JSON'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from runs stop' -l json -d '输出 JSON'

# logs
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from logs' -l tail -d '仅展示最后 N 行'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from logs' -l follow -d '持续输出直到结束'
complete -c jenkins-builder-cli -n '__fish_seen_subcommand_from logs' -l json -d '输出 JSON'

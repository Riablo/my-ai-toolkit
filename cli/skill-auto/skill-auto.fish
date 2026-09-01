# Fish completions for skill-auto

complete -c skill-auto -f
complete -c skill-auto -n 'not __fish_seen_subcommand_from on off' -a on -d '开启 Skill 自动调用与上下文注入'
complete -c skill-auto -n 'not __fish_seen_subcommand_from on off' -a off -d '关闭 Skill 自动调用与上下文注入'
complete -c skill-auto -n '__fish_seen_subcommand_from on off' -a '(__fish_complete_directories (commandline -ct))' -d 'skill 目录'
complete -c skill-auto -s h -l help -d '显示帮助'

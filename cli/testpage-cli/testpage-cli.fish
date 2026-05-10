# Fish completions for testpage-cli

complete -c testpage-cli -f

complete -c testpage-cli -n "not __fish_seen_subcommand_from init config push" -a init -d '初始化测试项目目录配置'
complete -c testpage-cli -n "not __fish_seen_subcommand_from init config push" -a config -d '查看配置或配置文件路径'
complete -c testpage-cli -n "not __fish_seen_subcommand_from init config push" -a push -d '发布 HTML 目录到测试服务器项目'

complete -c testpage-cli -n "__fish_seen_subcommand_from init" -l project-root -r -d '本地 html_test Git 项目目录'
complete -c testpage-cli -n "__fish_seen_subcommand_from init" -l base-url -r -d '访问前缀 URL'
complete -c testpage-cli -n "__fish_seen_subcommand_from init" -l default-subdir -r -d '默认发布子目录'

complete -c testpage-cli -n "__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from show path" -a show -d '显示当前配置'
complete -c testpage-cli -n "__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from show path" -a path -d '输出配置文件路径'
complete -c testpage-cli -n "__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from show path check" -a check -d '检查配置和仓库状态'

complete -c testpage-cli -n "__fish_seen_subcommand_from push" -l subdir -r -d '发布到指定子目录'
complete -c testpage-cli -n "__fish_seen_subcommand_from push" -l root -d '忽略默认子目录，直接发布到根目录'
complete -c testpage-cli -n "__fish_seen_subcommand_from push" -l name -r -d '发布时使用的目标目录名'

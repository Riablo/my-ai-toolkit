# Fish completions for cloudsaver-cli

complete -c cloudsaver-cli -f

complete -c cloudsaver-cli -n "not __fish_seen_subcommand_from search s save sv config" -a search -d '搜索网盘资源'
complete -c cloudsaver-cli -n "not __fish_seen_subcommand_from search s save sv config" -a save -d '转存 115 网盘资源'
complete -c cloudsaver-cli -n "not __fish_seen_subcommand_from search s save sv config" -a config -d '管理配置'

complete -c cloudsaver-cli -n "__fish_seen_subcommand_from search s" -l limit -r -d '限制结果数量'
complete -c cloudsaver-cli -n "__fish_seen_subcommand_from search s" -l no-table -d '不使用表格格式输出'

complete -c cloudsaver-cli -n "__fish_seen_subcommand_from save sv" -l folder -r -d '指定目标文件夹 ID'

complete -c cloudsaver-cli -n "__fish_seen_subcommand_from config" -l set-cookie -d '设置 115 网盘 Cookie'
complete -c cloudsaver-cli -n "__fish_seen_subcommand_from config" -l add-channel -d '添加 Telegram 搜索频道'
complete -c cloudsaver-cli -n "__fish_seen_subcommand_from config" -l remove-channel -d '删除 Telegram 搜索频道'
complete -c cloudsaver-cli -n "__fish_seen_subcommand_from config" -l set-proxy -d '设置 HTTP 代理'
complete -c cloudsaver-cli -n "__fish_seen_subcommand_from config" -l show -d '显示当前配置'

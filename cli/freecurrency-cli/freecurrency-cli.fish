# Fish completions for freecurrency-cli

complete -c freecurrency-cli -f

complete -c freecurrency-cli -n "not __fish_seen_subcommand_from init config convert latest cache" -a init -d '初始化 API Key'
complete -c freecurrency-cli -n "not __fish_seen_subcommand_from init config convert latest cache" -a config -d '查看配置'
complete -c freecurrency-cli -n "not __fish_seen_subcommand_from init config convert latest cache" -a convert -d '按货币对换算金额'
complete -c freecurrency-cli -n "not __fish_seen_subcommand_from init config convert latest cache" -a latest -d '查询最新汇率'
complete -c freecurrency-cli -n "not __fish_seen_subcommand_from init config convert latest cache" -a cache -d '查看或清理缓存'

complete -c freecurrency-cli -n "__fish_seen_subcommand_from init" -l api-key -r -d 'freecurrencyapi API Key'

complete -c freecurrency-cli -n "__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from show path" -a show -d '显示当前配置'
complete -c freecurrency-cli -n "__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from show path" -a path -d '输出配置文件路径'

complete -c freecurrency-cli -n "__fish_seen_subcommand_from convert" -l json -d '输出详细 JSON'

complete -c freecurrency-cli -n "__fish_seen_subcommand_from latest" -l base -r -d '基准货币'
complete -c freecurrency-cli -n "__fish_seen_subcommand_from latest" -l currencies -r -d '目标货币列表'

complete -c freecurrency-cli -n "__fish_seen_subcommand_from cache; and not __fish_seen_subcommand_from info clear" -a info -d '显示缓存统计信息'
complete -c freecurrency-cli -n "__fish_seen_subcommand_from cache; and not __fish_seen_subcommand_from info clear" -a clear -d '删除所有缓存'

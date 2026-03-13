# Fish completions for qweather-cli

complete -c qweather-cli -f

complete -c qweather-cli -n "not __fish_seen_subcommand_from init config now daily hourly" -a init -d '初始化 API Host 和 API Key'
complete -c qweather-cli -n "not __fish_seen_subcommand_from init config now daily hourly" -a config -d '查看配置'
complete -c qweather-cli -n "not __fish_seen_subcommand_from init config now daily hourly" -a now -d '查询实时天气'
complete -c qweather-cli -n "not __fish_seen_subcommand_from init config now daily hourly" -a daily -d '查询每日天气预报'
complete -c qweather-cli -n "not __fish_seen_subcommand_from init config now daily hourly" -a hourly -d '查询逐小时天气预报'

complete -c qweather-cli -n "__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from show path" -a show -d '显示当前配置'
complete -c qweather-cli -n "__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from show path" -a path -d '输出配置文件路径'

complete -c qweather-cli -n "__fish_seen_subcommand_from init" -l api-host -r -d 'QWeather API Host'
complete -c qweather-cli -n "__fish_seen_subcommand_from init" -l api-key -r -d 'QWeather API Key'

complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l city -r -d '城市名'
complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l location-id -r -d 'QWeather LocationID'
complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l lon -r -d '经度'
complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l lat -r -d '纬度'
complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l adm -r -d 'GeoAPI 上级行政区过滤'
complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l range -r -d 'GeoAPI 国家/地区范围'
complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l number -r -d 'GeoAPI 候选数量'
complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l location-index -r -d '选择第几个 GeoAPI 结果'
complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l lang -r -d '语言'
complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l unit -a "m i" -d '单位系统'
complete -c qweather-cli -n "__fish_seen_subcommand_from now daily hourly" -l raw -d '输出原始 JSON'

complete -c qweather-cli -n "__fish_seen_subcommand_from daily" -l days -a "3 7 10 15 30" -d '预报天数'
complete -c qweather-cli -n "__fish_seen_subcommand_from hourly" -l hours -a "24 72 168" -d '预报小时数'

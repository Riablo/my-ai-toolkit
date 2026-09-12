# Fish completions for cos-cli

complete -c cos-cli -n 'not __fish_seen_subcommand_from config upload' -a upload -d '上传图片或文件夹'
complete -c cos-cli -n 'not __fish_seen_subcommand_from config upload' -a config -d '管理配置'
complete -c cos-cli -l config -r -F -d '配置文件路径'
complete -c cos-cli -s h -l help -d '显示帮助'

complete -c cos-cli -n '__fish_seen_subcommand_from config' -f
complete -c cos-cli -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from init check show path' -a init -d '创建配置模板'
complete -c cos-cli -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from init check show path' -a check -d '本地校验配置'
complete -c cos-cli -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from init check show path' -a show -d '脱敏查看配置'
complete -c cos-cli -n '__fish_seen_subcommand_from config; and not __fish_seen_subcommand_from init check show path' -a path -d '显示配置路径'

complete -c cos-cli -n 'not __fish_seen_subcommand_from config' -s p -l prefix -r -f -d '对象路径前缀'
complete -c cos-cli -n 'not __fish_seen_subcommand_from config' -l md5 -d '文件名加入内容 MD5'
complete -c cos-cli -n 'not __fish_seen_subcommand_from config' -l no-md5 -d '不使用 MD5 重命名'
complete -c cos-cli -n 'not __fish_seen_subcommand_from config' -l all-files -d '包含非图片文件'
complete -c cos-cli -n 'not __fish_seen_subcommand_from config' -l dry-run -d '预览 Key 和 URL，不上传'
complete -c cos-cli -n 'not __fish_seen_subcommand_from config' -l format -r -f -a 'url key markdown json' -d '输出格式'
complete -c cos-cli -n 'not __fish_seen_subcommand_from config' -l json -d '输出 JSON'

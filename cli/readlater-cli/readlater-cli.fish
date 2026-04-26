# Fish completions for readlater-cli

complete -c readlater-cli -f

complete -c readlater-cli -n "not __fish_seen_subcommand_from fetch" -a fetch -d '抓取一个链接摘要'
complete -c readlater-cli -s j -l json -d '输出 JSON'
complete -c readlater-cli -l timeout -r -d '请求超时时间（秒）'
complete -c readlater-cli -l summary-length -r -d '概要最大长度'

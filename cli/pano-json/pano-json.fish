# Fish completions for pano-json

complete -c pano-json -f

complete -c pano-json -s o -l output -r -d '输出文件路径；传 - 表示输出到 stdout'
complete -c pano-json -l base-url -r -d 'JSON 相对路径的域名前缀'
complete -c pano-json -l timeout -r -d '请求超时时间（秒）'
complete -c pano-json -l pretty -d '保存前格式化 JSON'
complete -c pano-json -l print-url -d '只输出解析后的 JSON 下载地址'
complete -c pano-json -s h -l help -d '显示帮助'
complete -c pano-json -l version -d '显示版本'

# Fish completions for myskills

# 动态获取 skill 列表
function __myskills_skills
    myskills list 2>/dev/null | string replace -ra '\e\[[0-9;]*m' '' | string match -r '^\s+\S+' | string trim
end

# 禁用文件补全
complete -c myskills -f

# 子命令补全（仅在没有子命令时）
complete -c myskills -n "not __fish_seen_subcommand_from list link unlink status" -a list -d '列出所有可用的 skills'
complete -c myskills -n "not __fish_seen_subcommand_from list link unlink status" -a link -d '将 skill 软链接到目标目录'
complete -c myskills -n "not __fish_seen_subcommand_from list link unlink status" -a unlink -d '移除 skill 的所有软链接'
complete -c myskills -n "not __fish_seen_subcommand_from list link unlink status" -a status -d '查看所有 skills 的链接状态'

# link / unlink 的 skill 名称补全
complete -c myskills -n "__fish_seen_subcommand_from link unlink" -a "(__myskills_skills)"

# link / unlink 的目标参数补全
complete -c myskills -n "__fish_seen_subcommand_from link unlink" -l agents -d '~/.agents/skills/'
complete -c myskills -n "__fish_seen_subcommand_from link unlink" -l claude -d '~/.claude/skills/'
complete -c myskills -n "__fish_seen_subcommand_from link unlink" -l local-agents -d './.agents/skills/'
complete -c myskills -n "__fish_seen_subcommand_from link unlink" -l local-claude -d './.claude/skills/'

# 全局 -h/--help
complete -c myskills -s h -l help -d '显示帮助信息'

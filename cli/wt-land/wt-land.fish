# Fish completions for wt-land

function __wt_land_targets
    set -l current_ref (git symbolic-ref --quiet HEAD 2>/dev/null); or return

    git for-each-ref --format='%(refname)%09%(worktreepath)' refs/heads/ 2>/dev/null | awk -F '\t' -v current="$current_ref" '
        $1 != current {
            branch = substr($1, 12)
            print branch "\t" ($2 == "" ? "本地分支" : $2)
        }
    '
end

complete -c wt-land -f
complete -c wt-land -s h -l help -d '显示帮助'
complete -c wt-land -n '__fish_is_first_arg' -a '(__wt_land_targets)' -d '本地目标分支'

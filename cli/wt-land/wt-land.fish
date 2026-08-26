# Fish completions for wt-land

function __wt_land_targets
    set -l current_ref (git symbolic-ref --quiet HEAD 2>/dev/null); or return

    git worktree list --porcelain 2>/dev/null | awk -v current="$current_ref" '
        /^worktree / {
            path = substr($0, 10)
        }
        /^branch refs\/heads\// && $0 != "branch " current {
            branch = substr($0, 19)
            print branch "\t" path
        }
    '
end

complete -c wt-land -f
complete -c wt-land -s h -l help -d '显示帮助'
complete -c wt-land -n '__fish_is_first_arg' -a '(__wt_land_targets)' -d '目标 worktree 分支'

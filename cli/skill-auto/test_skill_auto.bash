#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

skill="$tmp_dir/example skill"
mkdir -p "$skill/agents"

cat > "$skill/SKILL.md" <<'EOF'
---
name: example
description: example skill
disable-model-invocation: true # keep this comment
---

# Example
EOF

cat > "$skill/agents/openai.yaml" <<'EOF'
interface:
  display_name: Example
policy:
  allow_implicit_invocation: false # keep this comment
dependencies:
  tools:
    - git
EOF

"$script_dir/skill-auto" on "$skill" >/dev/null
grep -q '^disable-model-invocation: false # keep this comment$' "$skill/SKILL.md"
grep -q '^  allow_implicit_invocation: true # keep this comment$' "$skill/agents/openai.yaml"
grep -q '^dependencies:$' "$skill/agents/openai.yaml"

"$script_dir/skill-auto" off "$skill" >/dev/null
grep -q '^disable-model-invocation: true # keep this comment$' "$skill/SKILL.md"
grep -q '^  allow_implicit_invocation: false # keep this comment$' "$skill/agents/openai.yaml"

minimal="$tmp_dir/minimal"
mkdir -p "$minimal"
cat > "$minimal/SKILL.md" <<'EOF'
---
name: minimal
description: minimal skill
---

# Minimal
EOF

"$script_dir/skill-auto" on "$minimal" >/dev/null
grep -q '^disable-model-invocation: false$' "$minimal/SKILL.md"
grep -q '^policy:$' "$minimal/agents/openai.yaml"
grep -q '^  allow_implicit_invocation: true$' "$minimal/agents/openai.yaml"

invalid="$tmp_dir/invalid"
mkdir -p "$invalid/agents"
printf '# no frontmatter\n' > "$invalid/SKILL.md"
printf 'policy:\n  allow_implicit_invocation: false\n' > "$invalid/agents/openai.yaml"
if "$script_dir/skill-auto" on "$invalid" >"$tmp_dir/out" 2>"$tmp_dir/err"; then
  echo 'expected invalid SKILL.md to fail' >&2
  exit 1
fi
grep -q '缺少有效的 YAML frontmatter' "$tmp_dir/err"
grep -q '^  allow_implicit_invocation: false$' "$invalid/agents/openai.yaml"

misplaced="$tmp_dir/misplaced"
mkdir -p "$misplaced/agents"
printf '%s\n' '---' 'name: misplaced' 'description: misplaced' '---' > "$misplaced/SKILL.md"
printf '%s\n' 'interface:' '  allow_implicit_invocation: false' 'policy:' > "$misplaced/agents/openai.yaml"
if "$script_dir/skill-auto" on "$misplaced" >"$tmp_dir/out" 2>"$tmp_dir/err"; then
  echo 'expected misplaced allow_implicit_invocation to fail' >&2
  exit 1
fi
grep -q '不在 policy 下' "$tmp_dir/err"

"$script_dir/skill-auto" --help | grep -q 'skill-auto on <skill 目录>'
grep -q "_directories 'skill 目录'" "$script_dir/_skill-auto"

echo 'ok: skill-auto 同步修改两种自动调用配置并提供目录补全'

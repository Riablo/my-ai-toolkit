#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
img="$script_dir/img"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cd "$tmp_dir"

expect_fail() {
  local code="$1"
  shift
  local status=0
  "$@" >out 2>err || status=$?
  if [ "$status" != "$code" ]; then
    echo "expected exit $code, got $status: $*" >&2
    cat err >&2
    exit 1
  fi
}

# 用假的 trash 代替系统命令，避免测试文件进入真实废纸篓。
mkdir fakebin trash-can
cat >fakebin/trash <<'EOF'
#!/usr/bin/env bash
[ -z "${FAKE_TRASH_FAIL:-}" ] || { echo 'trash failed' >&2; exit 1; }
mv -- "$@" "$TRASH_DIR/"
EOF
chmod +x fakebin/trash
export PATH="$tmp_dir/fakebin:$PATH" TRASH_DIR="$tmp_dir/trash-can"

loader() {
  vipsheader -f vips-loader "$1"
}

# 生成带纹理的照片样图、未压缩 PNG、透明 PNG 和非四种格式的 TIFF。
for band in r g b; do
  vips gaussnoise "$band.v" 320 240 --sigma 40 --mean 128
done
vips bandjoin "r.v g.v b.v" noise.v
vips gaussblur noise.v blur.v 3
vips cast blur.v rgb.v uchar
vips copy rgb.v photo.v --interpretation srgb
vips copy photo.v photo.tif
vips copy photo.v 'raw.png[compression=0]'
vips black clear.v 64 64 --bands 4
vips copy clear.v clear.png

# 分级帮助
"$img" --help | grep -q 'img <命令> --help'
"$img" -h | grep -q 'compress'
for cmd in compress convert resize; do
  "$img" "$cmd" --help | grep -q "^img $cmd - "
  "$img" "$cmd" -h photo.tif | grep -q "用法:"
done
"$img" convert -h | grep -q -- '-t, --to'
"$img" resize -h | grep -q -- '-w, --width'
if "$img" compress -h | grep -q -- '--to'; then
  echo 'compress help should not list --to' >&2
  exit 1
fi

# 参数校验
expect_fail 2 "$img"
expect_fail 2 "$img" unknown photo.tif
expect_fail 2 "$img" convert photo.tif
grep -q -- '-t 指定目标格式' err
expect_fail 2 "$img" convert -t gif photo.tif
expect_fail 2 "$img" resize photo.tif
expect_fail 2 "$img" resize -w 0 raw.png
expect_fail 2 "$img" compress -t png raw.png
grep -q '使用 img compress --help 查看帮助' err
expect_fail 2 "$img" convert -w 10 -t png raw.png
expect_fail 2 "$img" convert -t png
test -z "$(ls trash-can)"

# convert：任意可读格式转四种格式，尺寸不变
"$img" convert -t png photo.tif >out
grep -q 'photo.tif → photo.png' out
"$img" convert -t jpeg photo.tif >/dev/null
"$img" convert -t webp photo.tif >/dev/null
"$img" convert -t avif photo.tif >/dev/null
test "$(loader photo.png)" = pngload
test "$(loader photo.jpg)" = jpegload
test "$(loader photo.webp)" = webpload
test "$(vipsheader -f heif-compression photo.avif)" = av1
for f in photo.png photo.jpg photo.webp photo.avif; do
  test "$(vipsheader -f width "$f")" = 320
  test "$(vipsheader -f height "$f")" = 240
done
expect_fail 1 "$img" convert -t png raw.png
grep -q '压缩请用 img compress' err

# 透明区域转 JPEG 填白
"$img" convert -t jpg clear.png >/dev/null
test "$(vips getpoint clear.jpg 3 3)" = '255 255 255 '

# compress：原地替换，原图移入废纸篓，文件名和权限不变
cp raw.png keep.png
chmod 640 raw.png
before="$(stat -f %z raw.png)"
"$img" compress raw.png >out
grep -q '原图已移到废纸篓' out
cmp -s trash-can/raw.png keep.png
test "$(stat -f %z raw.png)" -lt "$before"
test "$(stat -f %Lp raw.png)" = 640
test "$(loader raw.png)" = pngload
test "$(vipsheader -f width raw.png)" = 320
test -z "$(ls -A | grep '^\.img\.' || true)"
expect_fail 1 "$img" compress photo.tif
grep -q '请先用 img convert 转换' err

# 已是最优时不改动，也不进废纸篓
rm trash-can/raw.png
compressed="$(shasum raw.png)"
"$img" compress raw.png >out
grep -q '已是最优，未改动' out
test "$(shasum raw.png)" = "$compressed"
test -z "$(ls trash-can)"

# 废纸篓失败时原图保持不变，不留临时文件
cp keep.png big.png
before="$(shasum big.png)"
FAKE_TRASH_FAIL=1 expect_fail 1 "$img" compress big.png
grep -q 'trash 失败' err
test "$(shasum big.png)" = "$before"
test -z "$(ls -A | grep '^\.img\.' || true)"

# -o：以原文件名输出到目录，原图不动；已存在时需 -f
"$img" compress -o compressed big.png >out
grep -q 'big.png → compressed/big.png' out
test "$(shasum big.png)" = "$before"
test -z "$(ls trash-can)"
printf 'keep' >compressed/big.png
expect_fail 1 "$img" compress -o compressed big.png
grep -q '已存在，用 -f 覆盖' err
test "$(cat compressed/big.png)" = keep
"$img" compress -f -o compressed big.png >/dev/null
test "$(loader compressed/big.png)" = pngload
# -o 指向原图所在目录时等同原地替换
"$img" compress -o . big.png >out
grep -q '原图已移到废纸篓' out
cmp -s trash-can/big.png keep.png

# 扩展名与内容不符时，即使 -f 也不覆盖原图
cp photo.jpg fake.png
before="$(shasum fake.png)"
expect_fail 1 "$img" convert -f -t png fake.png
grep -q '输出会覆盖原图' err
test "$(shasum fake.png)" = "$before"

# 指定输出目录，不存在时自动创建
"$img" convert -t webp -o 'out dir/nested' raw.png >/dev/null
test "$(loader 'out dir/nested/raw.webp')" = webpload

# resize：单边等比，双边强制
"$img" resize -w 160 photo.jpg >out
grep -q 'photo.160x120.jpg' out
test "$(vipsheader -f width photo.160x120.jpg)" = 160
"$img" resize -H 60 photo.webp >/dev/null
test "$(vipsheader -f height photo.80x60.webp)" = 60
"$img" resize --width 50 --height 50 photo.avif >/dev/null
test "$(vipsheader -f width photo.50x50.avif)" = 50
test "$(vipsheader -f height photo.50x50.avif)" = 50
expect_fail 1 "$img" resize -w 100 photo.tif

# 批量处理时单个失败不影响其他文件
expect_fail 1 "$img" convert -t avif missing.png raw.png
grep -q 'missing.png：文件不存在' err
test -e raw.avif

# 缺少依赖时提示 brew 安装
mkdir bin
ln -s "$(command -v bash)" bin/bash
ln -s "$(command -v vips)" bin/vips
PATH="$tmp_dir/bin:/usr/bin:/bin" expect_fail 1 "$img" compress raw.png
grep -q 'brew install' err
grep -q 'oxipng' err

# zsh 补全列出子命令
if command -v zsh >/dev/null 2>&1; then
  completion="$(zsh -fc '
    _describe() { print -rl -- "${commands[@]}"; }
    CURRENT=2
    source "$1"
  ' -- "$script_dir/_img")"
  grep -q '^compress:' <<<"$completion"
  grep -q '^convert:' <<<"$completion"
  grep -q '^resize:' <<<"$completion"
else
  echo '跳过 zsh 补全验证：未安装 zsh'
fi

echo 'img tests passed'

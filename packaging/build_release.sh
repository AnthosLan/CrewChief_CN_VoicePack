#!/usr/bin/env bash
# 从 output/ 打出可挂 GitHub Releases 的 zip。
#
# 拆成两个包是有意的：数字包覆盖了 numbers/0..99、point、hour 这些英文包里已有的
# 文件夹，却没有英文特有的 599 个合成件（45point6 之类）。混装会导致圈速中英混播，
# 所以数字包必须与 NumberReaderZh 配套发布，不能和 spotter 包合并。
#
# 压缩包内的路径全部保持 ASCII —— 上游 Release check list.txt 提过，Windows 内置
# 解压对非 UTF-8 标记的中文文件名会出乱码。说明文档正文是中文，但文件名叫
# INSTALL.txt，并写成 UTF-8 BOM + CRLF，老版本记事本也能正确显示。
#
# 用法：packaging/build_release.sh [版本号]
set -euo pipefail

VERSION="${1:-v0.1.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"

# 包名 -> output 下的源目录
declare -a PACKS=(
  "spotter:Spotter_final:INSTALL_spotter.txt"
  "numbers:Numbers:INSTALL_numbers.txt"
)

rm -rf "$DIST"
mkdir -p "$DIST"

for spec in "${PACKS[@]}"; do
  IFS=: read -r name srcdir install <<<"$spec"
  src="$ROOT/output/$srcdir/voice"
  [[ -d "$src" ]] || { echo "缺少 $src —— 先跑生成脚本" >&2; exit 1; }

  stage="$DIST/.stage_$name"
  mkdir -p "$stage"
  cp -R "$src" "$stage/voice"

  python3 -c "
import pathlib, sys
t = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
pathlib.Path(sys.argv[2]).write_bytes(b'\xef\xbb\xbf' + t.replace('\n', '\r\n').encode('utf-8'))
" "$ROOT/packaging/$install" "$stage/INSTALL.txt"

  find "$stage" -name '.DS_Store' -delete
  ( cd "$stage" && zip -r -X -q "$DIST/crewchief-zh-$name-$VERSION.zip" voice INSTALL.txt )
  rm -rf "$stage"

  wavs=$(unzip -l "$DIST/crewchief-zh-$name-$VERSION.zip" | grep -c '\.wav$' || true)
  printf '  %-42s %6s  %s 个 wav\n' \
    "crewchief-zh-$name-$VERSION.zip" \
    "$(du -h "$DIST/crewchief-zh-$name-$VERSION.zip" | cut -f1)" "$wavs"
done

echo
echo "产物在 $DIST —— 挂到 GitHub Releases，不要提交进仓库"

#!/usr/bin/env bash
# 把 output/ 下所有生成的语音打成一个 zip，挂 GitHub Releases。
#
# 合并成单包是使用者的选择。要注意 numbers 与 spotter 的适用条件并不相同：
# numbers 覆盖了 numbers/0..99、point、hour 这些英文包已有的文件夹，却没有
# 英文特有的 599 个合成件（45point6 之类），装在未打补丁的 CrewChief 上会让
# 圈速变成中英混播。所以 INSTALL.txt 把「原版程序要删掉 voice/numbers/」
# 写成了明确的一步，改这个脚本时别把那段说明弄丢。
#
# 压缩包内的路径全部保持 ASCII —— 上游 Release check list.txt 提过，Windows
# 内置解压对非 UTF-8 标记的中文文件名会出乱码。说明文档正文是中文，但文件名
# 叫 INSTALL.txt，并写成 UTF-8 BOM + CRLF，老版本记事本也能正确显示。
#
# 用法：packaging/build_release.sh [版本号]
set -euo pipefail

VERSION="${1:-v0.1.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
ZIP="$DIST/crewchief-zh-voicepack-$VERSION.zip"

# CPML 的 Notices 条款要求：拿到音频的人必须一并拿到条款全文或其 URL。
# 那个 URL（coqui.ai/cpml.txt）随 Coqui 2024 年关停已经 404，所以只能附全文。
# 缺文件就停下，不能发一个不带许可的包出去。见方案文档 §13.1。
[[ -f "$ROOT/packaging/CPML.txt" ]] || {
  echo "缺 packaging/CPML.txt —— CPML 要求随包传递条款全文，不能不带" >&2; exit 1; }

rm -rf "$DIST"
stage="$DIST/.stage"
mkdir -p "$stage/voice"

# output/<任意生成批次>/voice/<分类>/ 全部并到一棵 voice/ 树下。
# 各批次的分类互不重叠（spotter+radio_check / numbers），合并不会互相覆盖。
found=0
for src in "$ROOT"/output/*/voice; do
  [[ -d "$src" ]] || continue
  for category in "$src"/*/; do
    name=$(basename "$category")
    if [[ -e "$stage/voice/$name" ]]; then
      echo "冲突：voice/$name 在多个批次里都存在，先确认哪个是要发的" >&2
      exit 1
    fi
    cp -R "$category" "$stage/voice/$name"
    found=$((found + 1))
  done
done
[[ $found -gt 0 ]] || { echo "output/ 下没有可打包的 voice —— 先跑生成脚本" >&2; exit 1; }

# 转成 CRLF 再进包：老版本记事本遇到纯 LF 会把全文连成一行。
# 第三个参数 bom 时加 UTF-8 BOM —— INSTALL.txt 是中文需要；CPML.txt 是纯 ASCII 不加，
# 除换行符外与上游逐字一致（换行转换不改变正文）。
to_crlf() {
  python3 -c "
import pathlib, sys
t = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
data = t.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8')
pathlib.Path(sys.argv[2]).write_bytes((b'\xef\xbb\xbf' if sys.argv[3] == 'bom' else b'') + data)
" "$1" "$2" "$3"
}
to_crlf "$ROOT/packaging/INSTALL.txt" "$stage/INSTALL.txt" bom
to_crlf "$ROOT/packaging/CPML.txt"    "$stage/CPML.txt"    nobom

find "$stage" -name '.DS_Store' -delete
( cd "$stage" && zip -r -X -q "$ZIP" voice INSTALL.txt CPML.txt )
rm -rf "$stage"

echo "  $(basename "$ZIP")  $(du -h "$ZIP" | cut -f1)"
for category in $(unzip -l "$ZIP" | awk '/voice\//{split($4,a,"/"); print a[2]}' | sort -u); do
  n=$(unzip -l "$ZIP" | grep -c "voice/$category/.*\.wav$" || true)
  printf '    voice/%-14s %3s 个 wav\n' "$category" "$n"
done

echo
echo "产物在 $DIST —— 挂到 GitHub Releases，不要提交进仓库"

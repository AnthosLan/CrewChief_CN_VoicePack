# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这是什么

给 CrewChief（赛车模拟的 AI 车队工程师）做中文语音包的**制作工程**——语料 CSV、生成脚本、对上游的补丁。
不是一个应用：没有构建系统、没有测试框架、没有 requirements.txt。产物是音频文件，打成 zip 挂 Releases。

权威文档两份，改了行为必须同步更新：

- [docs/中文语音包制作方案.md](docs/中文语音包制作方案.md) —— 总方案、工作量分解、定稿参数、装包陷阱、命令速查（§12）
- [docs/数字与时间朗读设计.md](docs/数字与时间朗读设计.md) —— `NumberReaderZh` 的拆分规则与取舍

## 三仓库布局

本库不自包含。跑任何生成脚本前需要平级放在 `~/Projects/` 下的另外两个仓库：

| 路径 | 角色 |
|---|---|
| `CrewChief_CN_VoicePack` | 本库。语料、脚本、补丁的**唯一权威来源** |
| `crew-chief-autovoicepack` | 只提供 `.venv`（XTTS 运行环境）。生成脚本本身在本库 |
| `CrewChiefV4-main` | C# 目标程序，只读参考。`NumberReaderZh.cs` 最终拷进去 |

**同步是单向的：本库 → 另外两个。** 在 autovoicepack 或 CrewChiefV4-main 里临时改了东西，必须
`git diff > $PACK/patches/<对应>.diff` 回写本库，否则两边各自演化。`patches/` 里的 diff 是那些改动的
唯一留档。

Python 依赖装在 autovoicepack 的 venv 里（本库不放二进制依赖）。四个版本约束都是踩坑钉死的，
别放宽——`transformers>=4.57,<5`、`torch<2.9`、`torchaudio<2.9`、外加 `jieba`/`pypinyin`。原因见方案文档 §10。

## 常用命令

```bash
export PACK=~/Projects/CrewChief_CN_VoicePack
export AVP=~/Projects/crew-chief-autovoicepack
```

生成音频（脚本全部路径走参数，所以脚本在本库、venv 在 autovoicepack 不冲突）：

```bash
COQUI_TOS_AGREED=1 $AVP/.venv/bin/python $PACK/scripts/pilot_mac.py \
  --phrase_inventory $PACK/translations/spotter_zh.csv \
  --language zh-cn --baseline_audio_dir $PACK/baseline/Bart \
  --output_audio_dir $PACK/output \
  --xtts_speed 1.45 --eq_preset radio --voice_name ChiefZH
```

体检（最接近测试套件的东西，有问题 exit 1）：

```bash
python3 scripts/qa_pack.py --phrase_inventory translations/numbers_zh.csv --pack output/Numbers
```

数字朗读规则验证（44 个用例，无法过滤单条；有失败 exit 1）：

```bash
python3 scripts/make_numbers_inventory.py --verify
```

重生成数字语料 CSV：

```bash
python3 scripts/make_numbers_inventory.py --out translations/numbers_zh.csv
```

打包：

```bash
packaging/build_release.sh v0.1.0
```

Windows 上跑真正的 C# 单元测试（必须 Debug 构建）：

```bash
vstest.console.exe UnitTest\bin\Debug\UnitTest.dll /TestCaseFilter:"FullyQualifiedName~TestChinese"
```

## 关键约束

**文件夹名不能翻译。** CSV 里 `audio_path` 的每一段（`spotter/car_left`、`numbers/ten_thousand`）都是
CrewChief 播报逻辑里的标识符，写错这条消息永远不会播。只有音频内容和 `subtitle` 是中文。

**`make_numbers_inventory.py` 里有一份 `NumberReaderZh.cs` 的 Python 镜像。** 改了 C# 就得改 Python，
反之亦然——Mac 上编译不了 C#，`--verify` 是唯一能发现两边跑偏的手段。

**定稿参数不要随手改：** Bart 音色 / `zh-cn` / `--xtts_speed 1.45` / `--eq_preset radio` /
单声道 22050Hz 16-bit PCM 峰值 −1 dBFS。每一项的依据在方案文档 §2.1，改之前先读。

**音频链里重采样必须在归一化之前**（`pilot_mac.py:302`）。带限插值会在瞬态上过冲，反过来会让
16-bit 写入削波。这是修过的 bug，`qa_pack.py` 的削波检查就是它的回归防线。

**短句要多候选。** 一两个汉字是 XTTS 最不稳的地方（补幻觉音、音节念两遍）。两道防线只对短句生效：
`--artifact_trim_max_syllables`（默认 4）裁掉长间隙后的尾巴，`--attempts` 取最短的合格候选。
数字包用 `--attempts 5`，整句语料默认 1 次即可。

**`numbers/` 音频和 CrewChief 补丁必须一起上。** `sound_pack_language.txt` 还是 `en` 时用的是
`NumberReaderEn`，它会要 `numbers/1point3` 这类英文特有的合成件——中文包没有，结果是
「四十五 point three」的中英混播。spotter 和 radio_check 不经过 `NumberReader`，可以单独装。

**装包不要放 `alt/`。** 用非默认工程师语音包时，CrewChief 强制从基础包读 `spotter*` 和 `radio_check*`
（`Audio/Sounds.cs:1147`），照 autovoicepack README 的装法会得到「工程师中文、spotter 永远英文」。
正确装法是整包替换 + `override_default_sound_pack_location`，见方案文档 §7 和 packaging/INSTALL.txt。

## 版本控制约定

`output/` 和 `dist/` 不入库——有 `translations/` + `baseline/` + `scripts/` 就能完整复现。

`baseline/Bart/` 的 12 个 wav **必须入库**，它们是生成结果的必要输入。别往 .gitignore 加通配的
`*.wav` 规则（.gitignore 里有这条注释，保留它）。

`build_release.sh` 把 `output/<批次>/voice/<分类>/` 全部并到一棵 voice 树下，分类重名会直接报错退出。
新增生成批次时保证分类不重叠。

## 语言约定

文档、README、INSTALL.txt、脚本的用户可见输出、git commit message 都用中文。
Python 和 C# 的代码注释以英文为主（`NumberReaderZh.cs` 的类级说明英文、逐方法注释中文）。
沿用所在文件的既有风格。

CSV 格式（沿用 autovoicepack 的 inventory 格式，5 列）：

```csv
audio_path,audio_filename,subtitle,text_for_tts,original_english
\voice\spotter\car_left,1.wav,左边有车,左边有车,car left
```

`YOUR_NAME` 是占位符，生成时被 `--your_name` 替换；翻译时不能连它一起译掉。

## 术语表（已定稿）

`3 wide → 三辆并排`（不用「三宽」）、`clear → 安全`（不用「空了」）、`inside/outside → 内线/外线`、
`low/high → 内侧/外侧`、`box now → 进站`、`hold your line → 保持走线`。完整表见方案文档 §6.3。
机器翻译在赛车术语上不可靠，译完必须人工过一遍。

## 许可

XTTS v2 是 **Coqui CPML，非商用**。个人使用没问题，公开分发前需确认。若要商用，本方案的语料、
目录结构、后处理链都可复用，只需替换 TTS 引擎。

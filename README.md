# CrewChief 中文语音包

给 [CrewChief](https://gitlab.com/mr_belowski/CrewChiefV4)（赛车模拟游戏的 AI 车队工程师）制作中文语音包。目标游戏 **Assetto Corsa**。

本库是**制作工程**：存放翻译语料、音色参考、生成脚本和方案文档。生成出来的音频不入库——有这些输入就能完整复现。

📄 **完整方案见 [`docs/中文语音包制作方案.md`](docs/中文语音包制作方案.md)**

---

## 当前状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| 技术验证 | XTTS v2 中文生成链路跑通，参数定稿 | ✅ 完成 |
| Spotter | 58 条文案翻译、术语定稿 | ✅ 翻译完成，待生成 |
| radio_check | 52 条 | ⬜ 未开始 |
| 数字与时间 | `NumberReaderZh` + 数字音频 | ⬜ 未开始 |
| 工程师播报 | 3772 条文案 | ⬜ 未开始（主要工作量） |
| UI 中文化 | 2222 条 | ⬜ 未开始 |
| 语音指令 | 30–50 个高频指令 | ⬜ 未开始 |

**必做音频总量：3882 条去重文案 / 5819 个文件 / 约 143 分钟**，机器生成约 3 小时。主要瓶颈是翻译而非生成。

---

## 依赖的两个外部仓库

本库不自包含，需要配合：

| 仓库 | 用途 | 获取 |
|---|---|---|
| [crew-chief-autovoicepack](https://github.com/cktlco/crew-chief-autovoicepack) | 提供 XTTS 运行环境与 Python venv | `git clone` 到 `~/Projects/crew-chief-autovoicepack`，再打上 `patches/` 里的 diff |
| [CrewChiefV4](https://gitlab.com/mr_belowski/CrewChiefV4) | 目标程序源码，只读参考 | 需要改 `NumberReaderZh` / `ColloquialTime` 时才用 |

三者**平级放在 `~/Projects/` 下**，互不嵌套。本库是语料与脚本的唯一权威来源，另外两个只在需要时改动。

---

## 快速开始

### 1. 准备环境

```bash
git clone https://github.com/cktlco/crew-chief-autovoicepack ~/Projects/crew-chief-autovoicepack
cd ~/Projects/crew-chief-autovoicepack
git apply ~/Projects/CrewChief_CN_VoicePack/patches/autovoicepack-zh-cn-support.diff

python3 -m venv .venv
.venv/bin/pip install coqui-tts
.venv/bin/pip install "transformers>=4.57,<5"
.venv/bin/pip install "torch<2.9" "torchaudio<2.9"
.venv/bin/pip install jieba pypinyin
```

版本必须这么钉，四个依赖坑见方案文档 §10。

### 2. 生成 17 条样本试听（约 40 秒）

```bash
export PACK=~/Projects/CrewChief_CN_VoicePack
export AVP=~/Projects/crew-chief-autovoicepack

COQUI_TOS_AGREED=1 $AVP/.venv/bin/python $PACK/scripts/pilot_mac.py \
  --phrase_inventory $PACK/translations/spotter_sample_zh.csv \
  --language zh-cn \
  --baseline_audio_dir $PACK/baseline/Bart \
  --output_audio_dir $PACK/output \
  --xtts_speed 1.45 --eq_preset radio \
  --voice_name Test
```

首次运行会下载约 1.9 GB 的 XTTS v2 模型。

---

## 定稿参数

| 参数 | 值 | 依据 |
|---|---|---|
| 音色 | **Bart**（ElevenLabs 合成，无真人声纹问题） | 从官方完整包 30714 个文件里筛出 12 条干净片段，共 38.9 秒 |
| 语言码 | `zh-cn` | XTTS v2 支持的 17 语言之一 |
| 语速 | **1.45x** | 实测 188ms/音节，落在普通话正常语速区间（170–200ms） |
| EQ | **radio** | 原项目无线电曲线 |
| 音频格式 | 单声道 / 22050 Hz / 16-bit PCM，峰值 −1 dBFS | 与 CrewChief 语音包一致 |

术语表见方案文档 §6.3。已定：`3 wide → 三辆并排`、`clear → 安全`、`inside/outside → 内线/外线`。

---

## 目录说明

```
docs/            方案与设计文档
translations/    翻译语料 CSV  ← 核心资产
baseline/Bart/   音色参考音频（12 条 / 38.9s，必须入库才能复现）
scripts/         生成脚本，路径全部走参数
patches/         对 autovoicepack 的改动留档
output/          生成产物（.gitignore 排除）
```

`translations/` 的 CSV 沿用 autovoicepack 的 inventory 格式：

```csv
audio_path,audio_filename,subtitle,text_for_tts,original_english
\voice\spotter\car_left,1.wav,左边有车,左边有车,car left
```

`audio_path` 必须与 CrewChief 语音包的文件夹结构**逐字对应**——那些文件夹名是播报逻辑里的标识符，写错了这条消息就永远不会播。

---

## ⚠️ 两个必读的坑

**1. 装包不要放 `alt/` 目录。** CrewChief 在使用非默认工程师语音包时，会强制从基础包读取 `spotter*` 和 `radio_check*`（`Audio/Sounds.cs:1147`）。按 autovoicepack README 的装法，结果是工程师说中文、**spotter 永远说英文**——而 spotter 是比赛中出现频率最高的播报。正确装法见方案文档 §7。

**2. XTTS v2 是非商用许可。** Coqui Public Model License (CPML)。个人使用没问题，公开分发前需要确认。若要商用，本方案的语料、目录结构、后处理链都可以复用，只需替换 TTS 引擎。

---

## 授权

本库的翻译语料与脚本采用 MIT。

生成的音频受上游许可约束：XTTS v2 为 CPML（非商用）；Bart 音色来自 crew-chief-autovoicepack（MIT）；CrewChief 本体为 MIT。

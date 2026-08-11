# CrewChief 中文语音包

给 [CrewChief](https://gitlab.com/mr_belowski/CrewChiefV4)（赛车模拟的 AI 车队工程师）做的中文语音包，目标游戏 **Assetto Corsa**。

本库是**制作工程**，不是应用：存放翻译语料、音色参考、生成脚本、对上游的补丁和方案文档。
生成出来的音频不入库——有这些输入就能完整复现；成品打成 zip 挂 [Releases](https://github.com/AnthosLan/CrewChief_CN_VoicePack/releases)。

---

## 当前状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| 技术验证 | XTTS v2 中文生成链路跑通，参数定稿 | ✅ 完成 |
| Spotter | 124 条翻译 + 生成 | ✅ 完成 |
| radio_check | 4 条 | ✅ 完成 |
| 装包实测 | AC 中验证无线电测试与盲区提醒 | ✅ 通过 |
| 数字与时间 | `NumberReaderZh` + 138 条数字音频 | ✅ 完成 |
| 打包分发 | zip 构建脚本 + Releases | ✅ 完成 |
| 字幕字体 | 覆盖层能否渲染中文 | ⏸ 待 Windows 环境验证（改法已定，改 json 不用编译） |
| 工程师播报 | 3772 条文案 | ⬜ 未开始（主要工作量） |
| UI 中文化 | 2222 条 | ⬜ 未开始 |
| 语音指令 | 30–50 个高频指令 | ⬜ 未开始 |

**必做音频总量：3882 条去重文案 / 5819 个文件 / 约 143 分钟**，机器生成约 3 小时。主要瓶颈是翻译而非生成。

---

## 使用方法

成品在 [Releases](https://github.com/AnthosLan/CrewChief_CN_VoicePack/releases)，单个压缩包 266 条：

| 目录 | 条数 | 适用 |
|---|---|---|
| `voice/spotter/` | 124 | 原版 CrewChief 即可 |
| `voice/radio_check/` | 4 | 原版 CrewChief 即可 |
| `voice/numbers/` | 138 | **需要带 `NumberReaderZh` 的自编译版本** |

装法概要（完整步骤见 [`packaging/INSTALL.txt`](packaging/INSTALL.txt)，它也随压缩包一起分发）：

1. 把 `%LOCALAPPDATA%\CrewChiefV4\Sounds` 整个复制一份，例如 `D:\CrewChief_zh\Sounds`；
2. 把压缩包里的 `voice/` 合并进去，覆盖同名文件；
3. 属性页里设 `Override default Sound Pack location` 指向第 1 步的路径，重启 CrewChief；
4. 用原版程序的话，把复制出来那份的 `sound_pack_version_info.txt` 版本号改成 `9999`，
   否则上游一发新版，主界面的语音包下载按钮就会变绿，点下去英文包会盖掉中文包。

### ⚠️ 两个必须知道的坑

**1. 原版程序装 `numbers/` 会中英混播。** `numbers` 包覆盖了 `numbers/0`–`99`、`point`、`hour` 这些
英文包已有的文件夹，却没有英文特有的 599 个合成件（`45point6` 这类），圈速会念成「四十五 point six」。
**用原版 CrewChief 的话，解压后先把 `voice/numbers/` 整个删掉再合并。** 想要中文圈速就得自编译，
见 [`patches/crewchief-zh-numberreader.diff`](patches/crewchief-zh-numberreader.diff) 与
[数字与时间朗读设计 §8](docs/数字与时间朗读设计.md)。

**2. 不要装到 `alt/` 目录。** CrewChief 用非默认工程师语音包时，会强制从基础包读 `spotter*` 和
`radio_check*`（`Audio/Sounds.cs:1147`）。按 autovoicepack README 的装法，结果是工程师说中文、
**spotter 永远说英文**——而 spotter 恰恰是比赛中出现频率最高的播报。正确装法是整包替换 +
`override_default_sound_pack_location`，见[制作方案 §7](docs/中文语音包制作方案.md)。

---

## 第三方依赖

### 上游项目

本库不自包含，三者**平级放在 `~/Projects/` 下**，互不嵌套。本库是语料与脚本的唯一权威来源。

| 仓库 | 用途 | 许可 |
|---|---|---|
| [crew-chief-autovoicepack](https://github.com/cktlco/crew-chief-autovoicepack) | 提供 XTTS 运行环境（venv）与 Bart 音色 | MIT |
| [CrewChiefV4](https://gitlab.com/mr_belowski/CrewChiefV4) | 目标程序源码，只读参考；`NumberReaderZh` 最终落在这里 | MIT |

对这两个仓库的改动以 diff 形式留档在 [`patches/`](patches/)，那是唯一留档。

### 模型与 Python 依赖

装在 autovoicepack 的 `.venv` 里（本库不放二进制依赖）：

| 依赖 | 版本约束 | 用途 |
|---|---|---|
| `coqui-tts` | — | XTTS v2 推理，音色克隆 |
| `transformers` | `>=4.57,<5` | 5.x 移除了 XTTS 依赖的 `isin_mps_friendly` |
| `torch` | `<2.9` | 2.9+ 强制要 torchcodec，而它又要系统装 ffmpeg |
| `torchaudio` | `<2.9` | 同上；重采样与 EQ 也用它 |
| `jieba`、`pypinyin` | — | XTTS `zh-cn` 分支的中文 g2p 依赖，缺了报错 |

**四个版本约束都是踩坑钉死的，别放宽**，原因见[制作方案 §10](docs/中文语音包制作方案.md)。
生成脚本本身只依赖 `torch` / `torchaudio` 加标准库；`qa_pack.py` 和 `make_numbers_inventory.py` 纯标准库。

| 其他 | 说明 |
|---|---|
| **XTTS v2** 模型 | 首次运行下载约 1.9 GB，`COQUI_TOS_AGREED=1` 可非交互接受许可 |
| **Bart** 音色 | 来自 autovoicepack 的 ElevenLabs 合成音色，不涉及真人声纹 |
| **Ollama + qwen2.5:14b** | 仅批量翻译阶段用，非必需 |

---

## 目录结构

```
docs/            方案与设计文档
translations/    翻译语料 CSV  ← 核心资产
baseline/Bart/   音色参考音频（12 条 / 38.9s，必须入库才能复现）
scripts/         生成、体检、语料构建脚本
src/             对 CrewChief 的 C# 新增（NumberReaderZh）
patches/         对 autovoicepack 和 CrewChief 的改动留档
packaging/       安装说明 + CPML 原文 + Releases 打包脚本
output/          生成产物（不入库）
dist/            打包产物（不入库）
```

## 文档

| 文档 | 内容 |
|---|---|
| [制作方案](docs/中文语音包制作方案.md) | 总方案、工作量分解、定稿参数与依据、语料 CSV 格式、术语表、环境搭建、装包陷阱、命令速查、许可与分发 |
| [数字与时间朗读设计](docs/数字与时间朗读设计.md) | `NumberReaderZh` 的拆分规则、为什么中文只要 138 个文件夹、接入 CrewChief 的方式 |
| [INSTALL.txt](packaging/INSTALL.txt) | 随 Release 分发的最终用户安装说明 |

**想自己生成音频或参与制作**：环境搭建见制作方案 §10，全套命令（试听、全量生成、数字语料重建、体检、打包）见 §12，
定稿参数与依据见 §2.1。定稿参数（Bart / `zh-cn` / 1.45x / radio EQ / 单声道 22050Hz 16-bit）不要随手改。

---

## 授权

**本库的翻译语料与脚本采用 MIT。生成的音频不是 MIT**——它受上游模型许可约束，两者不能合并理解。

音频由 XTTS v2 生成，该模型采用 [Coqui Public Model License 1.0.0](https://huggingface.co/coqui/XTTS-v2/raw/main/LICENSE.txt)（CPML，非商用）。
CPML 管的是模型**及其输出**，所以开源发布并不解除约束。免费开源分发本身没问题，但要满足三条：

1. **随包附上 CPML 全文**——任何拿到副本的人也必须拿到条款。Release 的 zip 根目录已放
   [`CPML.txt`](packaging/CPML.txt)，转发时请连它一起；
2. **不能把音频改成 MIT**——CPML 不允许 sublicense，本库的 MIT 只覆盖语料与脚本；
3. **下游同样不能商用**——不能塞进付费产品或付费整合包。

要商用就得替换 TTS 引擎，语料、目录结构、后处理链都可复用。另有一层容易漏掉的条款：Bart 音色来自
crew-chief-autovoicepack（MIT），但它本身是 ElevenLabs 合成音，受该服务条款约束。完整说明见
[制作方案 §13](docs/中文语音包制作方案.md)。

CrewChief 本体为 MIT。以上是对许可文本的阅读理解，不是法律意见。

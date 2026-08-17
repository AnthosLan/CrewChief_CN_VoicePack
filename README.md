# CrewChief 中文语音包

[![Release](https://img.shields.io/github/v/release/AnthosLan/CrewChief_CN_VoicePack?include_prereleases&label=release)](https://github.com/AnthosLan/CrewChief_CN_VoicePack/releases)
[![语音](https://img.shields.io/badge/语音-5308%20条-blue)](#包含内容)
[![界面](https://img.shields.io/badge/界面文案-1305%20条-blue)](#包含内容)
[![许可](https://img.shields.io/badge/音频许可-CPML%20非商用-orange)](#许可)

把 [CrewChief](https://gitlab.com/mr_belowski/CrewChiefV4)（赛车模拟的 AI 车队工程师）变成中文的。
工程师和 spotter 说中文，程序界面是中文，还能用中文向工程师提问。

目标游戏 **Assetto Corsa**，其他 CrewChief 支持的游戏也能用，只是术语按 AC 校过。

> **听起来是这样的**
>
> 「左边有车」·「黄旗，二号弯有事故」·「还剩三圈」·「油量够跑到最后」
> 「你的圈速是一分二十三秒四」·「前面那台车轮胎已经不行了，可以上」

---

## 包含内容

| 内容 | 量 | 需要自己编译程序吗 |
|---|---:|---|
| 工程师播报（29 个分类） | 5042 条音频 | 不需要 |
| 盲区提醒 spotter + 无线电测试 | 128 条音频 | 不需要 |
| 界面文案（主界面、菜单、设置项、帮助文本） | 1305 条 | 不需要 |
| 中文语音指令 | 45 条 | 不需要，但要装 zh-CN 识别引擎 |
| 数字与时间（圈速、差距念中文） | 138 条音频 | **需要** |

音频规格：单声道 / 22050 Hz / 16-bit PCM，峰值 −1 dBFS。总计 1264 个文件夹 / 323 MB。

**四部分互相独立**，可以只装其中一样。

### 有意保留英文的部分

不是漏做——这些内容整个文件夹不发布，装上后自动播原来的英文原音：

- **车手名、弯角名** —— 中文车手本来也说 Eau Rouge、Hamilton
- **车辆组别号** —— GT3、GT300、LMP2、DTM、Group C 这类专有编号
- **超车辅助** —— DRS、KERS、push-to-pass

除了「本来就说英文」，还有个实际原因：中文语音引擎念拉丁字母不可靠，实测 `GTC` 三个字母能念到
1.73 秒，`DRS` 在句子里只占 0.25 秒。与其念不清楚，不如用原音。

界面文案里另有 913 条也**故意保持英文**：它们的值是 `UI_STARTUP_AND_PATHS`、`RESTART_REQUIRED`
这类程序内部标识符，不是给人看的文字，译了会让设置项从分组里消失或让游戏过滤失效。

---

## 系统要求

| | |
|---|---|
| 操作系统 | Windows（CrewChief 本身只有 Windows 版） |
| CrewChief | V4，原版即可 |
| 磁盘空间 | 约 700 MB（语音包要复制一份原目录再合并） |
| 可选 | 中文语音识别引擎——只有想用中文语音指令才需要 |
| 可选 | Visual Studio / msbuild——只有想让圈速数字也念中文才需要 |

---

## 安装

**完整步骤见 [`INSTALL.html`](packaging/INSTALL.html)**（浏览器打开，带目录和分步说明），
或纯文本版 [`INSTALL.txt`](packaging/INSTALL.txt)。两份都随压缩包一起分发。

下载：[**Releases**](https://github.com/AnthosLan/CrewChief_CN_VoicePack/releases) → `crewchief-zh-voicepack-*.zip`（约 290 MB）

### 语音（三步）

1. 把 `%LOCALAPPDATA%\CrewChiefV4\Sounds` **整个复制一份**到别处，例如 `D:\CrewChief_zh\Sounds`。
   不要直接改原目录，出问题时你需要能退回去。
2. 用原版 CrewChief 的话，**先删掉压缩包里的 `voice\numbers\` 整个文件夹**（原因见下面注意事项），
   再把 `voice` 合并进第 1 步复制出来的目录。
3. CrewChief 属性页搜 `Override default Sound Pack location`（**装了中文界面就搜「语音包」**——
   搜索框只匹配显示出来的标签，不匹配属性内部名），填第 1 步的路径，重启。

再加一步防覆盖：把 `D:\CrewChief_zh\Sounds\sound_pack_version_info.txt` 里的版本号改成 `9999`，
否则上游一发新版，主界面的语音包下载按钮会变绿，点下去英文包会盖掉中文包。

### 界面中文化（一步）

把压缩包里的 `ui_text_zh.txt` 复制到 `%LOCALAPPDATA%\CrewChiefV4\`，**改名为 `ui_text.txt`**，重启。

放用户目录而不是安装目录，是因为它在合并顺序里优先级最高，而且程序更新不会覆盖它。
没翻译到的条目自动回落英文，不会出现空白。

### 中文语音指令（两步）

1. 装中文识别引擎，二选一：`MSSpeech_SR_zh-CN_TELE.msi`（Microsoft Speech Platform），
   或 Windows 设置 → 时间和语言 → 语言 → 添加中文并勾选「语音识别」。
   实测 Windows 自带的就够用，不必特意装 MSSpeech。
2. 把 `speech_recognition_override.txt` 放进 CrewChief 的数据文件夹。**别猜路径**——
   用菜单「文件 → Open data files folder」打开，把文件丢进去（「我的文档」常被重定向到别的盘）。
3. 主界面「语音识别模式」选「始终启用」或「按住按钮」，重启。

用菜单「语音向导」验证：说一句指令，它会实时显示识别到的文本和置信度。先试「能听到吗」——
不用进游戏，最快确认链路通了的一条。

---

## ⚠️ 注意事项

### 1. 装完一点声音都没有？大概率不是语音包的问题

这是实测中最耗时间的一个坑。症状是**一点声音都没有**（连启动的无线电测试都没有），
但日志里满是 `Sound: ...` 行，**一行报错都没有**。

原因通常是 **CrewChief 不用 Windows 默认输出设备**——它自己存了一个设备 GUID，
所以「浏览器放视频有声音」完全不能说明 CrewChief 也有声音。

最快的定性办法：属性页搜 `nAudio`，**取消勾选 `Use nAudio for playback`**，重启。
这会让它改用 Windows 默认设备。有声音了就说明是设备选错，去主界面把
「Messages playback device」改对，然后把 nAudio 开回来（关着会让 spotter 失去打断能力）。

完整排查步骤见 [`INSTALL.html`](packaging/INSTALL.html) 的「装完一点声音都没有」一节。
**卸载重装 CrewChief 没用**——设置存在 `%LOCALAPPDATA%\Britton_IT_Ltd`，卸载不会清它。

### 2. 原版程序装了 `numbers/` 会中英混播

`numbers` 包会覆盖 `numbers/0`–`99`、`point`、`hour` 这些英文包已有的文件夹，但它**没有**英文特有的
928 个合成件（599 个 `45point6` 这类「数字point数字」，外加 `point75`、`1_23` 等预录整段）。
结果是圈速念成「四十五 point six」。

**用原版程序就删掉 `voice/numbers/`。** 想要中文圈速必须自己编译，改动见
[`patches/crewchief-zh-numberreader.diff`](patches/crewchief-zh-numberreader.diff)。

### 3. 不要装到 `alt/` 目录

CrewChief 在使用非默认工程师语音包时，会**强制从基础包**读 `spotter*` 和 `radio_check*`
（`Audio/Sounds.cs:1147`）。按 autovoicepack README 那样装到 `alt/`，结果是工程师说中文、
**spotter 永远说英文**——而 spotter 恰恰是比赛中出现频率最高的播报。

正确装法是上面写的「整包替换 + `Override default Sound Pack location`」。

### 4. 工程师语音和 spotter 语音两个下拉框保持默认

同上一条的原因。一旦选了 Jerry 之类的替代音色，spotter 会退回英文。

### 5. 字幕覆盖层默认是关闭的

想在游戏里看到中文字幕，得先自己开：属性页搜 `subtitle`，勾上「启用字幕覆盖层」，**重启**。
「装了包却没字幕」是正常的，不是缺陷。

开了之后会连带显示一大片设置控件挡住画面，**按 `Ctrl + Shift` 收起**（这个快捷键界面上没写）。
实测中文字体不用改；万一显示成方块，改 `我的文档\CrewChiefV4\subtitle_overlay.json` 里的
`"fontName"` 为 `"Microsoft YaHei"`。

### 6. `-skip_updates` 挡不住语音包更新

它只跳过程序本体的更新检查，语音包的 XML 照样下载比对。防覆盖要靠上面的 `9999` 那一步。

---

## 卸载

| 装的东西 | 卸载方法 |
|---|---|
| 语音 | 属性页里 `Override default Sound Pack location` 清空，重启 |
| 界面 | 删掉 `%LOCALAPPDATA%\CrewChiefV4\ui_text.txt`，重启 |
| 语音指令 | 删掉 `我的文档\CrewChiefV4\speech_recognition_override.txt`，重启 |

三样互相独立，可以只卸其中一样。原目录始终没被改过，所以随时能退回英文。

---

## 版本状态

当前是 **v1.0.0 Beta**。内容全部完成并通过自动体检（音频的时长/削波/字幕一致性、
文案的折行/占位符/快捷键/标识符），并已在 Windows + Assetto Corsa 上实跑验收：

| 验收项 | 结果 |
|---|---|
| 语音播报 | ✅ 单场 52 条实听，零消息被丢弃 |
| 界面文案 | ✅ 主界面、菜单、属性页全中文，控件无截断 |
| 中文语音指令 | ✅ 24 条实测，识别接受率 81%，常见指令置信度 0.92–0.99 |
| 中文字幕 | ✅ 正常渲染，不需要改字体 |
| 圈速数字（用法 B） | ⏸ 需自己编译，尚未验证 |

**仍标 Beta 的原因**：抽样通过不等于全量通过。5308 条语音只实听了几十条，1305 条文案只翻了几页，
**译文别扭这类问题只能靠使用者反馈**。遇到哪句说不通、界面文字看着怪、语音指令老是识别错，
欢迎提 [issue](https://github.com/AnthosLan/CrewChief_CN_VoicePack/issues)。

逐项证据与操作步骤见 [Windows 验收清单](docs/Windows验收清单.md)。

---

## 许可

**语料与脚本采用 MIT，但生成的音频不是 MIT。** 两者不能合并理解。

音频由 XTTS v2 生成，该模型采用
[Coqui Public Model License 1.0.0](https://huggingface.co/coqui/XTTS-v2/raw/main/LICENSE.txt)（CPML，**非商用**）。
CPML 管的是模型**及其输出**，所以开源发布并不解除约束。免费分发没问题，但要满足三条：

1. **随包附上 CPML 全文** —— 任何拿到副本的人也必须拿到条款。压缩包根目录已放
   [`CPML.txt`](packaging/CPML.txt)，转发时请连它一起。
2. **不能把音频改成 MIT** —— CPML 不允许 sublicense，本库的 MIT 只覆盖语料与脚本。
3. **下游同样不能商用** —— 不能塞进付费产品或付费整合包。

对使用者来说就是：自己玩、免费分享给车友都没问题；不能拿去卖。

要商用得替换 TTS 引擎（语料、目录结构、后处理链都可复用）。Coqui 已于 2024 年 1 月关停，
没有人能再出售商业许可。另有一层容易漏掉的条款：Bart 音色来自 crew-chief-autovoicepack（MIT），
但它本身是 ElevenLabs 合成音，受该服务条款约束。完整说明见[许可与分发](docs/许可与分发.md)。

CrewChief 本体为 MIT。以上是对许可文本的阅读理解，不是法律意见。

---

## 参与制作

本库是**制作工程**，不是应用：存放翻译语料、音色参考、生成脚本和对上游的补丁。
生成的音频不入库——有这些输入就能完整复现。

```
translations/    翻译语料 CSV  ← 核心资产
baseline/Bart/   音色参考音频（12 条 / 38.9s，必须入库才能复现）
scripts/         生成、体检、语料构建脚本
src/             对 CrewChief 的新增（NumberReaderZh.cs、ui_text_zh.txt 等）
patches/         对 autovoicepack 和 CrewChief 的改动留档
packaging/       安装说明 + CPML 原文 + 打包脚本
docs/            方案与设计文档
```

**制作量的真相**：机器生成只占几小时，人工审校 946 条修正才是瓶颈——机器翻译在赛车术语上
不可靠（反义、术语不统一、量纲错），必须逐条过。

### 环境

本库不自包含，三个仓库**平级放在 `~/Projects/` 下**：

| 仓库 | 用途 | 许可 |
|---|---|---|
| 本库 | 语料与脚本的唯一权威来源 | MIT |
| [crew-chief-autovoicepack](https://github.com/cktlco/crew-chief-autovoicepack) | 提供 XTTS 运行环境（venv）与 Bart 音色 | MIT |
| [CrewChiefV4](https://gitlab.com/mr_belowski/CrewChiefV4) | 目标程序源码，只读参考 | MIT |

Python 依赖装在 autovoicepack 的 `.venv` 里。**四个版本约束都是踩坑钉死的，别放宽**：
`transformers>=4.57,<5`、`torch<2.9`、`torchaudio<2.9`，外加 `jieba`/`pypinyin`。
逐条原因见[踩坑与经验总结 §7](docs/踩坑与经验总结.md)。

定稿参数（Bart / `zh-cn` / 1.45x / radio EQ / 单声道 22050Hz 16-bit）不要随手改，依据见制作方案 §2.1。

### 文档

| 文档 | 内容 |
|---|---|
| [制作方案](docs/中文语音包制作方案.md) | **流程与参数**：工作量分解、定稿参数、翻译方案、语料格式、术语表、环境搭建、命令速查 |
| [踩坑与经验总结](docs/踩坑与经验总结.md) | **为什么这么做、哪里会翻车**：被否决的方案、XTTS 中文的脾气、机翻错误类型、装包陷阱 |
| [Windows 验收清单](docs/Windows验收清单.md) | Beta 转正式版的 7 项验收，逐条写了操作步骤、判据、回修路径 |
| [许可与分发](docs/许可与分发.md) | CPML 的三个硬条件、baseline 音色的第二层条款、商用替代路线 |
| [数字与时间朗读设计](docs/数字与时间朗读设计.md) | `NumberReaderZh` 的拆分规则、为什么中文只要 138 个文件夹 |

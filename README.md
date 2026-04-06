<div align="center">

<br>

<img src="assets/icon.png" width="128" height="128" alt="pdf2zh" style="border-radius: 22px;">

<br>
<br>

# pdf2zh

### 学术 PDF 智能翻译，保留公式与排版

<br>

[![macOS](https://img.shields.io/badge/macOS-13.0+-000000?style=flat-square&logo=apple&logoColor=white)](https://github.com/AaronGIG/pdf2zh-desktop)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.0.0-blue?style=flat-square)](https://github.com/AaronGIG/pdf2zh-desktop/releases)

<br>

<p>
  <a href="#安装">安装</a>&ensp;·&ensp;
  <a href="#功能特性">功能</a>&ensp;·&ensp;
  <a href="#翻译服务">翻译服务</a>&ensp;·&ensp;
  <a href="#使用指南">使用指南</a>&ensp;·&ensp;
  <a href="README_EN.md">English</a>
</p>

<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/screenshot-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="assets/screenshot-light.png">
  <img src="assets/screenshot-light.png" width="720" alt="pdf2zh 界面预览" style="border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.12);">
</picture>

<br>
<br>

</div>

---

## 功能特性

<table>
<tr>
<td width="50%" valign="top">

### 🔤 精准翻译
支持 20+ 翻译服务，包括 Google、DeepL、OpenAI 及本地模型 Ollama。学术论文翻译准确率高，术语一致性强。

</td>
<td width="50%" valign="top">

### 📐 排版保留
数学公式、图表、脚注、页眉页脚完整保留。所见即所得，翻译后的 PDF 与原文布局一致。

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📄 多种输出
单语翻译、双语对照、左右并排三种布局。满足不同阅读场景需求。

</td>
<td width="50%" valign="top">

### 🤖 AI 布局检测
基于 DocLayout-YOLO 模型智能识别文档结构，精确定位正文、标题、图表区域。

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📚 批量处理
支持多文件队列翻译，每个文件独立进度追踪，大文件自动分块处理。

</td>
<td width="50%" valign="top">

### 🖥 原生体验
为 macOS 重新设计，支持深色模式、原生通知、系统级快捷键。

</td>
</tr>
</table>

---

## 安装

### 系统要求

| 项目 | 要求 |
|:--|:--|
| **操作系统** | macOS 13.0 Ventura 或更高 |
| **芯片** | Apple Silicon (M1/M2/M3/M4) 或 Intel |
| **内存** | 4 GB 以上 |
| **磁盘** | 750 MB 可用空间 |

### 下载安装

<br>

<div align="center">

[**⬇ 下载 pdf2zh for Mac**](https://github.com/AaronGIG/pdf2zh-desktop/releases/latest)

`.dmg` 安装包 · Apple Silicon & Intel 通用

</div>

<br>

```
1. 下载 pdf2zh.dmg
2. 双击打开，将 pdf2zh 拖入「应用程序」文件夹
3. 首次打开：右键点击应用 → 打开（仅需一次）
```

<details>
<summary><b>使用 Homebrew 安装</b></summary>

<br>

```bash
brew install --cask pdf2zh
```

</details>

<details>
<summary><b>从源码构建</b></summary>

<br>

```bash
git clone https://github.com/AaronGIG/pdf2zh-desktop.git
cd pdf2zh-desktop
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python _launcher.py
```

</details>

---

## 翻译服务

> 开箱即用，无需配置即可使用免费翻译服务。
> 付费服务需在设置中填入 API Key。

| 服务 | 类型 | 配置 |
|:--|:--|:--|
| **Google 翻译** | 免费 | 无需配置 |
| **Bing 翻译** | 免费 | 无需配置 |
| **DeepL** | 付费 | 需要 API Key |
| **OpenAI / GPT** | 付费 | 需要 API Key |
| **Azure 翻译** | 付费 | 需要 API Key |
| **Ollama** | 本地 | 需本地部署模型 |

<details>
<summary><b>如何配置 Ollama 本地翻译</b></summary>

<br>

1. 安装 [Ollama](https://ollama.com)
2. 拉取翻译模型：
   ```bash
   ollama pull qwen2.5:7b
   ```
3. 在 pdf2zh 设置中选择 Ollama，填入模型名称

</details>

---

## 使用指南

### 快速开始

<table>
<tr>
<td width="64" align="center">
<br>
<b>1</b>
</td>
<td>
<b>打开 PDF</b><br>
拖拽文件到窗口，或点击「选择文件」按钮
</td>
</tr>
<tr>
<td align="center">
<br>
<b>2</b>
</td>
<td>
<b>选择语言</b><br>
设置源语言和目标语言（默认：英语 → 中文）
</td>
</tr>
<tr>
<td align="center">
<br>
<b>3</b>
</td>
<td>
<b>开始翻译</b><br>
点击「翻译」，等待处理完成
</td>
</tr>
<tr>
<td align="center">
<br>
<b>4</b>
</td>
<td>
<b>查看结果</b><br>
翻译完成后自动打开输出文件，同时保存至输出目录
</td>
</tr>
</table>

### 快捷键

| 操作 | 快捷键 |
|:--|:--|
| 打开文件 | `⌘ O` |
| 开始翻译 | `⌘ ↵` |
| 停止翻译 | `⌘ .` |
| 偏好设置 | `⌘ ,` |
| 切换深色模式 | `⌘ ⇧ D` |

---

## 技术架构

```
pdf2zh.app
├── Contents/
│   ├── MacOS/
│   │   └── pdf2zh              # 主程序入口
│   ├── Resources/
│   │   ├── runtime/            # Python 3.12 运行时
│   │   ├── site-packages/      # 依赖库
│   │   └── config/             # 配置文件
│   ├── Frameworks/             # 动态库
│   └── Info.plist              # 应用元数据
└── pdf2zh_files/               # 翻译输出
```

| 组件 | 版本 | 用途 |
|:--|:--|:--|
| PyQt5 | 5.15.11 | GUI 框架 |
| pdf2zh | 1.9.9 | 翻译引擎 |
| PyMuPDF | 1.26.7 | PDF 处理 |
| babeldoc | 0.2.33 | 文档结构分析 |
| OnnxRuntime | 内置 | AI 布局检测 |

---

## 常见问题

<details>
<summary><b>提示"无法验证开发者"怎么办？</b></summary>
<br>
右键点击应用 → 选择「打开」→ 在弹窗中点击「打开」。仅首次启动需要此操作。
<br><br>
或在终端执行：

```bash
xattr -cr /Applications/pdf2zh.app
```
</details>

<details>
<summary><b>Apple Silicon 和 Intel 版本有区别吗？</b></summary>
<br>
提供 Universal 通用版本，自动适配两种架构。Apple Silicon 上 AI 布局检测可通过 CoreML 加速。
</details>

<details>
<summary><b>翻译大文件时内存不足？</b></summary>
<br>
应用默认启用分块处理，1000+ 页文档会自动分段翻译。如仍遇到问题，可在设置中调低「内存限制」参数。
</details>

<details>
<summary><b>如何更新到最新版本？</b></summary>
<br>
应用内置自动更新检查。也可手动前往 <a href="https://github.com/AaronGIG/pdf2zh-desktop/releases">Releases</a> 下载最新版本。
</details>

---

<div align="center">

<br>

基于 [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate)（EMNLP 2025）构建

Made with ♥ by [AaronGIG](https://github.com/AaronGIG)

<br>

</div>

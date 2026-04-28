<div align="center">

<br>

<img src="assets/icon.png" width="128" height="128" alt="pdf2zh" style="border-radius: 22px;">

<br>
<br>

# 📖 pdf2zh 桌面版 v2.2.6

### 开箱即用的 PDF 学术翻译神器 🚀

**🎉 无需安装 Python · 无需配置环境 · 下载解压双击就能用！**

**🖥️ 支持 Windows + macOS 双平台**

[![Windows](https://img.shields.io/badge/Windows-10/11-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/AaronGIG/pdf2zh-desktop/releases)
[![macOS](https://img.shields.io/badge/macOS-13.0+-000000?style=flat-square&logo=apple&logoColor=white)](https://github.com/AaronGIG/pdf2zh-desktop/releases)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Version](https://img.shields.io/badge/Version-2.2.0-blue?style=flat-square)](https://github.com/AaronGIG/pdf2zh-desktop/releases)

<p>
  <a href="#-三步上手就这么简单">快速开始</a>&ensp;·&ensp;
  <a href="#-桌面版增强亮点">功能特性</a>&ensp;·&ensp;
  <a href="#-支持-35-种语言20-翻译服务">翻译服务</a>&ensp;·&ensp;
  <a href="#-zotero-深度联动">Zotero 联动</a>&ensp;·&ensp;
  <a href="#-更新日志">更新日志</a>&ensp;·&ensp;
  <a href="README_EN.md">English</a>
</p>

> 基于 [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate)（EMNLP 2025）打造，在原项目基础上大幅增强桌面体验。

让学术 PDF 翻译变得像复制粘贴一样简单——公式、图表、排版全部完美保留 ✨

</div>

---

## 🤔 为什么选择桌面版？

还在为翻译一篇论文折腾 Python 环境？还在对着黑窗口敲命令行？

**桌面版帮你把这些烦恼统统打包带走 👋**

| | 原版（Web/CLI）🖥️ | ✨ 桌面版 |
| --- | --- | --- |
| 安装方式 | 需要 Python + pip 😵 | 解压即用 🎁 |
| 操作界面 | 浏览器 / 终端 | 原生桌面 GUI 🪟 |
| 翻译预览 | 浏览器内查看 | 内置 PDF 连续滚动预览 👁️ |
| 批量处理 | 命令行参数 | 拖放文件/文件夹一键操作 🖱️ |
| Zotero 联动 | 不支持 | 拖论文进来 → 译文自动回写 📚 |
| 离线能力 | 不支持 | 程序本体完全离线 📴 |

---

## ✨ 桌面版增强亮点

### 🎯 真正的「零门槛」

- 📦 **完全独立打包**：Python 3.12 运行时 + 所有依赖全部内置，不污染你的系统
- 🖱️ **告别命令行**：全图形化操作，拖拽文件就能翻译
- 🔧 **智能错误诊断**：出问题？程序自动弹窗告诉你怎么修
- 💼 **真·便携版**：拷贝到 U 盘带着走，换台电脑照样用

### 🚀 超长文档？不在话下！

- 📄 1000+ 页的大部头轻松拿下
- 🧩 **分块翻译**：自动分块逐段翻译，超过 50 页自动开启
- 🧠 **智能内存管理**：逐页释放布局数组，即使上千页也不会内存溢出
- ⏯️ 断点续传——中途退出也不怕，下次自动接着翻
- 📜 **扫描版 PDF 支持**：自动覆盖底图原文
- 📊 **独立表格翻译管线**：专利、检测报告等表格密集文件
- 🔍 **OCR 识别**：内置 RapidOCR，纯图片扫描件自动识别并翻译

### 🤖 AI 翻译配置

- 🧩 **20+ 预设模型**：DeepSeek V3/R1、GPT-4o、GLM-4、Gemini、Mistral、Ollama 等，下拉框直接选
- 🔧 **OpenAI 兼容格式**：17 个快捷预设一键配置任何兼容接口
- 🔗 **一键测试连接**：填完配置立即验证，通过后自动保存
- 📝 **自定义提示词**：内置风格模板 + 自定义保存/导入/导出
- 📚 **术语库**：5 个学科内置（计算机/医学/金融/法律/电气），支持 txt/csv/json 导入

### 🧠 智能检测

- 🌐 **自动识别源语言**：打开 PDF 自动检测，自动设置翻译方向
- 📄 **自动检测扫描件**：纯图片 PDF 自动开启 OCR
- ✅ **翻译前预检**：API Key / 加密 / 语言检查
- ⏱️ **预估剩余时间**：窗口标题显示进度百分比
- 💾 **崩溃恢复**：异常退出后下次启动自动恢复

### 📚 Zotero 深度联动

- 🔗 **自动检测**：从 Zotero 拖入 PDF 或条目，自动识别来源
- 📎 **自动关联**：翻译完成后译文自动添加为 Zotero 附件
- 🔌 **一键安装插件**：设置页一键安装 pdf2zh Connector，开箱即用
- 📐 **格式多选**：左右并排 / 双语对照 / 仅译文，任意组合放回 Zotero

### 📖 PDF 预览 & 历史记录

- 👀 **连续滚动预览**：懒加载，大文档不卡
- 📐 **自适应显示**：适应宽度 / 适应高度 / 最佳适配
- 🗂️ 完整翻译历史，右键菜单打开目录/复制路径
- 🔍 **预览首页**：先翻一页看效果，满意再翻全文
- 📝 翻译完成后自动打开输出文件

### 📁 拖放 & 批量翻译

- 🖱️ **拖放支持**：文件、文件夹、Zotero 条目直接拖入窗口
- 📂 统一文件管理：浏览文件（多选）、浏览文件夹、一键清空
- 🔄 批量翻译失败项标红，支持一键重试

---

## 🚀 三步上手，就这么简单

### 📥 第一步：下载

| 平台 | 下载 | 大小 | 启动方式 |
|------|------|------|---------|
| 🪟 Windows | [`pdf2zh-desktop-win-v2.2.5.zip`](https://github.com/AaronGIG/pdf2zh-desktop/releases/download/v2.2.5/pdf2zh-desktop-win-v2.2.5.zip) | ~340MB | 解压 → 双击 `pdf2zh.bat` |
| 🍎 macOS | [`pdf2zh-desktop-mac-v2.2.6.zip`](https://github.com/AaronGIG/pdf2zh-desktop/releases/download/v2.2.6/pdf2zh-desktop-mac-v2.2.6.zip) | ~620MB | 解压 → 双击 `pdf2zh.app` |

### 🖱️ 第二步：启动

- **Windows**：双击 `pdf2zh.bat`
- **macOS**：双击 `pdf2zh.app`（首次需右键 → 打开）

### 📄 第三步：翻译

拖入 PDF → 选翻译服务 → 点「开始翻译」→ 搞定！🎉

> 💡 **小贴士**：Google / Bing 翻译免费无需配置，打开就能用！
>
> ⚠️ 请从 [Releases 页面](https://github.com/AaronGIG/pdf2zh-desktop/releases/latest) 下载，**不要**点 Source code。

---

## 🌍 支持 35 种语言、20+ 翻译服务

| 类型 | 服务 |
| --- | --- |
| 🆓 免费 | Google 翻译、Bing 翻译 |
| 🔑 API Key | OpenAI、DeepL、DeepLX、DeepSeek、Gemini、Azure |
| 🇨🇳 国内服务 | 智谱 GLM、硅基流动、腾讯翻译、阿里 Qwen-MT |
| 🏠 本地部署 | Ollama、Xinference、Argos Translate（完全离线） |
| 🔧 其他 | Dify、AnythingLLM、Grok、Groq、OpenAI 兼容格式 |

**支持语言**：中文（简繁）、英、日、韩、法、德、俄、西、意、葡、荷、波兰、土耳其、阿拉伯、泰、越南、印尼、马来、印地、孟加拉、乌克兰、捷克、瑞典、丹麦、芬兰、希腊、希伯来、匈牙利、罗马尼亚、老挝、高棉、缅甸、格鲁吉亚 等

---

## 📄 三种输出格式

- 📝 **`文件名-mono.pdf`** — 纯译文版
- 📖 **`文件名-dual.pdf`** — 双语对照版
- ↔️ **`文件名-side_by_side.pdf`** — 左原文右译文（推荐）

---

## 🔗 Zotero 深度联动

```
从 Zotero 拖论文到 pdf2zh → 翻译 → 译文自动出现在 Zotero 附件栏
```

1. **设置页** → Zotero 联动 → 「一键安装 Zotero 插件」→ Zotero 重启
2. 从 Zotero **拖条目或 PDF 附件**到 pdf2zh 窗口
3. 翻译 → 译文自动关联为 Zotero 附件，标题带格式标签（如 `side by side - 论文名`）

> 不需要每次操作，插件只装一次。没装 Zotero 的用户完全不受影响。

---

## ⌨️ 快捷键

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl+T` / `⌘T` | 开始翻译 |
| `Ctrl+O` / `⌘O` | 打开文件 |
| `← →` | PDF 翻页 |
| `Ctrl+滚轮` | 缩放预览 |
| `F11` | 全屏 |

---

## 🔧 翻译参数

| 参数 | 说明 |
| --- | --- |
| 🌐 源语言 / 目标语言 | 35 种语言，自动检测 |
| 📃 页面范围 | 全部、仅首页、前 5 页、自定义 |
| 🔄 翻译完成后自动打开 | 默认开启 |
| 🧩 分块翻译 | 大文件自动分块，超 50 页自动开启 |
| 📜 扫描版 PDF | 覆盖底图原文 |
| 📊 翻译表格内容 | 独立管线，按单元格翻译 |
| 🔍 OCR 识别 | 纯图片扫描件自动识别 |
| 📝 自定义提示词 | 控制 AI 翻译风格 |
| 📚 术语库 | 专业术语对照，支持 txt/csv/json |

---

## 💻 系统要求

| 项目 | Windows | macOS |
| --- | --- | --- |
| 💿 操作系统 | Windows 10/11 64 位 | macOS 13.0+ |
| 🧠 内存 | 4 GB 起步（大文档建议 8 GB） | 4 GB 以上 |
| 💾 磁盘 | ~750 MB | ~750 MB |
| 🌐 网络 | 使用在线翻译服务时需联网 | 同左 |
| 🍎 芯片 | — | Apple Silicon (M 系列) |

---

## ❓ 常见问题

| 😰 遇到了啥？ | 💡 这样解决 |
| --- | --- |
| 双击 vbs 报"不兼容" | Windows 11 24H2 废弃了 VBScript，请改用 `pdf2zh.bat` |
| macOS 提示"无法验证开发者" | 右键 → 打开 → 确认（仅需一次） |
| 翻译中途断了 | 检查磁盘空间，重启后自动从缓存续接 |
| 排版错乱 / 乱码 | 试试勾选「跳过字体子集」 |
| 大文档内存不足？ | 勾选「分块翻译」，设置合适的块大小 |
| 扫描版原文和译文重叠？ | 勾选「扫描版 PDF」 |
| PDF 丢进去秒结束？ | 勾选「OCR 识别」 |
| 专利表格不翻译？ | 勾选「翻译表格内容」 |
| 怎么用 DeepSeek？ | 选 DeepSeek → 填 API Key → 选模型 |
| 怎么用自己的 API？ | 选「OpenAI 兼容格式」→ 快捷预设一键配置 |
| 怎么保证术语准确？ | 展开「术语库」→ 选学科模板或自定义 |
| Zotero 翻译后没显示附件？ | 安装 pdf2zh Connector 插件 |

---

## 📋 更新日志

### v2.2.0（2026-04-06）

#### Zotero 深度联动
- Zotero 条目/PDF 附件拖拽识别（解析 x-moz-custom-clipdata MIME）
- 翻译完成自动回写 + 通过插件自动关联附件
- 一键安装 pdf2zh Connector 插件（自动写 extensions.json + 重启 Zotero）
- 附件标题带格式标签（`side by side - 论文名`）
- 智能数据目录检测（读 prefs.js 自定义路径 + 多磁盘扫描 + 选最大库）
- 支持内置存储 / 绝对链接 / 相对链接三种附件格式

#### UI 优化
- 全新 UI（克莱因蓝配色 + 圆角卡片 + 微软雅黑）
- API 配置改为悬浮弹窗，切换服务零跳动
- 提示词 / 术语库改为弹窗编辑
- 连续滚动 PDF 预览（懒加载）
- 标签页三等分 + 使用说明标签页
- 字号切换（小/中/大）
- 缩略图面板自适应 + 页码标注
- 历史记录防抖 + 右键菜单（打开目录/复制路径）
- 翻译完成自动清空文件列表
- 窗口自适应屏幕分辨率

#### 翻译能力
- 独立表格翻译管线（按单元格翻译 + 自适应字号）
- 独立图注翻译管线
- 35 种语言支持 + 源语言自动识别
- 自动检测扫描件 + 翻译前预检
- 预估剩余时间 + 崩溃恢复 + 批量失败重试

#### 稳定性
- 修复取消翻译闪退
- 修复 ollama 导入阻塞（延迟导入）
- OnnxRuntime 8 秒超时机制
- PDF 预览快速切换 150ms 防抖
- 历史记录 200ms 防抖
- 删除/清空历史不再闪退

### v2.0.0（2026-04-03）

- 首个功能完整版本
- 20+ 翻译服务 + AI 配置面板
- OCR / 表格翻译 / 扫描版支持
- 术语库 + 自定义提示词
- 连续滚动预览 + 拖放 + 批量翻译

### v1.0.0（2026-03-22）

- 首个公开发布版本

---

## 👨‍💻 关于本项目

**桌面版作者**：[@AaronGIG](https://github.com/AaronGIG) (CAS)

桌面版的独立打包、GUI 增强、便携化改造、Zotero 联动等功能由 AaronGIG (CAS) 与 Claude (Anthropic AI) 协作开发完成 🤖✨

**核心翻译引擎**：[PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate)（EMNLP 2025），感谢原项目的贡献 🤝

---

<div align="center">

希望能做更有意义的事

**专注交付生产级的垂直学术公共品** 🍀

[GitHub](https://github.com/AaronGIG/pdf2zh-desktop) · [最新版本](https://github.com/AaronGIG/pdf2zh-desktop/releases/latest) · [反馈](https://github.com/AaronGIG/pdf2zh-desktop/issues) · [小红书: 艾伦说](https://www.xiaohongshu.com/user/profile/66c6fef7000000001d0315ef)

</div>

# pdf2zh 桌面版 · Windows 独立版

> 基于 [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate)（EMNLP 2025）改造，感谢原项目的贡献。

**无需安装 Python，无需配置环境，下载解压即用的 Windows 桌面翻译工具。**

将学术 PDF 翻译为目标语言，同时完整保留原文的公式、图表、排版和注释。

---

## 与网页版 / 命令行版的区别

原版 PDFMathTranslate 需要通过 pip 安装 Python 环境后才能使用。本项目将 Python 3.12 运行时和所有依赖完整打包为独立 Windows 程序，用户无需了解 Python，也不需要配置任何环境变量。

| | 原版（Web/CLI） | 本桌面版 |
| --- | --- | --- |
| 安装方式 | 需要 Python + pip | 解压即用 |
| 界面 | 浏览器 / 终端 | 原生 Windows GUI |
| 翻译结果预览 | 浏览器内查看 | 内置 PDF 预览器 |
| 批量处理 | 命令行参数 | 界面直接操作 |
| 离线使用 | 不支持 | 本体离线，翻译需联网 |

---

## 核心功能

### 排版保留

翻译过程中完整保留原文档结构：

- 数学公式（LaTeX 渲染）
- 图表、插图位置
- 表格格式
- 目录与章节结构
- 页面注释与标注

### 多种输出格式

每次翻译同时生成两个文件：

- **`文件名-mono.pdf`** — 纯译文版，仅含翻译后内容
- **`文件名-dual.pdf`** — 双语对照版，原文与译文交替排列

界面中还可选择第三种模式：

- **双语并排** — 左侧原文，右侧译文，适合对照阅读

### 翻译缓存与中断恢复

已翻译的段落写入本地 SQLite 数据库。翻译中途退出后，重新启动同一文件会自动跳过已完成内容，无需从头开始，也不会重复消耗 API 额度。

### AI 文档布局检测

使用 DocLayout-YOLO 模型识别页面排版结构（正文、公式、图注、标题等），确保翻译内容插入正确位置。需要安装 Visual C++ Redistributable（文件夹内已附带安装包）。

### 批量处理

一次添加多个 PDF，程序按顺序逐个翻译，每个文件单独计算进度。

### 内置 PDF 预览

使用 PyMuPDF 渲染，支持缩放、翻页和页面缩略图，翻译完成后可直接在界面预览结果。

---

## 支持的翻译服务

| 类型 | 服务 |
| --- | --- |
| 免费，无需配置 | Google 翻译、Bing 翻译 |
| 需要 API Key | OpenAI、DeepL、DeepLX、DeepSeek、Gemini、Azure OpenAI、Azure 翻译 |
| 国内服务 | 智谱 GLM、硅基流动、腾讯翻译、阿里 Qwen-MT |
| 其他 | Dify、AnythingLLM、Grok、Groq、Argos Translate（本地离线） |
| 本地部署 | Ollama、Xinference |

---

## 翻译参数说明

| 参数 | 说明 |
| --- | --- |
| 源语言 / 目标语言 | 支持中文（简繁）、英文、日文、韩文、法文、德文、俄文、西班牙文、意大利文 |
| 页面范围 | 全部、仅首页、前 5 页、自定义范围（如 1-3,7,10-12） |
| 线程数 | 控制并发 API 请求数量，影响速度与服务限流 |
| 跳过字体子集 | 处理某些特殊字体的 PDF 时使用 |
| 忽略缓存 | 强制重新翻译，不读取本地缓存 |
| 自定义公式字体 | 正则表达式匹配特定字体，用于识别公式区域 |

---

## 快速开始

### 首次使用

1. 下载并解压本仓库
2. 双击 **`install.bat`** — 检测环境，安装 VC++ 运行库，创建桌面快捷方式
3. 双击 **`pdf2zh.vbs`** 或桌面快捷方式启动

> 如果已安装过 Visual C++ Redistributable，可跳过 `install.bat`，直接启动。

### 使用步骤

1. 点击「添加文件」或直接拖拽 PDF 到程序窗口
2. 选择翻译服务（免费服务无需额外配置）
3. 填写 API Key（使用付费服务时）
4. 选择目标语言和页面范围
5. 点击「开始翻译」
6. 完成后在 `pdf2zh_files/` 目录查看输出文件

---

## 内置依赖

所有依赖已打包在 `core/site-packages/` 中，无需单独安装。

| 模块 | 版本 | 用途 |
| --- | --- | --- |
| PyQt5 | 5.15.11 | GUI 框架 |
| pdf2zh | 1.9.9 | 核心翻译引擎 |
| PyMuPDF (fitz) | 1.26.7 | PDF 解析、渲染与预览 |
| babeldoc | 0.2.33 | 文档结构分析 |
| OpenCV (cv2) | 内置 | 布局检测图像处理 |
| onnxruntime | 内置 | DocLayout-YOLO 推理（需 VC++） |
| fontTools | 内置 | 字体处理与子集提取 |
| Pillow / numpy | 内置 | 图像与数值处理 |
| peewee | 内置 | 翻译缓存数据库（SQLite ORM） |

---

## 系统要求

- **操作系统**：Windows 10 / 11，64 位
- **内存**：4 GB 以上（翻译大型文档建议 8 GB）
- **磁盘**：程序本体约 750 MB，翻译输出文件另需空间
- **网络**：翻译时需要访问对应服务的 API

---

## 关于 Visual C++ Redistributable

AI 布局检测功能（DocLayout-YOLO via onnxruntime）需要 Microsoft Visual C++ 2015-2022 运行库：

- **未安装时**：翻译功能完全正常，但布局检测会跳过，复杂排版的识别精度略有下降
- **安装**：双击文件夹内的 `VC_redist.x64.exe`，或运行 `install.bat` 自动处理
- **备用下载**：<https://aka.ms/vs/17/release/vc_redist.x64.exe>

---

## 目录结构

```text
pdf2zh-desktop-win/
├── core/
│   ├── runtime/        Python 3.12 嵌入式运行时（无需系统 Python）
│   └── site-packages/  所有依赖包
├── config/             应用配置文件
├── pdf2zh_files/       翻译输出目录（运行后自动创建）
├── logs/               启动与运行日志
├── pdf2zh.vbs          ★ 主启动入口（双击此文件）
├── _launcher.py        Python 启动器（异常自动弹窗）
├── run_desktop.bat     调试启动（保留控制台窗口）
├── install.bat         首次安装脚本
├── VC_redist.x64.exe   Visual C++ 运行库安装包
└── diagnostic.bat      系统诊断工具
```

---

## 出错排查

| 现象 | 处理方式 |
| --- | --- |
| 双击 vbs 无反应 | 查看 `logs/startup_*.log` |
| 翻译中途中断 | 检查磁盘空间；重新翻译会从缓存自动续接 |
| VC++ 相关错误 | 运行 `install.bat` 或手动安装 `VC_redist.x64.exe` |
| 布局错位或乱码 | 尝试勾选「跳过字体子集」选项 |
| 需要完整诊断 | 双击 `diagnostic.bat` 生成诊断报告 |

---

详细安装说明（含 AI 辅助排错教程）见 [INSTALL.md](INSTALL.md)

英文版说明见 [README_EN.md](README_EN.md)

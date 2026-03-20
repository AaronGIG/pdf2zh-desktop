# pdf2zh 桌面版（PyQt5 独立版）

基于 [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) 改造的 Windows 桌面端，**开箱即用，无需安装 Python 环境**。

---

## 快速开始

### 1. 首次安装（只需一次）

双击运行 **`install.bat`**

- 自动检查系统环境
- 安装 Visual C++ 运行库（如尚未安装）
- 在桌面创建快捷方式

> 如果已有 Visual C++ Redistributable，跳过此步，直接启动。

### 2. 启动程序

双击 **`pdf2zh.vbs`**（或桌面快捷方式）

- 直接弹出 PyQt5 GUI 窗口，**无控制台黑窗口**
- 支持拖拽 PDF 文件、选择翻译服务、配置 API Key

---

## 目录结构

```
pdf2zh-desktop-slim/
├── core/
│   ├── runtime/        Python 3.12 嵌入式运行时（无需系统 Python）
│   └── site-packages/  所有依赖包（PyQt5、pdf2zh、PyMuPDF 等）
├── config/             应用配置
├── pdf2zh_files/       翻译输出目录（自动创建）
├── logs/               启动日志（出错时查看）
├── pdf2zh.vbs          ★ 主启动入口（双击此文件）
├── _launcher.py        Python 启动器（错误自动弹窗提示）
├── run_desktop.bat     调试启动（有控制台，可看日志）
├── install.bat         首次安装脚本
├── VC_redist.x64.exe   Visual C++ 运行库安装包
└── diagnostic.bat      系统诊断工具
```

---

## 依赖模块状态

| 模块 | 状态 | 说明 |
|------|------|------|
| PyQt5 5.15.11 | ✅ 已内置 | GUI 框架 |
| pdf2zh 1.9.9 | ✅ 已内置 | 核心翻译引擎 |
| PyMuPDF (fitz) 1.26.7 | ✅ 已内置 | PDF 处理 |
| babeldoc 0.2.33 | ✅ 已内置 | 文档解析 |
| requests / tqdm / numpy | ✅ 已内置 | 基础依赖 |
| OpenCV (cv2) | ✅ 已内置 | 图像处理（布局检测用） |
| fontTools / Pillow | ✅ 已内置 | 字体/图像处理 |
| onnxruntime | ⚠️ 需 VC++ | AI 布局检测，见下方说明 |
| 所有翻译器 | ✅ 已内置 | Google/Bing/OpenAI/DeepL/Azure/Gemini/Deepseek 等 |

---

## 关于 Visual C++ Redistributable

**onnxruntime**（AI 文档布局检测模型）依赖 Microsoft Visual C++ Redistributable。

- **未安装时**：翻译仍可正常进行，但 AI 布局检测不可用，复杂排版的精度略有下降
- **安装方式**：双击文件夹内的 `VC_redist.x64.exe` 即可，或运行 `install.bat` 自动处理

下载地址（备用）：https://aka.ms/vs/17/release/vc_redist.x64.exe

---

## 支持的翻译服务

| 类型 | 服务 |
|------|------|
| 免费 | Google 翻译、Bing 翻译 |
| API Key | OpenAI、DeepL、DeepSeek、Gemini、Azure、智谱、硅基流动、腾讯、阿里 Qwen |
| 本地部署 | Ollama、Xinference |

---

## 系统要求

- Windows 10 / 11（64 位）
- 内存：建议 4GB 以上
- 磁盘：安装目录约 750MB，翻译输出另需空间

---

## 出错排查

1. **启动失败**：查看 `logs/` 目录下最新的 `startup_*.log`
2. **翻译失败**：检查磁盘剩余空间（翻译大文件时可能超出）
3. **VC++ 报错**：运行 `install.bat` 或手动安装 `VC_redist.x64.exe`
4. **详细诊断**：双击 `diagnostic.bat` 生成系统诊断报告

---

## GitHub 推送说明

本仓库包含完整二进制依赖（约 750MB），推送前建议：

1. 在仓库根目录添加 `.gitattributes` 启用 Git LFS 跟踪大文件：

```
*.dll filter=lfs diff=lfs merge=lfs -text
*.pyd filter=lfs diff=lfs merge=lfs -text
*.zip filter=lfs diff=lfs merge=lfs -text
*.onnx filter=lfs diff=lfs merge=lfs -text
*.exe filter=lfs diff=lfs merge=lfs -text
```

2. 或通过 GitHub Releases 上传压缩包，用户下载后解压即用。

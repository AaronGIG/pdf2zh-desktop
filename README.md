# pdf2zh 桌面版 · Windows

感谢 [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) 项目，本工具在其基础上改造为独立的 Windows 桌面版，无需安装 Python 或任何依赖，下载即用。

---

## 快速开始

### 首次使用

双击 **`install.bat`**，自动完成环境检测和快捷方式创建。

### 启动

双击 **`pdf2zh.vbs`** 或桌面快捷方式，直接弹出翻译窗口，无黑色控制台。

---

## 主要功能

- **保留原版排版**：公式、图表、表格位置不变
- **多翻译服务**：Google、Bing（免费）；OpenAI、DeepL、DeepSeek、Gemini、Azure、Qwen 等（需 API Key）；Ollama 本地模型
- **双语输出**：可生成仅译文版、双语交替版、双语并排版
- **翻译缓存**：已翻译的段落写入本地 SQLite 数据库，中断后重新翻译会自动跳过已完成内容，不重复调用 API
- **分页处理**：逐页翻译，避免大文件内存溢出
- **批量翻译**：支持一次添加多个 PDF

---

## 目录结构

```text
pdf2zh-desktop-win/
├── core/
│   ├── runtime/        Python 3.12 嵌入式运行时
│   └── site-packages/  所有依赖包（PyQt5、PyMuPDF、cv2 等）
├── config/             应用配置
├── pdf2zh_files/       翻译输出（自动创建）
├── logs/               启动日志
├── pdf2zh.vbs          ★ 主启动入口
├── _launcher.py        启动器（异常自动弹窗提示）
├── run_desktop.bat     调试启动（带控制台）
├── install.bat         首次安装
├── VC_redist.x64.exe   Visual C++ 运行库
└── diagnostic.bat      系统诊断
```

---

## 系统要求

- Windows 10 / 11，64 位
- 内存：4GB 以上
- 磁盘：程序约 750MB，翻译输出目录另需空间

---

## 关于 Visual C++ Redistributable

AI 文档布局检测（onnxruntime）需要 Visual C++ 运行库：

- **未安装**：翻译正常运行，但复杂排版的识别精度略降
- **安装**：双击 `VC_redist.x64.exe`，或运行 `install.bat` 自动处理
- **备用下载**：<https://aka.ms/vs/17/release/vc_redist.x64.exe>

---

## 内置依赖

| 模块 | 版本 | 用途 |
| --- | --- | --- |
| PyQt5 | 5.15.11 | GUI |
| pdf2zh | 1.9.9 | 翻译引擎 |
| PyMuPDF | 1.26.7 | PDF 解析与渲染 |
| babeldoc | 0.2.33 | 文档结构分析 |
| OpenCV | 内置 | 布局检测图像处理 |
| onnxruntime | 内置 | AI 布局模型（需 VC++） |
| fontTools / Pillow / numpy | 内置 | 字体、图像、数值处理 |

---

## 出错排查

| 现象 | 处理 |
| --- | --- |
| 启动无反应 | 查看 `logs/startup_*.log` |
| 翻译中途失败 | 检查磁盘剩余空间；重新翻译会从缓存继续 |
| VC++ 相关报错 | 运行 `install.bat` 或手动装 `VC_redist.x64.exe` |
| 需要完整诊断 | 双击 `diagnostic.bat` |

---

详细安装说明见 [INSTALL.md](INSTALL.md)

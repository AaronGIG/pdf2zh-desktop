# Pdf2zh Studio

Windows 桌面 PDF 学术翻译应用，整合 PDFMathTranslate 的排版翻译与本地 GGUF 模型推理。双击 `dist/Pdf2zhStudio/Pdf2zhStudio.exe` 启动，不需要脚本或系统 Python。

## 使用

1. 在“本地模型”中导入 GGUF 指令模型，建议 7B–14B、Q4_K_M。
2. 加载模型，回到“文档翻译”并选择 PDF。
3. 选择语言和输出格式，开始翻译。

译文默认保存在 `文档/Pdf2zhStudio`。导入的模型复制到 `%LOCALAPPDATA%/Pdf2zhStudio/models`。

## 构建

使用 Python 3.12 x64，依赖安装到 `.venv`。以该解释器运行 `.venv/PyInstaller/__main__.py Pdf2zhStudio.spec`。上游源码采用 AGPL-3.0 许可证。

# pdf2zh Desktop · Windows

A self-contained Windows desktop app built on top of [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate). No Python installation required — just download and run.

---

## Quick Start

### First-time setup

Double-click **`install.bat`** — it checks your environment and creates a desktop shortcut.

### Launch

Double-click **`pdf2zh.vbs`** or the desktop shortcut. The GUI opens directly with no console window.

---

## Features

- **Layout-preserving translation** — formulas, figures, and tables stay in place
- **Multiple translation services** — Google and Bing (free); OpenAI, DeepL, DeepSeek, Gemini, Azure, Qwen and more (API key required); Ollama for local models
- **Flexible output** — translation-only, bilingual alternating pages, or side-by-side bilingual
- **Translation cache** — completed paragraphs are saved to a local SQLite database. If a job is interrupted, restarting it resumes from where it left off without re-calling the API
- **Page-by-page processing** — large files are processed one page at a time, keeping memory usage low
- **Batch mode** — add multiple PDFs in one go

---

## Directory Layout

```text
pdf2zh-desktop-win/
├── core/
│   ├── runtime/        Embedded Python 3.12 (no system Python needed)
│   └── site-packages/  All dependencies (PyQt5, PyMuPDF, cv2, etc.)
├── config/             App configuration
├── pdf2zh_files/       Translation output (auto-created)
├── logs/               Startup logs
├── pdf2zh.vbs          ★ Main launcher — double-click this
├── _launcher.py        Python entry point with error dialog
├── run_desktop.bat     Debug launcher (shows console)
├── install.bat         First-time setup
├── VC_redist.x64.exe   Visual C++ Redistributable installer
└── diagnostic.bat      System diagnostic tool
```

---

## System Requirements

- Windows 10 / 11, 64-bit
- RAM: 4 GB or more recommended
- Disk: ~750 MB for the app, plus space for output files

---

## Visual C++ Redistributable

The AI layout detection model (onnxruntime) requires the Microsoft Visual C++ Redistributable:

- **Without it**: translation still works; complex layout detection is skipped, which may slightly reduce accuracy on dense documents
- **Install**: double-click `VC_redist.x64.exe`, or let `install.bat` handle it
- **Download**: <https://aka.ms/vs/17/release/vc_redist.x64.exe>

---

## Bundled Dependencies

| Package | Version | Purpose |
| --- | --- | --- |
| PyQt5 | 5.15.11 | GUI framework |
| pdf2zh | 1.9.9 | Translation engine |
| PyMuPDF | 1.26.7 | PDF parsing and rendering |
| babeldoc | 0.2.33 | Document structure analysis |
| OpenCV | bundled | Image processing for layout detection |
| onnxruntime | bundled | AI layout model (requires VC++) |
| fontTools / Pillow / numpy | bundled | Font, image, and numeric processing |

---

## Translation Services

| Type | Services |
| --- | --- |
| Free | Google Translate, Bing Translate |
| API key | OpenAI, DeepL, DeepSeek, Gemini, Azure, Zhipu, Silicon Flow, Tencent, Ali Qwen |
| Local | Ollama, Xinference |

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| App doesn't start | Check `logs/startup_*.log` |
| Translation fails mid-way | Check available disk space; restarting will resume from cache |
| VC++ error | Run `install.bat` or manually install `VC_redist.x64.exe` |
| Need full diagnostics | Double-click `diagnostic.bat` |

---

For installation instructions, see [INSTALL.md](INSTALL.md)

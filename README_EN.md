# pdf2zh Desktop · Windows Standalone

> Built on [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) (EMNLP 2025). Thanks to the original project.

**A zero-install Windows desktop app for translating academic PDFs — no Python, no pip, no setup.**

Translates scientific documents into your target language while preserving all formulas, figures, tables, and layout structure.

---

## How This Differs from the Web / CLI Version

The original PDFMathTranslate requires a Python environment installed via pip. This project bundles Python 3.12 and all dependencies into a standalone Windows application — no environment setup, no terminal, no configuration files.

| | Original (Web/CLI) | This Desktop Version |
| --- | --- | --- |
| Installation | Python + pip required | Unzip and run |
| Interface | Browser / terminal | Native Windows GUI |
| PDF preview | Browser | Built-in PDF viewer |
| Batch processing | Command-line flags | In-app UI |
| Offline use | Not supported | App runs offline; translation requires internet |

---

## Features

### Layout Preservation

Translation preserves the full document structure:

- Mathematical formulas (LaTeX rendered)
- Figures and diagrams (position intact)
- Tables and formatting
- Table of contents and chapter headings
- Annotations and markup

### Output Formats

Every translation produces two files by default:

- **`filename-mono.pdf`** — translation only, clean output
- **`filename-dual.pdf`** — bilingual alternating pages, original and translation side-by-side per page

A third mode is available in the interface:

- **Side-by-side bilingual** — original on the left, translation on the right, for direct comparison

### Translation Cache and Resume

Completed paragraphs are saved to a local SQLite database. If a job is interrupted, restarting it picks up where it left off — no re-processing, no wasted API calls.

### AI Document Layout Detection

Uses DocLayout-YOLO to identify page regions (body text, formulas, captions, headings, etc.) so translated content is inserted in the correct position. Requires Visual C++ Redistributable (installer included).

### Batch Processing

Add multiple PDFs at once. The app processes them sequentially with individual progress tracking per file.

### Built-in PDF Preview

Powered by PyMuPDF — supports zoom, page navigation, and thumbnail sidebar. Preview source or translated documents without leaving the app.

---

## Supported Translation Services

| Type | Services |
| --- | --- |
| Free, no setup | Google Translate, Bing Translate |
| API key required | OpenAI, DeepL, DeepLX, DeepSeek, Gemini, Azure OpenAI, Azure Translator |
| Additional | Zhipu GLM, Silicon Flow, Tencent, Ali Qwen-MT, Dify, AnythingLLM, Grok, Groq |
| Offline | Argos Translate (local, no internet needed) |
| Self-hosted | Ollama, Xinference |

---

## Translation Options

| Option | Description |
| --- | --- |
| Source / Target language | Simplified Chinese, Traditional Chinese, English, Japanese, Korean, French, German, Russian, Spanish, Italian |
| Page range | All, first page, first 5 pages, custom (e.g. 1-3,7,10-12) |
| Threads | Number of concurrent API requests; affects speed and rate limiting |
| Skip font subsetting | Useful for PDFs with non-standard embedded fonts |
| Ignore cache | Force re-translation, bypassing saved results |
| Formula font regex | Custom pattern to identify formula regions by font name |

---

## Quick Start

### First-time setup

1. Download and extract this repository
2. Double-click **`install.bat`** — checks your environment, installs VC++ if needed, creates a desktop shortcut
3. Double-click **`pdf2zh.vbs`** or the desktop shortcut to launch

> If you already have Visual C++ Redistributable installed, skip `install.bat` and launch directly.

### Usage

1. Click "Add Files" or drag PDFs into the app window
2. Select a translation service (free services need no configuration)
3. Enter your API key (for paid services)
4. Set target language and page range
5. Click "Start Translation"
6. Find output files in the `pdf2zh_files/` folder when done

---

## Bundled Dependencies

All packages are in `core/site-packages/` — nothing to install separately.

| Package | Version | Purpose |
| --- | --- | --- |
| PyQt5 | 5.15.11 | GUI framework |
| pdf2zh | 1.9.9 | Core translation engine |
| PyMuPDF (fitz) | 1.26.7 | PDF parsing, rendering, and preview |
| babeldoc | 0.2.33 | Document structure analysis |
| OpenCV (cv2) | bundled | Image processing for layout detection |
| onnxruntime | bundled | DocLayout-YOLO inference (requires VC++) |
| fontTools | bundled | Font processing and subsetting |
| Pillow / numpy | bundled | Image and numeric processing |
| peewee | bundled | Translation cache (SQLite ORM) |

---

## System Requirements

- **OS**: Windows 10 / 11, 64-bit
- **RAM**: 4 GB minimum (8 GB recommended for large documents)
- **Disk**: ~750 MB for the app; additional space for output files
- **Network**: Required when using online translation services

---

## Visual C++ Redistributable

The AI layout detection feature (DocLayout-YOLO via onnxruntime) requires the Microsoft Visual C++ 2015–2022 Redistributable:

- **Without it**: translation works fully; layout detection is skipped, which may reduce accuracy on complex documents
- **Install**: double-click `VC_redist.x64.exe` in the app folder, or run `install.bat`
- **Download**: <https://aka.ms/vs/17/release/vc_redist.x64.exe>

---

## Directory Layout

```text
pdf2zh-desktop-win/
├── core/
│   ├── runtime/        Embedded Python 3.12 (no system Python needed)
│   └── site-packages/  All bundled dependencies
├── config/             App configuration
├── pdf2zh_files/       Translation output (auto-created)
├── logs/               Startup and runtime logs
├── pdf2zh.vbs          ★ Main launcher — double-click this
├── _launcher.py        Python entry point with error dialog
├── run_desktop.bat     Debug launcher (shows console window)
├── install.bat         First-time setup script
├── VC_redist.x64.exe   Visual C++ Redistributable installer
└── diagnostic.bat      System diagnostic tool
```

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| App doesn't open | Check `logs/startup_*.log` |
| Translation stops mid-way | Check available disk space; restart to resume from cache |
| VC++ error on startup | Run `install.bat` or manually install `VC_redist.x64.exe` |
| Garbled text or layout issues | Try enabling "Skip font subsetting" |
| Need full diagnostics | Double-click `diagnostic.bat` |

---

For detailed installation steps and an AI-assisted troubleshooting guide, see [INSTALL.md](INSTALL.md)

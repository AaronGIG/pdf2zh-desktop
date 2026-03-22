# 📖 pdf2zh Desktop · Zero-Install PDF Academic Translator 🚀

**🎉 No Python needed · No environment setup · Just download, unzip, and go!**

> Built on [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) (EMNLP 2025), with a significantly enhanced desktop experience.

Translate academic PDFs as easily as copy-paste — formulas, figures, and layout all perfectly preserved ✨

---

## 🤔 Why the Desktop Version?

Tired of wrestling with Python environments just to translate a paper? Done with typing commands into a black terminal window?

**The Desktop version takes all those headaches away 👋**

| | Original (Web/CLI) 🖥️ | ✨ Desktop Version |
| --- | --- | --- |
| Installation | Python + pip required 😵 | Unzip and run 🎁 |
| Interface | Browser / terminal | Native Windows GUI 🪟 |
| PDF preview | In-browser | Built-in PDF viewer 👁️ |
| Batch processing | Command-line flags | One-click in the UI 🖱️ |
| Offline | Not supported | App runs fully offline 📴 |

---

## ✨ Desktop Enhancements

### 🎯 True Zero-Barrier Experience

- 📦 **Fully self-contained**: Python 3.12 runtime + all dependencies bundled — zero system pollution
- 🖱️ **No more command line**: Drag & drop your PDFs, click translate
- 🔧 **Smart error diagnostics**: Something wrong? The app pops up a dialog telling you how to fix it
- 💼 **Truly portable**: Copy to a USB drive, run on any Windows PC

### 🚀 Massive Documents? No Problem!

- 📄 1000+ page documents handled with ease
- 🧩 **Chunk translation**: Customize chunk size (5–200 pages), auto-splits large PDFs, built-in rate-limit delays, assembles the complete document when done
- 🧠 **Smart memory management**: Per-page layout array release prevents OOM even on 1000+ page books
- ⏯️ Auto-resume — quit mid-translation and pick up right where you left off, no wasted API calls

### 📚 History & Live Preview

- 🗂️ Full translation history, navigate with keyboard arrow keys
- 👀 Built-in PDF previewer — what you see is what you get
- 🔍 Before/after comparison at a glance
- 📝 Re-translating the same file auto-numbers output (`file(1)`, `file(2)`), never overwrites previous results

### 📁 Batch Translation

- 📂 Drop in a whole folder of PDFs — each file translated and tracked individually
- 🎯 Smart file detection — only processes PDF files

---

## 🚀 Three Steps to Get Started

1. 📥 **Download and extract** this repository
2. 🖱️ **Double-click `pdf2zh.bat`** to launch (first-time users: run `install.bat` first)
   > ⚠️ Windows 11 24H2+ users: use `pdf2zh.bat`. Older Windows versions can also use `pdf2zh.vbs`.
3. 📄 **Drop in a PDF** → pick a translation service → hit "Start Translation" → done! 🎉

> 💡 **Tip**: Google / Bing translation is free and requires zero configuration — just open and go!

---

## 🌍 20+ Translation Services — Pick Your Favorite

| Type | Services |
| --- | --- |
| 🆓 Free | Google Translate, Bing Translate |
| 🔑 API Key Required | OpenAI, DeepL, DeepLX, DeepSeek, Gemini, Azure |
| 🇨🇳 China-based | Zhipu GLM, Silicon Flow, Tencent, Ali Qwen-MT |
| 🏠 Self-hosted | Ollama, Xinference, Argos Translate (fully offline) |
| 🔧 Other | Dify, AnythingLLM, Grok, Groq |

---

## 📄 Three Output Formats

Every translation generates:

- 📝 **`filename-mono.pdf`** — Translation only, clean and crisp
- 📖 **`filename-dual.pdf`** — Bilingual version, original and translation alternating
- ↔️ **Side-by-side** — Original on the left, translation on the right

---

## 🤖 AI-Powered Layout Detection

Built-in DocLayout-YOLO model identifies page regions (body text, formulas, captions, headings, etc.) and ensures translated content is placed in exactly the right spot.

- ✅ Status indicator: "AI Layout Detection Enabled ✓" shown at translation start
- 📋 Full translation logs at `logs/translate.log` for easy debugging

> ⚠️ Requires [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) (`VC_redist.x64.exe` included in the folder).
> Without it, translation works perfectly — layout detection accuracy is just slightly reduced.

---

## 🔧 Translation Options

| Option | Description |
| --- | --- |
| 🌐 Source / Target Language | Chinese (Simplified/Traditional), English, Japanese, Korean, French, German, Russian, Spanish, Italian |
| 📃 Page Range | All, first page, first 5, custom (e.g. `1-3,7,10-12`) |
| ⚡ Threads | Concurrent API requests — affects speed and rate limiting |
| 🔤 Skip Font Subsetting | For PDFs with non-standard embedded fonts |
| 🔄 Ignore Cache | Force re-translation |
| 📐 Formula Font Regex | Custom pattern to identify formula regions |
| 🧩 Chunk Translation | Split large files into N-page chunks, with configurable size and rate-limit delay |

---

## 💻 System Requirements

| | Requirement |
| --- | --- |
| 💿 OS | Windows 10 / 11, 64-bit |
| 🧠 RAM | 4 GB minimum (8 GB recommended for large docs) |
| 💾 Disk | ~750 MB for the app + space for output files |
| 🌐 Network | Required for online translation services |

---

## 📦 Bundled Dependencies

Everything is pre-packaged — truly out of the box ✅

| Package | Version | Purpose |
| --- | --- | --- |
| PyQt5 | 5.15.11 | GUI framework |
| pdf2zh | 1.9.9 | Core translation engine |
| PyMuPDF | 1.26.7 | PDF parsing & preview |
| babeldoc | 0.2.33 | Document structure analysis |
| onnxruntime | bundled | AI layout detection (needs VC++) |
| OpenCV / Pillow / numpy | bundled | Image processing |
| fontTools | bundled | Font processing |
| peewee | bundled | Translation cache (SQLite) |

---

## 📂 Directory Structure

```text
pdf2zh-desktop-win/
├── core/
│   ├── runtime/        ⚙️ Embedded Python 3.12
│   └── site-packages/  📦 All bundled packages
├── config/             ⚙️ App configuration
├── pdf2zh_files/       📄 Translation output
├── logs/               📋 Runtime logs
├── pdf2zh.bat          ⭐ Main launcher (double-click me!)
├── pdf2zh.vbs          ⭐ Alt launcher (older Windows)
├── _launcher.py        🐍 Python entry point
├── debug_start.bat     🔧 Debug launcher (shows console + diagnostics)
├── install.bat         📥 First-time setup script
├── VC_redist.x64.exe   🔧 VC++ Redistributable
└── diagnostic.bat      🩺 System diagnostic tool
```

---

## ❓ Troubleshooting

| 😰 What happened? | 💡 How to fix |
| --- | --- |
| VBS says "incompatible" | Windows 11 24H2 deprecated VBScript — use `pdf2zh.bat` instead |
| Double-clicked, nothing happened | Check `logs/startup_*.log` |
| Translation stopped midway | Check disk space; restart to auto-resume from cache |
| VC++ error | Run `install.bat` or manually install `VC_redist.x64.exe` |
| Garbled text / layout issues | Try enabling "Skip font subsetting" |
| AI layout detection status? | Check progress bar message; details in `logs/translate.log` |
| Out of memory on large docs? | Enable "Chunk Translation" and set an appropriate chunk size |
| Need full diagnostics? | Double-click `diagnostic.bat` for a report 📋 |

---

## 👨‍💻 About This Project

**Desktop version author**: [@AaronGIG](https://github.com/AaronGIG)

The standalone packaging, GUI enhancements, portable design, and smart diagnostics were co-developed by AaronGIG and Claude (Anthropic AI) 🤖✨

**Core translation engine**: [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) (EMNLP 2025) — thanks to the original project 🤝

---

📖 Detailed install guide → [INSTALL.md](INSTALL.md) | 🇨🇳 中文说明 → [README.md](README.md)

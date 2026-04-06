# pdf2zh-desktop Mac v2.2.0 — 完整复刻指南

> 目标：在一台全新 Mac 上，从零完美复刻出与当前版本一模一样的 app
> 编写日期：2026-04-06
> 适用于：macOS 13.0+ / Apple Silicon & Intel

---

## 一、项目全貌

### 是什么
一个 macOS 桌面 PDF 论文翻译工具，基于 PyQt5 + pdf2zh 引擎，开箱即用的 .app。

### 核心特性
- 20+ 翻译服务（Google/Bing/DeepSeek/OpenAI/DeepL 等）
- 3 种输出模式：双语交替(Dual) / 仅翻译(Mono) / 左右并排(Side by Side)
- PDF 预览：连续滚动 + 缩略图 + 高亮标注
- AI 助手：8 个预设 prompt + 自定义 prompt 库 + 论文问答
- Zotero 联动：拖入即翻 → 译文自动回写
- 历史管理：分组/标签/搜索
- 术语库 + 提示词模板
- 深色模式 + 主题色自定义
- 关怀系统：节日/时段/里程碑消息
- 小黑猫桌面宠物彩蛋

---

## 二、环境准备

### 2.1 系统要求
```
macOS 13.0 (Ventura) 或更高
Python 3.12（推荐用 pyenv 或 Homebrew 安装）
Xcode Command Line Tools
```

### 2.2 安装 Python 3.12
```bash
brew install python@3.12
# 或
pyenv install 3.12.7
pyenv global 3.12.7
```

### 2.3 创建虚拟环境
```bash
python3.12 -m venv venv
source venv/bin/activate
```

### 2.4 安装依赖
```bash
# 核心
pip install PyQt5==5.15.11 pyqt5-sip==12.18.0
pip install PyMuPDF==1.26.7
pip install pdf2zh==1.9.9
pip install babeldoc==0.2.33

# AI & 翻译服务
pip install openai==1.77.0
pip install deepl==1.22.0
pip install tencentcloud-sdk-python-tmt==3.0.1374
pip install azure-ai-translation-text==1.0.1
pip install ollama==0.4.8

# ML 推理
pip install onnxruntime==1.21.1
pip install onnx==1.20.1
pip install rapidocr_onnxruntime==1.4.4
pip install numpy==2.4.2
pip install opencv-python-headless==4.11.0.86

# 工具
pip install requests==2.32.3
pip install peewee==3.18.1
pip install tenacity==9.1.2
pip install pillow==11.2.1
pip install lxml==5.4.0
pip install fontTools==4.57.0
pip install pikepdf==9.7.0
pip install pdfminer.six
pip install huggingface_hub==0.31.1
pip install tqdm==4.67.1
pip install httpx==0.28.1
pip install certifi charset_normalizer

# 打包
pip install pyinstaller
```

---

## 三、文件结构

从仓库 `AaronGIG/pdf2zh-desktop` 的 `mac/` 目录获取源码：

```
mac/
├── ui/
│   ├── __init__.py              # 空文件（包标记）
│   ├── main_window.py           # 主窗口 (~5700 行)
│   ├── translate_worker.py      # 翻译 worker + Zotero 工具函数
│   ├── config_manager.py        # 配置 + 历史管理
│   ├── ai_client.py             # AI 服务检测 + chat API
│   ├── caring.py                # 关怀消息系统
│   ├── quotes.py                # 多语言名言库
│   ├── glossary_manager.py      # 术语库管理
│   └── prompt_manager.py        # 提示词模板管理
│
├── assets/
│   ├── app_icon.png             # 应用图标
│   ├── author_avatar.png        # 作者头像
│   ├── qq_group_qr.png          # QQ群二维码
│   ├── doclayout_yolo.onnx      # 布局检测模型 (72MB)
│   ├── pdf2zh-connector.xpi     # Zotero 插件
│   ├── zotero-plugin/           # 插件源码
│   └── zotero-plugin-unpacked/  # 插件未打包版
│
├── pdf2zh.spec                  # PyInstaller 打包配置
├── pdf2zh.command               # Shell 启动脚本
└── README.md
```

---

## 四、设计风格 & 审美规范

### 4.1 颜色系统（Apple Design System）

**浅色模式 (L):**
```python
bg = "#FFFFFF"         # 主背景
bg2 = "#F5F5F7"        # 次级背景
card = "#FFFFFF"       # 卡片
card_b = "rgba(0,0,0,0.06)"  # 卡片边框
acc = "#0071E3"        # 强调色（Apple Blue）
acc_h = "#0077ED"      # 强调色 hover
t1 = "#1D1D1F"         # 主文字
t2 = "#6E6E73"         # 次文字
t3 = "#AEAEB2"         # 弱文字
inp = "#F5F5F7"        # 输入框背景
inp_b = "rgba(0,0,0,0.08)"  # 输入框边框
err = "#FF3B30"        # 错误红
elev = "#FFFFFF"       # 弹出层
```

**深色模式 (D):**
```python
bg = "#1C1C1E"
bg2 = "#2C2C2E"
card = "#2C2C2E"
card_b = "rgba(255,255,255,0.06)"
acc = "#0A84FF"        # 深色模式蓝
t1 = "#F5F5F7"
t2 = "#8E8E93"
t3 = "#48484A"
inp = "#3A3A3C"
err = "#FF453A"
elev = "#3A3A3C"
```

### 4.2 排版规范
- 标题：13-16px，font-weight:600-700
- 正文：12-13px
- 辅助文字：10-11px
- 字体族：`'Helvetica Neue', 'PingFang SC', sans-serif`
- 行高：line-height:165%（聊天气泡）
- 圆角：6px（小按钮）、8px（输入框/卡片）、10px（下拉菜单）、12px（大卡片/气泡）、16px（药丸按钮）
- 阴影：`0 4px 28px rgba(0,0,0,0.03)` 极淡

### 4.3 交互规范
- 按钮 hover：浅蓝色背景 `acc_l = rgba(0,113,227,0.12)`
- 按钮 pressed：强调色背景 + 白字
- 输入框 focus：边框变蓝 `acc`
- 过渡：深浅模式切换用 `windowOpacity` 动画 150ms
- 拖放反馈：蓝色光晕 `QGraphicsDropShadowEffect`
- 禁止使用 emoji 除非用户要求

### 4.4 布局原则
- 绝对不允许页面跳动/闪烁
- 固定高度容器包裹动态内容（如进度卡片）
- QStackedWidget 切换不改变布局尺寸
- 启动时固定显示翻译页，不记忆"关于"页

---

## 五、核心架构

### 5.1 应用入口
```python
# main_window.py 底部
def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = Pdf2zhApp(sys.argv); app.setStyle("Fusion")
    w = MainWindow(); w.show()
    sys.exit(app.exec_())
```

### 5.2 页面结构
```
MainWindow (QMainWindow)
├── Sidebar (导航栏)
│   ├── 🌐 翻译
│   ├── 📖 阅读
│   ├── 🔧 设置
│   └── 💡 关于
│
└── QStackedWidget (页面切换)
    ├── TranslatePage (index 0) — 翻译页
    ├── ReaderPage (index 1) — 阅读页
    ├── SettingsPage (index 2) — 设置页
    └── AboutPage (index 3) — 关于页
```

### 5.3 翻译页结构
```
TranslatePage
├── DropArea (拖放区 + 文件列表)
│   ├── 拖放目标
│   ├── 文件列表 (支持多文件批量)
│   └── Zotero 提示条
│
├── 参数区
│   ├── 源语言 / 目标语言 ComboBox
│   ├── 翻译服务 ComboBox
│   ├── 页码范围
│   ├── 输出格式
│   ├── 线程数
│   └── 分块翻译设置
│
├── 进度卡片 (固定高度容器，不跳动)
│   ├── 进度条 + 百分比
│   ├── 状态文字
│   └── 关怀消息
│
└── 开始翻译 / 停止按钮
```

### 5.4 阅读页结构
```
ReaderPage (QHBoxLayout)
├── 左侧面板 (历史 + 详情)
│   ├── 分组栏 (ScrollArea + 固定"＋"按钮)
│   ├── 历史列表 (QListWidget)
│   └── 详情面板
│
└── 右侧 (QSplitter)
    ├── 缩略图面板 (可折叠)
    ├── PreviewPage (PDF 预览)
    │   ├── 工具栏 (Dual/Mono/SideBySide/连续)
    │   ├── 单页模式 (QScrollArea)
    │   ├── 连续模式 (QScrollArea + 懒加载)
    │   └── 高亮标注系统
    └── QAPanelWidget (AI 助手，可折叠)
```

### 5.5 AI 助手结构
```
QAPanelWidget
├── 头部 (标题 + 服务状态 + 清空 + ⚙设置)
├── 快捷操作栏 (3 个等宽药丸按钮)
├── 聊天区 (QScrollArea + 气泡)
└── 输入区 (文本框 + 发送按钮)

Prompt 库 (⚙ 弹窗):
├── 8 个内置预设 (不可删除)
├── 自定义 prompt (可增删)
├── 勾选 ≤3 个显示在快捷栏
├── 导入 .txt/.md/.json
└── 恢复默认
```

---

## 六、关键技术细节

### 6.1 PyQt5 信号槽防崩溃
**所有信号处理函数必须 try/except 包裹。** PyQt5 如果槽函数抛异常会调用 C++ abort()，导致闪退且无 traceback。

```python
def _on_done(self, result):
    try:
        # 业务逻辑
    except Exception:
        pass
```

### 6.2 QThread Worker 信号竞态
启动新 worker 前必须断开旧 worker 的所有信号：

```python
def _stop_workers(self):
    for attr in ('_worker', '_summary_worker'):
        w = getattr(self, attr, None)
        if w:
            for sig in ('chunk', 'result', 'finished', 'error'):
                try: getattr(w, sig).disconnect()
                except: pass
            setattr(self, attr, None)
            w.quit()
```

### 6.3 QComboBox 焦点虚线框
macOS 上 QComboBox 有系统画的焦点虚线框，用 CSS 无法去除：

```python
def _fix_combo_popup(combo):
    combo.setAttribute(Qt.WA_MacShowFocusRect, False)
```

在 MainWindow.__init__ 结尾对所有 combo 调用。

### 6.4 资源路径兼容
开发环境和 PyInstaller 打包后的路径不同：

```python
def _res(*parts):
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, *parts)
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), *parts)
```

### 6.5 Zotero 拖拽（macOS 特有）
macOS 跨进程拖拽会丢失自定义 MIME type（`zotero/item`）。Mac 端用 4 层 fallback：
1. file URL（最可靠）
2. text/plain 中的 file:// 路径
3. zotero/item MIME（Mac 上跨进程为空）
4. text/plain 标题模糊匹配（Mac only hack）

### 6.6 SQLite 只读访问 Zotero 数据库
Zotero 运行时锁数据库，用 immutable 模式绕过：
```python
conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
```

### 6.7 小黑猫彩蛋
- `_NekoCat(QWidget)` — QPainter 手绘，无图片资源
- 行为：60% 走路、20% 坐下、20% 快跑
- 交互：hover 加速、单击喵叫、双击消失
- 频率：启动 3 秒出现，之后每 20 分钟出现一次

### 6.8 翻译完成通知
```python
subprocess.Popen(["osascript", "-e",
    f'display notification "{msg}" with title "pdf2zh" sound name "Glass"'])
```

---

## 七、打包步骤

### 7.1 打包命令
```bash
cd mac/
python3 -m PyInstaller pdf2zh.spec --noconfirm
```

### 7.2 产物
```
dist/pdf2zh.app    # 可直接运行的 macOS 应用
```

### 7.3 分发
```bash
# 压缩
zip -r pdf2zh-desktop-mac-v2.2.0.zip dist/pdf2zh.app

# 上传到 GitHub Release
gh release create v2.2.0 pdf2zh-desktop-mac-v2.2.0.zip \
    --title "v2.2.0" --notes "更新日志..."
```

### 7.4 常见打包坑

| 坑 | 原因 | 解决 |
|----|------|------|
| `ModuleNotFoundError: pdf2zh` | hiddenimports 不全 | 在 spec 里加 `collect_all('pdf2zh')` |
| `onnxruntime` 找不到 | 二进制不兼容 | 确保 pip 安装的是 arm64 版 |
| `babeldoc` 可选 | 不是所有环境有 | try/except 包裹 collect_all |
| 启动闪退无报错 | 信号槽异常 | 从终端运行 .app/Contents/MacOS/pdf2zh 看 traceback |
| 字体渲染异常 | `Monospace` 字体缺失 | 忽略警告，不影响功能 |

---

## 八、运行时配置文件

| 文件 | 路径 | 用途 |
|------|------|------|
| 用户配置 | `~/pdf2zh_gui_config.json` | 翻译设置、API Key、主题 |
| 翻译历史 | `~/pdf2zh_history.json` | 历史记录 + 分组 + 标签 |
| 术语库 | `~/pdf2zh_glossary.json` | 当前激活的术语库 |
| 提示词 | `~/pdf2zh_prompts.json` | 用户自定义提示词 |
| AI prompt 库 | 存在 config 中 `ai_prompt_library` | 快捷操作库 |
| 输出目录 | `~/Documents/pdf2zh_files/` | 翻译输出 |

---

## 九、Git 协作规范

### 绝对禁止
- `git push --force` — 会删掉其他同事的提交
- 如果 push 被拒绝，先 `git pull --rebase` 再 push

### 仓库结构
```
AaronGIG/pdf2zh-desktop (共享仓库)
├── mac/          # Mac 端代码（本文档覆盖）
├── core/         # Win 端共享核心
├── config/       # Win 端配置
├── assets/       # Win 端资源
└── *.bat/*.vbs   # Win 端启动脚本
```

### 提交规范
- Mac 端只改 `mac/` 目录下的文件
- 不动 Win 端文件、不动根目录 README
- commit message 格式：`v2.2.0 (Mac): 简要描述`

---

## 十、验证清单

打包完成后逐项测试：

- [ ] 启动 3 秒内无闪退，无页面跳动
- [ ] 翻译页默认显示，不闪到"关于"
- [ ] 拖入 PDF 有蓝色光晕反馈
- [ ] Google 翻译可正常翻译
- [ ] 翻译完成有系统通知 + 自动跳转阅读页
- [ ] 记住上次翻译设置（服务/语言/格式）
- [ ] AI 助手 ⚙ 弹窗正常显示 8 个预设
- [ ] 快捷操作栏 3 个药丸按钮正常
- [ ] 运行中点按钮不闪退（busy 保护）
- [ ] 深色/浅色模式切换无残留
- [ ] QComboBox 无焦点虚线框
- [ ] 分组栏右键菜单正常（重命名/删除/排序）
- [ ] "＋"按钮位置固定不动
- [ ] 历史双击打开预览
- [ ] QQ 群按钮弹出二维码弹窗
- [ ] 小黑猫 3 秒后出现走一趟
- [ ] 连续启动退出 10 次无崩溃

---

**以上就是完整复刻所需的全部信息。源码在仓库 `mac/` 目录，按本文档的环境准备 + 打包步骤操作即可。**

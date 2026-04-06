# Zotero 联动功能 — Windows 版技术移植指南

> 作者：Mac 版开发者
> 目标读者：Win 版同事
> 日期：2026-04-06
> 状态：Mac 版已完成全部功能并稳定运行

---

## 一、功能概述

### 用户使用流程
```
从 Zotero 拖论文到 pdf2zh → 翻译 → 译文自动保存回 Zotero 原位
```

### 核心原则
| 原则 | 说明 |
|------|------|
| **自动识别** | app 自动检测文件是否来自 Zotero，不需要用户手动切换模式 |
| **不存两份** | Zotero 来源的 PDF，译文只放回原位，可选是否保留 app 输出目录的副本 |
| **格式可选** | 用户在设置页选择放回哪些格式（dual / mono / side_by_side），支持任意组合 |
| **插件增强** | 可选安装 Zotero 插件 `pdf2zh Connector`，实现译文自动关联为 Zotero 附件 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    main_window.py                        │
│                                                         │
│  TranslatePage                                          │
│  ├─ DropArea.dropEvent()     ← 拖拽入口                │
│  │   ├─ 解析 file URL       ← Finder/Explorer 拖文件   │
│  │   ├─ 解析 zotero/item    ← Zotero 自定义 MIME       │
│  │   ├─ 解析 text/plain     ← macOS 跨进程 fallback    │
│  │   └─ _check_zotero_source()  ← 显示/隐藏提示条     │
│  │                                                      │
│  ├─ _on_file_done()         ← 单文件翻译完成            │
│  │   └─ _zotero_writeback() ← 回写逻辑核心             │
│  │       ├─ shutil.copy2()  ← 复制译文到 Zotero 目录   │
│  │       └─ zotero_auto_link() ← HTTP→插件→关联附件    │
│  │                                                      │
│  └─ SettingsPage            ← Zotero 设置卡片           │
│      ├─ zotero_output_modes ← ["side_by_side"] 默认     │
│      └─ zotero_keep_copy    ← True 默认                 │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                  translate_worker.py                     │
│                                                         │
│  detect_zotero_source(path)      ← 路径检测             │
│  get_zotero_item_key(path)       ← 提取 8 位 key       │
│  zotero_auto_link(key, path, t)  ← HTTP POST 关联附件  │
│  zotero_plugin_installed()       ← ping 检测插件        │
│  resolve_zotero_items(ids)       ← SQLite 解析条目      │
│  resolve_zotero_collection(id)   ← SQLite 解析集合      │
│  resolve_zotero_by_title(text)   ← 标题模糊匹配        │
│  _find_zotero_data_dir()         ← 定位数据目录         │
│  _resolve_zotero_path(...)       ← 路径拼接             │
│                                                         │
├─────────────────────────────────────────────────────────┤
│              assets/zotero-plugin/                       │
│                                                         │
│  manifest.json    ← Zotero 插件清单                     │
│  bootstrap.js     ← 注册 HTTP 端点                      │
│    POST /pdf2zh/attach  ← 添加附件                      │
│    GET  /pdf2zh/ping    ← 健康检查                      │
└─────────────────────────────────────────────────────────┘
```

---

## 三、需要实现的模块（按优先级排列）

### 3.1 路径检测（必须，最先做）

```python
import re

def detect_zotero_source(file_path: str):
    """检测文件是否来自 Zotero storage，返回 Zotero 子文件夹路径或 None

    匹配模式：
      .../Zotero/storage/XXXXXXXX/...
    """
    m = re.search(r'[/\\][Zz]otero[/\\]storage[/\\][A-Za-z0-9]{8}[/\\]', file_path)
    if m:
        return file_path[:m.end()]
    return None

def get_zotero_item_key(file_path: str):
    """从 Zotero 路径提取 8 位 item key"""
    m = re.search(r'[/\\][Zz]otero[/\\]storage[/\\]([A-Za-z0-9]{8})[/\\]', file_path)
    return m.group(1) if m else None
```

**⚠️ Win 特有注意点：**
- Windows 路径用 `\`，正则里 `[/\\]` 已经兼容了
- Windows 默认 Zotero 数据目录在 `C:\Users\<user>\Zotero\`
- 也可能在 `%APPDATA%\Zotero\Zotero\Profiles\` 里的 `prefs.js` 指定了自定义位置

### 3.2 定位 Zotero 数据目录（必须）

Mac 版的实现：

```python
def _find_zotero_data_dir():
    candidates = [os.path.expanduser("~/Zotero")]
    if platform.system() == "Darwin":
        candidates.append(os.path.expanduser("~/Library/Application Support/Zotero"))
    for d in candidates:
        if os.path.isfile(os.path.join(d, "zotero.sqlite")):
            return d
    return None
```

**Win 版需要改为：**

```python
def _find_zotero_data_dir():
    candidates = [os.path.expanduser("~/Zotero")]
    if platform.system() == "Windows":
        # Windows 常见位置
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            candidates.append(os.path.join(appdata, "Zotero", "Zotero"))
        # 用户可能自定义了数据目录
        candidates.append(os.path.expanduser("~\\Zotero"))
    for d in candidates:
        if os.path.isfile(os.path.join(d, "zotero.sqlite")):
            return d
    return None
```

### 3.3 SQLite 只读访问（必须）

Mac 和 Win 共通的坑：**Zotero 运行时数据库被锁**。

解决方案：用 `immutable=1` 模式打开，绕过锁：

```python
conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
```

**⚠️ Windows 特有坑：**
- Windows 路径含 `\` 和 `:` (如 `C:\Users\`)，直接拼 URI 会出错
- **必须**用 `pathlib.Path(db_path).as_uri()` 或手动转义：

```python
import pathlib
db_uri = pathlib.Path(db_path).as_uri() + "?mode=ro&immutable=1"
conn = sqlite3.connect(db_uri, uri=True)
```

或者用 `urllib.parse.quote`：
```python
from urllib.parse import quote
safe_path = quote(db_path.replace("\\", "/"), safe="/:")
db_uri = f"file:///{safe_path}?mode=ro&immutable=1"
```

### 3.4 翻译完成回写（必须）

```python
def _zotero_writeback(self, file_path, output_files):
    """把译文复制回 Zotero 原位 + 尝试自动关联附件"""
    import shutil
    zotero_dir = detect_zotero_source(file_path)
    if not zotero_dir:
        return
    cfg = UserConfigManager.load()
    modes = cfg.get("zotero_output_modes", ["side_by_side"])
    keep_copy = cfg.get("zotero_keep_copy", True)
    item_key = get_zotero_item_key(file_path)

    for mode in modes:
        src = output_files.get(mode)
        if not src or not os.path.exists(src):
            continue
        dst = os.path.join(zotero_dir, os.path.basename(src))
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
            if not keep_copy:
                try:
                    os.remove(src)
                except OSError:
                    pass
        # 尝试通过 pdf2zh Connector 插件自动关联附件
        if item_key:
            mode_label = {"side_by_side": "并排", "dual": "双语", "mono": "译文"}.get(mode, mode)
            zotero_auto_link(item_key, dst, f"翻译 ({mode_label})")
```

**⚠️ Win 特有注意点：**
- `shutil.copy2` 在 Windows 上可能因文件被占用而失败（Zotero 可能正在读取 PDF）
- 建议加重试机制：
```python
import time
for attempt in range(3):
    try:
        shutil.copy2(src, dst)
        break
    except PermissionError:
        if attempt < 2:
            time.sleep(0.5)
        else:
            raise
```
- Windows 上 `os.path.abspath` 不做大小写统一，比较路径时考虑 `.lower()`

### 3.5 Zotero 插件通信（增强功能，可后做）

```python
def zotero_auto_link(item_key, file_path, title):
    """通过 pdf2zh-connector 插件将译文自动添加为 Zotero 附件"""
    import urllib.request
    import json
    payload = json.dumps({
        "itemKey": item_key,
        "filePath": file_path,  # ← Win 上必须是绝对路径
        "title": title
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:23119/pdf2zh/attach",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
    return data
```

**⚠️ Win 特有注意点：**
- `file_path` 必须是**绝对路径**，Zotero 的 `importFromFile` 需要它
- Windows 路径 `C:\Users\...` 直接传 JSON 没问题，`json.dumps` 会自动处理 `\` 转义
- Zotero 端口 23119 是固定的（Zotero Connector 标准端口）
- 防火墙可能阻断 localhost:23119 → 如果 `zotero_plugin_installed()` 返回 False，UI 上提示用户检查防火墙

### 3.6 拖拽识别（必须，但 Win 比 Mac 简单）

Mac 版遇到的**最大坑**在这里，Win 版反而更简单。

**Mac 的痛点：**
macOS 跨进程拖拽时，Zotero 的自定义 MIME type (`zotero/item`, `zotero/collection`) 无法跨进程传递。只能拿到 `text/plain`（引用文本）和文件 URL。所以 Mac 版不得不写了 `resolve_zotero_by_title()` 做标题模糊匹配，非常 hacky。

**Win 的优势：**
Windows 的 OLE 拖拽协议支持跨进程自定义 MIME，Zotero 拖出的条目可以直接通过 `zotero/item` MIME 获取 item ID 列表。

```python
def dropEvent(self, event):
    md = event.mimeData()

    # 方式 1：标准 file URL（从 Zotero 拖 PDF 附件，或从 Explorer 拖文件）
    if md.hasUrls():
        fs = [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
        # 过滤 PDF
        fs = [f for f in fs if f.lower().endswith('.pdf')]

    # 方式 2：Zotero 自定义 MIME（Win 上可以跨进程获取）
    if not fs and md.hasFormat("zotero/item"):
        zot_data = md.data("zotero/item")
        # 解析为 item ID 列表 → 查 SQLite 获取 PDF 路径
        item_ids = parse_zotero_item_data(zot_data)
        fs = resolve_zotero_items(item_ids)

    # 方式 3：Zotero 集合拖拽
    if not fs and md.hasFormat("zotero/collection"):
        zot_coll = md.data("zotero/collection")
        collection_id = parse_zotero_collection_data(zot_coll)
        fs = resolve_zotero_collection(collection_id)
```

**⚠️ Win 特有注意点：**
- `zotero/item` MIME 的数据格式是 JSON bytes，内容为 `{"libraryID": 1, "itemIDs": [123, 456]}`
- 需要验证 Win 上 PyQt5 的 `QMimeData.data("zotero/item")` 是否能正确接收
- 如果不行，fallback 到方式 1（file URL）即可，Zotero 拖 PDF 附件时会带文件路径
- **不需要** Mac 版那套 `resolve_zotero_by_title()` 标题匹配 hack

### 3.7 UI 部分

#### 提示条（翻译页顶部）
```python
self._zotero_hint = QLabel("📚 Zotero 文献 · 译文自动保存回原位")
self._zotero_hint.setStyleSheet(
    "background:rgba(0,122,255,0.08); color:#007AFF; "
    "border-radius:6px; padding:6px 12px; font-size:11px;")
self._zotero_hint.setVisible(False)
```

文件添加时调用 `_check_zotero_source()` 显示/隐藏。

#### 设置页 Zotero 卡片
```python
# 三个 CheckBox + 一个保留副本选项
self._zot_sbs = QCheckBox("左右并排 (Side by Side)")   # 默认勾选
self._zot_dual = QCheckBox("双语对照 (Dual)")
self._zot_mono = QCheckBox("仅翻译 (Mono)")
self._zot_keep_copy = QCheckBox("同时保留输出目录副本")  # 默认勾选
```

配置持久化到 `UserConfigManager`：
```json
{
    "zotero_output_modes": ["side_by_side"],
    "zotero_keep_copy": true
}
```

---

## 四、Zotero 插件（assets/zotero-plugin/）

这个插件是**可选的**，不安装也能用基本功能（文件回写）。安装后增加"自动关联附件"能力。

### 文件结构
```
assets/zotero-plugin/
├── manifest.json      ← 插件元数据
└── bootstrap.js       ← 注册两个 HTTP 端点
```

### 插件做了什么
1. `POST /pdf2zh/attach` — 接收 `{itemKey, filePath, title}`，调用 `Zotero.Attachments.importFromFile` 把译文添加为附件
2. `GET /pdf2zh/ping` — 健康检查，返回 `{"status": "ok"}`

### 安装方式
Zotero → 工具 → 附加组件 → 从文件安装 → 选择 `zotero-plugin` 目录下的 `.xpi` 文件（或直接拖入）

**Win 版不需要改插件代码**，`bootstrap.js` 是纯 Zotero API，跨平台通用。只需确保打包时 `assets/zotero-plugin/` 目录随 app 一起分发。

---

## 五、踩过的坑 & 经验总结

### 坑 1：macOS 跨进程 MIME 丢失（Win 不受影响）
macOS 的安全沙箱会剥离非标准 MIME type。从 Zotero 拖条目到 pdf2zh 时，`zotero/item` MIME 为空，只有 `text/plain` 可用。Mac 版不得不写了 `resolve_zotero_by_title()` 做标题模糊匹配。

**Win 版：不需要这个 hack。** Windows OLE 拖拽支持自定义 MIME 跨进程传递。但建议还是保留 file URL 作为 fallback。

### 坑 2：SQLite 数据库锁
Zotero 运行时会锁定 `zotero.sqlite`。普通的 `sqlite3.connect()` 会报 `database is locked`。

**解决方案：** `immutable=1` 参数（见 3.3 节）。这告诉 SQLite 文件不会被修改，跳过所有锁检查。代价是看不到 Zotero 最新的未提交更改，但对我们的只读查询完全够用。

### 坑 3：Zotero storage 路径格式
Zotero 数据库里 `itemAttachments.path` 的值是 `storage:filename.pdf`，**不是**完整路径。需要拼接：

```python
actual_path = os.path.join(zotero_data_dir, "storage", item_key, filename)
```

其中 `item_key` 是 8 位字母数字（如 `KSII2GGN`），`filename` 需要去掉 `storage:` 前缀。

### 坑 4：一个父条目可能有多个 PDF 附件
用户可能给一个 Zotero 条目附加了多个 PDF（原文 + 补充材料等）。我们只想翻译原始论文，不想翻译之前的翻译件。

**解决方案：** `ORDER BY ia.itemID ASC LIMIT 1` — 只取最早添加的 PDF 附件。

### 坑 5：拖拽多个条目 vs 拖拽多个文件
- 从 Zotero 拖 1 个条目：可能给 1 个 file URL + zotero/item MIME
- 从 Zotero 拖多个条目：file URL 可能只含第一个文件，其他文件需要通过 MIME 解析
- 从 Explorer 拖多个 PDF：只有 file URL，没有 zotero MIME

**建议：** 先试 zotero/item MIME，拿到 item ID 列表后批量查 SQLite。如果 MIME 为空，fallback 到 file URL。

### 坑 6：PyQt5 信号槽中的异常导致闪退
PyQt5 的信号槽（signal/slot）如果抛出未捕获的异常，会直接调用 C++ 的 `abort()`，导致应用闪退，**没有任何 Python traceback**。

**解决方案：** 所有 signal handler 都用 `try/except` 包裹：
```python
def _on_done(self, result):
    try:
        # ... 业务逻辑 ...
        self._zotero_writeback(fp, output_files)
    except Exception:
        pass  # 或者 log
```

### 坑 7：QThread worker 的信号竞态
翻译 worker 在后台线程运行。如果用户快速操作（连点按钮、切换文件），旧 worker 的信号可能发到已被删除的 widget 上 → 闪退。

**解决方案：**
```python
def _stop_workers(self):
    for attr in ('_worker', '_summary_worker'):
        w = getattr(self, attr, None)
        if w:
            for sig in ('chunk', 'result', 'finished', 'error'):
                try:
                    getattr(w, sig).disconnect()
                except Exception:
                    pass
            setattr(self, attr, None)
            w.quit()
```

在启动新 worker 前先调用 `_stop_workers()`。

---

## 六、推荐实现顺序

```
Phase 1（核心功能，~2天）
├─ detect_zotero_source()         ← 路径检测
├─ _find_zotero_data_dir()        ← Win 路径适配
├─ _zotero_writeback()            ← 翻译完成回写
├─ _zotero_hint UI 提示条         ← 翻译页
└─ 设置页 Zotero 卡片             ← 3 个 CheckBox

Phase 2（拖拽增强，~1天）
├─ dropEvent 解析 zotero/item MIME
├─ resolve_zotero_items()          ← SQLite 查询
└─ resolve_zotero_collection()     ← SQLite 查询

Phase 3（插件联动，~0.5天）
├─ zotero_auto_link()              ← HTTP POST
├─ zotero_plugin_installed()       ← ping 检测
└─ 打包 zotero-plugin 到 assets/
```

**Phase 1 完成后就能覆盖 80% 的用户场景。** 用户从 Zotero 里打开 PDF → 拖进 app → 翻译 → 译文自动回写。Phase 2 和 3 是锦上添花。

---

## 七、配置项汇总

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `zotero_output_modes` | `list[str]` | `["side_by_side"]` | 回写到 Zotero 的译文格式 |
| `zotero_keep_copy` | `bool` | `True` | 是否同时保留 app 输出目录副本 |

---

## 八、测试验证清单

- [ ] 从 Explorer 拖 Zotero storage 目录下的 PDF → 识别为 Zotero 来源，显示提示条
- [ ] 翻译完成 → 译文出现在 Zotero 原目录下
- [ ] 在 Zotero 中刷新 → 能看到新的 PDF 附件
- [ ] 设置页勾选 Dual + Mono → 翻译后原目录出现两个译文
- [ ] 取消勾选"保留副本" → 翻译后 app 输出目录无副本
- [ ] 拖非 Zotero 的 PDF → 不显示提示条，走正常流程
- [ ] Zotero 未运行时翻译 → 文件回写正常（不依赖插件）
- [ ] 安装 pdf2zh Connector 插件 → 译文自动关联为 Zotero 附件
- [ ] 快速连续拖入多个文件 → 不闪退，批量翻译 + 批量回写

---

## 九、文件清单

Mac 版中与 Zotero 相关的所有文件和代码位置：

| 文件 | 位置/函数 | 说明 |
|------|----------|------|
| `ui/translate_worker.py` | `detect_zotero_source()` (L59) | 路径检测 |
| `ui/translate_worker.py` | `get_zotero_item_key()` (L72) | 提取 item key |
| `ui/translate_worker.py` | `zotero_auto_link()` (L78) | HTTP 关联附件 |
| `ui/translate_worker.py` | `zotero_plugin_installed()` (L110) | ping 检测 |
| `ui/translate_worker.py` | `_find_zotero_data_dir()` (L121) | 定位数据目录 |
| `ui/translate_worker.py` | `resolve_zotero_items()` (L134) | SQLite 解析条目 |
| `ui/translate_worker.py` | `resolve_zotero_collection()` (L190) | SQLite 解析集合 |
| `ui/translate_worker.py` | `resolve_zotero_by_title()` (L264) | 标题匹配 (**Mac only，Win 不需要**) |
| `ui/main_window.py` | `DropArea.dropEvent()` (~L600) | 拖拽入口 |
| `ui/main_window.py` | `TranslatePage._check_zotero_source()` (L3010) | 提示条控制 |
| `ui/main_window.py` | `TranslatePage._zotero_writeback()` (L3197) | 回写核心 |
| `ui/main_window.py` | `SettingsPage` (~L4230) | Zotero 设置卡片 |
| `assets/zotero-plugin/manifest.json` | — | Zotero 插件清单 |
| `assets/zotero-plugin/bootstrap.js` | — | Zotero 插件代码 |

> 行号基于 2026-04-06 的 Mac 版代码，可能随后续更新变化。建议用函数名搜索定位。

---

**有问题随时在仓库 issue 里问我。祝开发顺利！**

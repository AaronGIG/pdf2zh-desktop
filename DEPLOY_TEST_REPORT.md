# pdf2zh-desktop 部署测试报告

**测试日期**: 2026-03-21
**测试环境**: Windows 11 Home China (10.0.26200)，全新机器，屏幕物理分辨率 2880x1800 (DPR=2.0)
**部署方式**: `git clone` 从 GitHub 仓库
**嵌入式 Python**: 3.12.9（core/runtime/python.exe）
**仓库地址**: https://github.com/AaronGIG/pdf2zh-desktop

---

## 一、部署流程

```bash
cd d:\Soft
git clone https://github.com/AaronGIG/pdf2zh-desktop.git
```

- LFS 文件随 clone 自动拉取，无需额外 `git lfs pull`
- 仓库约 542 MiB / 23169 个文件 / 2352 个 LFS 对象
- 克隆完成后即可使用，无需 install.bat

---

## 二、发现的问题与修复

### [致命] 问题 1：pdf2zh.vbs 双击永远不弹出窗口 ✅ 已修复

**现象**:
双击 `pdf2zh.vbs` 后，`pythonw.exe` 进程正常启动，日志显示"GUI 窗口已显示"，但屏幕上**永远看不到窗口**。反复双击只会创建多个不可见的 pythonw.exe 进程。

**根因**:
`shell.Run cmd, 0, False` 中第二个参数 `0` 表示 **`SW_HIDE`（隐藏窗口）**。Windows 会将 `STARTUPINFO.wShowWindow` 设为 `SW_HIDE`，**进程内第一次 `ShowWindow` 调用被覆盖为隐藏**，PyQt5 的 `window.show()` 实际被强制改为隐藏操作。`pythonw.exe` 本身无控制台，用 `SW_HIDE` 毫无意义。

**修复**: `shell.Run cmd, 0, False` → `shell.Run cmd, 1, False`

---

### [严重] 问题 2：PyQt5 与 OnnxRuntime DLL 冲突 — AI 布局检测失效 ✅ 已修复

**现象**:
即使 VC++ Redistributable 已安装（注册表验证 v14.44.35211 存在），OnnxRuntime 仍报错 `Microsoft Visual C++ Redistributable is not installed`。

**根因**:
**PyQt5 导入时会修改 Windows DLL 搜索路径**，导致 OnnxRuntime 的 `onnxruntime_pybind11_state.pyd` 无法找到 VC++ DLL。

**修复**:
在 `_launcher.py` 中添加 `preload_onnxruntime()`，**在任何 PyQt5 导入之前**通过 `os.add_dll_directory()` 注册 DLL 路径并预加载 OnnxRuntime。

**验证**: 修复后 OnnxRuntime 预加载成功，翻译时 AI 布局检测生效，排版质量显著提升。

---

### [严重] 问题 3：pythonw.exe 下翻译时 tqdm 崩溃 ✅ 已修复

**现象**:
通过 `pdf2zh.vbs` 启动后翻译报错：`AttributeError: 'NoneType' object has no attribute 'write'`

**根因**:
`pythonw.exe` 没有控制台，`sys.stdout/stderr` 均为 `None`，`tqdm` 写入 `None.write()` 时崩溃。

**修复**:
在 `_launcher.py` 最顶部重定向：

```python
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
```

---

### [严重] 问题 4：窗口位置可能跑到屏幕外 ✅ 已修复

**修复**: 添加 `ensure_window_visible()` 函数，启动时强制居中显示，窗口大小不超过屏幕可用区域。

---

### [严重] 问题 5：bat 启动脚本绕过了 _launcher.py 的修复 ✅ 已修复

**修复**: `run_desktop.bat` 和 `run_desktop_smart.bat` 的启动命令统一改为调用 `_launcher.py`。

---

### [中等] 问题 6：VC++ 自动安装逻辑 ✅ 已处理

`pdf2zh.vbs` 通过注册表检测 VC++ 是否安装，未安装时弹窗询问。`_launcher.py` 的 `preload_onnxruntime()` 做了 try/except：VC++ 缺失时 AI 布局检测降级，基础翻译不受影响。

---

### [低] 问题 7：多个启动入口

| 文件 | 黑窗口 | VC++检测 | 定位 |
|------|--------|---------|------|
| `pdf2zh.vbs` | 无 | 有 | ⭐ 用户入口 |
| `run_desktop.bat` | 有 | 无 | 🔧 快速调试 |
| `run_desktop_smart.bat` | 有（带诊断） | 无 | 🔧 详细调试 |

---

### [低] 问题 8：`run_desktop_smart.bat` AI 模型包检测路径错误 ✅ 已修复

**原问题**: 检查 `models\layout` 目录，始终提示未安装。实际 AI 模型由 babeldoc 管理，首次翻译时自动下载到用户缓存目录。

**修复**: 改为检测 VC++ 运行库安装状态（AI 布局检测的实际前提条件）。

---

### [低] 问题 9：控制台输出 "not in git repo"

来自上游 pdf2zh 库的版本检测逻辑，仅在 bat 调试模式下可见，`pdf2zh.vbs` 正常启动不显示。不修改。

---

## 三、UI/UX 反馈

### 反馈 1：批量模式文件列表字体偏小

**位置**: `gui_pyqt5.py` 约第 1165 行 `QListWidget`

**建议**: 设置更大的字体或行高。

### 反馈 2：批量模式缺少分页/分块翻译功能

**需求**: 翻译大文档（1000+ 页）时，支持按每 N 页分块翻译，自动拼接。

### 反馈 3：不要添加 AA_EnableHighDpiScaling

测试中尝试添加过 `QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)`，结果窗口变得过大且 PDF 预览模糊。原始的渲染方式显示效果更精致。**不要加这个属性。**

---

## 四、修改文件清单

| 文件 | 关键改动 | 解决问题 |
|------|----------|----------|
| `pdf2zh.vbs` | `shell.Run cmd, 0` → `1` + VC++ 自动检测 | 窗口不弹出 + VC++ 引导 |
| `_launcher.py` | stdout/stderr 重定向 + OnnxRuntime 预加载 + 窗口居中 | tqdm 崩溃 + DLL 冲突 + 窗口位置 |
| `run_desktop.bat` | 启动命令改为 `_launcher.py` | 绕过修复 |
| `run_desktop_smart.bat` | 启动命令改为 `_launcher.py` + 修正 AI 模型检测 | 绕过修复 + 误导提示 |

---

## 五、部署体验总结

| 项目 | 修复前 | 修复后 |
|------|--------|--------|
| VBS 双击启动 | 窗口永远不弹出 | 正常弹出并置前 |
| VBS 下翻译 | tqdm 崩溃 | 正常翻译 |
| AI 布局检测 | 始终失败（DLL 冲突） | 正常工作 |
| 窗口位置 | 可能跑到屏幕外 | 居中显示 |
| bat 启动 | 绕过所有修复 | 统一走 _launcher.py |
| 翻译排版质量 | 差（无 AI 布局） | 好（AI 布局生效） |
| 一步部署体验 | 不可用 | git clone 后双击即用 |

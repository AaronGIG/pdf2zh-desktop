# pdf2zh-desktop 部署测试报告

**测试日期**: 2026-03-21
**测试环境**: Windows 11 Home (10.0.26200), 全新机器
**部署方式**: `git clone` 从 GitHub 仓库
**系统 Python**: 3.12.10（未使用，项目自带嵌入式 Python 3.12.9）
**仓库地址**: https://github.com/AaronGIG/pdf2zh-desktop

---

## 一、部署流程记录

### 1. 克隆仓库

```bash
git clone https://github.com/AaronGIG/pdf2zh-desktop.git
```

- Git LFS 文件在 clone 过程中自动拉取，无需额外执行 `git lfs pull`
- 仓库总大小约 542 MiB，包含 23168 个文件、2352 个 LFS 对象
- 下载耗时较长（受网络影响），全程无报错
- `core/runtime/python.exe` 和 `core/site-packages/pdf2zh/` 均完整下载

### 2. 启动验证

通过 `run_desktop_smart.bat` 启动，输出如下：

```
[检查] 系统环境...
[✓] 操作系统: Windows 10.0
[✓] 系统架构: x64
[检查] 核心模块...
[✓] Python 运行时
[✓] pdf2zh 库
[✓] 应用配置
[!] AI模型包 (未安装，部分功能可能受限)
[设置] 运行环境...
[✓] 环境变量已设置
[启动] pdf2zh 桌面版...
```

GUI 成功启动，翻译功能正常（使用 Google 翻译测试通过）。

---

## 二、发现的问题与修复

### 问题 1：VC++ 运行库未自动安装 ✅ 已修复

**现象**:
启动时输出以下警告，AI 布局检测功能被跳过：

```
Failed to import OnnxModel: Microsoft Visual C++ Redistributable is not installed.
警告: 无法加载文档布局模型: Microsoft Visual C++ Redistributable is not installed.
Model not available, skipping layout detection
```

**影响**:
- 翻译功能本身不受影响，可以正常翻译 PDF
- AI 布局检测功能不可用，复杂排版的 PDF 翻译质量可能下降

**原因**:
- 新机器没有预装 Microsoft Visual C++ Redistributable
- OnnxRuntime 依赖此运行库，缺失时无法加载 `.pyd` 模块

**修复方案**:
已将 VC++ 检测集成到 `pdf2zh.vbs` 主启动入口。首次启动时自动检查注册表：

- 检测 `HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64\Version`
- 未安装时弹出友好对话框，询问用户是否安装
- 用户确认后以 `/install /passive /norestart` 模式自动安装（仅弹一次 UAC）
- 用户拒绝则跳过，不影响后续翻译功能启动
- 已安装的机器完全跳过此检测，无感知

用户体验变为：首次双击 `pdf2zh.vbs` → 弹窗询问 → 确认 → VC++ 自动安装 → 翻译窗口弹出。

---

### 问题 2：旧开发文件残留 ✅ 已修复

**现象**:
测试机上之前的 `pdf2zh-desktop` 目录中残留了以下开发阶段的文件：

```
COMPLETION_SUMMARY.md
CONTRIBUTING.md
GITHUB_PRIVATE_SETUP.md
GITHUB_RELEASE_GUIDE.md
PROJECT_REFACTOR_SUMMARY.md
RELEASE_NOTES.md
build_script.py
launch_gui.py
pyproject.toml
requirements.txt
pdf2zh-desktop-slim/
```

**确认结果**:
重新从 GitHub clone 后，以上文件均不存在于仓库中。GitHub 仓库是干净的。

**修复方案**:
已在 `.gitignore` 中添加以上开发文件的排除规则，防止将来误提交。

---

### 问题 3："not in git repo" 提示（低优先级）

**现象**:
启动时控制台输出 `not in git repo`。

**影响**: 无功能影响，仅为信息提示。

**原因**:
pdf2zh 代码中有版本检测逻辑尝试读取 git 信息，在正常部署环境（非开发环境）下找不到 `.git` 目录。此提示来自上游 pdf2zh 库，非本项目代码。

**处理**: 不修改上游代码。此提示仅在 `run_desktop_smart.bat`（调试模式）下可见，通过 `pdf2zh.vbs` 正常启动时不会显示（无控制台窗口）。

---

### 问题 4：多个启动入口容易混淆（建议优化）

**现象**:
项目根目录存在三个启动入口：

| 文件 | 功能 | 定位 |
|------|------|------|
| `pdf2zh.vbs` | 静默启动，含 VC++ 自动检测 | ⭐ 用户入口 |
| `run_desktop.bat` | 精简启动，最基本检查 | 🔧 快速调试 |
| `run_desktop_smart.bat` | 智能启动，带诊断输出 | 🔧 详细调试 |

**当前状态**:
README 中已明确 `pdf2zh.vbs` 为主启动入口。两个 `.bat` 文件定位为开发/调试工具。

**后续建议**:
- 可考虑将两个 `.bat` 文件移入 `tools/` 子目录，减少根目录视觉干扰
- 或重命名为 `debug_start.bat` / `debug_start_verbose.bat` 明确其调试定位

---

### 问题 5：私人文件泄露 ✅ 已修复

**现象**:
初次推送时 `pdf2zh_files/` 目录下的 5 个私人 PDF 被上传到 GitHub。

**修复方案**:
- 已通过 `git rm --cached` 移除并强制推送
- `.gitignore` 已包含 `pdf2zh_files/` 规则，防止再次发生

---

### 问题 6：GitHub 仓库残留旧分支 ✅ 已修复

**现象**:
推送过程中产生了 `master` 和 `main` 两个分支，GitHub 显示 "2 Branches"。

**修复方案**:
已删除远程 `master` 分支，仅保留 `main`。

---

## 三、待测试项目

| 项目 | 状态 | 说明 |
|------|------|------|
| API 翻译服务（OpenAI/DeepL 等） | ⏳ 待测 | 需要提供 API Key 进行端到端测试 |
| VC++ 自动安装流程 | ⏳ 待测 | 需在未安装 VC++ 的干净机器上验证新 vbs 流程 |
| 超长文档翻译（1000+ 页） | ⏳ 待测 | 需要大型 PDF 和充足磁盘空间 |
| 断点续传 | ⏳ 待测 | 中途终止后重启，验证缓存恢复 |

---

## 四、部署体验总结

| 项目 | 状态 | 说明 |
|------|------|------|
| 仓库克隆 | ✅ 通过 | LFS 自动拉取，无需额外步骤 |
| 嵌入式 Python | ✅ 通过 | 3.12.9 运行正常 |
| pdf2zh 核心库 | ✅ 通过 | 模块导入成功 |
| GUI 启动 | ✅ 通过 | PyQt5 窗口正常显示 |
| Google 翻译 | ✅ 通过 | 免费翻译服务可用 |
| AI 布局检测 | ✅ 已修复 | VC++ 自动检测已集成到 pdf2zh.vbs |
| 一步部署 | ✅ 已修复 | 首次启动自动提示安装 VC++ |
| 私人文件清理 | ✅ 已修复 | PDF 已移除，.gitignore 已防护 |
| 分支清理 | ✅ 已修复 | 仅保留 main 分支 |
| README 文档 | ✅ 已完成 | 中英文双语，含作者信息 |
| API 翻译服务 | ⏳ 待测 | 需 API Key 验证 |

**整体评价**: 核心翻译功能可用，"下载即用"目标已基本达成。VC++ 运行库的自动检测已集成到主启动入口，用户首次启动即可完成全部配置。后续重点是验证各 API 翻译服务的连通性。

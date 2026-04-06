# 安装说明 / Installation Guide

---

## 手动安装

### 第一步：下载

**方式 A — Git（推荐，支持大文件）**

需要提前安装 [Git](https://git-scm.com) 和 [Git LFS](https://git-lfs.com)。

```bash
git lfs install
git clone https://github.com/AaronGIG/pdf2zh-desktop.git
cd pdf2zh-desktop
git lfs pull
```

**方式 B — 直接下载 ZIP**

在 GitHub 仓库页面点击 **Code → Download ZIP**，解压到任意位置。

> 注意：ZIP 下载不包含 Git LFS 内容，部分二进制文件可能缺失。推荐使用方式 A。

---

### 第二步：安装 Visual C++ 运行库

双击文件夹内的 **`VC_redist.x64.exe`** 安装，全程点"下一步"即可。

- 如已安装可跳过（安装程序会自动检测）
- 此步骤影响 AI 布局检测功能，不影响翻译本身

---

### 第三步：运行安装脚本（可选）

双击 **`install.bat`** 可自动完成：

- 检测系统环境
- 安装 VC++ 运行库（如未安装）
- 在桌面创建快捷方式

如果不想运行脚本，跳过此步直接启动也可以。

---

### 第四步：启动

双击 **`pdf2zh.vbs`**，翻译窗口直接弹出。

---

### 使用翻译服务

| 服务 | 是否需要 API Key | 获取地址 |
| --- | --- | --- |
| Google / Bing | 否，直接使用 | — |
| OpenAI | 是 | <https://platform.openai.com/api-keys> |
| DeepL | 是 | <https://www.deepl.com/pro-api> |
| DeepSeek | 是 | <https://platform.deepseek.com> |
| Gemini | 是 | <https://aistudio.google.com/apikey> |
| Ollama | 否，需本地部署 | <https://ollama.com> |

在界面的「翻译服务」下拉框选择服务后，会出现对应的 API Key 输入框，填入即可。

---

### 翻译结果在哪里

输出文件保存在程序目录的 `pdf2zh_files/` 文件夹内，包含：

- `文件名-mono.pdf` — 纯译文版
- `文件名-dual.pdf` — 双语对照版

---

### 常见问题

**Q：双击 pdf2zh.vbs 没有反应？**

查看 `logs/` 目录下最新的 `startup_*.log` 文件，把错误内容复制出来排查。

**Q：翻译到一半停了？**

检查磁盘剩余空间。重新点翻译，程序会从缓存继续，已翻译的部分不会重复调用 API。

**Q：提示 VC++ 相关错误？**

运行 `VC_redist.x64.exe` 或 `install.bat`。

**Q：需要完整的系统诊断？**

双击 `diagnostic.bat`，会生成一份诊断报告。

---

---

## AI 辅助安装教程

如果遇到安装或启动问题，可以直接把错误信息交给 AI 来解决。以下是具体做法。

---

### 推荐使用的 AI 工具

- [Claude](https://claude.ai)（推荐）
- [ChatGPT](https://chatgpt.com)
- 任何支持对话的 AI 助手

---

### 操作流程

#### 情况一：启动闪退或无反应

1. 打开 `logs/` 目录，找到最新的 `startup_*.log` 文件
2. 用记事本打开，全选复制
3. 打开 AI 对话框，粘贴以下内容：

```
我在运行 pdf2zh-desktop-win 时遇到了问题，以下是启动日志：

[粘贴日志内容]

请帮我分析原因并告诉我怎么解决。
```

---

#### 情况二：翻译报错

1. 翻译时如果弹出错误对话框，截图或复制错误文字
2. 发给 AI：

```
我在使用 pdf2zh-desktop-win 翻译 PDF 时出现了以下错误：

[粘贴错误信息]

我用的翻译服务是 [填写你用的服务，例如 OpenAI]，请帮我排查。
```

---

#### 情况三：需要配置某个翻译服务

直接问 AI：

```
我想在 pdf2zh-desktop-win 里使用 [服务名称，例如 DeepSeek] 翻译 PDF，
请告诉我怎么获取 API Key，以及在界面里怎么填写。
```

---

#### 情况四：运行 install.bat 出错

1. 双击 `diagnostic.bat`，等待生成报告
2. 报告会提示"是否复制到剪贴板"，选"是"
3. 粘贴给 AI：

```
我在 Windows 上运行 pdf2zh-desktop-win 的 install.bat 出现问题，
以下是系统诊断报告：

[粘贴报告内容]

请帮我分析并给出解决步骤。
```

---

### 提问技巧

- **描述你做了什么**：比如"双击了 pdf2zh.vbs"而不是"打开程序"
- **粘贴完整错误**：不要只说"出错了"，把错误文字或截图一起发
- **说明你的系统**：Windows 10 还是 Windows 11，有没有安装过 Python

---

如果 AI 给的方案解决了问题，欢迎到 [Issues](https://github.com/AaronGIG/pdf2zh-desktop/issues) 提交，帮助其他用户。

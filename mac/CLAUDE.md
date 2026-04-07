# 强制规则 — Mac 端 Claude 必须遵守

## 绝对禁止

1. **禁止 git push --force** — 任何情况下都不许用 --force 或 --force-with-lease 推送到共享仓库。唯一例外：修复之前错误的 force push，且必须先跟用户确认。

2. **禁止修改 Win 端代码** — 不许动根目录下的 Win 端文件，包括但不限于：
   - `*.bat`, `*.vbs`, `config/`, `core/`, `_launcher.py`, `install.bat`, `uninstall.bat`
   - 根目录的 `README.md`, `README_EN.md`, `INSTALL.md`
   - 任何不在 `mac/` 目录下的源码文件
   
3. **Mac 端代码只在 `mac/` 目录下改** — 提交时只 add `mac/` 下的文件。

## Git 操作规范

- push 前必须先 `git pull origin main`
- 有冲突用 `git merge` 解决，不用 rebase --force
- 不要 `git checkout` 覆盖整个工作目录（会丢失本地文件）
- 不要 `git reset --hard`（会丢失未提交的改动）

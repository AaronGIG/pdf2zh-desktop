"""pdf2zh 桌面版启动器 — 调用同目录的 core/runtime/pythonw.exe _launcher.py"""
import os, sys, subprocess

app_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
pythonw = os.path.join(app_dir, "core", "runtime", "pythonw.exe")
script = os.path.join(app_dir, "_launcher.py")

if not os.path.exists(pythonw):
    import ctypes
    ctypes.windll.user32.MessageBoxW(0,
        "找不到 Python 运行时：core\\runtime\\pythonw.exe\n\n请确保完整解压了压缩包。",
        "pdf2zh 桌面版", 0x10)
    sys.exit(1)

env = os.environ.copy()
env.pop("PYTHONHOME", None)
env.pop("PYTHONPATH", None)
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PYTHONIOENCODING"] = "utf-8"

subprocess.Popen([pythonw, script], cwd=app_dir, env=env)

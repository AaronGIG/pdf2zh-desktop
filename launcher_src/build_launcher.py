"""
用项目自带的 Python + PyInstaller 打包一个极简启动器 exe
生成的 pdf2zh.exe 只有一个功能：调用同目录的 core/runtime/pythonw.exe _launcher.py
"""
import subprocess
import sys
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(APP_DIR, "core", "runtime", "python.exe")
ICON = os.path.join(APP_DIR, "assets", "icon.ico")

# 极简启动器脚本
LAUNCHER_SCRIPT = os.path.join(APP_DIR, "launcher_src", "_stub.py")
with open(LAUNCHER_SCRIPT, "w", encoding="utf-8") as f:
    f.write('''
import os, sys, subprocess

app_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
pythonw = os.path.join(app_dir, "core", "runtime", "pythonw.exe")
script = os.path.join(app_dir, "_launcher.py")

if not os.path.exists(pythonw):
    import ctypes
    ctypes.windll.user32.MessageBoxW(0,
        "找不到 Python 运行时：core\\\\runtime\\\\pythonw.exe\\n\\n请确保完整解压了压缩包。",
        "pdf2zh 桌面版", 0x10)
    sys.exit(1)

env = os.environ.copy()
env.pop("PYTHONHOME", None)
env.pop("PYTHONPATH", None)
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PYTHONIOENCODING"] = "utf-8"

subprocess.Popen([pythonw, script], cwd=app_dir, env=env)
''')

# 检查是否有 PyInstaller
try:
    subprocess.run([PYTHON, "-c", "import PyInstaller"], check=True, capture_output=True)
except subprocess.CalledProcessError:
    print("Installing PyInstaller...")
    subprocess.run([PYTHON, "-m", "pip", "install", "pyinstaller", "--quiet"], check=True)

# 打包
cmd = [
    PYTHON, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "pdf2zh",
    "--icon", ICON,
    "--distpath", APP_DIR,
    "--workpath", os.path.join(APP_DIR, "launcher_src", "build"),
    "--specpath", os.path.join(APP_DIR, "launcher_src"),
    LAUNCHER_SCRIPT,
]
print(f"Running: {' '.join(cmd)}")
subprocess.run(cmd, check=True)
print(f"\nDone! pdf2zh.exe created at: {APP_DIR}")

"""
pdf2zh 桌面版启动器
由 pdf2zh.vbs 调用，使用 pythonw.exe 运行（无控制台窗口）
错误写入日志文件，并通过 Qt 对话框提示用户
"""
import sys
import os
import traceback
from pathlib import Path
from datetime import datetime

APP_DIR = Path(__file__).parent
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"startup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def log(msg: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")


def show_error_dialog(title: str, message: str):
    """尝试用 Qt 显示错误，失败则用 Windows 原生对话框"""
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        _app = QApplication.instance() or QApplication(sys.argv)
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setDetailedText(f"日志文件: {LOG_FILE}")
        msg_box.exec_()
    except Exception:
        # 后备: 使用 Windows MessageBox via ctypes
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"{message}\n\n日志文件: {LOG_FILE}",
                title,
                0x10,  # MB_ICONERROR
            )
        except Exception:
            pass


def main():
    log("=== pdf2zh 桌面版启动 ===")
    log(f"Python: {sys.version}")
    log(f"工作目录: {os.getcwd()}")

    try:
        log("导入 pdf2zh.gui_pyqt5...")
        from pdf2zh.gui_pyqt5 import main as gui_main
        log("导入成功，启动 GUI...")
        gui_main()
        log("GUI 正常退出")
    except ImportError as e:
        msg = f"模块导入失败: {e}\n\n请检查 core\\site-packages 是否完整。"
        log(f"[ERROR] {msg}\n{traceback.format_exc()}")
        show_error_dialog("pdf2zh - 启动失败", msg)
        sys.exit(1)
    except Exception as e:
        msg = f"程序启动失败: {e}"
        log(f"[ERROR] {msg}\n{traceback.format_exc()}")
        show_error_dialog("pdf2zh - 运行错误", msg)
        sys.exit(1)


if __name__ == "__main__":
    main()

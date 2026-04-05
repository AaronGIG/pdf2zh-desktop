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

# pythonw.exe 没有控制台，sys.stdout/stderr 为 None，
# 会导致 tqdm 等库写入时崩溃 (AttributeError: 'NoneType' object has no attribute 'write')
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

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


def preload_onnxruntime():
    """在 PyQt5 之前预加载 OnnxRuntime，避免 DLL 搜索路径冲突。

    PyQt5 会修改 Windows DLL 搜索路径，导致 OnnxRuntime 的
    onnxruntime_pybind11_state.pyd 无法找到 VC++ DLL 而加载失败。
    必须在任何 PyQt5 导入之前完成 OnnxRuntime 的加载。
    """
    import threading

    app_dir = str(APP_DIR)

    if hasattr(os, 'add_dll_directory'):
        runtime_dir = os.path.join(app_dir, 'core', 'runtime')
        if os.path.isdir(runtime_dir):
            os.add_dll_directory(os.path.abspath(runtime_dir))

        onnx_dll_dir = os.path.join(app_dir, 'core', 'site-packages', 'onnxruntime', 'capi')
        if os.path.isdir(onnx_dll_dir):
            os.add_dll_directory(os.path.abspath(onnx_dll_dir))

    result = [None]
    def _load():
        try:
            import onnxruntime
            import onnx
            result[0] = onnxruntime.__version__
        except Exception as e:
            result[0] = f"ERROR: {e}"

    t = threading.Thread(target=_load, daemon=True)
    t.start()
    t.join(timeout=8)  # 最多等 8 秒

    if t.is_alive():
        log("OnnxRuntime 预加载超时（8秒），跳过，AI布局检测将不可用")
    elif result[0] and not str(result[0]).startswith("ERROR"):
        log(f"OnnxRuntime 预加载成功: {result[0]}")
    else:
        log(f"OnnxRuntime 预加载失败（AI布局检测将不可用）: {result[0]}")


def ensure_window_visible(window, app):
    """根据屏幕分辨率自适应窗口大小并居中显示。"""
    screen = app.primaryScreen().availableGeometry()
    # 按屏幕大小自适应：占屏幕 85% 但不超过 1400x900
    w = min(int(screen.width() * 0.85), 1400)
    h = min(int(screen.height() * 0.85), 900)
    # 最小保证 900x600
    w = max(w, 900)
    h = max(h, 600)
    window.resize(w, h)
    x = screen.x() + (screen.width() - w) // 2
    y = screen.y() + (screen.height() - h) // 2
    window.move(x, y)


def main():
    log("=== pdf2zh 桌面版启动 ===")
    log(f"Python: {sys.version}")
    log(f"工作目录: {os.getcwd()}")

    # 设置 Qt 插件路径，避免与系统中其他 Qt 安装冲突
    qt_plugin_path = str(APP_DIR / "core" / "site-packages" / "PyQt5" / "Qt5" / "plugins")
    os.environ["QT_PLUGIN_PATH"] = qt_plugin_path
    log(f"QT_PLUGIN_PATH: {qt_plugin_path}")

    # 关键：必须在 PyQt5 之前预加载 OnnxRuntime
    log("预加载 OnnxRuntime...")
    preload_onnxruntime()

    try:
        log("导入 pdf2zh.gui_pyqt5...")
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication
        from pdf2zh.gui_pyqt5 import PDF2ZHMainWindow
        log("导入成功，启动 GUI...")

        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        app.setStyleSheet("""
            * {
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 14px;
            }
            QMainWindow {
                background: #fafbfc;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 15px;
                color: #333;
                border: 1px solid #e0e4ea;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #4169E1;
            }
            QPushButton {
                border: 1px solid #d0d5dd;
                border-radius: 4px;
                padding: 5px 10px;
                background: white;
            }
            QPushButton:hover {
                background: #f0f4ff;
                border-color: #4169E1;
            }
            QPushButton:pressed {
                background: #e0e8ff;
            }
            QPushButton:disabled {
                background: #f5f5f5;
                color: #aaa;
                border-color: #e0e0e0;
            }
            QComboBox {
                border: 1px solid #d0d5dd;
                border-radius: 4px;
                padding: 4px 8px;
                background: white;
            }
            QComboBox:hover {
                border-color: #4169E1;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #d0d5dd;
                border-radius: 4px;
                background: white;
                selection-background-color: #e8eeff;
                selection-color: #333;
                padding: 2px;
            }
            QLineEdit {
                border: 1px solid #d0d5dd;
                border-radius: 4px;
                padding: 4px 8px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #4169E1;
            }
            QSpinBox {
                border: 1px solid #d0d5dd;
                border-radius: 4px;
                padding: 3px 6px;
                background: white;
            }
            QCheckBox {
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #bbb;
                border-radius: 3px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #4169E1;
                border-color: #4169E1;
            }
            QListWidget {
                border: 1px solid #e0e4ea;
                border-radius: 4px;
                background: white;
            }
            QListWidget::item {
                padding: 3px 6px;
            }
            QListWidget::item:selected {
                background: #e8eeff;
                color: #333;
            }
            QTextEdit {
                border: 1px solid #d0d5dd;
                border-radius: 4px;
                background: white;
            }
            QTextEdit:focus {
                border-color: #4169E1;
            }
            QProgressBar {
                border: none;
                border-radius: 3px;
                background: #e8ecf4;
            }
            QProgressBar::chunk {
                background: #4169E1;
                border-radius: 3px;
            }
            QTabBar::tab {
                font-size: 14px;
                padding: 8px 6px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                font-weight: bold;
                color: #4169E1;
                border-bottom: 2px solid #4169E1;
            }
            QTabBar::tab:!selected {
                color: #666;
            }
            QTabBar::tab:hover:!selected {
                color: #333;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid #4169E1;
                font-weight: bold;
                color: #4169E1;
            }
            QTabWidget::pane {
                border: 1px solid #d0d5dd;
                border-radius: 0 0 6px 6px;
                background: white;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QToolTip {
                background-color: #FFFDF0;
                color: #333;
                border: 1px solid #D4C89A;
                border-radius: 8px;
                padding: 8px 12px;
                font-family: "Microsoft YaHei", "微软雅黑", sans-serif;
                font-size: 16px;
                line-height: 1.6;
            }
        """)
        window = PDF2ZHMainWindow()
        ensure_window_visible(window, app)
        window.show()
        window.raise_()
        window.activateWindow()
        log("GUI 窗口已显示")
        sys.exit(app.exec_())
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

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
    t.join(timeout=3)  # 最多等 3 秒

    if t.is_alive():
        log("OnnxRuntime 预加载超时（3秒），跳过")
    elif result[0] and not str(result[0]).startswith("ERROR"):
        log(f"OnnxRuntime 预加载成功: {result[0]}")
    else:
        log(f"OnnxRuntime 预加载失败（AI布局检测将不可用）: {result[0]}")


def ensure_window_visible(window, app):
    """确保窗口在可见屏幕范围内并居中显示（兼容 DPI 缩放）。"""
    screen = app.primaryScreen().availableGeometry()
    # availableGeometry 已经是逻辑像素，直接用
    sw, sh = screen.width(), screen.height()
    w = min(int(sw * 0.85), 1400)
    h = min(int(sh * 0.85), 900)
    # 低分辨率/高缩放时降低最小值
    w = max(w, min(860, sw - 40))
    h = max(h, min(560, sh - 40))
    window.resize(w, h)
    x = screen.x() + (sw - w) // 2
    y = screen.y() + (sh - h) // 2
    window.move(x, y)
    log(f"屏幕逻辑分辨率: {sw}x{sh}, 窗口: {w}x{h}")


def main():
    log("=== pdf2zh 桌面版启动 ===")
    log(f"Python: {sys.version}")
    log(f"工作目录: {os.getcwd()}")

    # 设置 Qt 插件路径，避免与系统中其他 Qt 安装冲突
    qt_plugin_path = str(APP_DIR / "core" / "site-packages" / "PyQt5" / "Qt5" / "plugins")
    os.environ["QT_PLUGIN_PATH"] = qt_plugin_path
    log(f"QT_PLUGIN_PATH: {qt_plugin_path}")

    # DPI 感知：让 Qt 正确处理高分屏缩放
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    # 关键：必须在 PyQt5 之前预加载 OnnxRuntime
    log("预加载 OnnxRuntime...")
    preload_onnxruntime()

    try:
        log("导入 pdf2zh.gui_pyqt5...")
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        from pdf2zh.gui_pyqt5 import PDF2ZHMainWindow
        log("导入成功，启动 GUI...")

        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # ── DPI 感知样式表生成 ──
        dpr = app.primaryScreen().devicePixelRatio()
        # 逻辑像素缩放因子：1080p=1.0, 2K≈1.33, 4K=2.0
        # Qt AA_EnableHighDpiScaling 已处理物理→逻辑映射，
        # 但部分 Windows 系统 DPI 缩放不完美，需兜底
        log(f"DPI ratio: {dpr}")

        def build_stylesheet(base_font=14):
            """根据基准字号生成完整样式表（所有尺寸等比联动）"""
            f = base_font          # 正文
            f1 = f + 1             # GroupBox 标题
            fs = f - 1             # 辅助文字
            ft = f + 2             # Tooltip
            pad_v = max(3, f // 3) # 垂直内边距
            pad_h = max(6, f // 2) # 水平内边距
            r = max(3, f // 3)     # 圆角
            r2 = r + 2             # 大圆角
            ind = f                # checkbox indicator
            bw = max(1, f // 14)   # 边框宽度
            sp = max(4, f // 3)    # checkbox spacing
            return f"""
            * {{ font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif; font-size: {f}px; }}
            QMainWindow {{ background: #fafbfc; }}
            QGroupBox {{ font-weight: bold; font-size: {f1}px; color: #333;
                border: {bw}px solid #e0e4ea; border-radius: {r2}px; margin-top: {sp+4}px; padding-top: {f}px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: {pad_h+4}px; padding: 0 {sp}px; color: #4169E1; }}
            QPushButton {{ border: {bw}px solid #d0d5dd; border-radius: {r}px; padding: {pad_v}px {pad_h}px; background: white; }}
            QPushButton:hover {{ background: #f0f4ff; border-color: #4169E1; }}
            QPushButton:pressed {{ background: #e0e8ff; }}
            QPushButton:disabled {{ background: #f5f5f5; color: #aaa; border-color: #e0e0e0; }}
            QComboBox {{ border: {bw}px solid #d0d5dd; border-radius: {r}px; padding: {pad_v}px {pad_h}px; background: white; }}
            QComboBox:hover {{ border-color: #4169E1; }}
            QComboBox QAbstractItemView {{ border: {bw}px solid #d0d5dd; border-radius: {r}px;
                background: white; selection-background-color: #e8eeff; selection-color: #333; padding: 2px; }}
            QLineEdit {{ border: {bw}px solid #d0d5dd; border-radius: {r}px; padding: {pad_v}px {pad_h}px; background: white; }}
            QLineEdit:focus {{ border-color: #4169E1; }}
            QSpinBox {{ border: {bw}px solid #d0d5dd; border-radius: {r}px; padding: {pad_v-1}px {sp}px; background: white; }}
            QCheckBox {{ spacing: {sp}px; }}
            QCheckBox::indicator {{ width: {ind}px; height: {ind}px; border: {bw}px solid #bbb; border-radius: {r}px; background: white; }}
            QCheckBox::indicator:checked {{ background: #4169E1; border-color: #4169E1; }}
            QListWidget {{ border: {bw}px solid #e0e4ea; border-radius: {r}px; background: white; }}
            QListWidget::item {{ padding: {pad_v-1}px {sp}px; }}
            QListWidget::item:selected {{ background: #e8eeff; color: #333; }}
            QTextEdit {{ border: {bw}px solid #d0d5dd; border-radius: {r}px; background: white; }}
            QTextEdit:focus {{ border-color: #4169E1; }}
            QProgressBar {{ border: none; border-radius: {r}px; background: #e8ecf4; }}
            QProgressBar::chunk {{ background: #4169E1; border-radius: {r}px; }}
            QTabBar::tab {{ font-size: {f}px; padding: {pad_h}px {sp}px; border: none; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ font-weight: bold; color: #4169E1; border-bottom: 2px solid #4169E1; background: white; }}
            QTabBar::tab:!selected {{ color: #666; }}
            QTabBar::tab:hover:!selected {{ color: #333; }}
            QTabWidget::pane {{ border: {bw}px solid #d0d5dd; border-radius: 0 0 {r2}px {r2}px; background: white; }}
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ width: {max(10, f-2)}px; }}
            QScrollBar:horizontal {{ height: {max(10, f-2)}px; }}
            QToolTip {{ background: #FFFDF0; color: #333; border: {bw}px solid #D4C89A;
                border-radius: {r2+2}px; padding: {pad_h}px {pad_h+4}px;
                font-family: "Microsoft YaHei"; font-size: {ft}px; }}
            """

        # 存为全局函数供字号切换时调用
        import builtins
        builtins._pdf2zh_build_stylesheet = build_stylesheet

        # 从用户配置读取上次字号，默认小(12)
        _saved_font = 12
        try:
            import json as _json
            _cfg_path = os.path.join(os.path.expanduser("~"), "pdf2zh_gui_config.json")
            if os.path.exists(_cfg_path):
                with open(_cfg_path, 'r', encoding='utf-8') as _f:
                    _cfg = _json.load(_f)
                _level = _cfg.get('font_size_level', '小')
                _saved_font = {'小': 12, '中': 14, '大': 16}.get(_level, 12)
        except Exception:
            pass
        log(f"初始字号: {_saved_font}px")
        app.setStyleSheet(build_stylesheet(_saved_font))
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

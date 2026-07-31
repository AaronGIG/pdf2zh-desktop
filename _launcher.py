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
    t.join(timeout=30)  # 等待加载完成（AI布局检测必须）

    if t.is_alive():
        log("OnnxRuntime 预加载超时（30秒），继续启动")
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


def _parse_cli_args(argv):
    """v2.3.4: 解析 Zotero 右键唤起的命令行参数
    支持: pdf2zh.exe [--format=side_by_side|dual|mono|all] [--auto] <file.pdf>
    """
    result = {"file": None, "format": None, "auto": False, "silent": False}
    try:
        for arg in argv[1:]:
            if arg.startswith("--format="):
                fmt = arg.split("=", 1)[1].strip()
                if fmt in ("mono", "dual", "side_by_side", "all"):
                    result["format"] = fmt
            elif arg == "--auto":
                result["auto"] = True
            elif arg == "--silent":
                result["silent"] = True
            elif arg.lower().endswith(".pdf") and os.path.isfile(arg):
                result["file"] = arg
    except Exception:
        pass
    return result


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

        # v2.3.4: 解析 Zotero 右键传来的 CLI 参数
        _cli = _parse_cli_args(sys.argv)
        log(f"[cli] parsed = {_cli}")

        # ── 单实例检测 + CLI 参数转发（Zotero 右键唤起）──
        from PyQt5.QtNetwork import QLocalServer, QLocalSocket
        import json as _json
        _instance_key = "pdf2zh-desktop-singleton-lock"
        _socket = QLocalSocket()
        _socket.connectToServer(_instance_key)
        if _socket.waitForConnected(500):
            # 已有实例：把文件+参数发过去让它翻译，本进程退出
            log("检测到已有实例，转发参数后退出")
            if _cli.get("file"):
                try:
                    _socket.write(_json.dumps(_cli).encode("utf-8"))
                    _socket.waitForBytesWritten(1000)
                except Exception:
                    pass
            _socket.disconnectFromServer()
            _socket.close()
            sys.exit(0)
        _socket.close()
        _server = QLocalServer()
        _server.removeServer(_instance_key)
        _server.listen(_instance_key)
        log("单实例锁已创建")

        # ── DPI 感知样式表生成 ──
        dpr = app.primaryScreen().devicePixelRatio()
        log(f"DPI ratio: {dpr}")

        # DPR 补偿系数：高分屏上 Qt 会把逻辑像素放大到物理像素，
        # 导致同样 12px 在 4K@200% 屏显示为 24px 物理，视觉偏大。
        # 补偿公式：dpr>1 时缩小基准字号，使各屏幕物理显示大小接近。
        import builtins
        builtins._pdf2zh_dpr = dpr
        builtins._pdf2zh_dpr_scale = 1.0 / max(1.0, dpr ** 0.6)  # 高分屏更强补偿

        def build_stylesheet(base_font=14):
            """根据基准字号生成完整样式表（所有尺寸等比联动，DPR 自动补偿）"""
            dpr_scale = getattr(builtins, '_pdf2zh_dpr_scale', 1.0)
            f = max(8, round(base_font * dpr_scale))  # DPR 补偿后的实际字号（下限 8px）
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
            QCheckBox::indicator {{ width: {ind}px; height: {ind}px; border: {bw}px solid #c8cdd4; border-radius: {max(2, r // 2)}px; background: white; }}
            QCheckBox::indicator:hover {{ border-color: #4169E1; }}
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
            QPushButton#translateBtn {{ background: #165DFF; color: white; font-size: {f}px;
                padding: {pad_v}px {pad_h}px; border-radius: {r}px; border: none; }}
            QPushButton#translateBtn:hover {{ background: #0E42D2; }}
            QPushButton#translateBtn:disabled {{ background: #ccc; color: #888; }}
            """

        # 存为全局函数供字号切换时调用
        import builtins
        builtins._pdf2zh_build_stylesheet = build_stylesheet

        # 从用户配置读取上次字号，默认极小(10)
        _saved_font = 10
        try:
            import json as _json
            _cfg_path = os.path.join(os.path.expanduser("~"), "pdf2zh_gui_config.json")
            if os.path.exists(_cfg_path):
                with open(_cfg_path, 'r', encoding='utf-8') as _f:
                    _cfg = _json.load(_f)
                _level = _cfg.get('font_size_level', '极小')
                _saved_font = {'极小': 10, '小': 12, '中': 14, '大': 16, '极大': 18}.get(_level, 10)
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

        # v2.3.4: Zotero 右键唤起处理 —— 加文件 + 设格式 + 自动翻译
        from PyQt5.QtCore import QTimer as _QTimer

        def _handle_cli(payload):
            try:
                log(f"[cli] _handle_cli payload={payload}")
                file_path = payload.get("file")
                if not file_path or not os.path.isfile(file_path):
                    log(f"[cli] file invalid: {file_path}")
                    return
                if hasattr(window, "batch_files"):
                    if file_path not in window.batch_files:
                        window.batch_files.append(file_path)
                    if hasattr(window, "current_file") and not window.current_file:
                        window.current_file = file_path
                    if hasattr(window, "file_list_widget"):
                        try:
                            window.file_list_widget.addItem(os.path.basename(file_path))
                        except Exception:
                            pass
                fmt = payload.get("format")
                if fmt:
                    window._cli_output_format = fmt
                # v2.3.4: 后台静默模式 —— 最小化窗口不抢焦点, 完成后自动关闭
                silent = bool(payload.get("silent"))
                if silent:
                    window._cli_silent = True
                if payload.get("auto"):
                    window._cli_auto = True
                    log(f"[cli] auto=True silent={silent}, 600ms后触发 start_translation")
                    _QTimer.singleShot(600,
                        lambda: (log("[cli] 调用 start_translation"), window.start_translation()) if hasattr(window, "start_translation") else log("[cli] 无 start_translation 方法"))
                try:
                    if silent:
                        window.showMinimized()
                    else:
                        # v2.3.4: showNormal 确保被上次静默最小化/隐藏的窗口能重现
                        window.showNormal(); window.raise_(); window.activateWindow()
                except Exception:
                    pass
            except Exception as _e:
                log(f"[cli handle] {_e}")

        def _on_new_conn():
            conn = _server.nextPendingConnection()
            if conn:
                conn.waitForReadyRead(1000)
                data = conn.readAll().data().decode("utf-8", errors="ignore")
                conn.close()
                try:
                    payload = _json.loads(data) if data.startswith("{") else {"file": data, "format": None, "auto": False}
                    _handle_cli(payload)
                except Exception:
                    pass
        try:
            _server.newConnection.connect(_on_new_conn)
        except Exception:
            pass

        if _cli.get("file"):
            _QTimer.singleShot(400, lambda: _handle_cli(_cli))

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

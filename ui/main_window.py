"""
pdf2zh for Mac — 完整版主窗口
全功能适配: 三种预览模式 / 分块翻译 / 页码范围 / 历史记录 / 20+翻译服务
"""

import sys
import os
import json
import webbrowser
import time
from pathlib import Path
import fitz


def _res(*parts):
    """获取资源文件路径，兼容 PyInstaller 打包和开发环境"""
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, *parts)
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), *parts)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLayout,
    QPushButton, QLabel, QComboBox, QProgressBar, QFileDialog, QDialog,
    QStackedWidget, QStackedLayout, QFrame, QScrollArea, QGraphicsDropShadowEffect,
    QCheckBox, QListWidget, QListWidgetItem, QLineEdit, QSpinBox, QPlainTextEdit,
    QSizePolicy, QSlider, QSplitter, QTabBar, QMessageBox, QMenu, QAction,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize, QEvent, QRect
from PyQt5.QtGui import (QColor, QDragEnterEvent, QDropEvent, QImage, QPixmap,
                         QScreen, QIcon, QPainter, QPainterPath, QPen, QRegion)

from ui.config_manager import UserConfigManager, HistoryManager
from ui.translate_worker import (
    TranslateWorker, LANG_MAP, SERVICE_MAP, PAGE_PRESETS,
    OUTPUT_MODES, parse_page_range, detect_zotero_source,
    get_zotero_item_key, zotero_auto_link, zotero_plugin_installed,
    build_service_envs, SummaryWorker, QAWorker,
)

# ─── 苹果风配色 ─────────────────────────────────────────────

L = {
    "bg":"#FFF","bg2":"#F9F9FB","bg3":"#F2F2F7","elev":"#FFF",
    "sb":"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #FBFBFD,stop:1 #F2F2F7)",
    "sb_act":"rgba(0,113,227,0.12)","sb_hov":"rgba(0,0,0,0.04)",
    "t1":"#1D1D1F","t2":"#6E6E73","t3":"#AEAEB2","t4":"#C7C7CC",
    "acc":"#0071E3","acc_l":"rgba(0,113,227,0.10)","acc_h":"#0077ED","acc_p":"#005BBB",
    "acc_g":"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0071E3,stop:1 #00A1FF)",
    "ok":"#34C759","err":"#FF3B30",
    "brd":"rgba(0,0,0,0.06)","brd_s":"rgba(0,0,0,0.10)",
    "card":"#FFF","card_b":"rgba(0,0,0,0.04)",
    "inp":"#F2F2F7","inp_b":"rgba(0,0,0,0.08)",
    "dz_bg":"#FAFBFF","dz_b":"rgba(0,113,227,0.20)",
    "tag_bg":"rgba(0,113,227,0.08)","tag_fg":"#0071E3",
    "scr":"rgba(0,0,0,0.12)","scr_h":"rgba(0,0,0,0.24)",
    "pv_bg":"#FFFFFF","pv_tb":"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #FBFBFD,stop:1 #F2F2F7)",
    "pv_l_bg":"rgba(0,113,227,0.07)","pv_l_fg":"#0071E3",
    "link":"#6E6E73","link_h":"#0071E3",
}

D = {
    "bg":"#1C1C1E","bg2":"#2C2C2E","bg3":"#3A3A3C","elev":"#2C2C2E",
    "sb":"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #242426,stop:1 #1C1C1E)",
    "sb_act":"rgba(10,132,255,0.20)","sb_hov":"rgba(255,255,255,0.06)",
    "t1":"#F5F5F7","t2":"#98989D","t3":"#636366","t4":"#48484A",
    "acc":"#0A84FF","acc_l":"rgba(10,132,255,0.15)","acc_h":"#409CFF","acc_p":"#0071E3",
    "acc_g":"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0A84FF,stop:1 #5AC8FA)",
    "ok":"#30D158","err":"#FF453A",
    "brd":"rgba(255,255,255,0.06)","brd_s":"rgba(255,255,255,0.10)",
    "card":"#2C2C2E","card_b":"rgba(255,255,255,0.12)",
    "inp":"#3A3A3C","inp_b":"rgba(255,255,255,0.08)",
    "dz_bg":"#2A2A2E","dz_b":"rgba(10,132,255,0.35)",
    "tag_bg":"rgba(10,132,255,0.15)","tag_fg":"#0A84FF",
    "scr":"rgba(255,255,255,0.12)","scr_h":"rgba(255,255,255,0.24)",
    "pv_bg":"#1C1C1E","pv_tb":"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2C2C2E,stop:1 #242426)",
    "pv_l_bg":"rgba(10,132,255,0.12)","pv_l_fg":"#0A84FF",
    "link":"#98989D","link_h":"#0A84FF",
}

_C = L   # 当前活跃配色（深色/浅色切换时更新）


# ─── 磨砂提示气泡 ──────────────────────────────────────────
class _Tip(QWidget):
    """截取屏幕 → 缩放模糊 → 叠加半透明蒙层 → 圆角裁剪 = 磨砂玻璃"""
    _inst = None
    _PAD = 10

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._text = ""
        self._blur_pix = None

    def _grab_and_blur(self, x, y, w, h):
        """安全截取屏幕区域并模糊"""
        try:
            screen = QApplication.primaryScreen()
            if not screen:
                return
            pix = screen.grabWindow(0, x, y, w, h)
            if pix.isNull():
                return
            img = pix.toImage()
            # 缩小到 1/8 再放大 = 快速高斯模糊
            from PyQt5.QtCore import QSize
            tiny = img.scaled(QSize(max(1, w // 8), max(1, h // 8)),
                              Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            blurred = tiny.scaled(QSize(w, h),
                                  Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self._blur_pix = QPixmap.fromImage(blurred)
        except Exception:
            self._blur_pix = None

    def paintEvent(self, e):
        from PyQt5.QtGui import QPainter, QPainterPath, QFont, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pad = self._PAD
        rect = self.rect().adjusted(pad, pad, -pad, -pad)
        radius = 8.0
        is_dark = (_C is D)
        path = QPainterPath()
        path.addRoundedRect(float(rect.x()), float(rect.y()),
                            float(rect.width()), float(rect.height()), radius, radius)
        # ── 柔和阴影 ──
        for i in range(5):
            a = max(1, (35 if is_dark else 20) // (i + 1))
            d = (i + 1) * 2.0
            sp = QPainterPath()
            sr = rect.adjusted(-d, -d + 1, d, d + 2)
            sp.addRoundedRect(float(sr.x()), float(sr.y()),
                              float(sr.width()), float(sr.height()), radius + d, radius + d)
            p.fillPath(sp, QColor(0, 0, 0, a))
        # ── 裁剪到圆角 ──
        p.setClipPath(path)
        # ── 模糊背景 ──
        if self._blur_pix and not self._blur_pix.isNull():
            p.drawPixmap(rect, self._blur_pix)
        else:
            fb = QColor(45, 45, 48) if is_dark else QColor(245, 245, 247)
            p.fillPath(path, fb)
        # ── 半透明蒙层（磨砂感的关键） ──
        overlay = QColor(30, 30, 32, 140) if is_dark else QColor(255, 255, 255, 178)
        p.fillRect(rect, overlay)
        # ── 顶部高光 ──
        hi = QPainterPath()
        hr = rect.adjusted(1, 1, -1, -rect.height() + 16)
        hi.addRoundedRect(float(hr.x()), float(hr.y()),
                          float(hr.width()), float(hr.height()), radius - 1, radius - 1)
        p.fillPath(hi, QColor(255, 255, 255, 25 if is_dark else 120))
        # ── 边框 ──
        p.setClipping(False)
        brd = QColor(255, 255, 255, 20) if is_dark else QColor(0, 0, 0, 15)
        p.setPen(QPen(brd, 0.5))
        p.drawPath(path)
        # ── 文字 ──
        p.setPen(QColor(_C["t1"]))
        font = QFont("Helvetica Neue", 11)
        font.setFamilies(["Helvetica Neue", "PingFang SC"])
        p.setFont(font)
        tr = rect.adjusted(10, 7, -10, -7)
        p.drawText(tr, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, self._text)
        p.end()

    def _calc_size(self):
        from PyQt5.QtGui import QFont, QFontMetrics
        font = QFont("Helvetica Neue", 11)
        font.setFamilies(["Helvetica Neue", "PingFang SC"])
        fm = QFontMetrics(font)
        br = fm.boundingRect(0, 0, 300, 9999,
                             Qt.AlignLeft | Qt.TextWordWrap, self._text)
        pad = self._PAD
        self.setFixedSize(br.width() + 20 + pad * 2, br.height() + 14 + pad * 2)

    @classmethod
    def show_tip(cls, pos, text, widget=None):
        if not text:
            cls.hide_tip(); return
        if cls._inst is None:
            cls._inst = cls()
        tip = cls._inst
        tip._text = text
        tip._calc_size()
        # 先确保 tooltip 自身不可见，再截取目标位置的屏幕
        tip.hide()
        pad = tip._PAD
        tx, ty = pos.x() + 8, pos.y() + 14
        # 边界检测：确保不超出屏幕
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            if tx + tip.width() > sg.right():
                tx = sg.right() - tip.width()
            if ty + tip.height() > sg.bottom():
                ty = pos.y() - tip.height() - 4  # 移到光标上方
            tx = max(sg.left(), tx)
            ty = max(sg.top(), ty)
        bx, by = tx + pad, ty + pad
        tw, th = tip.width() - pad * 2, tip.height() - pad * 2
        tip._grab_and_blur(bx, by, tw, th)
        tip.move(tx, ty)
        tip.show()
        tip.update()

    @classmethod
    def hide_tip(cls):
        if cls._inst: cls._inst.hide()


def _fix_combo_popup(combo):
    """去掉 QComboBox 的 macOS 焦点虚线框"""
    combo.setAttribute(Qt.WA_MacShowFocusRect, False)


def _install_tip_filter(app):
    """安装全局 tooltip 拦截 + combo 修复"""
    from PyQt5.QtCore import QObject

    class F(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.ToolTip:
                text = ""
                if hasattr(obj, 'toolTip'):
                    text = obj.toolTip()
                # QListWidget viewport → item tooltip
                if not text and hasattr(obj, 'parent'):
                    p = obj.parent()
                    if hasattr(p, 'itemAt'):
                        item = p.itemAt(event.pos())
                        if item: text = item.toolTip()
                if text:
                    from PyQt5.QtGui import QCursor
                    _Tip.show_tip(QCursor.pos(), text, obj)
                    event.accept()
                    return True
                return False
            if event.type() == QEvent.Leave:
                _Tip.hide_tip()
            return False

    f = F(app)
    app._tip_filter = f
    app.installEventFilter(f)


def S(c):
    return f"""
    QMainWindow{{background:{c["bg"]};}}
    QWidget{{font-family:"Helvetica Neue","PingFang SC";font-size:13px;color:{c["t1"]};outline:none;}}
    #Central{{background:{c["bg"]};}}
    QStackedWidget{{background:{c["bg"]};}}
    QStackedWidget>QWidget{{background:{c["bg"]};}}
    QLabel{{background:transparent;border:none;}}
    QToolTip{{background:transparent;border:none;padding:0;}}
    /* ── 侧边栏 ── */
    #Sidebar{{background:{c["sb"]};border-right:0.5px solid {c["brd"]};}}
    #SB{{background:transparent;border:none;border-radius:7px;padding:6px 12px;text-align:left;font-size:13px;color:{c["t2"]};letter-spacing:0.2px;border-left:3px solid transparent;}}
    #SB:hover{{background:{c["sb_hov"]};color:{c["t1"]};}}
    #SB[active="true"]{{background:{c["sb_act"]};color:{c["acc"]};font-weight:600;border-left:3px solid {c["acc"]};border-top-left-radius:0;border-bottom-left-radius:0;}}
    #SBLink{{background:transparent;border:none;font-size:10px;color:{c["link"]};padding:1px 3px;}}
    #SBLink:hover{{color:{c["acc"]};}}
    /* ── 按钮 ── */
    #Pr{{background:{c["acc_g"]};color:white;border:none;border-radius:12px;padding:12px 32px;font-size:15px;font-weight:600;letter-spacing:0.3px;}}
    #Pr:hover{{background:{c["acc_h"]};}}#Pr:pressed{{background:{c["acc_p"]};padding:13px 32px 11px 32px;}}
    #Pr:disabled{{background:{c["bg3"]};color:{c["t4"]};border:1px solid {c["brd"]};}}
    #Sc{{background:{c["bg2"]};color:{c["t1"]};border:0.5px solid {c["brd_s"]};border-radius:8px;padding:8px 18px;font-size:13px;font-weight:500;}}
    #Sc:hover{{background:{c["bg3"]};border-color:{c["acc"]};}}
    #Gh{{background:transparent;color:{c["acc"]};border:none;border-radius:6px;padding:6px 12px;font-size:13px;font-weight:500;}}
    #Gh:hover{{background:{c["acc_l"]};}}
    #GhDanger{{background:transparent;color:{c["err"]};border:none;border-radius:6px;padding:6px 12px;font-size:13px;font-weight:500;}}
    #GhDanger:hover{{background:rgba(255,59,48,0.08);}}
    #TB{{background:transparent;color:{c["t2"]};border:none;border-radius:6px;padding:5px 10px;font-size:13px;font-weight:500;}}
    #TB:hover{{background:{c["sb_hov"]};color:{c["t1"]};}}
    #TB[active="true"]{{background:{c["acc_l"]};color:{c["acc"]};font-weight:600;}}
    /* ── 输入控件 ── */
    QComboBox{{background:{c["inp"]};border:1.5px solid {c["inp_b"]};border-radius:8px;padding:8px 14px;font-size:13px;min-height:22px;color:{c["t1"]};}}
    QComboBox:hover{{border-color:{c["brd_s"]};}}QComboBox:focus{{border-color:{c["acc"]};border-width:1.5px;outline:none;}}
    QComboBox::drop-down{{border:none;width:28px;subcontrol-origin:padding;subcontrol-position:center right;}}
    QComboBox::down-arrow{{image:none;width:8px;height:5px;border-left:4px solid transparent;border-right:4px solid transparent;border-top:5px solid {c["t3"]};margin-right:10px;}}
    QComboBox QAbstractItemView{{background:{c["elev"]};border:none;border-radius:10px;padding:6px 4px;color:{c["t1"]};outline:0;}}
    QComboBox QAbstractItemView::item{{padding:6px 12px;border:none;border-radius:6px;margin:1px 2px;}}
    QComboBox QAbstractItemView::item:hover{{background:{c["acc_l"]};}}
    QComboBox QAbstractItemView::item:selected{{background:{c["acc"]};color:white;}}
    QLineEdit{{background:{c["inp"]};border:1.5px solid {c["inp_b"]};border-radius:8px;padding:8px 14px;font-size:13px;color:{c["t1"]};}}
    QLineEdit:focus{{border-color:{c["acc"]};border-width:2px;background:{c["elev"]};}}
    QLineEdit[readOnly="true"]{{color:{c["t2"]};}}
    QSpinBox{{background:{c["inp"]};border:1.5px solid {c["inp_b"]};border-radius:8px;padding:6px 10px;font-size:13px;color:{c["t1"]};}}
    QSpinBox:focus{{border-color:{c["acc"]};border-width:2px;}}
    QTextEdit{{background:{c["inp"]};color:{c["t1"]};border:1.5px solid {c["inp_b"]};border-radius:8px;}}
    QTextEdit:focus{{border-color:{c["acc"]};border-width:2px;}}
    /* ── 进度条 ── */
    QProgressBar{{background:{c["bg3"]};border:none;border-radius:3px;max-height:6px;min-height:6px;font-size:1px;}}
    QProgressBar::chunk{{background:{c["acc_g"]};border-radius:3px;}}
    /* ── 卡片 ── */
    #Card{{background:{c["card"]};border:0.5px solid {c["card_b"]};border-radius:12px;}}
    #Card:hover{{border-color:{c["acc"]};}}
    #DZ{{background:{c["dz_bg"]};border:2px dashed {c["dz_b"]};border-radius:12px;}}
    #DZ:hover{{border-color:{c["acc"]};}}
    /* ── 列表 ── */
    QListWidget{{background:transparent;border:none;outline:none;}}
    QListWidget::item{{background:{c["card"]};border:0.5px solid {c["card_b"]};border-radius:8px;padding:4px 10px;margin:2px 0;}}
    QListWidget::item:selected{{background:{c["acc"]};color:white;border-color:{c["acc"]};}}
    QListWidget::item:hover:!selected{{background:{c["bg2"]};}}
    /* ── 滚动条 ── */
    QScrollArea{{border:none;background:transparent;}}
    QScrollBar:vertical{{background:transparent;width:10px;margin:4px 2px;}}
    QScrollBar::handle:vertical{{background:{c["scr"]};border-radius:4px;min-height:36px;}}
    QScrollBar::handle:vertical:hover{{background:{c["scr_h"]};}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical,QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{{height:0;background:transparent;}}
    QScrollBar:horizontal{{height:0;}}
    /* ── 复选框 ── */
    QCheckBox{{spacing:10px;font-size:13px;}}
    QCheckBox::indicator{{width:18px;height:18px;border-radius:5px;border:1.5px solid {c["brd_s"]};background:{c["elev"]};}}
    QCheckBox::indicator:hover{{border-color:{c["acc"]};background:{c["acc_l"]};}}
    QCheckBox::indicator:checked{{background:{c["acc"]};border-color:{c["acc"]};}}
    /* ── 标签/分隔 ── */
    #Tag{{background:{c["tag_bg"]};color:{c["tag_fg"]};border:none;border-radius:6px;padding:3px 10px;font-size:11px;font-weight:600;}}
    #Div{{background:{c["brd"]};max-height:0.5px;min-height:0.5px;}}
    /* ── 预览区 ── */
    #PA{{background:{c["pv_bg"]};}}
    #PT{{background:{c["pv_tb"]};border-bottom:0.5px solid {c["brd"]};}}
    #PL{{background:{c["pv_l_bg"]};color:{c["pv_l_fg"]};border:none;border-radius:6px;padding:3px 12px;font-size:11px;font-weight:600;}}
    QSplitter::handle{{background:{c["brd"]};width:1px;}}
    QSplitter::handle:hover{{background:{c["acc"]};}}
    QSlider::groove:horizontal{{background:{c["bg3"]};height:4px;border-radius:2px;}}
    QSlider::handle:horizontal{{background:{c["acc"]};width:14px;height:14px;margin:-5px 0;border-radius:7px;}}
    QSlider::handle:horizontal:hover{{background:{c["acc_h"]};width:16px;height:16px;margin:-6px 0;border-radius:8px;}}
    QMenu{{background:{c["elev"]};border:1px solid {c["brd_s"]};border-radius:10px;padding:6px 4px;}}
    QMenu::item{{padding:4px 28px 4px 14px;border-radius:6px;font-size:13px;margin:1px 4px;}}
    QMenu::item:selected{{background:{c["acc"]};color:white;}}
    QMenu::separator{{height:1px;background:{c["brd"]};margin:4px 12px;}}
    /* ── 字体层级: 24 / 15 / 13 / 11 ── */
    #PT0{{font-size:24px;font-weight:700;letter-spacing:-0.3px;}}
    #PT1{{font-size:15px;color:{c["t2"]};}}
    #ST{{font-size:13px;font-weight:600;}}
    #SL{{font-size:11px;font-weight:600;letter-spacing:0.8px;color:{c["t3"]};padding:6px 0 2px 0;}}
    #FL{{font-size:13px;font-weight:500;color:{c["t2"]};padding:2px 0;}}
    #Cap{{font-size:11px;color:{c["t3"]};}}
    #Mono{{font-family:"Menlo",monospace;font-size:12px;color:{c["t2"]};}}
    /* ── 进度卡片 ── */
    #ProgPct{{font-family:"Menlo",monospace;font-size:20px;font-weight:700;color:{c["acc"]};background:transparent;}}
    #ProgLabel{{font-size:13px;font-weight:600;color:{c["t1"]};}}
    #ProgIcon{{font-size:16px;background:transparent;}}
    #ProgDetail{{font-size:11px;color:{c["t2"]};}}
    #ProgTip{{font-size:11px;color:{c["t3"]};font-style:italic;}}
    #ProgCancel{{background:transparent;color:{c["err"]};border:none;font-size:13px;font-weight:500;padding:6px 12px;border-radius:6px;}}
    #ProgCancel:hover{{background:rgba(255,59,48,0.08);}}
    /* ── 拖拽区 ── */
    #DZTitle{{font-size:15px;font-weight:600;color:{c["t1"]};background:transparent;}}
    #DZSub{{font-size:11px;color:{c["t3"]};background:transparent;}}
    /* ── 历史面板 ── */
    #HistList{{background:transparent;border:none;font-size:11px;color:{c["t1"]};}}
    #HistList::item{{background:transparent;border:none;border-bottom:0.5px solid {c["brd"]};padding:8px 6px;margin:0;border-radius:0;}}
    #HistList::item:selected{{background:{c["sb_act"]};color:{c["acc"]};border-radius:6px;border-bottom:none;}}
    #HistList::item:hover:!selected{{background:{c["sb_hov"]};border-radius:6px;}}
    #HistPanel{{border-right:0.5px solid {c["brd"]};}}
    #HistDetail{{font-size:10px;color:{c["t2"]};background:{c["bg2"]};border:0.5px solid {c["brd"]};border-radius:8px;padding:4px 6px;}}
    /* ── 自定义进度条 ── */
    #ProgBar{{background:{c["bg3"]};border:none;border-radius:6px;max-height:12px;min-height:12px;font-size:1px;}}
    #ProgBar::chunk{{background:{c["acc_g"]};border-radius:6px;}}
    /* ── 预览工具栏控件 ── */
    #PageInput{{font-family:'Menlo',monospace;font-size:13px;font-weight:600;padding:4px;border-radius:6px;border:1px solid {c["inp_b"]};background:{c["inp"]};color:{c["t1"]};}}
    #PageInput:focus{{border-color:{c["acc"]};}}
    #TotalLbl{{font-family:'Menlo',monospace;font-size:11px;color:{c["t2"]};background:transparent;}}
    #ZoomPct{{font-family:'Menlo',monospace;font-size:11px;color:{c["t2"]};background:transparent;}}
    #SBSep{{font-size:10px;color:{c["t3"]};background:transparent;padding:0;}}
    #KBKey{{font-family:'Menlo',monospace;font-size:10px;font-weight:600;color:{c["t2"]};background:{c["bg3"]};border-radius:4px;padding:3px 8px;}}
    """


class _EggLogo(QLabel):
    """
    📄 Logo 彩蛋按钮：
    · 悬停 5 秒 → 烟花爆炸
    · 连续点击 5 次 → emoji 飘落
    所有动画在 MainWindow 层播放。
    """
    def __init__(self, text="📄", size=22):
        super().__init__(text)
        self.setStyleSheet(f"font-size:{size}px;background:transparent;border:none;")
        self.setCursor(Qt.PointingHandCursor)
        self._click_count = 0
        self._click_timer = QTimer(); self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._reset_clicks)
        self._hover_timer = QTimer(); self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._on_hover_egg)

    def enterEvent(self, e):
        super().enterEvent(e)
        self._hover_timer.start(5000)

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self._hover_timer.stop()

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        self._click_count += 1
        self._click_timer.start(1200)
        if self._click_count >= 5:
            self._click_count = 0
            self._trigger_confetti()

    def _reset_clicks(self):
        self._click_count = 0

    def _main_window(self):
        w = self
        while w:
            if isinstance(w, QMainWindow): return w
            w = w.parentWidget()
        return None

    def _on_hover_egg(self):
        """悬停 5 秒 → 烟花从 Logo 处爆发"""
        mw = self._main_window()
        if not mw: return
        import random, math
        from PyQt5.QtCore import QPropertyAnimation, QPoint
        center = self.mapTo(mw, self.rect().center())
        firework_emoji = ["🎆","✨","💫","⭐","🌟","🎇","💥","🔥"]
        for _ in range(30):
            lbl = QLabel(random.choice(firework_emoji), mw)
            lbl.setStyleSheet(f"font-size:{random.randint(14,32)}px;background:transparent;")
            lbl.move(center); lbl.show()
            angle = random.uniform(0, 2 * math.pi)
            dist = random.randint(120, 350)
            end = QPoint(center.x() + int(math.cos(angle) * dist),
                         center.y() + int(math.sin(angle) * dist))
            anim = QPropertyAnimation(lbl, b"pos")
            anim.setDuration(random.randint(800, 1600))
            anim.setStartValue(center); anim.setEndValue(end)
            from PyQt5.QtCore import QEasingCurve
            anim.setEasingCurve(QEasingCurve.OutQuad)
            anim.finished.connect(lbl.deleteLater)
            anim.start(); lbl._anim = anim

    def _trigger_confetti(self):
        """连续点击 5 次 → emoji 从天而降"""
        mw = self._main_window()
        if not mw: return
        import random
        from datetime import datetime
        from PyQt5.QtCore import QPropertyAnimation, QPoint, QEasingCurve
        md = (datetime.now().month, datetime.now().day)
        holiday = {
            (1,1):["🎆","🥳","🎊","🎉","✨"],  (2,14):["💝","💕","💗","🥰","💌"],
            (5,1):["🎊","🎉","🌸","✨","🌟"],   (10,1):["🇨🇳","🎆","🎉","✨","💫"],
            (10,31):["🎃","👻","🍬","⭐","✨"],  (12,25):["🎄","🎅","❄️","🎁","✨"],
        }
        pool = holiday.get(md, ["✨","🎉","🚀","💡","🌟","💎","🦋","🌈","🧸","💫","⭐","🌸","🎈","🎵","💗","🌙","🦄"])
        for _ in range(25):
            lbl = QLabel(random.choice(pool), mw)
            lbl.setStyleSheet(f"font-size:{random.randint(18,42)}px;background:transparent;")
            x = random.randint(0, mw.width() - 40)
            lbl.move(x, -40); lbl.show()
            anim = QPropertyAnimation(lbl, b"pos")
            anim.setDuration(random.randint(1500, 3500))
            anim.setStartValue(lbl.pos())
            anim.setEndValue(QPoint(x + random.randint(-60, 60), mw.height() + 40))
            anim.setEasingCurve(QEasingCurve.OutQuad)
            anim.finished.connect(lbl.deleteLater)
            anim.start(); lbl._anim = anim


class _RoundMenu(QMenu):
    """圆角右键菜单 — FramelessWindowHint + 自绘圆角背景 + mask 裁切"""
    _R = 10  # corner radius

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            self.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 让 Qt 的默认 QMenu 绘制不画背景，只画菜单项
        self.setStyleSheet("QMenu{background:transparent;border:none;}")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(),
                            self._R, self._R)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self._R
        rect = self.rect()
        is_dark = isinstance(_C, dict) and _C.get("bg") == "#1C1C1E"
        bg = QColor(_C.get("elev", "#FFF")) if isinstance(_C, dict) else QColor("#FFF")
        brd = QColor(0, 0, 0, 18) if not is_dark else QColor(255, 255, 255, 18)
        path = QPainterPath()
        path.addRoundedRect(
            rect.x() + 0.5, rect.y() + 0.5,
            rect.width() - 1.0, rect.height() - 1.0,
            float(r), float(r))
        p.fillPath(path, bg)
        p.setPen(QPen(brd, 0.5))
        p.drawPath(path)
        p.end()
        super().paintEvent(e)


def _div():
    d = QFrame(); d.setObjectName("Div"); d.setFrameShape(QFrame.HLine); return d


def _md2html(text):
    """Markdown → HTML — 让 AI 回复像 Claude 一样优雅"""
    import re as _re
    # 转义 HTML
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # 加粗
    text = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # 斜体
    text = _re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    # 行内代码
    text = _re.sub(r'`([^`]+)`', r'<code style="background:rgba(0,0,0,0.06);border-radius:3px;padding:1px 4px;font-family:Menlo,monospace;font-size:10px;">\1</code>', text)
    # 列表项 (- item)
    text = _re.sub(r'^- (.+)$', r'<div style="margin:2px 0;padding-left:12px;text-indent:-8px;">·  \1</div>', text, flags=_re.MULTILINE)
    # 数字列表 (1. item)
    text = _re.sub(r'^(\d+)\. (.+)$', r'<div style="margin:2px 0;padding-left:12px;text-indent:-12px;">\1. \2</div>', text, flags=_re.MULTILINE)
    # 段落换行
    text = text.replace('\n\n', '<div style="height:8px;"></div>')
    text = text.replace('\n', '<br>')
    return text


def _card(level="md"):
    """统一阴影层级: sm=微弱, md=默认卡片, lg=悬浮"""
    _SHADOW = {"sm":(12,2,8), "md":(20,4,12), "lg":(28,6,16)}
    blur, y, a = _SHADOW.get(level, _SHADOW["md"])
    c = QFrame(); c.setObjectName("Card")
    s = QGraphicsDropShadowEffect(); s.setBlurRadius(blur); s.setOffset(0,y); s.setColor(QColor(0,0,0,a))
    c.setGraphicsEffect(s); return c


# ═══════════════════════════════════════════════════════════════
#  拖拽区
# ═══════════════════════════════════════════════════════════════

class DropZone(QFrame):
    files_dropped = pyqtSignal(list)
    def __init__(self):
        super().__init__(); self.setObjectName("DZ"); self.setAcceptDrops(True)
        self.setFixedHeight(140); self.setCursor(Qt.PointingHandCursor)

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0,0,0,0)

        # ── Page 0: 拖拽提示 ──
        p0 = QWidget(); p0.setStyleSheet("background:transparent;")
        lo0 = QHBoxLayout(p0); lo0.setAlignment(Qt.AlignCenter); lo0.setSpacing(16)
        lo0.setContentsMargins(32,20,32,20)
        ic = QLabel("📥"); ic.setStyleSheet("font-size:36px;background:transparent;"); lo0.addWidget(ic)
        txt = QVBoxLayout(); txt.setSpacing(3)
        t = QLabel("将 PDF 拖放至此处"); t.setObjectName("DZTitle"); txt.addWidget(t)
        s = QLabel("或点击浏览 · 支持批量"); s.setObjectName("DZSub"); txt.addWidget(s)
        lo0.addLayout(txt); lo0.addStretch()
        self._stack.addWidget(p0)

        # ── Page 1: 文件列表 ──
        p1 = QWidget(); p1.setStyleSheet("background:transparent;")
        lo1 = QVBoxLayout(p1); lo1.setContentsMargins(10,6,10,4); lo1.setSpacing(3)

        self._zotero_hint = QLabel("📚 Zotero 文献 · 译文自动保存回原位")
        self._zotero_hint.setStyleSheet(
            "font-size:10px;color:#1a56db;background:#e8f0fe;"
            "border-radius:3px;padding:2px 6px;")
        self._zotero_hint.setVisible(False)
        lo1.addWidget(self._zotero_hint)

        self.flist = QListWidget()
        self.flist.setSelectionMode(QListWidget.ExtendedSelection)
        lo1.addWidget(self.flist)

        fbtn = QHBoxLayout(); fbtn.setSpacing(6)
        self._fcount_label = QLabel(""); self._fcount_label.setObjectName("Cap")
        self._fcount_label.setStyleSheet("font-size:10px;background:transparent;")
        fbtn.addWidget(self._fcount_label); fbtn.addStretch()
        self._add_btn = QPushButton("＋ 添加"); self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.setStyleSheet("font-size:10px;padding:1px 8px;border:1px solid #ccc;border-radius:3px;background:transparent;")
        fbtn.addWidget(self._add_btn)
        self._del_btn = QPushButton("删除选中"); self._del_btn.setObjectName("TB"); self._del_btn.setCursor(Qt.PointingHandCursor)
        self._del_btn.setStyleSheet("font-size:10px;padding:1px 6px;")
        fbtn.addWidget(self._del_btn)
        self._clr_btn = QPushButton("清空"); self._clr_btn.setObjectName("GhDanger"); self._clr_btn.setCursor(Qt.PointingHandCursor)
        self._clr_btn.setStyleSheet("font-size:10px;padding:1px 6px;")
        fbtn.addWidget(self._clr_btn)
        lo1.addLayout(fbtn)
        self._stack.addWidget(p1)

    def dragEnterEvent(self, e):
        c = _C
        self.setStyleSheet(
            f"#DZ{{background:{c['acc_l']};border:2.5px solid {c['acc']};"
            f"border-radius:14px;}}")
        # 呼吸脉动动画
        from PyQt5.QtCore import QPropertyAnimation
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(600); anim.setLoopCount(-1)  # 无限循环
        anim.setStartValue(1.0); anim.setEndValue(0.85)
        # QWidget 没有 windowOpacity，用 graphicsEffect 模拟缩放
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(20); effect.setOffset(0, 0)
        effect.setColor(QColor(c['acc']))
        self.setGraphicsEffect(effect)
        self._drag_effect = effect
        e.acceptProposedAction()
    def dragLeaveEvent(self, e):
        self.setStyleSheet("")
        self.setGraphicsEffect(None)
        self._drag_effect = None
    def dragMoveEvent(self, e):
        e.acceptProposedAction()
    def dropEvent(self, e):
        self.setStyleSheet("")
        self.setGraphicsEffect(None)
        import glob
        fs = []
        md = e.mimeData()

        def _collect(p):
            """从路径收集 PDF：文件直接加，文件夹递归扫描"""
            if p.lower().endswith('.pdf') and os.path.isfile(p):
                fs.append(p)
            elif os.path.isdir(p):
                fs.extend(sorted(glob.glob(
                    os.path.join(p, '**', '*.pdf'), recursive=True)))

        # 1) 标准 file URL（Finder 拖文件/文件夹、Zotero 拖 PDF 附件）
        for u in md.urls():
            p = u.toLocalFile()
            if p:
                _collect(p)

        # 检测是否来自 Zotero（macOS 拖多个条目时 URL 只含一个文件）
        _from_zotero = False
        if fs:
            from ui.translate_worker import detect_zotero_source
            _from_zotero = any(detect_zotero_source(f) for f in fs)

        # 2) text/plain 中的 file:// 路径或本地路径
        if not fs and md.hasText():
            for line in md.text().strip().splitlines():
                line = line.strip()
                if line.startswith("file://"):
                    from PyQt5.QtCore import QUrl
                    line = QUrl(line).toLocalFile()
                if line and os.path.exists(line):
                    _collect(line)

        # 3) Zotero 自定义 MIME（同进程或支持跨进程的平台）
        if not fs:
            from ui.translate_worker import resolve_zotero_items, resolve_zotero_collection
            zot_data = md.data("zotero/item")
            if zot_data and len(zot_data):
                try:
                    import json as _json
                    raw = bytes(zot_data).decode("utf-8", errors="ignore").strip()
                    try:
                        parsed = _json.loads(raw)
                        if isinstance(parsed, dict) and "itemIDs" in parsed:
                            item_ids = [int(x) for x in parsed["itemIDs"]]
                        elif isinstance(parsed, list):
                            item_ids = [int(x) for x in parsed]
                        elif isinstance(parsed, int):
                            item_ids = [parsed]
                        else:
                            item_ids = []
                    except (ValueError, TypeError):
                        item_ids = [int(x) for x in raw.split(",")
                                    if x.strip().isdigit()]
                    if item_ids:
                        fs = resolve_zotero_items(item_ids)
                except Exception:
                    pass
            if not fs:
                zot_coll = md.data("zotero/collection")
                if zot_coll and len(zot_coll):
                    try:
                        raw = bytes(zot_coll).decode("utf-8", errors="ignore").strip()
                        if raw:
                            fs = resolve_zotero_collection(raw)
                    except Exception:
                        pass

        # 4) macOS 跨进程 Zotero：text/plain 匹配标题/集合名
        #    也在 layer 1 仅拿到部分 Zotero URL 时运行，补全缺失的文件
        if (not fs or _from_zotero) and md.hasText():
            try:
                from ui.translate_worker import (
                    resolve_zotero_by_title, resolve_zotero_collection_by_name)
                txt = md.text().strip()
                if txt:
                    extra = resolve_zotero_by_title(txt)
                    existing = set(fs)
                    for f in extra:
                        if f not in existing:
                            fs.append(f)
                            existing.add(f)
                if not fs and txt:
                    fs = resolve_zotero_collection_by_name(txt)
            except Exception:
                pass

        self.setStyleSheet("")  # 恢复默认样式
        if fs:
            self.files_dropped.emit(fs)
    def mousePressEvent(self, e):
        if self._stack.currentIndex() == 0:
            fs, _ = QFileDialog.getOpenFileNames(self, "选择 PDF", "", "PDF (*.pdf)")
            if fs: self.files_dropped.emit(fs)


class SummaryCard(QFrame):
    """智能摘要卡片 — 可折叠，点击按钮调用 AI 生成结构化摘要"""
    def __init__(self):
        super().__init__()
        self.setObjectName("Card")
        lo = QVBoxLayout(self); lo.setContentsMargins(16, 10, 16, 10); lo.setSpacing(6)
        # 头部
        hdr = QHBoxLayout(); hdr.setSpacing(8)
        ic = QLabel("✨"); ic.setStyleSheet("font-size:14px;background:transparent;")
        hdr.addWidget(ic)
        t = QLabel("智能摘要"); t.setStyleSheet("font-size:13px;font-weight:600;background:transparent;")
        hdr.addWidget(t); hdr.addStretch()
        self._svc_label = QLabel("")
        self._svc_label.setStyleSheet("font-size:10px;color:gray;background:transparent;")
        hdr.addWidget(self._svc_label)
        self.gen_btn = QPushButton("生成摘要"); self.gen_btn.setObjectName("Sc")
        self.gen_btn.setCursor(Qt.PointingHandCursor)
        self.gen_btn.setStyleSheet("font-size:11px;padding:3px 12px;")
        self.gen_btn.clicked.connect(self._generate)
        hdr.addWidget(self.gen_btn)
        self._collapse_btn = QPushButton("▼"); self._collapse_btn.setObjectName("Gh")
        self._collapse_btn.setFixedSize(24, 24); self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.setStyleSheet("font-size:10px;padding:0;")
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        hdr.addWidget(self._collapse_btn)
        lo.addLayout(hdr)
        # 内容区
        self._body = QLabel("")
        self._body.setWordWrap(True); self._body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._body.setStyleSheet("font-size:12px;line-height:160%;background:transparent;padding:4px 0;")
        self._body.setVisible(False)
        lo.addWidget(self._body)
        self._collapsed = False
        self._worker = None
        self._pdf_path = None
        # 检测 AI 服务（优先使用独立助手配置）
        from ui.ai_client import detect_assistant_service
        svc = detect_assistant_service()
        if svc:
            self._svc_label.setText(f"via {svc['name']}")
        else:
            self.gen_btn.setEnabled(False)
            self.gen_btn.setToolTip("请在设置中配置 AI 服务 API Key")

    def set_pdf(self, path):
        self._pdf_path = path
        self._body.setText(""); self._body.setVisible(False)
        self._collapse_btn.setText("▼")

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed and bool(self._body.text()))
        self._collapse_btn.setText("▶" if self._collapsed else "▼")

    def _generate(self):
        if not self._pdf_path or not os.path.exists(self._pdf_path):
            return
        # 刷新服务检测（优先使用独立助手配置）
        from ui.ai_client import detect_assistant_service
        svc = detect_assistant_service()
        if not svc:
            self._body.setText("⚠️ 未配置 AI 服务。请在设置页配置 API Key（如 DeepSeek、OpenAI 等）")
            self._body.setVisible(True)
            return
        self._svc_label.setText(f"via {svc['name']}")
        self.gen_btn.setEnabled(False); self.gen_btn.setText("生成中…")
        self._body.setText("⏳ 正在分析论文，请稍候…"); self._body.setVisible(True)
        self._collapsed = False; self._collapse_btn.setText("▼")
        self._worker = SummaryWorker(self._pdf_path)
        self._worker.result.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(lambda: self._cleanup())
        self._worker.start()

    def _on_result(self, text):
        self._body.setText(text)
        self._body.setVisible(True)

    def _on_error(self, err):
        self._body.setText(f"⚠️ {err}")
        self._body.setVisible(True)

    def _cleanup(self):
        self.gen_btn.setEnabled(True); self.gen_btn.setText("生成摘要")
        if self._worker:
            w = self._worker; self._worker = None
            w.quit(); QTimer.singleShot(100, lambda: w.deleteLater() if not w.isRunning() else None)


class SB(QWidget):
    """侧边栏按钮 — 图标固定宽度 + 文字对齐"""
    clicked = pyqtSignal()
    def __init__(self, icon, label):
        super().__init__()
        self.setFixedHeight(32); self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("SB"); self.setProperty("active", False)
        lo = QHBoxLayout(self); lo.setContentsMargins(12,0,12,0); lo.setSpacing(0)
        self._icon = QLabel(icon); self._icon.setFixedWidth(24); self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setStyleSheet("font-size:16px;background:transparent;border:none;")
        self._label = QLabel(label)
        self._label.setStyleSheet("font-size:13px;background:transparent;border:none;padding-left:8px;")
        lo.addWidget(self._icon); lo.addWidget(self._label); lo.addStretch()
    def set_active(self, v):
        self.setProperty("active", v); self.style().unpolish(self); self.style().polish(self)
    def mousePressEvent(self, e):
        self.clicked.emit()


# ═══════════════════════════════════════════════════════════════
#  PDF 预览 — 支持 MONO / DUAL / Side-by-Side 三模式切换
# ═══════════════════════════════════════════════════════════════

class PDFPageWidget(QLabel):
    def __init__(self):
        super().__init__(); self.setAlignment(Qt.AlignCenter)
    def set_pixmap(self, px):
        self.setPixmap(px)
        self.setFixedSize(px.size())


from PyQt5.QtCore import QObject, QTimer

class _PinchFilter(QObject):
    """全局捕获 macOS 触控板双指缩放 (NativeGesture)"""
    def __init__(self, preview):
        super().__init__(preview)
        self._preview = preview
        self._pending = False

    def _is_preview_child(self, widget):
        """检查 widget 是否属于 preview 控件树"""
        try:
            w = widget
            for _ in range(30):
                if w is self._preview:
                    return True
                p = w.parentWidget() if hasattr(w, 'parentWidget') else None
                if p is None:
                    return False
                w = p
        except RuntimeError:
            return False
        return False

    def _do_zoom(self):
        """延迟执行缩放，避免在事件处理期间修改控件树"""
        self._pending = False
        try:
            acc = self._preview._pinch_accumulator
            if abs(acc) > 0.08:
                new_zoom = self._preview.zoom * (1.0 + acc * 0.15)
                new_zoom = max(0.3, min(new_zoom, 5.0))
                self._preview._pinch_accumulator = 0.0
                self._preview._apply_zoom(new_zoom)
        except (RuntimeError, AttributeError):
            pass

    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.NativeGesture:
                if event.gestureType() == Qt.ZoomNativeGesture and self._is_preview_child(obj):
                    self._preview._pinch_accumulator += event.value()
                    if not self._pending and abs(self._preview._pinch_accumulator) > 0.08:
                        self._pending = True
                        QTimer.singleShot(0, self._do_zoom)
                    return True
        except (RuntimeError, AttributeError):
            pass
        return False


class _AutoGrowTextEdit(QWidget):
    """自适应高度的输入框 — 内容少时单行，多时自动向上增长（最多 5 行）"""
    returnPressed = pyqtSignal()

    def __init__(self, placeholder=""):
        super().__init__()
        lo = QVBoxLayout(self); lo.setContentsMargins(0, 0, 0, 0); lo.setSpacing(0)
        from PyQt5.QtWidgets import QTextEdit
        self._te = QTextEdit()
        self._te.setPlaceholderText(placeholder)
        self._te.setAcceptRichText(False)
        self._te.setStyleSheet(
            f"QTextEdit{{background:transparent;border:none;"
            f"padding:4px 6px;font-size:13px;font-family:'Helvetica Neue','PingFang SC';"
            f"color:{_C['t1']};}}")
        self._te.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._te.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._te.document().contentsChanged.connect(self._adjust_height)
        self._te.installEventFilter(self)
        lo.addWidget(self._te)
        self._min_h = 36; self._max_h = 120
        self._te.setFixedHeight(self._min_h)

    def text(self):
        return self._te.toPlainText()

    def clear(self):
        self._te.clear()

    def setPlaceholderText(self, t):
        self._te.setPlaceholderText(t)

    def _adjust_height(self):
        """只在实际行数变化时调整高度（按行跳变，不逐像素增长）"""
        line_h = 20  # 13px font ≈ 20px line height
        doc_h = self._te.document().size().height()
        new_lines = max(1, round(doc_h / line_h))
        if not hasattr(self, '_cur_lines'):
            self._cur_lines = 1
        if new_lines != self._cur_lines:
            self._cur_lines = new_lines
            target_h = max(self._min_h, min(new_lines * line_h + 8, self._max_h))
            self._te.setFixedHeight(target_h)

    def eventFilter(self, obj, event):
        if obj == self._te and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers():
                self.returnPressed.emit()
                return True
        return super().eventFilter(obj, event)


class _FlowLayout(QLayout):
    """自动换行布局 — 按钮放不下时自动折行，避免文字被截断"""
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._items = []
        self._spacing = spacing

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, idx): return self._items[idx] if 0 <= idx < len(self._items) else None
    def takeAt(self, idx):
        if 0 <= idx < len(self._items):
            return self._items.pop(idx)
        return None

    def expandingDirections(self): return Qt.Orientations()
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._do_layout(QRect(0, 0, w, 0), test=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test=False)

    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        s = QSize()
        for item in self._items:
            s = s.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        s += QSize(m.left() + m.right(), m.top() + m.bottom())
        return s

    def _do_layout(self, rect, test=False):
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = effective.x(), effective.y()
        line_h = 0
        sp = self._spacing if self._spacing >= 0 else 4
        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            if x + w > effective.right() + 1 and line_h > 0:
                x = effective.x()
                y += line_h + sp
                line_h = 0
            if not test:
                item.setGeometry(QRect(x, y, w, h))
            x += w + sp
            line_h = max(line_h, h)
        return y + line_h - rect.y() + m.bottom()


# ── AI 快捷操作 预设库 ──────────────────────────────────────────
# id 用于标识，label 显示在按钮上，prompt 是发给 LLM 的指令
# type="summary" 走 SummaryWorker（内置摘要引擎），其余走 QAWorker

_BUILTIN_PROMPTS = [
    {
        "id": "summary", "label": "📝 摘要", "prompt": "", "type": "summary",
        "desc": "结构化论文摘要（内置引擎）",
    },
    {
        "id": "explain", "label": "📖 讲解",
        "desc": "通俗讲解论文核心内容",
        "prompt": (
            "请用通俗易懂的语言讲解这篇论文，假设读者具有本科水平但不熟悉该细分领域。\n\n"
            "请按以下结构输出：\n"
            "## 一句话总结\n用一句话概括论文在做什么。\n\n"
            "## 研究背景\n这个领域之前遇到了什么问题？为什么需要这项研究？\n\n"
            "## 核心方法\n作者提出了什么方法或思路？用类比或直觉解释，避免公式。\n\n"
            "## 主要发现\n实验结果说明了什么？和之前的方法相比有什么提升？\n\n"
            "## 为什么重要\n这项工作对该领域或实际应用有什么意义？"
        ),
    },
    {
        "id": "questions", "label": "❓ 深度提问",
        "desc": "生成 5 个深度问题帮助理解",
        "prompt": (
            "请基于这篇论文，提出 5 个有深度的问题，帮助读者批判性地理解论文内容。\n\n"
            "要求：\n"
            "- 每个问题聚焦论文的不同方面（方法、实验、假设、局限性、应用前景等）\n"
            "- 每个问题后附 2-3 句解释，说明为什么这个问题值得思考\n"
            "- 问题应该有启发性，而非简单的事实复述\n\n"
            "格式：\n**Q1: [问题]**\n[为什么值得思考]\n\n依此类推。"
        ),
    },
    {
        "id": "critique", "label": "🔍 批判分析",
        "desc": "评估论文的优缺点和局限性",
        "prompt": (
            "请对这篇论文进行批判性分析，像一位资深审稿人一样思考。\n\n"
            "请从以下维度评价：\n"
            "## 主要优点\n论文在方法、实验设计、写作等方面做得好的地方（2-3 点）\n\n"
            "## 潜在不足\n方法论上的局限、实验设计的缺陷、未讨论的边界条件（2-3 点）\n\n"
            "## 可信度评估\n实验结果是否充分支撑了论文的结论？有没有过度声称？\n\n"
            "## 改进建议\n如果你是作者，你会在哪些方面做进一步的工作？"
        ),
    },
    {
        "id": "methods", "label": "🧪 方法详解",
        "desc": "深入解析论文的技术方法",
        "prompt": (
            "请深入解析这篇论文的技术方法，适合有一定基础的读者。\n\n"
            "请涵盖：\n"
            "## 问题形式化\n论文要解决的问题是如何数学/形式化定义的？\n\n"
            "## 方法流程\n按步骤描述方法的完整流程，用编号列表。\n\n"
            "## 关键创新点\n和现有方法相比，核心创新在哪里？\n\n"
            "## 实验设置\n用了什么数据集、基线方法、评估指标？\n\n"
            "## 核心结果\n最重要的实验结论是什么？数据支撑如何？"
        ),
    },
    {
        "id": "related", "label": "🔗 相关工作",
        "desc": "梳理论文引用的相关研究脉络",
        "prompt": (
            "请梳理这篇论文的相关工作和研究脉络。\n\n"
            "请输出：\n"
            "## 研究领域定位\n这篇论文属于哪个研究方向？\n\n"
            "## 关键前置工作\n论文建立在哪些重要的前人工作之上？列出 3-5 篇最重要的，并说明关系。\n\n"
            "## 方法演进\n该领域的方法是如何一步步发展到本文的？用时间线或逻辑链描述。\n\n"
            "## 与竞争方法的对比\n本文方法与最相近的竞争方法有什么本质区别？"
        ),
    },
    {
        "id": "application", "label": "💡 应用场景",
        "desc": "分析论文成果的实际应用可能性",
        "prompt": (
            "请分析这篇论文的研究成果可以如何应用到实际场景中。\n\n"
            "请涵盖：\n"
            "## 直接应用\n基于论文当前的成果，最可能直接落地的应用场景是什么？\n\n"
            "## 潜在扩展\n如果进一步发展，还可能应用在哪些领域？\n\n"
            "## 落地挑战\n从研究到实际部署，可能遇到哪些技术或工程上的困难？\n\n"
            "## 商业价值\n这项技术对行业可能产生什么影响？"
        ),
    },
    {
        "id": "keyterms", "label": "📚 术语表",
        "desc": "提取并解释论文中的关键术语",
        "prompt": (
            "请提取这篇论文中的关键专业术语和概念，生成一个术语表。\n\n"
            "要求：\n"
            "- 提取 8-12 个最重要的术语\n"
            "- 每个术语给出：中文翻译（如适用）、一句话定义、在论文中的具体含义\n"
            "- 按照术语在论文中出现的逻辑顺序排列\n\n"
            "格式：\n**术语名** (English Term)\n定义：...\n论文中的含义：..."
        ),
    },
]

# 默认激活的 3 个（显示在快捷栏上）
_DEFAULT_ACTIVE_IDS = ["summary", "explain", "questions"]


class QAPanelWidget(QWidget):
    """AI 论文助手面板 — 可自定义快捷操作库 + 聊天界面"""

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(260); self.setMaximumWidth(420)
        self._busy = False  # 是否有 worker 在运行
        lo = QVBoxLayout(self); lo.setContentsMargins(12, 10, 12, 12); lo.setSpacing(0)

        # ── 头部 ──
        hdr = QHBoxLayout(); hdr.setSpacing(6)
        t = QLabel("AI 助手"); t.setStyleSheet(
            "font-size:13px;font-weight:600;background:transparent;letter-spacing:0.3px;")
        hdr.addWidget(t); hdr.addStretch()
        self._svc_label = QLabel("")
        self._svc_label.setStyleSheet(f"font-size:10px;color:{_C['t3']};background:transparent;")
        hdr.addWidget(self._svc_label)
        clr = QPushButton("清空"); clr.setObjectName("Gh")
        clr.setStyleSheet("font-size:10px;padding:2px 6px;")
        clr.setCursor(Qt.PointingHandCursor); clr.clicked.connect(self._clear)
        hdr.addWidget(clr)
        self._cfg_btn = QPushButton("⚙")
        self._cfg_btn.setCursor(Qt.PointingHandCursor)
        self._cfg_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;font-size:13px;"
            f"padding:2px 5px;color:{_C['t3']};}}"
            f"QPushButton:hover{{color:{_C['acc']};}}")
        self._cfg_btn.clicked.connect(self._open_settings)
        hdr.addWidget(self._cfg_btn)
        lo.addLayout(hdr)
        lo.addSpacing(6)

        # ── 快捷操作栏 ──
        self._quick_frame = QFrame()
        self._quick_frame.setStyleSheet("QFrame{background:transparent;border:none;}")
        self._quick_layout = QHBoxLayout(self._quick_frame)
        self._quick_layout.setContentsMargins(0, 0, 0, 0)
        self._quick_layout.setSpacing(6)
        self._quick_btns = []
        lo.addWidget(self._quick_frame)
        lo.addSpacing(8)

        # ── 聊天区 ──
        self._chat_scroll = QScrollArea(); self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setFrameShape(QFrame.NoFrame)
        self._chat_container = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(0, 4, 0, 4); self._chat_layout.setSpacing(12)
        self._chat_layout.setAlignment(Qt.AlignTop)
        self._chat_scroll.setWidget(self._chat_container)
        lo.addWidget(self._chat_scroll, 1)
        lo.addSpacing(8)

        # ── 输入区 ──
        self._inp_frame = QFrame()
        self._inp_frame.setStyleSheet(
            f"QFrame{{background:{_C['card']};border:0.5px solid {_C['brd']};"
            f"border-radius:12px;}}")
        inp_lo = QHBoxLayout(self._inp_frame)
        inp_lo.setContentsMargins(10, 6, 6, 6); inp_lo.setSpacing(6)
        self._input = _AutoGrowTextEdit("输入问题…")
        inp_lo.addWidget(self._input, 1)
        self._send_btn = QPushButton("发送"); self._send_btn.setObjectName("Pr")
        self._send_btn.setStyleSheet("font-size:11px;padding:6px 16px;border-radius:8px;")
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.clicked.connect(self._send)
        self._send_btn.setFixedHeight(32)
        inp_lo.addWidget(self._send_btn, 0, Qt.AlignBottom)
        lo.addWidget(self._inp_frame)
        self._input.returnPressed.connect(self._send)
        self._char_count = None

        # ── 状态 ──
        self._paper_text = ""
        self._pdf_path = None
        self._messages = []
        self._worker = None
        self._summary_worker = None
        self._current_ai_bubble = None
        self._streaming_text = ""

        # 加载 prompt 库 & 激活列表
        self._load_library()

    # ══════════════════════════════════════════════════════════════
    #  Prompt 库 & 持久化
    # ══════════════════════════════════════════════════════════════

    def _load_library(self):
        """从配置加载 prompt 库和激活列表"""
        cfg = UserConfigManager.load()
        # 库：内置 + 用户自定义
        saved_lib = cfg.get("ai_prompt_library", None)
        if saved_lib is not None:
            self._library = saved_lib
        else:
            self._library = [dict(p) for p in _BUILTIN_PROMPTS]
        # 激活的 ID 列表（显示在快捷栏，最多 3 个）
        self._active_ids = cfg.get("ai_active_ids", list(_DEFAULT_ACTIVE_IDS))
        self._rebuild_quick_bar()

    def _save_library(self):
        cfg = UserConfigManager.load()
        cfg["ai_prompt_library"] = self._library
        cfg["ai_active_ids"] = self._active_ids
        UserConfigManager.save(cfg)

    def _get_active_prompts(self):
        """返回当前激活的 prompt 列表（按 _active_ids 顺序）"""
        id_map = {p["id"]: p for p in self._library}
        return [id_map[aid] for aid in self._active_ids if aid in id_map]

    # ══════════════════════════════════════════════════════════════
    #  快捷栏
    # ══════════════════════════════════════════════════════════════

    def _rebuild_quick_bar(self):
        """根据激活列表重建快捷按钮 — 等宽圆角药丸"""
        while self._quick_layout.count():
            item = self._quick_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._quick_btns = []
        c = _C
        for prompt_data in self._get_active_prompts():
            b = QPushButton(prompt_data["label"])
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setFixedHeight(32)
            b.setStyleSheet(
                f"QPushButton{{background:{c['card']};border:0.5px solid {c['card_b']};"
                f"border-radius:16px;padding:0 10px;font-size:12px;color:{c['t1']};}}"
                f"QPushButton:hover{{background:{c['acc_l']};border-color:{c['acc']};}}"
                f"QPushButton:pressed{{background:{c['acc']};color:white;"
                f"border-color:{c['acc']};}}"
                f"QPushButton:disabled{{opacity:0.5;}}")
            pid = prompt_data["id"]
            b.clicked.connect(lambda _, _pid=pid: self._exec_by_id(_pid))
            self._quick_layout.addWidget(b, 1)  # stretch=1 等宽分布
            self._quick_btns.append(b)

    def _exec_by_id(self, prompt_id):
        """执行指定 ID 的快捷操作"""
        try:
            if self._busy:
                return
            id_map = {p["id"]: p for p in self._library}
            act = id_map.get(prompt_id)
            if not act:
                return
            if act.get("type") == "summary":
                self._run_summary()
            else:
                prompt = act.get("prompt", "")
                if prompt:
                    self._run_preset(prompt, act.get("label", ""))
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════
    #  ⚙ 设置弹窗 — prompt 库管理 + 激活选择
    # ══════════════════════════════════════════════════════════════

    def _open_settings(self):
        """打开 prompt 库配置弹窗"""
        try:
            self._do_open_settings()
        except Exception:
            pass

    def _do_open_settings(self):
        c = _C
        dlg = QDialog(self)
        dlg.setWindowTitle("AI 快捷操作配置")
        dlg.setMinimumSize(520, 580)
        dlg.resize(560, 660)
        dlg.setStyleSheet(f"""
            QDialog{{background:{c['bg']};}}
            QLabel{{color:{c['t1']};background:transparent;}}
            QScrollArea{{background:{c['bg']};border:none;}}
            QWidget#scroll_inner{{background:{c['bg']};}}
            QLineEdit{{background:{c['inp']};border:1px solid {c['inp_b']};
                border-radius:6px;padding:6px 10px;font-size:13px;color:{c['t1']};
                min-height:20px;}}
            QLineEdit:focus{{border-color:{c['acc']};}}
            QPlainTextEdit{{background:{c['inp']};border:1px solid {c['inp_b']};
                border-radius:8px;padding:8px 10px;font-size:12px;color:{c['t1']};
                line-height:160%;}}
            QPlainTextEdit:focus{{border-color:{c['acc']};}}
            QCheckBox{{color:{c['t1']};spacing:6px;}}
            QCheckBox::indicator{{width:18px;height:18px;border-radius:5px;
                border:1.5px solid {c['inp_b']};background:{c['inp']};}}
            QCheckBox::indicator:checked{{background:{c['acc']};border-color:{c['acc']};}}
        """)
        dlo = QVBoxLayout(dlg); dlo.setContentsMargins(24, 20, 24, 18); dlo.setSpacing(14)

        # ── 标题行 ──
        hdr = QHBoxLayout()
        title = QLabel("快捷操作库"); title.setStyleSheet("font-size:16px;font-weight:600;")
        hdr.addWidget(title); hdr.addStretch()
        hint_l = QLabel("勾选最多 3 个显示在快捷栏")
        hint_l.setStyleSheet(f"font-size:11px;color:{c['t3']};")
        hdr.addWidget(hint_l)
        dlo.addLayout(hdr)

        # ── 滚动区 ──
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget(); container.setObjectName("scroll_inner")
        clo = QVBoxLayout(container); clo.setContentsMargins(0, 0, 0, 0); clo.setSpacing(10)
        clo.setAlignment(Qt.AlignTop)

        _cards = []  # list of entry dicts

        def _make_card(p, parent_layout):
            pid = p.get("id", "")
            tp = p.get("type", "")
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:{c['card']};border:0.5px solid {c['card_b']};"
                f"border-radius:12px;}}")
            card_lo = QVBoxLayout(card)
            card_lo.setContentsMargins(14, 12, 14, 12); card_lo.setSpacing(8)

            # ── 第一行：勾选 + 名称 + 删除 ──
            r1 = QHBoxLayout(); r1.setSpacing(10)
            cb = QCheckBox()
            cb.setFixedSize(22, 22)
            cb.setChecked(pid in self._active_ids)
            cb.setToolTip("勾选后显示在快捷栏")
            r1.addWidget(cb, 0, Qt.AlignVCenter)
            name_inp = QLineEdit(p.get("label", "")); name_inp.setMaxLength(12)
            name_inp.setPlaceholderText("按钮名称")
            name_inp.setFixedHeight(32)
            r1.addWidget(name_inp, 1, Qt.AlignVCenter)
            is_builtin = any(bp["id"] == pid for bp in _BUILTIN_PROMPTS)
            del_btn = QPushButton("×")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setFixedSize(26, 26)
            del_btn.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;color:{c['t3']};"
                f"font-size:16px;font-weight:600;border-radius:13px;}}"
                f"QPushButton:hover{{background:rgba(255,59,48,0.1);color:{c['err']};}}")
            if is_builtin:
                del_btn.setVisible(False)
            r1.addWidget(del_btn, 0, Qt.AlignVCenter)
            card_lo.addLayout(r1)

            # ── 第二行：描述 ──
            desc = p.get("desc", "")
            if desc:
                dl = QLabel(desc)
                dl.setStyleSheet(f"font-size:11px;color:{c['t3']};padding-left:32px;")
                card_lo.addWidget(dl)

            # ── 第三行：Prompt 编辑 ──
            if tp == "summary":
                hl = QLabel("🔧 内置摘要引擎，自动分析论文结构并生成结构化摘要")
                hl.setStyleSheet(
                    f"font-size:11px;color:{c['t3']};padding:6px 10px;"
                    f"background:{c['bg2']};border-radius:6px;")
                hl.setWordWrap(True)
                card_lo.addWidget(hl)
                prompt_inp = None
            else:
                prompt_inp = QPlainTextEdit()
                prompt_inp.setPlainText(p.get("prompt", ""))
                prompt_inp.setPlaceholderText("输入提示词…\n\n描述你希望 AI 对论文做什么分析")
                prompt_inp.setMinimumHeight(90)
                prompt_inp.setMaximumHeight(200)
                card_lo.addWidget(prompt_inp)

            parent_layout.addWidget(card)
            entry = {"cb": cb, "name": name_inp, "prompt": prompt_inp,
                     "id": pid, "type": tp, "card": card}
            _cards.append(entry)

            # 删除
            def _del(_, _e=entry):
                _e["card"].setVisible(False)
                _e["card"].deleteLater()
                _e["deleted"] = True
            del_btn.clicked.connect(_del)

            # 勾选约束：最多 3 个
            def _on_check(state, _e=entry):
                checked = [e for e in _cards
                           if not e.get("deleted") and e["cb"].isChecked()]
                if len(checked) > 3:
                    _e["cb"].setChecked(False)
            cb.stateChanged.connect(_on_check)

        for p in self._library:
            _make_card(p, clo)

        scroll.setWidget(container)
        dlo.addWidget(scroll, 1)

        # ── 底部按钮区 ──
        blo = QHBoxLayout(); blo.setSpacing(8)
        # 新建
        add_btn = QPushButton("＋ 新建")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(
            f"QPushButton{{background:{c['acc_l']};border:none;border-radius:8px;"
            f"padding:8px 14px;font-size:12px;color:{c['acc']};}}"
            f"QPushButton:hover{{background:{c['acc']};color:white;}}")
        _counter = [0]
        def _on_add():
            _counter[0] += 1
            new_p = {"id": f"custom_{_counter[0]}_{id(dlg)}",
                     "label": "🔧 自定义", "prompt": "", "desc": "自定义提示词"}
            _make_card(new_p, clo)
            QTimer.singleShot(50, lambda: scroll.verticalScrollBar().setValue(
                scroll.verticalScrollBar().maximum()))
        add_btn.clicked.connect(_on_add)
        blo.addWidget(add_btn)

        # 导入
        imp_btn = QPushButton("📥 导入")
        imp_btn.setCursor(Qt.PointingHandCursor)
        imp_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {c['inp_b']};"
            f"border-radius:8px;padding:8px 14px;font-size:12px;color:{c['t2']};}}"
            f"QPushButton:hover{{border-color:{c['acc']};color:{c['acc']};}}")
        def _on_import():
            path, _ = QFileDialog.getOpenFileName(
                dlg, "导入提示词",
                str(Path.home()),
                "文本文件 (*.txt *.md);;JSON (*.json);;所有文件 (*)")
            if not path:
                return
            try:
                content = Path(path).read_text(encoding="utf-8")
                fname = Path(path).stem
                # 尝试 JSON
                try:
                    data = json.loads(content)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        _counter[0] += 1
                        new_p = {
                            "id": f"import_{_counter[0]}_{id(dlg)}",
                            "label": item.get("label", f"📥 {fname}"),
                            "prompt": item.get("prompt", content),
                            "desc": item.get("desc", "导入的提示词"),
                        }
                        _make_card(new_p, clo)
                except (json.JSONDecodeError, AttributeError):
                    # 纯文本 → 整个文件内容作为 prompt
                    _counter[0] += 1
                    new_p = {
                        "id": f"import_{_counter[0]}_{id(dlg)}",
                        "label": f"📥 {fname[:8]}",
                        "prompt": content,
                        "desc": "导入的提示词",
                    }
                    _make_card(new_p, clo)
                QTimer.singleShot(50, lambda: scroll.verticalScrollBar().setValue(
                    scroll.verticalScrollBar().maximum()))
            except Exception as e:
                QMessageBox.warning(dlg, "导入失败", str(e))
        imp_btn.clicked.connect(_on_import)
        blo.addWidget(imp_btn)

        # 恢复默认
        reset_btn = QPushButton("恢复默认")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {c['inp_b']};"
            f"border-radius:8px;padding:8px 14px;font-size:12px;color:{c['t2']};}}"
            f"QPushButton:hover{{border-color:{c['acc']};color:{c['acc']};}}")
        def _on_reset():
            for entry in _cards:
                entry["deleted"] = True
                entry["card"].setVisible(False)
                entry["card"].deleteLater()
            _cards.clear()
            for p in _BUILTIN_PROMPTS:
                _make_card(dict(p), clo)
            for entry in _cards:
                entry["cb"].setChecked(entry["id"] in _DEFAULT_ACTIVE_IDS)
        reset_btn.clicked.connect(_on_reset)
        blo.addWidget(reset_btn)

        blo.addStretch()
        ok_btn = QPushButton("保存")
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet(
            f"QPushButton{{background:{c['acc']};color:white;border:none;"
            f"font-size:13px;padding:8px 30px;border-radius:8px;}}"
            f"QPushButton:hover{{background:{c['acc_h']};}}")
        ok_btn.clicked.connect(dlg.accept)
        blo.addWidget(ok_btn)
        dlo.addLayout(blo)

        # ── 执行弹窗 ──
        if dlg.exec_() == QDialog.Accepted:
            new_library = []
            new_active = []
            for entry in _cards:
                if entry.get("deleted"):
                    continue
                try:
                    label = entry["name"].text().strip()
                except RuntimeError:
                    continue
                if not label:
                    continue
                p = {"id": entry["id"], "label": label, "type": entry["type"]}
                p["desc"] = next((bp.get("desc", "") for bp in _BUILTIN_PROMPTS
                                  if bp["id"] == entry["id"]), "自定义提示词")
                if entry["type"] == "summary":
                    p["prompt"] = ""
                else:
                    p["prompt"] = entry["prompt"].toPlainText() if entry["prompt"] else ""
                new_library.append(p)
                if entry["cb"].isChecked():
                    new_active.append(entry["id"])
            if new_active:
                self._library = new_library
                self._active_ids = new_active[:3]
                self._save_library()
                self._rebuild_quick_bar()

    # ══════════════════════════════════════════════════════════════
    #  论文上下文 & 聊天
    # ══════════════════════════════════════════════════════════════

    def set_paper_context(self, pdf_path):
        """提取 PDF 文本作为问答上下文"""
        self._pdf_path = pdf_path
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for i in range(min(15, len(doc))):
                text += doc[i].get_text()
            doc.close()
            self._paper_text = text[:10000]
        except Exception:
            self._paper_text = ""
        self._messages = []
        self._clear()
        try:
            from ui.ai_client import detect_assistant_service
            svc = detect_assistant_service()
            self._svc_label.setText(f"via {svc['name']} · {svc['model']}" if svc else "未配置")
            self._send_btn.setEnabled(bool(svc))
        except Exception:
            pass

    def _clear(self):
        try:
            self._messages = []
            self._current_ai_bubble = None
            self._stop_workers()
            while self._chat_layout.count():
                w = self._chat_layout.takeAt(0).widget()
                if w:
                    w.deleteLater()
        except Exception:
            pass

    def _add_bubble(self, text, is_user=True):
        """添加消息气泡"""
        row = QWidget(); row.setStyleSheet("background:transparent;")
        row_lo = QHBoxLayout(row)
        row_lo.setContentsMargins(0, 0, 0, 0); row_lo.setSpacing(0)
        bubble = QLabel()
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bubble.setMaximumWidth(300)
        c = _C
        if is_user:
            bubble.setText(text)
            bubble.setStyleSheet(
                f"background:{c['acc']};color:white;border-radius:12px;"
                f"border-bottom-right-radius:4px;"
                f"padding:8px 12px;font-size:12px;"
                f"font-family:'Helvetica Neue','PingFang SC';")
            row_lo.addStretch(); row_lo.addWidget(bubble)
        else:
            bubble.setTextFormat(Qt.RichText)
            html = _md2html(text) if text and not text.startswith('⏳') else text
            bubble.setText(html)
            bubble.setStyleSheet(
                f"background:{c['card']};border:0.5px solid {c['card_b']};"
                f"border-radius:12px;border-top-left-radius:4px;"
                f"padding:10px 14px;font-size:12px;line-height:165%;"
                f"font-family:'Helvetica Neue','PingFang SC';")
            row_lo.addWidget(bubble); row_lo.addStretch()
        self._chat_layout.addWidget(row)
        QTimer.singleShot(50, lambda: self._safe_scroll_bottom())
        return bubble

    def _safe_scroll_bottom(self):
        try:
            sb = self._chat_scroll.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════
    #  AI Worker 管理（摘要 / 问答 / 流式）
    # ══════════════════════════════════════════════════════════════

    def _set_busy(self, busy):
        self._busy = busy
        try:
            self._send_btn.setEnabled(not busy)
            for b in self._quick_btns:
                b.setEnabled(not busy)
        except Exception:
            pass

    def _run_summary(self):
        """使用 SummaryWorker 生成结构化摘要"""
        try:
            if not self._pdf_path or not os.path.exists(self._pdf_path):
                return
            from ui.ai_client import detect_assistant_service
            svc = detect_assistant_service()
            if not svc:
                self._add_bubble("⚠️ 未配置 AI 服务", is_user=False)
                return
            self._stop_workers()
            self._set_busy(True)
            self._add_bubble("📝 生成摘要", is_user=True)
            self._current_ai_bubble = self._add_bubble("⏳ 正在分析论文…", is_user=False)
            self._summary_worker = SummaryWorker(self._pdf_path)
            self._summary_worker.result.connect(self._on_summary_result)
            self._summary_worker.error.connect(self._on_qa_error)
            self._summary_worker.finished.connect(self._on_summary_done)
            self._summary_worker.start()
        except Exception:
            self._set_busy(False)

    def _run_preset(self, prompt, label=""):
        """用预设 prompt 发起问答"""
        try:
            if not self._paper_text:
                return
            from ui.ai_client import detect_assistant_service
            svc = detect_assistant_service()
            if not svc:
                self._add_bubble("⚠️ 未配置 AI 服务", is_user=False)
                return
            self._stop_workers()
            self._set_busy(True)
            self._add_bubble(label or (prompt[:15] + "…"), is_user=True)
            self._messages = [
                {"role": "system", "content": (
                    "你是论文阅读助手。以下是论文全文内容（可能被截断），请根据论文内容回答用户问题。\n"
                    "回答要准确、有深度，用中文。使用 Markdown 格式化输出。\n"
                    "如果论文中没有相关信息，请如实说明。\n\n"
                    f"论文内容：\n{self._paper_text}"
                )},
                {"role": "user", "content": prompt},
            ]
            self._current_ai_bubble = self._add_bubble("⏳ 思考中…", is_user=False)
            self._worker = QAWorker(list(self._messages))
            self._worker.chunk.connect(self._on_chunk)
            self._worker.finished.connect(self._on_qa_done)
            self._worker.error.connect(self._on_qa_error)
            self._worker.start()
            self._streaming_text = ""
        except Exception:
            self._set_busy(False)

    def _stop_workers(self):
        """断开并停止所有 AI worker"""
        for attr in ('_worker', '_summary_worker'):
            w = getattr(self, attr, None)
            if w:
                for sig in ('chunk', 'result', 'finished', 'error'):
                    try:
                        getattr(w, sig).disconnect()
                    except Exception:
                        pass
                setattr(self, attr, None)
                try:
                    w.quit()
                except Exception:
                    pass

    @staticmethod
    def _widget_alive(w):
        try:
            w.objectName()
            return True
        except RuntimeError:
            return False

    def _on_summary_result(self, text):
        try:
            if self._current_ai_bubble and self._widget_alive(self._current_ai_bubble):
                self._current_ai_bubble.setText(_md2html(text))
                QTimer.singleShot(0, self._safe_scroll_bottom)
        except Exception:
            pass

    def _on_summary_done(self):
        try:
            self._set_busy(False)
            self._current_ai_bubble = None
            if self._summary_worker:
                w = self._summary_worker; self._summary_worker = None
                w.quit()
        except Exception:
            self._set_busy(False)

    def _on_chunk(self, text):
        try:
            self._streaming_text += text
            if self._current_ai_bubble and self._widget_alive(self._current_ai_bubble):
                self._current_ai_bubble.setText(_md2html(self._streaming_text))
                QTimer.singleShot(0, self._safe_scroll_bottom)
        except Exception:
            pass

    def _on_qa_done(self, full_text):
        try:
            if self._current_ai_bubble and self._widget_alive(self._current_ai_bubble):
                self._current_ai_bubble.setText(_md2html(full_text))
            self._messages.append({"role": "assistant", "content": full_text})
            self._set_busy(False)
            self._current_ai_bubble = None
            if self._worker:
                w = self._worker; self._worker = None
                w.quit()
        except Exception:
            self._set_busy(False)

    def _on_qa_error(self, err):
        try:
            if self._current_ai_bubble and self._widget_alive(self._current_ai_bubble):
                self._current_ai_bubble.setText(f"⚠️ {err}")
            self._set_busy(False)
            self._current_ai_bubble = None
            for attr in ('_worker', '_summary_worker'):
                w = getattr(self, attr, None)
                if w:
                    setattr(self, attr, None)
                    w.quit()
        except Exception:
            self._set_busy(False)

    def _send(self):
        try:
            q = self._input.text().strip()
            if not q or not self._paper_text or self._busy:
                return
            self._stop_workers()
            self._input.clear()
            self._set_busy(True)
            self._add_bubble(q, is_user=True)
            if not self._messages:
                self._messages.append({
                    "role": "system",
                    "content": (
                        "你是论文阅读助手。以下是论文全文内容（可能被截断），请根据论文内容回答用户问题。\n"
                        "回答要准确、有深度，用中文。使用 Markdown 格式化输出。\n"
                        "如果论文中没有相关信息，请如实说明。\n\n"
                        f"论文内容：\n{self._paper_text}"
                    )
                })
            self._messages.append({"role": "user", "content": q})
            self._current_ai_bubble = self._add_bubble("⏳ 思考中…", is_user=False)
            self._worker = QAWorker(list(self._messages))
            self._worker.chunk.connect(self._on_chunk)
            self._worker.finished.connect(self._on_qa_done)
            self._worker.error.connect(self._on_qa_error)
            self._worker.start()
            self._streaming_text = ""
        except Exception:
            self._set_busy(False)

    # ══════════════════════════════════════════════════════════════
    #  主题切换
    # ══════════════════════════════════════════════════════════════

    def update_theme(self, c):
        try:
            self._svc_label.setStyleSheet(f"font-size:10px;color:{c['t3']};background:transparent;")
            self._inp_frame.setStyleSheet(
                f"QFrame{{background:{c['card']};border:0.5px solid {c['brd']};"
                f"border-radius:12px;}}")
            self._quick_frame.setStyleSheet("QFrame{background:transparent;border:none;}")
            self._rebuild_quick_bar()
            self._cfg_btn.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;font-size:13px;"
                f"padding:2px 5px;color:{c['t3']};}}"
                f"QPushButton:hover{{color:{c['acc']};}}")
        except Exception:
            pass


class PreviewPage(QWidget):
    """三合一预览: 顶部模式切换按钮 + PDF 显示"""
    fullscreen_toggled = pyqtSignal(bool)
    history_toggled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.doc = None
        self.current_page = 0
        self.zoom = 1.5
        self.output_files = {}
        self.current_mode = "side_by_side"  # 默认 Side by Side
        self.setFocusPolicy(Qt.StrongFocus)  # 接收键盘事件

        lo = QVBoxLayout(self); lo.setContentsMargins(0,0,0,0); lo.setSpacing(0)

        # 工具栏
        tb = QWidget(); tb.setObjectName("PT"); tb.setFixedHeight(48)
        tl = QHBoxLayout(tb); tl.setContentsMargins(12,0,12,0); tl.setSpacing(6)

        # 模式切换按钮
        self.mode_btns = {}
        for label, mode in [("Dual","dual"),("Mono","mono"),("Side by Side","side_by_side")]:
            b = QPushButton(label); b.setObjectName("TB"); b.setCursor(Qt.PointingHandCursor)
            b.setProperty("active", mode == "side_by_side")
            b.clicked.connect(lambda _, m=mode: self.switch_mode(m))
            tl.addWidget(b); self.mode_btns[mode] = b

        tl.addSpacing(8)
        # 连续滚动 / 单页 切换
        self._continuous = True
        self.scroll_btn = QPushButton("连续"); self.scroll_btn.setObjectName("TB")
        self.scroll_btn.setCursor(Qt.PointingHandCursor)
        self.scroll_btn.setProperty("active", True)
        self.scroll_btn.clicked.connect(self._toggle_continuous)
        tl.addWidget(self.scroll_btn)

        tl.addSpacing(12)
        ob = QPushButton("打开"); ob.setObjectName("Sc"); ob.setCursor(Qt.PointingHandCursor)
        ob.setStyleSheet("padding:6px 14px;font-size:13px;")
        ob.clicked.connect(self.open_file); tl.addWidget(ob)

        tl.addStretch()

        # 翻页：首页 < 上一页 | 页码输入 / 总页数 | 下一页 > 末页
        first_btn = QPushButton("⟨⟨"); first_btn.setObjectName("TB"); first_btn.setFixedWidth(32)
        first_btn.setCursor(Qt.PointingHandCursor)
        first_btn.clicked.connect(self.first_page); tl.addWidget(first_btn)

        prev_btn = QPushButton("‹"); prev_btn.setObjectName("TB"); prev_btn.setFixedWidth(32)
        prev_btn.setCursor(Qt.PointingHandCursor)
        prev_btn.clicked.connect(self.prev_page); tl.addWidget(prev_btn)

        # 页码输入框
        self.page_input = QLineEdit("1")
        self.page_input.setFixedWidth(42)
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.setObjectName("PageInput")
        self.page_input.returnPressed.connect(self._jump_to_page)
        tl.addWidget(self.page_input)

        self.total_label = QLabel("/ —")
        self.total_label.setObjectName("TotalLbl")
        tl.addWidget(self.total_label)

        next_btn = QPushButton("›"); next_btn.setObjectName("TB"); next_btn.setFixedWidth(32)
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.clicked.connect(self.next_page); tl.addWidget(next_btn)

        last_btn = QPushButton("⟩⟩"); last_btn.setObjectName("TB"); last_btn.setFixedWidth(32)
        last_btn.setCursor(Qt.PointingHandCursor)
        last_btn.clicked.connect(self.last_page); tl.addWidget(last_btn)

        tl.addStretch()

        # 缩放
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(30,400); self.zoom_slider.setValue(150)
        self.zoom_slider.setFixedWidth(90); self.zoom_slider.valueChanged.connect(self.on_zoom)
        tl.addWidget(self.zoom_slider)
        self.zoom_pct = QLabel("150%")
        self.zoom_pct.setObjectName("ZoomPct")
        self.zoom_pct.setFixedWidth(36)
        tl.addWidget(self.zoom_pct)
        # 适配模式：适宽 / 适页 两个按钮
        self._fit_mode = "width"   # "width" 适宽 | "page" 适页
        self.fit_btn = QPushButton("适宽"); self.fit_btn.setObjectName("TB")
        self.fit_btn.setCursor(Qt.PointingHandCursor)
        self.fit_btn.setProperty("active", True)
        self.fit_btn.clicked.connect(self._switch_to_fit_width)
        tl.addWidget(self.fit_btn)
        self.fitpage_btn = QPushButton("适页"); self.fitpage_btn.setObjectName("TB")
        self.fitpage_btn.setCursor(Qt.PointingHandCursor)
        self.fitpage_btn.clicked.connect(self._switch_to_fit_page)
        tl.addWidget(self.fitpage_btn)

        tl.addSpacing(6)
        self._is_fullscreen = False
        # 全屏中唤出历史面板
        self.hist_btn = QPushButton("历史"); self.hist_btn.setObjectName("TB")
        self.hist_btn.setCursor(Qt.PointingHandCursor)
        self.hist_btn.setVisible(False)
        self.hist_btn.clicked.connect(self.history_toggled.emit)
        tl.addWidget(self.hist_btn)
        # AI 问答按钮
        self.qa_btn = QPushButton("AI 问答"); self.qa_btn.setObjectName("TB")
        self.qa_btn.setCursor(Qt.PointingHandCursor)
        self.qa_btn.clicked.connect(self._toggle_qa_panel)
        tl.addWidget(self.qa_btn)
        # 高亮按钮
        self.hl_btn = QPushButton("高亮"); self.hl_btn.setObjectName("TB")
        self.hl_btn.setCursor(Qt.PointingHandCursor)
        self.hl_btn.setCheckable(True)
        self.hl_btn.clicked.connect(self._toggle_highlight)
        tl.addWidget(self.hl_btn)
        # 擦除按钮
        self.hl_erase_btn = QPushButton("擦除"); self.hl_erase_btn.setObjectName("TB")
        self.hl_erase_btn.setCursor(Qt.PointingHandCursor)
        self.hl_erase_btn.setCheckable(True)
        self.hl_erase_btn.clicked.connect(self._toggle_erase)
        self.hl_erase_btn.setVisible(False)  # 进入高亮模式才显示
        tl.addWidget(self.hl_erase_btn)
        # 全屏按钮
        self.fs_btn = QPushButton("全屏"); self.fs_btn.setObjectName("TB")
        self.fs_btn.setCursor(Qt.PointingHandCursor)
        self.fs_btn.clicked.connect(self._toggle_fullscreen)
        tl.addWidget(self.fs_btn)

        lo.addWidget(tb)

        # 内容区：缩略图 + 主视图（QSplitter 支持拖拽调整缩略图宽度）
        self.body_splitter = QSplitter(Qt.Horizontal)
        self.body_splitter.setHandleWidth(1)
        self.body_splitter.setChildrenCollapsible(True)

        # 缩略图面板
        self.thumb_scroll = QScrollArea()
        self.thumb_scroll.setMinimumWidth(60); self.thumb_scroll.setMaximumWidth(240)
        self.thumb_scroll.setWidgetResizable(True); self.thumb_scroll.setFrameShape(QFrame.NoFrame)
        self.thumb_scroll.setObjectName("PA"); self.thumb_scroll.setFocusPolicy(Qt.StrongFocus)
        self.thumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumb_container = QWidget(); self.thumb_container.setObjectName("PA")
        self.thumb_layout = QVBoxLayout(self.thumb_container)
        self.thumb_layout.setContentsMargins(4,6,4,6); self.thumb_layout.setSpacing(4)
        self.thumb_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.thumb_scroll.setWidget(self.thumb_container)
        self.thumb_scroll.setVisible(False)
        self.body_splitter.addWidget(self.thumb_scroll)

        # 主视图容器
        self._main_view = QWidget(); self._main_view.setObjectName("PA")
        _mv_lo = QHBoxLayout(self._main_view)
        _mv_lo.setContentsMargins(0,0,0,0); _mv_lo.setSpacing(0)

        # 主视图 — 单页模式
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignCenter); self.scroll.setObjectName("PA")
        self.page_widget = PDFPageWidget()
        self.page_widget.setStyleSheet("padding:2px;")
        shadow = QGraphicsDropShadowEffect(); shadow.setBlurRadius(28); shadow.setOffset(0,4)
        shadow.setColor(QColor(0,0,0,30)); self.page_widget.setGraphicsEffect(shadow)
        self.scroll.setWidget(self.page_widget)
        self._highlight_mode = False
        self._hl_erase_mode = False
        self._hl_start = None
        self._hl_overlay = None
        self.scroll.setVisible(False)  # 默认连续模式，隐藏单页
        _mv_lo.addWidget(self.scroll)

        # 主视图 — 连续滚动模式（默认显示）
        self.cont_scroll = QScrollArea(); self.cont_scroll.setWidgetResizable(True)
        self.cont_scroll.setObjectName("PA"); self.cont_scroll.setVisible(True)
        self.cont_container = QWidget(); self.cont_container.setObjectName("PA")
        self.cont_layout = QVBoxLayout(self.cont_container)
        self.cont_layout.setContentsMargins(0,0,0,0); self.cont_layout.setSpacing(4)
        self.cont_layout.setAlignment(Qt.AlignHCenter)
        self.cont_scroll.setWidget(self.cont_container)
        self.cont_scroll.verticalScrollBar().valueChanged.connect(self._on_cont_scroll)
        _mv_lo.addWidget(self.cont_scroll)
        self._cont_page_widgets = []

        self.body_splitter.addWidget(self._main_view)
        # AI 问答面板（右侧，默认隐藏）
        self.qa_panel = QAPanelWidget()
        self.qa_panel.setVisible(False)
        self.body_splitter.addWidget(self.qa_panel)
        self.body_splitter.setSizes([140, 800, 0])
        self.body_splitter.setCollapsible(0, True)   # 缩略图可折叠
        self.body_splitter.setCollapsible(1, False)
        self.body_splitter.setCollapsible(2, True)   # QA 面板可折叠
        # 拖拽缩略图面板宽度时自动重建缩略图
        self.body_splitter.splitterMoved.connect(self._on_thumb_panel_resized)
        self.body_widget = self.body_splitter  # 兼容引用
        lo.addWidget(self.body_splitter)

        # 空状态
        self.empty = QWidget(); self.empty.setObjectName("PA")
        el = QVBoxLayout(self.empty); el.setAlignment(Qt.AlignCenter); el.setSpacing(16)
        el.setContentsMargins(40, 40, 40, 40)
        ic = QLabel(); ic.setFixedSize(64, 64); ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet(f"background:{_C['acc_l']};border-radius:32px;font-size:28px;")
        ic.setText("👀"); self._empty_icon = ic; el.addWidget(ic, alignment=Qt.AlignCenter)
        m = QLabel("翻译完成后在此预览"); m.setStyleSheet(f"font-size:15px;font-weight:600;color:{_C['t1']};"); m.setAlignment(Qt.AlignCenter); el.addWidget(m)
        s = QLabel("支持 Dual · Mono · Side by Side 三种模式切换"); s.setObjectName("Cap"); s.setAlignment(Qt.AlignCenter); el.addWidget(s)
        s2 = QLabel("← 也可点击左侧历史记录直接打开"); s2.setStyleSheet(f"font-size:11px;color:{_C['t3']};"); s2.setAlignment(Qt.AlignCenter); el.addWidget(s2)
        self.body_widget.setVisible(False); lo.addWidget(self.empty)
        self._thumb_labels = []

        # 滚轮缩放
        self.scroll.wheelEvent = self._wheel_event
        self.cont_scroll.wheelEvent = self._wheel_event
        # macOS 触控板双指缩放：用独立 QObject 做全局 eventFilter（安全）
        self._pinch_accumulator = 0.0
        self._pinch_filter = _PinchFilter(self)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self._pinch_filter)

    def _apply_zoom(self, new_zoom):
        """统一缩放处理"""
        self.zoom = new_zoom
        slider_val = int(new_zoom * 100)
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(min(slider_val, 400))
        self.zoom_slider.blockSignals(False)
        self.zoom_pct.setText(f"{slider_val}%")
        if self._continuous:
            self._render_continuous()
        else:
            self.render_page()

    def _reset_fit(self):
        """还原到当前适配模式的最佳贴合"""
        if self.doc:
            if self._fit_mode == "page":
                self._fit_page()
            else:
                self._fit_width()
            if self._continuous:
                self._render_continuous()
            else:
                self.render_page()

    def _wheel_event(self, event):
        """滚轮翻页 + Ctrl+滚轮缩放"""
        mods = event.modifiers()

        # Ctrl + 滚轮 = 缩放
        if mods & Qt.ControlModifier:
            delta = event.angleDelta().y()
            step = 0.1 if delta > 0 else -0.1
            self._apply_zoom(max(0.5, min(self.zoom + step, 4.0)))
            return

        # 连续滚动模式：自然滚动
        if self._continuous:
            target = self.cont_scroll
            QScrollArea.wheelEvent(target, event)
            return

        # 单页模式：到边界翻页
        sb = self.scroll.verticalScrollBar()
        delta = event.angleDelta().y()
        at_bottom = sb.value() >= sb.maximum()
        at_top = sb.value() <= sb.minimum()

        if delta < 0 and at_bottom:
            self.next_page()
        elif delta > 0 and at_top:
            self.prev_page()
        else:
            QScrollArea.wheelEvent(self.scroll, event)

    def set_output_files(self, files: dict):
        """翻译完成后设置三种文件路径"""
        self.output_files = files
        self.switch_mode(self.current_mode)

    def switch_mode(self, mode):
        self.current_mode = mode
        for m, b in self.mode_btns.items():
            b.setProperty("active", m == mode)
            b.style().unpolish(b); b.style().polish(b)

        path = self.output_files.get(mode, "")
        if path and os.path.exists(path):
            self.load_pdf(path)
            return
        if self.output_files:
            # 回退到有文件的模式
            for fallback in ["dual", "mono", "side_by_side"]:
                fp = self.output_files.get(fallback, "")
                if fp and os.path.exists(fp):
                    self.load_pdf(fp); break

    def load_pdf(self, path):
        try:
            same_file = (path == getattr(self, '_loaded_path', None) and self.doc)
            if not same_file:
                self._loaded_path = path
                self.doc = fitz.open(path)
                self.current_page = 0
                self._last_thumb_vp_w = -1  # 强制首次重建缩略图
                self._last_fit_zoom = -1   # 强制首次渲染
            self.empty.setVisible(False)
            self.body_widget.setVisible(True)
            self.thumb_scroll.setVisible(True)
            # 视口已就绪 → 立即贴合渲染（zoom 未变则跳过）
            vp = self.scroll.viewport() if not self._continuous else self.cont_scroll.viewport()
            if vp.width() >= 100:
                self._fit_and_render()
            else:
                QTimer.singleShot(0, self._fit_and_render)
            # 设置 AI 面板上下文
            if not same_file:
                self.qa_panel.set_paper_context(path)
        except Exception as e:
            self.page_widget.setText(f"加载失败: {e}")

    def _toggle_qa_panel(self):
        """切换 AI 问答面板 — 即时更新布局"""
        vis = not self.qa_panel.isVisible()
        self.qa_panel.setVisible(vis)
        self.qa_btn.setProperty("active", vis)
        self.qa_btn.style().unpolish(self.qa_btn); self.qa_btn.style().polish(self.qa_btn)
        if vis:
            sizes = self.body_splitter.sizes()
            self.body_splitter.setSizes([sizes[0], max(sizes[1] - 300, 400), 300])
        else:
            sizes = self.body_splitter.sizes()
            self.body_splitter.setSizes([sizes[0], sizes[1] + sizes[2], 0])
        # 立即重新适配渲染，确保 PDF 视图即时伸缩
        QTimer.singleShot(0, self._fit_and_render)

    def _toggle_highlight(self):
        """切换高亮标注模式"""
        self._highlight_mode = self.hl_btn.isChecked()
        self._hl_erase_mode = False
        self.hl_btn.setProperty("active", self._highlight_mode)
        self.hl_btn.style().unpolish(self.hl_btn); self.hl_btn.style().polish(self.hl_btn)
        # 显示/隐藏擦除按钮
        self.hl_erase_btn.setVisible(self._highlight_mode)
        if not self._highlight_mode:
            self.hl_erase_btn.setChecked(False)
            self.hl_erase_btn.setProperty("active", False)
            self.hl_erase_btn.style().unpolish(self.hl_erase_btn)
            self.hl_erase_btn.style().polish(self.hl_erase_btn)
        cursor = Qt.CrossCursor if self._highlight_mode else Qt.ArrowCursor
        if self._continuous:
            for w in self._cont_page_widgets:
                w.setCursor(cursor)
        else:
            self.page_widget.setCursor(cursor)

    def _toggle_erase(self):
        """切换擦除模式（高亮模式的子模式）"""
        self._hl_erase_mode = self.hl_erase_btn.isChecked()
        self.hl_erase_btn.setProperty("active", self._hl_erase_mode)
        self.hl_erase_btn.style().unpolish(self.hl_erase_btn)
        self.hl_erase_btn.style().polish(self.hl_erase_btn)

    # ── 高亮标注 ──

    def _hl_mouse_press(self, e, page_idx, label):
        if not getattr(self, '_highlight_mode', False):
            return
        if e.button() == Qt.LeftButton:
            self._hl_start = e.pos()
            self._hl_page_idx = page_idx
            self._hl_label = label
            # 擦除模式：按了擦除按钮 或 按住 Option 键
            is_erase = getattr(self, '_hl_erase_mode', False) or (e.modifiers() & Qt.AltModifier)
            self._hl_dragging_delete = bool(is_erase)
            if is_erase:
                # 红色半透明删除覆盖层
                if not hasattr(self, '_hl_del_overlay') or self._hl_del_overlay is None:
                    self._hl_del_overlay = QWidget(label)
                    self._hl_del_overlay.setStyleSheet(
                        "background:rgba(255,59,48,0.18);border:1.5px solid rgba(255,59,48,0.6);border-radius:3px;")
                from PyQt5.QtCore import QRect
                self._hl_del_overlay.setGeometry(QRect(self._hl_start, QSize()))
                self._hl_del_overlay.show()
                self._hl_del_overlay.raise_()
            else:
                # 蓝色添加高亮覆盖层
                if not hasattr(self, '_hl_overlay') or self._hl_overlay is None:
                    from PyQt5.QtWidgets import QRubberBand
                    self._hl_overlay = QRubberBand(QRubberBand.Rectangle, label)
                from PyQt5.QtCore import QRect
                self._hl_overlay.setGeometry(QRect(self._hl_start, QSize()))
                self._hl_overlay.show()

    def _hl_mouse_move(self, e, label):
        if not getattr(self, '_highlight_mode', False) or not hasattr(self, '_hl_start'):
            return
        if self._hl_start is None:
            return
        from PyQt5.QtCore import QRect
        if getattr(self, '_hl_dragging_delete', False):
            if hasattr(self, '_hl_del_overlay') and self._hl_del_overlay:
                self._hl_del_overlay.setGeometry(QRect(self._hl_start, e.pos()).normalized())
        elif hasattr(self, '_hl_overlay') and self._hl_overlay:
            self._hl_overlay.setGeometry(QRect(self._hl_start, e.pos()).normalized())

    def _hl_mouse_release(self, e, page_idx, label):
        if not getattr(self, '_highlight_mode', False) or not hasattr(self, '_hl_start'):
            return
        try:
            # 隐藏覆盖层
            if hasattr(self, '_hl_overlay') and self._hl_overlay:
                self._hl_overlay.hide()
            if hasattr(self, '_hl_del_overlay') and self._hl_del_overlay:
                self._hl_del_overlay.hide()

            end = e.pos()
            start = self._hl_start
            is_delete = getattr(self, '_hl_dragging_delete', False)
            self._hl_start = None
            self._hl_dragging_delete = False

            if not self.doc:
                return

            is_small = abs(end.x() - start.x()) < 8 and abs(end.y() - start.y()) < 8

            if is_delete:
                # 擦除模式
                if is_small:
                    # 小范围点击 → 删除点击处的高亮
                    self._hl_delete_at(page_idx, end)
                else:
                    # 大范围框选 → 批量删除
                    self._hl_delete_in_rect(page_idx, start, end)
                return

            # 左键：添加高亮
            if is_small:
                return
            # 屏幕坐标 → PDF 坐标
            x0 = min(start.x(), end.x()) / self.zoom
            y0 = min(start.y(), end.y()) / self.zoom
            x1 = max(start.x(), end.x()) / self.zoom
            y1 = max(start.y(), end.y()) / self.zoom
            sel_rect = fitz.Rect(x0, y0, x1, y1)
            page = self.doc[page_idx]
            # 在选区内查找文字，按文字位置创建高亮
            words = page.get_text("words")
            quads = []
            for w in words:
                wr = fitz.Rect(w[:4])
                if sel_rect.intersects(wr):
                    quads.append(wr.quad)
            if not quads:
                return  # 选区内无文字（如图片 PDF），不添加
            annot = page.add_highlight_annot(quads=quads)
            annot.set_colors(stroke=(1, 0.85, 0.2))
            try:
                annot.set_opacity(0.35)
            except AttributeError:
                pass  # 旧版 PyMuPDF 无此方法
            annot.update()
            self._hl_save_and_render(page_idx)
        except Exception:
            pass  # 防止任何异常导致闪退

    def _hl_delete_in_rect(self, page_idx, start, end):
        """批量删除框选区域内的所有高亮"""
        try:
            if not self.doc:
                return
            x0 = min(start.x(), end.x()) / self.zoom
            y0 = min(start.y(), end.y()) / self.zoom
            x1 = max(start.x(), end.x()) / self.zoom
            y1 = max(start.y(), end.y()) / self.zoom
            sel_rect = fitz.Rect(x0, y0, x1, y1)
            page = self.doc[page_idx]
            annots = page.annots()
            if not annots:
                return
            # 收集要删除的高亮（不能边遍历边删除）
            to_del = [a for a in annots if a.type[0] == 8 and sel_rect.intersects(a.rect)]
            if not to_del:
                return
            for a in to_del:
                page.delete_annot(a)
            self._hl_save_and_render(page_idx)
        except Exception:
            pass

    def _hl_save_and_render(self, page_idx):
        """高亮变更后：保存文件 + 重新渲染"""
        path = getattr(self, '_loaded_path', None)
        if path:
            try:
                self.doc.save(path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            except Exception:
                try:
                    self.doc.save(path)
                except Exception:
                    pass
        if self._continuous:
            self._render_single_cont_page(page_idx)
        else:
            self.render_page()

    def _hl_delete_at(self, page_idx, pos):
        """删除点击位置的高亮注释"""
        try:
            if not self.doc:
                return
            page = self.doc[page_idx]
            px, py = pos.x() / self.zoom, pos.y() / self.zoom
            point = fitz.Point(px, py)
            annots = page.annots()
            if not annots:
                return
            for annot in annots:
                if annot.type[0] == 8 and annot.rect.contains(point):
                    page.delete_annot(annot)
                    self._hl_save_and_render(page_idx)
                    return
        except Exception:
            pass

    def _render_single_cont_page(self, page_idx):
        """重新渲染连续模式中的单个页面"""
        if page_idx < len(self._cont_page_widgets):
            label = self._cont_page_widgets[page_idx]
            dpr = label.devicePixelRatioF() if hasattr(label, 'devicePixelRatioF') else 1.0
            rz = self.zoom * dpr
            page = self.doc[page_idx]
            pix = page.get_pixmap(matrix=fitz.Matrix(rz, rz))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(dpr)
            label.setPixmap(pm)
            label.setFixedSize(pm.size() / dpr)

    def _install_highlight_events(self, label, page_idx):
        """给页面 widget 安装高亮鼠标事件
        高亮模式：左键拖拽添加 | 擦除模式/Option+拖拽：框选批量删除
        """
        orig_press = label.mousePressEvent
        orig_move = label.mouseMoveEvent
        orig_release = label.mouseReleaseEvent
        def _press(e):
            if getattr(self, '_highlight_mode', False):
                self._hl_mouse_press(e, page_idx, label)
            else:
                orig_press(e)
        def _move(e):
            if getattr(self, '_highlight_mode', False):
                self._hl_mouse_move(e, label)
            else:
                orig_move(e)
        def _release(e):
            if getattr(self, '_highlight_mode', False):
                self._hl_mouse_release(e, page_idx, label)
            else:
                orig_release(e)
        label.mousePressEvent = _press
        label.mouseMoveEvent = _move
        label.mouseReleaseEvent = _release

    def _hl_show_delete_menu(self, e, page_idx, label):
        """右键菜单：删除点击位置的高亮"""
        if not self.doc:
            return
        page = self.doc[page_idx]
        px, py = e.pos().x() / self.zoom, e.pos().y() / self.zoom
        point = fitz.Point(px, py)
        # 检查是否有高亮在此位置
        found = False
        for annot in page.annots():
            if annot.type[0] == 8 and annot.rect.contains(point):
                found = True; break
        if not found:
            return
        menu = _RoundMenu(label)
        act = menu.addAction("删除高亮")
        act.triggered.connect(lambda: self._hl_delete_at(page_idx, e.pos()))
        menu.exec_(label.mapToGlobal(e.pos()))

    def _fit_and_render(self):
        """统一：计算贴合 + 渲染（只在尺寸真正变化时才重新渲染）"""
        if not self.doc:
            return
        # 缩略图面板宽度变了 → 重建缩略图
        cur_tw = self.thumb_scroll.viewport().width() if self.thumb_scroll.isVisible() else 0
        if cur_tw > 40 and cur_tw != getattr(self, '_last_thumb_vp_w', 0):
            self._last_thumb_vp_w = cur_tw
            self._build_thumbnails()
        # 计算 zoom，只有变了才重新渲染（避免重复工作）
        old_zoom = self.zoom
        if self._fit_mode == "page":
            self._fit_page()
        else:
            self._fit_width()
        if self.zoom != getattr(self, '_last_fit_zoom', -1):
            self._last_fit_zoom = self.zoom
            if self._continuous:
                self._render_continuous()
            else:
                self.render_page()

    def _build_thumbnails(self):
        """生成所有页面的缩略图"""
        # 清空旧缩略图
        for lbl in self._thumb_labels:
            lbl.setParent(None)
        self._thumb_labels = []

        if not self.doc:
            return

        dpr = QApplication.instance().devicePixelRatio() if QApplication.instance() else 2.0
        # 缩略图宽度 = 面板宽度 - 左右 margin(4+4) - border(2+2) - 滚动条余量
        panel_w = self.thumb_scroll.viewport().width() if self.thumb_scroll.viewport().width() > 40 else self.thumb_scroll.width()
        thumb_w = max(50, panel_w - 12)

        for i in range(len(self.doc)):
            page = self.doc[i]
            # 计算缩略图缩放比例
            scale = (thumb_w * dpr) / page.rect.width
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            qpx = QPixmap.fromImage(img)
            qpx.setDevicePixelRatio(dpr)

            lbl = QLabel()
            lbl.setPixmap(qpx)
            lbl.setFixedSize(int(pix.width / dpr) + 4, int(pix.height / dpr) + 4)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                "border:2px solid transparent;border-radius:4px;padding:1px;"
                "background:transparent;"
            )
            lbl.setCursor(Qt.PointingHandCursor)
            # 点击跳转
            page_idx = i
            lbl.mousePressEvent = lambda e, idx=page_idx: self._thumb_clicked(idx)

            self.thumb_layout.addWidget(lbl, alignment=Qt.AlignHCenter)
            self._thumb_labels.append(lbl)

        self.thumb_layout.addStretch()
        self._highlight_thumb(0)

    def _thumb_clicked(self, idx):
        self.current_page = idx
        if self._continuous and idx < len(self._cont_page_widgets):
            self.cont_scroll.ensureWidgetVisible(self._cont_page_widgets[idx], 0, 0)
            self._update_page_display()
            self._highlight_thumb(idx)
        else:
            self.render_page()
        self.setFocus()

    def _highlight_thumb(self, idx):
        """高亮当前页缩略图，颜色由 _thumb_color 控制"""
        color = getattr(self, '_thumb_color', _C['acc'])
        for i, lbl in enumerate(self._thumb_labels):
            if i == idx:
                lbl.setStyleSheet(
                    f"border:2px solid {color};border-radius:4px;padding:1px;"
                    "background:transparent;"
                )
            else:
                lbl.setStyleSheet(
                    "border:2px solid transparent;border-radius:4px;padding:1px;"
                    "background:transparent;"
                )
        if idx < len(self._thumb_labels):
            self.thumb_scroll.ensureWidgetVisible(self._thumb_labels[idx])

    def _fit_width(self):
        """自动计算缩放比例 — 所有模式统一 fit width"""
        if not self.doc or len(self.doc) == 0:
            return
        page = self.doc[0]
        pw = page.rect.width
        vp = self.scroll.viewport() if not self._continuous else self.cont_scroll.viewport()
        avail_w = vp.width() - 8
        if avail_w < 100 or pw <= 0:
            return
        optimal_zoom = avail_w / pw
        optimal_zoom = max(0.3, min(optimal_zoom, 3.0))
        self.zoom = optimal_zoom
        slider_val = int(optimal_zoom * 100)
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(slider_val)
        self.zoom_slider.blockSignals(False)
        self.zoom_pct.setText(f"{slider_val}%")

    def _fit_page(self):
        """自动计算缩放比例 — 整页适配 (宽高都不超出视口)"""
        if not self.doc or len(self.doc) == 0:
            return
        page = self.doc[0]
        pw, ph = page.rect.width, page.rect.height
        vp = self.scroll.viewport() if not self._continuous else self.cont_scroll.viewport()
        avail_w = vp.width() - 8
        avail_h = vp.height() - 8
        if avail_w < 100 or avail_h < 100 or pw <= 0 or ph <= 0:
            return
        zoom_w = avail_w / pw
        zoom_h = avail_h / ph
        optimal_zoom = min(zoom_w, zoom_h)
        optimal_zoom = max(0.3, min(optimal_zoom, 3.0))
        self.zoom = optimal_zoom
        slider_val = int(optimal_zoom * 100)
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(slider_val)
        self.zoom_slider.blockSignals(False)
        self.zoom_pct.setText(f"{slider_val}%")

    def _switch_to_fit_width(self):
        """切换到适宽模式"""
        self._fit_mode = "width"
        self.fit_btn.setProperty("active", True)
        self.fit_btn.style().unpolish(self.fit_btn); self.fit_btn.style().polish(self.fit_btn)
        self.fitpage_btn.setProperty("active", False)
        self.fitpage_btn.style().unpolish(self.fitpage_btn); self.fitpage_btn.style().polish(self.fitpage_btn)
        self._reset_fit()

    def _switch_to_fit_page(self):
        """切换到适页模式"""
        self._fit_mode = "page"
        self.fitpage_btn.setProperty("active", True)
        self.fitpage_btn.style().unpolish(self.fitpage_btn); self.fitpage_btn.style().polish(self.fitpage_btn)
        self.fit_btn.setProperty("active", False)
        self.fit_btn.style().unpolish(self.fit_btn); self.fit_btn.style().polish(self.fit_btn)
        self._reset_fit()

    def render_page(self):
        if not self.doc or self.current_page >= len(self.doc): return
        pg = self.doc[self.current_page]
        # Retina: 渲染 2x 分辨率再缩回，保证清晰
        dpr = QApplication.instance().devicePixelRatio() if QApplication.instance() else 2.0
        render_zoom = self.zoom * dpr
        mat = fitz.Matrix(render_zoom, render_zoom)
        pix = pg.get_pixmap(matrix=mat, alpha=False)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        qpix = QPixmap.fromImage(img)
        qpix.setDevicePixelRatio(dpr)
        self.page_widget.set_pixmap(qpix)
        # setFixedSize 用逻辑尺寸（物理尺寸 / dpr）
        self.page_widget.setFixedSize(int(pix.width / dpr), int(pix.height / dpr))
        self._install_highlight_events(self.page_widget, self.current_page)
        self._update_page_display()
        self._highlight_thumb(self.current_page)
        self.scroll.verticalScrollBar().setValue(0)

    def first_page(self):
        if self.doc:
            self.current_page = 0; self.render_page()
    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1; self.render_page()
    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1; self.render_page()
    def last_page(self):
        if self.doc:
            self.current_page = len(self.doc) - 1; self.render_page()
    def _jump_to_page(self):
        """页码输入框回车跳转，超范围闪红提示"""
        try:
            n = int(self.page_input.text()) - 1
            if self.doc and 0 <= n < len(self.doc):
                self.current_page = n; self.render_page()
                return
        except ValueError:
            pass
        # 输入无效：闪红 + 重置
        self.page_input.setStyleSheet(f"border:1.5px solid {_C['err']};border-radius:6px;")
        self.page_input.setText(str(self.current_page + 1) if self.doc else "")
        QTimer.singleShot(800, lambda: self.page_input.setStyleSheet(""))
    def _update_page_display(self):
        total = len(self.doc) if self.doc else 0
        self.page_input.setText(str(self.current_page + 1) if total else "")
        self.total_label.setText(f"/ {total}" if total else "/ —")
    def on_zoom(self, v):
        self.zoom = v / 100.0; self.zoom_pct.setText(f"{v}%")
        if self.doc:
            if self._continuous:
                self._render_continuous()
            else:
                self.render_page()
    def open_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF (*.pdf)")
        if p: self.load_pdf(p)
    def contextMenuEvent(self, event):
        if not self.doc:
            return
        menu = _RoundMenu(self)
        menu.addAction("打开其他 PDF…", self.open_file)
        menu.addSeparator()
        menu.addAction("放大", lambda: self._apply_zoom(min(self.zoom + 0.1, 4.0)))
        menu.addAction("缩小", lambda: self._apply_zoom(max(self.zoom - 0.1, 0.3)))
        menu.addAction("适合宽度", self._switch_to_fit_width)
        menu.addAction("适合页面", self._switch_to_fit_page)
        menu.addSeparator()
        lp = getattr(self, '_loaded_path', None)
        if lp and os.path.exists(lp):
            menu.addAction("在 Finder 中显示",
                           lambda: __import__("subprocess").Popen(["open", "-R", lp]))
        menu.exec_(event.globalPos())
    def _toggle_fullscreen(self):
        self._is_fullscreen = not self._is_fullscreen
        self.fs_btn.setText("退出" if self._is_fullscreen else "全屏")
        self.fs_btn.setProperty("active", self._is_fullscreen)
        self.fs_btn.style().unpolish(self.fs_btn); self.fs_btn.style().polish(self.fs_btn)
        self.hist_btn.setVisible(self._is_fullscreen)
        self.fullscreen_toggled.emit(self._is_fullscreen)
        QTimer.singleShot(80, self._on_resize_done)

    def _on_thumb_panel_resized(self):
        """拖拽分割线后重建缩略图 + 重新适配 PDF 视图"""
        if not hasattr(self, '_thumb_resize_timer'):
            self._thumb_resize_timer = QTimer(); self._thumb_resize_timer.setSingleShot(True)
            self._thumb_resize_timer.timeout.connect(self._rebuild_thumbs_fit)
        self._thumb_resize_timer.start(200)
        # 立即适配 PDF 视图大小（QA 面板伸缩时也需要）
        if not hasattr(self, '_fit_timer'):
            self._fit_timer = QTimer(); self._fit_timer.setSingleShot(True)
            self._fit_timer.timeout.connect(self._fit_and_render)
        self._fit_timer.start(50)

    def _rebuild_thumbs_fit(self):
        if self.doc and self.thumb_scroll.isVisible():
            self._build_thumbnails()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._is_fullscreen:
            self._toggle_fullscreen(); return
        if event.key() == Qt.Key_Up:
            self.prev_page()
        elif event.key() == Qt.Key_Down:
            self.next_page()
        elif event.key() == Qt.Key_Home:
            self.first_page()
        elif event.key() == Qt.Key_End:
            self.last_page()
        else:
            super().keyPressEvent(event)
    def mousePressEvent(self, event):
        """点击预览区域获取焦点，让键盘事件生效"""
        self.setFocus()
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        """窗口大小变化时重新适配"""
        super().resizeEvent(event)
        if self.doc:
            from PyQt5.QtCore import QTimer
            # 用定时器防止频繁重渲染
            if not hasattr(self, '_resize_timer'):
                self._resize_timer = QTimer(); self._resize_timer.setSingleShot(True)
                self._resize_timer.timeout.connect(self._on_resize_done)
            self._resize_timer.start(100)

    def _on_resize_done(self):
        self._fit_and_render()

    # ── 连续滚动模式 ──
    def _toggle_continuous(self):
        self._continuous = not self._continuous
        self.scroll_btn.setProperty("active", self._continuous)
        self.scroll_btn.style().unpolish(self.scroll_btn)
        self.scroll_btn.style().polish(self.scroll_btn)
        self.scroll.setVisible(not self._continuous)
        self.cont_scroll.setVisible(self._continuous)
        if self.doc:
            self._fit_and_render()
            # 延迟再算一次，等 scroll 显隐切换布局稳定
            QTimer.singleShot(0, self._fit_and_render)

    def _render_continuous(self):
        """分帧渲染所有页面到连续滚动容器（避免大文件卡 UI）"""
        if not self.doc:
            return
        # 清空旧内容
        for w in self._cont_page_widgets:
            w.setParent(None)
        self._cont_page_widgets = []
        self._cont_render_idx = 0
        self._cont_render_dpr = QApplication.instance().devicePixelRatio() if QApplication.instance() else 2.0

        # 先放置占位标签
        total = len(self.doc)
        for i in range(total):
            lbl = QLabel("加载中…" if i == 0 else "")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"background:transparent;color:{_C['t3']};font-size:11px;min-height:200px;")
            self.cont_layout.addWidget(lbl, alignment=Qt.AlignHCenter)
            self._cont_page_widgets.append(lbl)
        self._update_page_display()

        # 分帧渲染：每帧渲染 2 页
        self._render_batch_continuous()

    def _render_batch_continuous(self):
        """每次渲染 2 页，释放 UI 事件循环"""
        if not self.doc:
            return
        idx = getattr(self, '_cont_render_idx', 0)
        total = len(self.doc)
        dpr = self._cont_render_dpr
        batch = 2  # 每帧渲染页数
        for _ in range(batch):
            if idx >= total:
                return
            pg = self.doc[idx]
            render_zoom = self.zoom * dpr
            mat = fitz.Matrix(render_zoom, render_zoom)
            pix = pg.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            qpix = QPixmap.fromImage(img)
            qpix.setDevicePixelRatio(dpr)
            lbl = self._cont_page_widgets[idx]
            lbl.setPixmap(qpix)
            lbl.setFixedSize(int(pix.width / dpr), int(pix.height / dpr))
            lbl.setStyleSheet("background:transparent;")
            self._install_highlight_events(lbl, idx)
            idx += 1
        self._cont_render_idx = idx
        if idx < total:
            QTimer.singleShot(0, self._render_batch_continuous)

    def _on_cont_scroll(self, value):
        """连续滚动时更新页码和缩略图高亮"""
        if not self._continuous or not self._cont_page_widgets:
            return
        vp_center = value + self.cont_scroll.viewport().height() // 2
        for i, w in enumerate(self._cont_page_widgets):
            wy = w.y()
            if wy <= vp_center <= wy + w.height():
                if self.current_page != i:
                    self.current_page = i
                    self._update_page_display()
                    self._highlight_thumb(i)
                break

    def update_theme(self, c):
        """深色/浅色切换时更新内联样式"""
        self._empty_icon.setStyleSheet(f"background:{c['acc_l']};border-radius:32px;font-size:28px;")
        self._thumb_color = c['acc']
        if self._thumb_labels:
            self._highlight_thumb(self.current_page)
        # 更新 AI 面板
        self.qa_panel.update_theme(c)


# ═══════════════════════════════════════════════════════════════
#  翻译页面 — 全功能
# ═══════════════════════════════════════════════════════════════

class TranslatePage(QWidget):
    translation_done = pyqtSignal(dict)  # {"mono":..., "dual":..., "side_by_side":...}

    def __init__(self):
        super().__init__()
        self.worker = None
        self.pending_files = []
        self.cfg = UserConfigManager.load()

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("PA")
        content = QWidget(); content.setObjectName("PA")
        outer_lo = QVBoxLayout(content); outer_lo.setContentsMargins(0,0,0,0)
        outer_lo.addStretch(1)  # 上部弹性 — 垂直居中

        inner = QWidget()
        lo = QVBoxLayout(inner); lo.setContentsMargins(40,0,40,0); lo.setSpacing(12)

        # 标题 + 四叶草徽章 + 人文关怀
        hdr = QHBoxLayout()
        t = QLabel("翻译"); t.setObjectName("PT0"); hdr.addWidget(t)
        self.clover_label = QLabel("")
        self.clover_label.setStyleSheet("font-size:16px;background:transparent;")
        hdr.addWidget(self.clover_label)
        hdr.addStretch()
        # 尝试显示关怀消息，否则显示默认副标题
        _subtitle = "拖入学术 PDF，保留公式与原始排版"
        try:
            from ui.caring import get_caring_message
            _cm = get_caring_message()
            if _cm:
                _subtitle = f"{_cm[0]} {_cm[2]}"
        except Exception:
            pass
        st = QLabel(_subtitle); st.setObjectName("PT1"); hdr.addWidget(st)
        lo.addLayout(hdr)

        # 拖拽区（内含文件列表，高度固定，不影响下方布局）
        self.drop = DropZone(); self.drop.files_dropped.connect(self.on_files_added)
        self.drop._add_btn.clicked.connect(self._browse_more)
        self.drop._del_btn.clicked.connect(self._remove_selected_files)
        self.drop._clr_btn.clicked.connect(self._clear_files)
        lo.addWidget(self.drop)
        # 引用 DropZone 内嵌的控件
        self.flist = self.drop.flist
        self._fcount_label = self.drop._fcount_label
        self._zotero_hint = self.drop._zotero_hint
        # 文件列表右键菜单
        self.flist.setContextMenuPolicy(Qt.CustomContextMenu)
        self.flist.customContextMenuRequested.connect(self._flist_context_menu)

        # ── 配置卡片 ──
        card = _card()
        cl = QVBoxLayout(card); cl.setContentsMargins(16,12,16,12); cl.setSpacing(0)

        # 语言行
        r1 = QHBoxLayout(); r1.setSpacing(12)
        for label, items, attr, default in [
            ("源语言", list(LANG_MAP.keys()), "src_combo", self.cfg.get("lang_in","自动检测")),
            ("目标语言", list(LANG_MAP.keys()), "tgt_combo", self.cfg.get("lang_out","中文(简体)")),
        ]:
            col = QVBoxLayout(); col.setSpacing(4)
            lb = QLabel(label); lb.setObjectName("FL"); col.addWidget(lb)
            cb = QComboBox(); cb.addItems(items); cb.setMinimumWidth(160)
            idx = cb.findText(default)
            if idx >= 0: cb.setCurrentIndex(idx)
            col.addWidget(cb); r1.addLayout(col)
            setattr(self, attr, cb)
        r1.addStretch()
        cl.addLayout(r1)
        cl.addSpacing(8); cl.addWidget(_div()); cl.addSpacing(8)

        # 服务 + 格式 + 页码
        r2 = QHBoxLayout(); r2.setSpacing(12)
        # 翻译服务
        col = QVBoxLayout(); col.setSpacing(4)
        lb = QLabel("翻译服务"); lb.setObjectName("FL"); col.addWidget(lb)
        self.svc_combo = QComboBox(); self.svc_combo.addItems(list(SERVICE_MAP.keys()))
        self.svc_combo.setMinimumWidth(180)
        saved_svc = self.cfg.get("service", "Bing 翻译")
        idx = self.svc_combo.findText(saved_svc)
        if idx >= 0: self.svc_combo.setCurrentIndex(idx)
        col.addWidget(self.svc_combo); r2.addLayout(col)

        # 页码范围
        col = QVBoxLayout(); col.setSpacing(4)
        lb = QLabel("页码范围"); lb.setObjectName("FL"); col.addWidget(lb)
        self.page_combo = QComboBox(); self.page_combo.addItems(list(PAGE_PRESETS.keys()))
        self.page_combo.setMinimumWidth(120)
        self.page_combo.currentTextChanged.connect(self._on_page_changed)
        col.addWidget(self.page_combo); r2.addLayout(col)

        # 自定义页码输入
        self.custom_page = QLineEdit(); self.custom_page.setPlaceholderText("例: 1-5, 8, 10-12")
        self.custom_page.setVisible(False); self.custom_page.setFixedWidth(160)
        r2.addWidget(self.custom_page)

        r2.addStretch()
        cl.addLayout(r2)
        cl.addSpacing(8); cl.addWidget(_div()); cl.addSpacing(8)

        # 输出格式 + 线程
        r3 = QHBoxLayout(); r3.setSpacing(12)
        col = QVBoxLayout(); col.setSpacing(4)
        lb = QLabel("输出格式"); lb.setObjectName("FL"); col.addWidget(lb)
        self.fmt_combo = QComboBox(); self.fmt_combo.addItems(list(OUTPUT_MODES.keys()))
        _saved_fmt = self.cfg.get("output_format", "左右并排 (Side by Side)")
        _fmt_idx = self.fmt_combo.findText(_saved_fmt)
        self.fmt_combo.setCurrentIndex(_fmt_idx if _fmt_idx >= 0 else 2)
        self.fmt_combo.setMinimumWidth(180)
        col.addWidget(self.fmt_combo); r3.addLayout(col)

        col = QVBoxLayout(); col.setSpacing(4)
        lb = QLabel("线程数"); lb.setObjectName("FL"); col.addWidget(lb)
        self.thread_spin = QSpinBox(); self.thread_spin.setRange(1,32)
        self.thread_spin.setValue(self.cfg.get("thread_count", 8))
        col.addWidget(self.thread_spin); r3.addLayout(col)

        r3.addStretch()
        cl.addLayout(r3)
        cl.addSpacing(8); cl.addWidget(_div()); cl.addSpacing(8)

        # 分块翻译
        r4 = QHBoxLayout(); r4.setSpacing(16)
        self.chunk_check = QCheckBox("分块翻译（大文件推荐）")
        self.chunk_check.setChecked(self.cfg.get("chunk_enabled", False))
        self.chunk_check.toggled.connect(self._on_chunk_toggled)
        r4.addWidget(self.chunk_check)

        self.chunk_size_label = QLabel("每块"); self.chunk_size_label.setObjectName("Cap")
        self.chunk_size_spin = QSpinBox(); self.chunk_size_spin.setRange(5,200)
        self.chunk_size_spin.setValue(self.cfg.get("chunk_size", 50))
        self.chunk_size_unit = QLabel("页"); self.chunk_size_unit.setObjectName("Cap")

        self.chunk_delay_label = QLabel("间隔"); self.chunk_delay_label.setObjectName("Cap")
        self.chunk_delay_spin = QSpinBox(); self.chunk_delay_spin.setRange(0,120)
        self.chunk_delay_spin.setValue(self.cfg.get("chunk_delay", 10))
        self.chunk_delay_unit = QLabel("秒"); self.chunk_delay_unit.setObjectName("Cap")

        for w in [self.chunk_size_label, self.chunk_size_spin, self.chunk_size_unit,
                   self.chunk_delay_label, self.chunk_delay_spin, self.chunk_delay_unit]:
            r4.addWidget(w)
            w.setVisible(self.chunk_check.isChecked())

        r4.addStretch()
        cl.addLayout(r4)

        lo.addWidget(card)

        # ── 进度卡片（固定高度占位，避免布局跳动） ──
        self._prog_holder = QWidget()
        self._prog_holder.setFixedHeight(130)
        ph_lo = QVBoxLayout(self._prog_holder)
        ph_lo.setContentsMargins(0,0,0,0); ph_lo.setSpacing(0)

        self.prog_card = _card("lg")
        self.prog_card.setVisible(False)
        pc_lo = QVBoxLayout(self.prog_card)
        pc_lo.setContentsMargins(24, 14, 24, 14)
        pc_lo.setSpacing(8)

        row1 = QHBoxLayout(); row1.setSpacing(12)
        self.prog_icon = QLabel("⏳"); self.prog_icon.setObjectName("ProgIcon")
        row1.addWidget(self.prog_icon)
        self.prog_label = QLabel("正在翻译…"); self.prog_label.setObjectName("ProgLabel")
        row1.addWidget(self.prog_label)
        row1.addStretch()
        self.prog_pct = QLabel("0%"); self.prog_pct.setObjectName("ProgPct")
        row1.addWidget(self.prog_pct)
        pc_lo.addLayout(row1)

        self.prog_bar = QProgressBar(); self.prog_bar.setRange(0, 100)
        self.prog_bar.setObjectName("ProgBar")
        pc_lo.addWidget(self.prog_bar)

        self.prog_tip = QLabel(""); self.prog_tip.setObjectName("ProgTip")
        pc_lo.addWidget(self.prog_tip)

        row2 = QHBoxLayout(); row2.setSpacing(10)
        self.prog_detail = QLabel(""); self.prog_detail.setObjectName("ProgDetail")
        row2.addWidget(self.prog_detail)
        row2.addStretch()
        self.stop_btn = QPushButton("取消")
        self.stop_btn.setObjectName("ProgCancel")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self._cancel)
        row2.addWidget(self.stop_btn)
        pc_lo.addLayout(row2)

        ph_lo.addWidget(self.prog_card)
        lo.addWidget(self._prog_holder)

        # ── 开始按钮 ──
        br = QHBoxLayout(); br.setSpacing(10)
        br.addStretch()
        self.go_btn = QPushButton("开始翻译"); self.go_btn.setObjectName("Pr")
        self.go_btn.setFixedWidth(200); self.go_btn.setFixedHeight(48)
        self.go_btn.setEnabled(False)
        self.go_btn.clicked.connect(self._start)
        br.addWidget(self.go_btn)
        self.dice_btn = QPushButton("🎲")
        self.dice_btn.setCursor(Qt.PointingHandCursor)
        self.dice_btn.setStyleSheet("font-size:18px;padding:6px;border:none;background:transparent;")
        self.dice_btn.clicked.connect(self._dice_game)
        br.addWidget(self.dice_btn)
        br.addStretch()
        lo.addLayout(br)

        outer_lo.addWidget(inner)
        outer_lo.addStretch(2)  # 下部弹性稍大 — 视觉重心偏上

        self._update_dice()  # 初始化骰子状态
        scroll.setWidget(content)
        page_lo = QVBoxLayout(self); page_lo.setContentsMargins(0,0,0,0); page_lo.addWidget(scroll)

    def _on_page_changed(self, text):
        self.custom_page.setVisible(text == "自定义")

    def _on_chunk_toggled(self, checked):
        for w in [self.chunk_size_label, self.chunk_size_spin, self.chunk_size_unit,
                   self.chunk_delay_label, self.chunk_delay_spin, self.chunk_delay_unit]:
            w.setVisible(checked)

    def on_files_added(self, files):
        for f in files:
            if not os.path.isfile(f):
                continue
            # 去重
            exists = False
            for i in range(self.flist.count()):
                if self.flist.item(i).data(Qt.UserRole) == f:
                    exists = True; break
            if exists:
                continue
            name = os.path.basename(f)
            if len(name) > 50:
                name = name[:22] + "…" + name[-22:]
            sz = os.path.getsize(f)
            s = f"{sz/1048576:.1f} MB" if sz > 1048576 else f"{sz/1024:.0f} KB"
            item = QListWidgetItem(f"  📄  {name}    {s}")
            item.setData(Qt.UserRole, f)
            self.flist.addItem(item)
        self._update_fcount()
        self._check_zotero_source()

    def _flist_context_menu(self, pos):
        item = self.flist.itemAt(pos)
        menu = _RoundMenu(self)
        menu.addAction("添加文件…", self._browse_more)
        if item:
            fp = item.data(Qt.UserRole)
            menu.addSeparator()
            menu.addAction("在 Finder 中显示", lambda: self._reveal_in_finder(fp))
            menu.addAction("移除", lambda: self._remove_item(item))
        if self.flist.count() > 0:
            menu.addSeparator()
            menu.addAction("清空全部", self._clear_files)
        menu.exec_(self.flist.viewport().mapToGlobal(pos))

    def _reveal_in_finder(self, path):
        import subprocess
        subprocess.Popen(["open", "-R", path])

    def _remove_item(self, item):
        self.flist.takeItem(self.flist.row(item))
        self._update_fcount(); self._check_zotero_source()

    def _browse_more(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "选择 PDF", "", "PDF (*.pdf)")
        if fs: self.on_files_added(fs)

    def _update_fcount(self):
        n = self.flist.count()
        if n > 0:
            self.drop._stack.setCurrentIndex(1)  # 切换到文件列表
            self.go_btn.setEnabled(True)
            self._fcount_label.setText(f"共 {n} 个文件")
        else:
            self.drop._stack.setCurrentIndex(0)  # 切换回拖拽提示
            self.go_btn.setEnabled(False)
            self._fcount_label.setText("")

    def _check_zotero_source(self):
        has_zotero = False
        for i in range(self.flist.count()):
            p = self.flist.item(i).data(Qt.UserRole)
            if detect_zotero_source(p):
                has_zotero = True
                break
        self._zotero_hint.setVisible(has_zotero)

    def _remove_selected_files(self):
        for item in reversed(self.flist.selectedItems()):
            self.flist.takeItem(self.flist.row(item))
        self._update_fcount()
        self._check_zotero_source()

    def _clear_files(self):
        self.flist.clear()
        self._update_fcount()
        self._zotero_hint.setVisible(False)

    def _get_pages(self):
        preset = self.page_combo.currentText()
        if preset == "自定义":
            txt = self.custom_page.text().strip()
            return parse_page_range(txt) if txt else None
        return PAGE_PRESETS.get(preset)

    def _save_config(self):
        self.cfg["service"] = self.svc_combo.currentText()
        self.cfg["lang_in"] = self.src_combo.currentText()
        self.cfg["lang_out"] = self.tgt_combo.currentText()
        self.cfg["output_format"] = self.fmt_combo.currentText()
        self.cfg["thread_count"] = self.thread_spin.value()
        self.cfg["chunk_enabled"] = self.chunk_check.isChecked()
        self.cfg["chunk_size"] = self.chunk_size_spin.value()
        self.cfg["chunk_delay"] = self.chunk_delay_spin.value()
        UserConfigManager.save(self.cfg)

    def _start(self):
        files = []
        for i in range(self.flist.count()):
            p = self.flist.item(i).data(Qt.UserRole)
            if p: files.append(p)
        if not files: return
        # 确保按钮连接正常（重试模式可能改过）
        try: self.go_btn.clicked.disconnect()
        except TypeError: pass
        self.go_btn.clicked.connect(self._start)

        self._save_config()
        self.pending_files = files
        self._batch_idx = 0
        self._batch_results = []     # [(file_path, output_files_dict), ...]
        self._output_dir = os.path.expanduser("~/Documents/pdf2zh_files")
        os.makedirs(self._output_dir, exist_ok=True)

        self.go_btn.setEnabled(False); self.go_btn.setText("翻译中…")
        self.prog_card.setVisible(True); self.stop_btn.setVisible(True)
        self.prog_bar.setValue(0)
        self.prog_pct.setText("0%")
        self.prog_label.setText("正在翻译…")
        self.prog_icon.setText("⏳")
        self.prog_tip.setText("")

        self._translate_next()

    def _translate_next(self):
        """启动队列中下一个文件的翻译"""
        idx = self._batch_idx
        total = len(self.pending_files)
        if idx >= total:
            self._on_batch_done()
            return

        fp = self.pending_files[idx]
        if total > 1:
            self.prog_label.setText(f"正在翻译 ({idx+1}/{total})…")
            self.prog_detail.setText(os.path.basename(fp))
        self.prog_bar.setValue(0); self.prog_pct.setText("0%")

        envs = build_service_envs(self.svc_combo.currentText())
        self.worker = TranslateWorker(
            file_path=fp,
            output_dir=self._output_dir,
            lang_in=LANG_MAP.get(self.src_combo.currentText(), ""),
            lang_out=LANG_MAP.get(self.tgt_combo.currentText(), "zh"),
            service=SERVICE_MAP.get(self.svc_combo.currentText(), "bing"),
            pages=self._get_pages(),
            thread_count=self.thread_spin.value(),
            chunk_enabled=self.chunk_check.isChecked(),
            chunk_size=self.chunk_size_spin.value(),
            chunk_delay=self.chunk_delay_spin.value(),
            envs=envs,
        )
        self.worker.progress.connect(self._on_prog)
        self.worker.status.connect(self._on_status)
        self.worker.finished.connect(self._on_single_done)
        self.worker.error.connect(self._on_single_err)
        self.worker.start()

    def _cancel(self):
        if self.worker: self.worker.cancel()
        self.prog_label.setText("正在取消…")

    _TIPS = [
        "翻译中，请稍候…", "公式和图表会完整保留",
        "AI 正在识别文档布局…", "保持网络连接以获得最佳速度",
        "快好了，再等等…", "pdf2zh-desktop · 学术翻译利器",
        "排版会和原文一模一样", "支持 20+ 翻译引擎",
        "每一篇论文，都是知识跨越语言的桥梁",
        "科研不易，感谢你的坚持",
    ]

    def _on_prog(self, cur, total):
        if total > 0:
            pct = min(int(cur/total*100), 100)
            self.prog_bar.setValue(pct); self.prog_pct.setText(f"{pct}%")
            self.prog_detail.setText(f"已处理 {cur}/{total} 页")
            # 趣味提示 + 深夜关怀
            import random
            if cur % 5 == 1 or cur == total:
                from ui.caring import get_caring_message
                caring = get_caring_message()
                if caring:
                    tip = f"{caring[0]} {caring[1]}"
                elif pct >= 90:
                    tip = "马上就好！"
                elif pct >= 50:
                    tip = "已经过半了，加油！"
                else:
                    tip = random.choice(self._TIPS)
                self.prog_tip.setText(tip)

    def _on_status(self, text):
        self.prog_detail.setText(text)

    def _on_single_done(self, output_files):
        """单文件翻译完成 — 回写 Zotero + 记录历史 + 推进队列"""
        fp = self.pending_files[self._batch_idx]

        if self.worker:
            w = self.worker; self.worker = None
            w.quit()
            QTimer.singleShot(100, lambda: w.deleteLater() if not w.isRunning() else None)

        # 保存历史
        HistoryManager.add_record({
            "file": {"name": os.path.basename(fp), "path": fp},
            "translation": {
                "service": self.svc_combo.currentText(),
                "lang_in": self.src_combo.currentText(),
                "lang_out": self.tgt_combo.currentText(),
            },
            "output_files": output_files,
            "status": "success",
        })
        self.translation_done.emit(output_files)

        # Zotero 回写：按此文件自身的来源路径，把译文复制回原位
        self._zotero_writeback(fp, output_files)

        self._batch_results.append((fp, output_files))

        # 推进到下一个文件
        self._batch_idx += 1
        self._translate_next()

    def _on_single_err(self, msg):
        """单文件翻译出错 — 记录后继续下一个"""
        fp = self.pending_files[self._batch_idx]

        if self.worker:
            w = self.worker; self.worker = None
            w.quit()
            QTimer.singleShot(100, lambda: w.deleteLater() if not w.isRunning() else None)

        self._batch_results.append((fp, None))  # None = 失败

        total = len(self.pending_files)
        if total > 1:
            # 批量模式：跳过出错的，继续下一个
            self.prog_detail.setText(f"⚠️ {os.path.basename(fp)} 翻译出错，跳过")
            self._batch_idx += 1
            QTimer.singleShot(1000, self._translate_next)
        else:
            # 单文件模式：直接报错
            self._on_err(msg)

    def _zotero_writeback(self, file_path, output_files):
        """把译文复制回 Zotero 原位 + 尝试自动关联附件"""
        import shutil
        zotero_dir = detect_zotero_source(file_path)
        if not zotero_dir:
            return
        cfg = UserConfigManager.load()
        modes = cfg.get("zotero_output_modes", ["side_by_side"])
        keep_copy = cfg.get("zotero_keep_copy", True)
        item_key = get_zotero_item_key(file_path)
        for mode in modes:
            src = output_files.get(mode)
            if not src or not os.path.exists(src):
                continue
            dst = os.path.join(zotero_dir, os.path.basename(src))
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copy2(src, dst)
                if not keep_copy:
                    try:
                        os.remove(src)
                    except OSError:
                        pass
            # 尝试通过 pdf2zh Connector 插件自动关联附件
            if item_key:
                mode_label = {"side_by_side": "并排", "dual": "双语", "mono": "译文"}.get(mode, mode)
                zotero_auto_link(item_key, dst, f"翻译 ({mode_label})")

    def _on_batch_done(self):
        """全部文件翻译完成"""
        self.prog_bar.setValue(100); self.prog_pct.setText("100%")
        self.prog_icon.setText("✅")
        self.go_btn.setEnabled(True); self.go_btn.setText("开始翻译")
        self.stop_btn.setVisible(False)

        total = len(self._batch_results)
        ok = sum(1 for _, r in self._batch_results if r is not None)
        failed = total - ok
        has_zotero = any(detect_zotero_source(fp) for fp, _ in self._batch_results)

        # 收集失败的文件用于重试
        self._failed_files = [fp for fp, r in self._batch_results if r is None]

        if total == 1 and ok == 1:
            self.prog_label.setText("翻译完成")
            if has_zotero:
                self.prog_detail.setText("译文已保存回 Zotero 原位")
            else:
                self.prog_detail.setText("输出至 ~/Documents/pdf2zh_files")
        elif failed == 0:
            self.prog_label.setText(f"全部完成（{ok} 篇）")
            if has_zotero:
                self.prog_detail.setText("所有译文已保存回 Zotero 原位")
            else:
                self.prog_detail.setText("输出至 ~/Documents/pdf2zh_files")
        else:
            self.prog_label.setText(f"完成 {ok} 篇，失败 {failed} 篇")
            self.prog_detail.setText("部分文件翻译出错")
            # 显示重试按钮
            self.go_btn.setText(f"重试失败 ({failed} 篇)")
            try: self.go_btn.clicked.disconnect()
            except TypeError: pass
            self.go_btn.clicked.connect(self._retry_failed)
            self.go_btn.setEnabled(True)

        # macOS 系统通知 — 翻译完成后通知用户（适合长时间翻译时切到其他 app）
        try:
            import subprocess
            msg = f"{ok} 篇翻译完成" if failed == 0 else f"完成 {ok} 篇，失败 {failed} 篇"
            subprocess.Popen([
                "osascript", "-e",
                f'display notification "{msg}" with title "pdf2zh" sound name "Glass"'
            ])
        except Exception:
            pass

        # 关怀消息
        from ui.caring import get_caring_message, get_session_tip
        caring = get_caring_message()
        if caring:
            self.prog_tip.setText(f"{caring[0]} {caring[1]}")
        else:
            self.prog_tip.setText(get_session_tip())

        # 翻译完成后自动清空文件列表
        self._clear_files()

        # 骰子系统
        try:
            from datetime import date
            cfg = UserConfigManager.load()
            today = date.today().isoformat()
            if cfg.get("dice_date") != today:
                cfg["dice_date"] = today; cfg["dice_today_pages"] = 0
                cfg["dice_used"] = False; cfg["dice_clovers"] = 0
            cfg["dice_today_pages"] = cfg.get("dice_today_pages", 0) + max(1, self.thread_spin.value())
            UserConfigManager.dice_save(cfg)
            self._update_dice()
        except Exception:
            pass

    def _retry_failed(self):
        """重试上次批量翻译中失败的文件"""
        failed = getattr(self, '_failed_files', [])
        if not failed:
            return
        # 恢复按钮到正常状态
        try: self.go_btn.clicked.disconnect()
        except TypeError: pass
        self.go_btn.clicked.connect(self._start)
        # 把失败文件重新加入列表并启动
        self.on_files_added(failed)
        self._failed_files = []
        self._start()

    def _on_err(self, msg):
        self.prog_icon.setText("❌")
        self.prog_label.setText("翻译出错")
        self.prog_pct.setText("!")
        self.prog_detail.setText(msg)
        self.prog_bar.setValue(0)
        self.go_btn.setEnabled(True); self.go_btn.setText("重试翻译")
        self.stop_btn.setVisible(False)
        if self.worker:
            w = self.worker; self.worker = None
            w.quit()
            QTimer.singleShot(100, lambda: w.deleteLater() if not w.isRunning() else None)

    # ── 骰子系统（静默、无文字、四叶草） ──

    def _update_dice(self):
        """骰子 🎲 在按钮区，四叶草 🍀 在标题旁"""
        from datetime import date
        cfg = UserConfigManager.load()
        today = date.today().isoformat()
        pages = cfg.get("dice_today_pages", 0)

        # 新的一天重置
        if cfg.get("dice_date") != today:
            self.clover_label.setText("")
            if pages >= 5:
                self.dice_btn.setText("🎲"); self.dice_btn.setEnabled(True); self.dice_btn.show()
            else:
                self.dice_btn.hide()
            return

        # 四叶草：当天翻译不足 5 页则清掉
        clovers = cfg.get("dice_clovers", 0) if cfg.get("dice_used") else 0
        if clovers > 0 and pages < 5:
            clovers = 0
            cfg["dice_clovers"] = 0; UserConfigManager.dice_save(cfg)
        self.clover_label.setText("🍀" * clovers if clovers > 0 else "")

        # 骰子按钮
        if cfg.get("dice_used"):
            self.dice_btn.hide()  # 已掷过，骰子消失
        elif pages >= 5:
            self.dice_btn.setText("🎲"); self.dice_btn.setEnabled(True); self.dice_btn.show()
        else:
            self.dice_btn.hide()

    def _dice_game(self):
        """点击骰子 → 静默掷骰 → 四叶草或消失"""
        import random
        from datetime import date

        cfg = UserConfigManager.load()
        today = date.today().isoformat()

        # 日期重置
        if cfg.get("dice_date") != today:
            cfg["dice_date"] = today; cfg["dice_today_pages"] = 0
            cfg["dice_used"] = False; cfg["dice_clovers"] = 0
            UserConfigManager.dice_save(cfg)

        # 签名校验
        if not UserConfigManager.dice_verify(cfg):
            cfg["dice_date"] = today; cfg["dice_today_pages"] = 0
            cfg["dice_used"] = False; cfg["dice_clovers"] = 0
            UserConfigManager.dice_save(cfg)
            self._update_dice(); return

        # 静默检查资格
        if cfg.get("dice_used") or cfg.get("dice_today_pages", 0) < 5:
            return

        # 标记已用
        cfg["dice_used"] = True; cfg["dice_clovers"] = 0
        UserConfigManager.dice_save(cfg)

        self.dice_btn.setEnabled(False)
        self._dice_roll_step(0)

    def _dice_roll_step(self, clovers):
        """逐次掷骰：6 → 🍀 累加，非 6 → 结束"""
        import random
        FACES = "⚀⚁⚂⚃⚄⚅"

        val = 6 if random.random() < 0.5 else random.choice([1,2,3,4,5])
        flicker = [0]

        def tick():
            flicker[0] += 1
            if flicker[0] < 10:
                self.dice_btn.setText(FACES[random.randint(0,5)])
                QTimer.singleShot(55, tick)
            else:
                # 定格
                self.dice_btn.setText(FACES[val - 1])
                if val == 6:
                    nc = clovers + 1
                    self._dice_mini_firework()
                    QTimer.singleShot(700, lambda: self._dice_got_six(nc))
                else:
                    # 短暂显示骰面，然后骰子消失，四叶草留在标题旁
                    QTimer.singleShot(1500, lambda: self._dice_finish(clovers))
        tick()

    def _dice_got_six(self, clovers):
        """掷中 6：标题旁加 🍀，继续或结束"""
        # 四叶草实时更新到标题旁
        self.clover_label.setText("🍀" * clovers)

        # 保存中间状态
        cfg = UserConfigManager.load()
        cfg["dice_clovers"] = clovers
        UserConfigManager.dice_save(cfg)

        if clovers >= 6:
            # 全部 6！终极大奖
            from datetime import date
            today = date.today().isoformat()
            cfg["dice_win_code"] = UserConfigManager.dice_win_code(today)
            cfg["theme_unlocked"] = True
            UserConfigManager.save(cfg)
            self.dice_btn.hide()
            mw = self.window()
            if hasattr(mw, '_midnight_bloom'):
                mw._midnight_bloom()
            return

        # ≥3 个 6 静默解锁主题色
        if clovers == 3:
            cfg2 = UserConfigManager.load()
            cfg2["theme_unlocked"] = True
            UserConfigManager.save(cfg2)

        # 按钮回到 🎲 继续下一轮
        self.dice_btn.setText("🎲")
        QTimer.singleShot(600, lambda: self._dice_roll_step(clovers))

    def _dice_finish(self, clovers):
        """掷骰结束：骰子消失，四叶草留在标题旁"""
        cfg = UserConfigManager.load()
        cfg["dice_clovers"] = clovers
        UserConfigManager.dice_save(cfg)
        # 骰子消失，四叶草已在标题旁
        self.dice_btn.hide()
        self.clover_label.setText("🍀" * clovers if clovers > 0 else "")

    def _dice_mini_firework(self):
        """从骰子按钮位置爆发迷你烟花"""
        import random, math
        from PyQt5.QtCore import QPropertyAnimation, QPoint, QEasingCurve
        mw = self.window()
        center = self.dice_btn.mapTo(mw, self.dice_btn.rect().center())
        emojis = ["✨","💫","⭐","🌟","🎇","🔥","🎆"]
        for _ in range(12):
            lbl = QLabel(random.choice(emojis), mw)
            lbl.setStyleSheet(f"font-size:{random.randint(12,22)}px;background:transparent;")
            lbl.move(center); lbl.show(); lbl.raise_()
            angle = random.uniform(0, 2 * math.pi)
            dist = random.randint(50, 160)
            end = QPoint(center.x() + int(math.cos(angle) * dist),
                         center.y() + int(math.sin(angle) * dist))
            anim = QPropertyAnimation(lbl, b"pos")
            anim.setDuration(random.randint(600, 1100))
            anim.setStartValue(center); anim.setEndValue(end)
            anim.setEasingCurve(QEasingCurve.OutQuad)
            anim.finished.connect(lbl.deleteLater)
            anim.start(); lbl._anim = anim


# ═══════════════════════════════════════════════════════════════
#  阅读页面 — 历史 + 预览合体
# ═══════════════════════════════════════════════════════════════

class ReaderPage(QWidget):
    """左侧历史列表 + 右侧 PDF 预览
    两级导航：历史列表 ←(Left/Right)→ 预览区
    预览区内上下键翻页，缩略图跟随高亮"""
    fullscreen_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._preview_active = False
        lo = QHBoxLayout(self); lo.setContentsMargins(0,0,0,0); lo.setSpacing(0)

        # QSplitter 实现可拖拽分割
        from PyQt5.QtWidgets import QSplitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(True)

        # ── 左侧：历史面板 ──
        left = QWidget()
        left.setObjectName("HistPanel"); left.setMinimumWidth(180); left.setMaximumWidth(420)
        ll = QVBoxLayout(left); ll.setContentsMargins(12,12,12,12); ll.setSpacing(8)

        # 标题行
        hdr = QHBoxLayout(); hdr.setSpacing(4)
        t = QLabel("翻译历史"); t.setStyleSheet("font-size:13px;font-weight:600;")
        hdr.addWidget(t); hdr.addStretch()
        self.thumb_toggle = QPushButton("缩略图"); self.thumb_toggle.setObjectName("TB")
        self.thumb_toggle.setCursor(Qt.PointingHandCursor)
        self.thumb_toggle.setProperty("active", True)
        self.thumb_toggle.setStyleSheet("font-size:11px;padding:2px 6px;")
        self.thumb_toggle.clicked.connect(self._toggle_thumbs)
        hdr.addWidget(self.thumb_toggle)
        cb = QPushButton("清空"); cb.setObjectName("Gh"); cb.setCursor(Qt.PointingHandCursor)
        cb.setStyleSheet("font-size:11px;padding:2px 6px;")
        cb.clicked.connect(self._clear); hdr.addWidget(cb)
        ll.addLayout(hdr)

        # ── 分组筛选栏：左侧可滚动按钮区 + 右侧固定"＋" ──
        _group_row = QHBoxLayout(); _group_row.setContentsMargins(0, 0, 0, 0); _group_row.setSpacing(4)
        self._group_bar = QScrollArea()
        self._group_bar.setMaximumHeight(34); self._group_bar.setFrameShape(QFrame.NoFrame)
        self._group_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._group_bar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._group_bar.setWidgetResizable(True)
        self._group_container = QWidget()
        self._group_layout = QHBoxLayout(self._group_container)
        self._group_layout.setContentsMargins(0, 0, 0, 0); self._group_layout.setSpacing(4)
        self._group_bar.setWidget(self._group_container)
        _group_row.addWidget(self._group_bar, 1)
        # "＋"按钮 — 独立于 scroll area，绝对不参与 group_layout
        self._add_btn = QPushButton("＋"); self._add_btn.setObjectName("Gh")
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.setStyleSheet("font-size:10px;padding:4px 8px;")
        self._add_btn.setToolTip("新建分组")
        self._add_btn.setFixedSize(28, 26)
        self._add_btn.clicked.connect(self._create_group)
        _group_row.addWidget(self._add_btn, 0)  # stretch=0, 固定尺寸
        ll.addLayout(_group_row)
        self._current_group_id = None  # None = 全部
        self._current_tag_filter = None

        # 历史列表
        self.list_w = QListWidget()
        self.list_w.setObjectName("HistList")
        self.list_w.setFocusPolicy(Qt.StrongFocus)
        self.list_w.setSelectionMode(QListWidget.SingleSelection)
        self.list_w.currentItemChanged.connect(self._on_select)
        self.list_w.itemClicked.connect(lambda item: self._on_select(item, None))
        self.list_w.itemDoubleClicked.connect(self._open_in_reader)
        self.list_w.installEventFilter(self)
        self.list_w.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_w.customContextMenuRequested.connect(self._hist_context_menu)
        ll.addWidget(self.list_w)

        # 详情面板
        self.detail_label = QLabel("↑ 选择记录查看详情")
        self.detail_label.setObjectName("HistDetail")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet(
            "#HistDetail{font-size:10px;padding:4px 6px;line-height:125%;}")
        self.detail_label.setMinimumHeight(48)
        ll.addWidget(self.detail_label)
        # 文件操作按钮 — 紧凑行，紧贴详情面板
        fops = QHBoxLayout(); fops.setSpacing(4); fops.setContentsMargins(6, 2, 6, 0)
        self._btn_reveal = QPushButton("📂 Finder"); self._btn_reveal.setObjectName("Gh")
        self._btn_reveal.setCursor(Qt.PointingHandCursor)
        self._btn_reveal.setStyleSheet("font-size:9px;padding:2px 6px;")
        self._btn_reveal.setToolTip("在 Finder 中显示翻译文件")
        self._btn_reveal.clicked.connect(self._reveal_in_finder)
        self._btn_reveal.setVisible(False)
        fops.addWidget(self._btn_reveal)
        self._btn_open_src = QPushButton("📄 源文件"); self._btn_open_src.setObjectName("Gh")
        self._btn_open_src.setCursor(Qt.PointingHandCursor)
        self._btn_open_src.setStyleSheet("font-size:9px;padding:2px 6px;")
        self._btn_open_src.setToolTip("用默认应用打开源 PDF")
        self._btn_open_src.clicked.connect(self._open_source)
        self._btn_open_src.setVisible(False)
        fops.addWidget(self._btn_open_src)
        fops.addStretch()
        ll.addLayout(fops)
        self._current_record = None

        splitter.addWidget(left)

        # ── 右侧：预览 ──
        self.preview = PreviewPage()
        self.preview.installEventFilter(self)
        splitter.addWidget(self.preview)

        # 初始比例：左 260, 右 stretch
        splitter.setSizes([260, 800])
        self._splitter = splitter
        self._hist_panel = left
        lo.addWidget(splitter)

        self._show_thumbs = True
        # 缩略图点击 → 进入预览模式
        self._orig_thumb_clicked = self.preview._thumb_clicked
        self.preview._thumb_clicked = self._on_thumb_clicked
        # 全屏信号
        self.preview.fullscreen_toggled.connect(self._on_fullscreen)
        self.preview.history_toggled.connect(self._toggle_hist_in_fullscreen)
        self._fs_hist_visible = False
        self.refresh()

    def showEvent(self, event):
        """页面显示时自动选中第一条"""
        super().showEvent(event)
        if self.list_w.count() > 0 and not self.list_w.currentItem():
            self.list_w.setCurrentRow(0)
        self.list_w.setFocus()

    def _on_thumb_clicked(self, idx):
        """点击缩略图 → 进入预览模式 + 跳转页面"""
        self._enter_preview()
        self._orig_thumb_clicked(idx)

    def _enter_preview(self):
        """进入预览模式：缩略图显示蓝色高亮"""
        self._preview_active = True
        self.preview._thumb_color = _C["acc"]
        self.preview.setFocus()
        self.preview._highlight_thumb(self.preview.current_page)

    def _exit_preview(self):
        """退出预览模式：缩略图变灰色，焦点回列表"""
        self._preview_active = False
        self.preview._thumb_color = _C["t3"]
        self.list_w.setFocus()
        self.preview._highlight_thumb(self.preview.current_page)

    def eventFilter(self, obj, event):
        """两级导航: 历史列表 ←→ 预览区（一次按键切换）
        全屏模式下 Left 键会先唤出历史面板"""
        from PyQt5.QtCore import QEvent
        if event.type() == QEvent.KeyPress:
            key = event.key()
            # 历史列表 → 右键 → 进入预览
            if obj == self.list_w and key == Qt.Key_Right:
                self._enter_preview()
                return True
            # 预览区 → 左键
            if obj == self.preview and key == Qt.Key_Left:
                # 全屏且历史面板隐藏 → 先唤出历史
                if self.preview._is_fullscreen and not self._fs_hist_visible:
                    self._toggle_hist_in_fullscreen()
                    return True
                self._exit_preview()
                return True
        return super().eventFilter(obj, event)

    def _on_fullscreen(self, fs):
        """全屏阅读模式：隐藏历史面板+侧边栏"""
        if fs:
            self._saved_splitter_sizes = self._splitter.sizes()
            self._hist_panel.setVisible(False)
            self._fs_hist_visible = False
            self.preview.hist_btn.setProperty("active", False)
            self.preview.hist_btn.style().unpolish(self.preview.hist_btn)
            self.preview.hist_btn.style().polish(self.preview.hist_btn)
        else:
            self._hist_panel.setVisible(True)
            self._splitter.setSizes(self._saved_splitter_sizes)
            self._fs_hist_visible = False
        self.fullscreen_changed.emit(fs)
        self._quick_refit()

    def _toggle_hist_in_fullscreen(self):
        """全屏模式下切换历史面板"""
        if not self.preview._is_fullscreen:
            return
        self._fs_hist_visible = not self._fs_hist_visible
        self._hist_panel.setVisible(self._fs_hist_visible)
        self.preview.hist_btn.setProperty("active", self._fs_hist_visible)
        self.preview.hist_btn.style().unpolish(self.preview.hist_btn)
        self.preview.hist_btn.style().polish(self.preview.hist_btn)
        if self._fs_hist_visible:
            self._splitter.setSizes([self._saved_splitter_sizes[0], 800])
            self.list_w.setFocus()
        self._quick_refit()

    def _quick_refit(self):
        """快速贴合（不重建缩略图，只调 zoom + 渲染）"""
        if not self.preview.doc:
            return
        def _do():
            if self.preview._fit_mode == "page":
                self.preview._fit_page()
            else:
                self.preview._fit_width()
            if self.preview.zoom != getattr(self.preview, '_last_fit_zoom', -1):
                self.preview._last_fit_zoom = self.preview.zoom
                if self.preview._continuous:
                    self.preview._render_continuous()
                else:
                    self.preview.render_page()
        QTimer.singleShot(0, _do)
        QTimer.singleShot(80, _do)

    def _toggle_thumbs(self):
        """切换缩略图显示，自动重新适配宽度"""
        self._show_thumbs = not self._show_thumbs
        self.thumb_toggle.setProperty("active", self._show_thumbs)
        self.thumb_toggle.style().unpolish(self.thumb_toggle)
        self.thumb_toggle.style().polish(self.thumb_toggle)
        if self._show_thumbs:
            self.preview.thumb_scroll.setVisible(True)
            # 确保 splitter 给缩略图合理宽度
            sizes = self.preview.body_splitter.sizes()
            if sizes[0] < 60:
                self.preview.body_splitter.setSizes([100, sizes[1]])
        else:
            self.preview.thumb_scroll.setVisible(False)
        self._quick_refit()

    def refresh(self):
        self.list_w.clear()
        data = HistoryManager.load_all()
        records = data.get("records", [])
        groups = data.get("groups", [])
        all_tags = data.get("tags", [])

        # ── 重建分组筛选栏 ──
        self._rebuild_group_bar(groups)

        # ── 按分组/标签筛选 ──
        filtered = records
        gid = self._current_group_id
        if gid is not None:
            filtered = [r for r in filtered if r.get("group_id") == gid]
        tid = self._current_tag_filter
        if tid is not None:
            filtered = [r for r in filtered if tid in r.get("tags", [])]

        if not filtered:
            item = QListWidgetItem("暂无翻译记录")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QColor(_C["t3"]))
            self.list_w.addItem(item)
            return
        for r in filtered:
            ts = r.get("timestamp", "")[:16].replace("T", " ")
            fname = r.get("file", {}).get("name", "?")
            svc = r.get("translation", {}).get("service", "?")
            lang_in = r.get("translation", {}).get("lang_in", "")
            lang_out = r.get("translation", {}).get("lang_out", "")
            status = "✓" if r.get("status") == "success" else "✗"
            # 两行显示：文件名 + 服务·时间
            item = QListWidgetItem()
            item.setData(Qt.UserRole, r)
            item.setToolTip(f"{fname}\n{svc} · {lang_in}→{lang_out} · {ts[5:]}")
            # 有标签时行高多留空间
            has_tags = bool(r.get("tags"))
            item.setSizeHint(QSize(0, 56 if has_tags else 44))
            self.list_w.addItem(item)
            # 自定义 widget 双行布局
            w = QWidget(); wl = QVBoxLayout(w)
            wl.setContentsMargins(2, 2, 2, 2); wl.setSpacing(0)
            l1 = QLabel(f"{status} {fname}"); l1.setStyleSheet(f"font-size:12px;color:{_C['t1']};background:transparent;")
            l2 = QLabel(f"{svc} · {lang_in}→{lang_out} · {ts[5:]}")
            l2.setStyleSheet(f"font-size:11px;color:{_C['t2']};background:transparent;")
            wl.addWidget(l1); wl.addWidget(l2)
            # 标签行
            rec_tags = r.get("tags", [])
            if rec_tags and all_tags:
                tag_row = QHBoxLayout(); tag_row.setSpacing(4); tag_row.setContentsMargins(0, 1, 0, 0)
                for td in all_tags:
                    if td["id"] in rec_tags:
                        dot = QLabel(f"● {td['name']}")
                        dot.setStyleSheet(f"font-size:9px;color:{td['color']};background:transparent;")
                        tag_row.addWidget(dot)
                tag_row.addStretch()
                wl.addLayout(tag_row)
            w._l1 = l1; w._l2 = l2
            self.list_w.setItemWidget(item, w)

    def _rebuild_group_bar(self, groups):
        """重建分组筛选按钮栏 — 支持右键菜单（重命名/删除/图标）"""
        while self._group_layout.count():
            w = self._group_layout.takeAt(0).widget()
            if w: w.deleteLater()
        self._group_btns = []
        c = _C
        # ── "全部"按钮（固定，不可删除） ──
        btn_all = QPushButton("全部"); btn_all.setObjectName("TB")
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.setStyleSheet("font-size:10px;padding:4px 10px;")
        btn_all.setProperty("active", self._current_group_id is None)
        btn_all.clicked.connect(lambda: self._select_group(None))
        self._group_layout.addWidget(btn_all)
        # ── 动态分组按钮 ──
        for g in groups:
            b = QPushButton(f"{g['icon']} {g['name']}"); b.setObjectName("TB")
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("font-size:10px;padding:4px 10px;")
            b.setProperty("active", self._current_group_id == g["id"])
            gid = g["id"]
            b.clicked.connect(lambda checked, _id=gid: self._select_group(_id))
            # 右键菜单
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(
                lambda pos, _id=gid, _btn=b: self._group_context_menu(_id, _btn, pos))
            self._group_layout.addWidget(b)
            self._group_btns.append((gid, b))
        self._group_layout.addStretch()

    def _select_group(self, group_id):
        self._current_group_id = group_id
        self.refresh()

    def _create_group(self):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "新建分组", "分组名称：")
        if ok and name.strip():
            g = HistoryManager.add_group(name.strip())
            # 在 stretch 前面插入新按钮（"＋"在 layout 外，不受影响）
            stretch_idx = self._group_layout.count() - 1  # 最后一个是 stretch
            b = QPushButton(f"{g['icon']} {g['name']}"); b.setObjectName("TB")
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("font-size:10px;padding:4px 10px;")
            b.setProperty("active", False)
            gid = g["id"]
            b.clicked.connect(lambda checked, _id=gid: self._select_group(_id))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(
                lambda pos, _id=gid, _btn=b: self._group_context_menu(_id, _btn, pos))
            self._group_layout.insertWidget(stretch_idx, b)
            self._group_btns.append((gid, b))

    def _group_context_menu(self, group_id, btn, pos):
        """分组按钮右键菜单：重命名 / 修改图标 / 上移 / 下移 / 删除"""
        try:
            menu = _RoundMenu(self)
            menu.addAction("重命名", lambda: self._rename_group(group_id))
            menu.addAction("修改图标", lambda: self._change_group_icon(group_id))
            menu.addSeparator()
            # 上移 / 下移
            ids = [gid for gid, _ in self._group_btns]
            idx = ids.index(group_id) if group_id in ids else -1
            if idx > 0:
                menu.addAction("↑ 上移", lambda: self._move_group(group_id, -1))
            if idx < len(ids) - 1:
                menu.addAction("↓ 下移", lambda: self._move_group(group_id, 1))
            menu.addSeparator()
            menu.addAction("删除分组", lambda: self._delete_group(group_id))
            menu.exec_(btn.mapToGlobal(pos))
        except Exception:
            pass

    def _rename_group(self, group_id):
        from PyQt5.QtWidgets import QInputDialog
        data = HistoryManager.load_all()
        old_name = ""
        for g in data.get("groups", []):
            if g["id"] == group_id:
                old_name = g["name"]
                break
        name, ok = QInputDialog.getText(self, "重命名分组", "新名称：", text=old_name)
        if ok and name.strip():
            HistoryManager.rename_group(group_id, name.strip())
            self.refresh()

    def _change_group_icon(self, group_id):
        from PyQt5.QtWidgets import QInputDialog
        icons = ["📁", "📂", "📚", "📖", "🔬", "🧪", "💻", "🎓", "📝", "⭐",
                 "🔖", "📌", "🏷️", "💡", "🔍", "📊", "🧬", "🌐", "🤖", "📐"]
        icon, ok = QInputDialog.getItem(self, "选择图标", "分组图标：", icons, 0, False)
        if ok:
            HistoryManager.update_group_icon(group_id, icon)
            self.refresh()

    def _move_group(self, group_id, direction):
        """上移 direction=-1，下移 direction=1"""
        data = HistoryManager.load_all()
        groups = data.get("groups", [])
        ids = [g["id"] for g in groups]
        idx = ids.index(group_id) if group_id in ids else -1
        if idx < 0:
            return
        new_idx = idx + direction
        if 0 <= new_idx < len(ids):
            ids[idx], ids[new_idx] = ids[new_idx], ids[idx]
            HistoryManager.reorder_groups(ids)
            self.refresh()

    def _delete_group(self, group_id):
        data = HistoryManager.load_all()
        name = ""
        count = 0
        for g in data.get("groups", []):
            if g["id"] == group_id:
                name = g["name"]
                break
        for r in data.get("records", []):
            if r.get("group_id") == group_id:
                count += 1
        reply = QMessageBox.question(
            self, "删除分组",
            f"确定删除分组「{name}」吗？\n该分组下的 {count} 个文件将移至「全部」。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            HistoryManager.delete_group(group_id)
            if self._current_group_id == group_id:
                self._current_group_id = None
            self.refresh()

    def _move_to_group(self, record_id, group_id):
        HistoryManager.move_to_group(record_id, group_id)
        self.refresh()

    def _toggle_tag(self, record_id, tag_id):
        HistoryManager.toggle_record_tag(record_id, tag_id)
        self.refresh()

    def _hist_context_menu(self, pos):
        item = self.list_w.itemAt(pos)
        if not item:
            return
        r = item.data(Qt.UserRole)
        if not r:
            return
        menu = _RoundMenu(self)
        # 在 Finder 中显示译文
        files = r.get("output_files", {})
        has_output = any(os.path.exists(files.get(m, "")) for m in ["dual","mono","side_by_side"])
        if has_output:
            menu.addAction("在 Finder 中显示译文", self._reveal_in_finder)
        # 打开原文
        src = r.get("file", {}).get("path", "")
        if src and os.path.exists(src):
            menu.addAction("打开原文", self._open_source)
            menu.addAction("在 Finder 中显示原文",
                           lambda: __import__("subprocess").Popen(["open", "-R", src]))
        menu.addSeparator()
        # 移到分组
        record_id = r.get("id")
        data = HistoryManager.load_all()
        groups = data.get("groups", [])
        if groups:
            grp_menu = _RoundMenu(self); grp_menu.setTitle("移到分组")
            grp_menu.addAction("无分组", lambda: self._move_to_group(record_id, None))
            for g in groups:
                gid = g["id"]
                grp_menu.addAction(f"{g['icon']} {g['name']}",
                    lambda _id=gid: self._move_to_group(record_id, _id))
            menu.addMenu(grp_menu)
        # 标签
        all_tags = data.get("tags", [])
        tag_menu = _RoundMenu(self); tag_menu.setTitle("标签")
        for t in all_tags:
            a = tag_menu.addAction(f"● {t['name']}")
            a.setCheckable(True)
            a.setChecked(t["id"] in r.get("tags", []))
            tid = t["id"]
            a.toggled.connect(lambda checked, _tid=tid: self._toggle_tag(record_id, _tid))
        tag_menu.addSeparator()
        tag_menu.addAction("新建标签…", self._create_tag)
        menu.addMenu(tag_menu)
        menu.addSeparator()
        menu.addAction("清空全部历史", self._clear)
        menu.exec_(self.list_w.viewport().mapToGlobal(pos))

    def _create_tag(self):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "新建标签", "标签名称：")
        if ok and name.strip():
            colors = ["#FF3B30", "#FF9F0A", "#34C759", "#007AFF", "#AF52DE", "#FF2D55"]
            import random
            HistoryManager.add_tag(name.strip(), random.choice(colors))

    def _on_select(self, current, previous):
        # 恢复上一个
        if previous:
            w = self.list_w.itemWidget(previous)
            if w and hasattr(w, '_l1'):
                w._l1.setStyleSheet(f"font-size:12px;color:{_C['t1']};background:transparent;")
                w._l2.setStyleSheet(f"font-size:11px;color:{_C['t2']};background:transparent;")
        # 当前变白
        if current:
            w = self.list_w.itemWidget(current)
            if w and hasattr(w, '_l1'):
                w._l1.setStyleSheet("font-size:12px;color:white;background:transparent;")
                w._l2.setStyleSheet("font-size:11px;color:rgba(255,255,255,0.7);background:transparent;")

        r = current.data(Qt.UserRole) if current else None
        if not r:
            return
        # 更新详情面板
        fname = r.get("file", {}).get("name", "—")
        svc = r.get("translation", {}).get("service", "—")
        li = r.get("translation", {}).get("lang_in", "")
        lo2 = r.get("translation", {}).get("lang_out", "")
        ts = r.get("timestamp", "")[:19].replace("T", " ")
        self.detail_label.setText(f"📄 {fname}\n🌐 {svc} · {li}→{lo2}\n🕐 {ts}")
        self._current_record = r
        # 显示文件操作按钮（有输出文件时）
        has_files = bool(r.get("output_files"))
        self._btn_reveal.setVisible(has_files)
        self._btn_open_src.setVisible(bool(r.get("file", {}).get("path")))
        # 加载预览
        if "output_files" in r:
            self.preview.set_output_files(r["output_files"])

    def _open_in_reader(self, item):
        """双击历史记录 → 加载到预览并聚焦预览区"""
        r = item.data(Qt.UserRole) if item else None
        if not r or "output_files" not in r:
            return
        self.preview.set_output_files(r["output_files"])
        self._preview_active = True
        self.preview.setFocus()

    def set_output_files(self, files):
        """外部调用（翻译完成后）"""
        self.preview.set_output_files(files)
        self.refresh()
        if self.list_w.count() > 0:
            self.list_w.setCurrentRow(0)

    def _clear(self):
        HistoryManager.clear(); self.refresh()

    def _reveal_in_finder(self):
        """在 Finder 中显示翻译输出文件"""
        r = self._current_record
        if not r:
            return
        import subprocess
        # 优先显示当前预览模式的文件，否则任一输出文件
        files = r.get("output_files", {})
        path = ""
        for mode in [self.preview.current_mode, "dual", "mono", "side_by_side"]:
            p = files.get(mode, "")
            if p and os.path.exists(p):
                path = p; break
        if path:
            subprocess.run(["open", "-R", path])

    def _open_source(self):
        """用系统默认应用打开源 PDF"""
        r = self._current_record
        if not r:
            return
        import subprocess
        path = r.get("file", {}).get("path", "")
        if path and os.path.exists(path):
            subprocess.run(["open", path])

    def update_theme(self, c):
        """深色/浅色切换时更新历史列表颜色"""
        self.preview.update_theme(c)
        self.preview._thumb_color = c["acc"] if self._preview_active else c["t3"]
        if self.preview._thumb_labels:
            self.preview._highlight_thumb(self.preview.current_page)
        # 刷新所有历史条目颜色
        for i in range(self.list_w.count()):
            item = self.list_w.item(i)
            w = self.list_w.itemWidget(item)
            if w and hasattr(w, '_l1'):
                is_sel = (item == self.list_w.currentItem())
                if is_sel:
                    w._l1.setStyleSheet("font-size:12px;color:white;background:transparent;")
                    w._l2.setStyleSheet("font-size:11px;color:rgba(255,255,255,0.7);background:transparent;")
                else:
                    w._l1.setStyleSheet(f"font-size:12px;color:{c['t1']};background:transparent;")
                    w._l2.setStyleSheet(f"font-size:11px;color:{c['t2']};background:transparent;")


# ═══════════════════════════════════════════════════════════════
#  设置页面
# ═══════════════════════════════════════════════════════════════

class SettingsPage(QWidget):
    dark_mode_changed = pyqtSignal(bool)
    theme_color_changed = pyqtSignal(str)

    SERVICE_CONFIGS = {
        # 推荐
        "DeepSeek":        {"key_ph":"密钥",  "models":["deepseek-chat","deepseek-reasoner","deepseek-coder"], "url":"https://api.deepseek.com/v1"},
        "OpenAI":          {"key_ph":"sk-...", "models":["gpt-4o","gpt-4o-mini","gpt-4-turbo","gpt-3.5-turbo","o1","o1-mini","o1-pro"], "url":"https://api.openai.com/v1"},
        # 国际服务
        "Azure OpenAI":    {"key_ph":"密钥",  "models":["gpt-4o","gpt-4-turbo","gpt-35-turbo"], "url":"https://YOUR_RESOURCE.openai.azure.com"},
        "DeepL":           {"key_ph":"密钥",  "models":[], "url":""},
        "Gemini":          {"key_ph":"密钥",  "models":["gemini-pro","gemini-1.5-pro","gemini-1.5-flash","gemini-2.0-flash"], "url":""},
        "Groq":            {"key_ph":"密钥",  "models":["llama-3.1-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768","llama-3.3-70b-versatile"], "url":"https://api.groq.com/openai/v1"},
        # 国产大模型
        "Zhipu 智谱":     {"key_ph":"密钥",  "models":["glm-4","glm-4-flash","glm-4-plus","glm-3-turbo","cogview-3"], "url":"https://open.bigmodel.cn/api/paas/v4"},
        "Qwen 通义千问":  {"key_ph":"密钥",  "models":["qwen-turbo","qwen-plus","qwen-max","qwen-long"], "url":"https://dashscope.aliyuncs.com/compatible-mode/v1"},
        "Tencent 腾讯":   {"key_ph":"密钥",  "models":["hunyuan-pro","hunyuan-standard","hunyuan-lite"], "url":""},
        "Silicon 硅基流动":{"key_ph":"密钥",  "models":["deepseek-ai/DeepSeek-V3","Qwen/Qwen2.5-72B-Instruct","Pro/THUDM/glm-4-9b-chat"], "url":"https://api.siliconflow.cn/v1"},
        "ModelScope":      {"key_ph":"密钥",  "models":["qwen-turbo","qwen-plus"], "url":"https://dashscope.aliyuncs.com/compatible-mode/v1"},
        # 本地 & 其他
        "Ollama 本地":     {"key_ph":"留空",  "models":["qwen2.5:7b","llama3.1:8b","gemma2:9b","deepseek-r1:8b"], "url":"http://localhost:11434/v1"},
        "Argos Translate":  {"key_ph":"留空",  "models":[], "url":""},
        "AnythingLLM":     {"key_ph":"密钥",  "models":[], "url":"http://localhost:3001/api/v1"},
        "Grok":            {"key_ph":"密钥",  "models":["grok-2","grok-2-mini"], "url":"https://api.x.ai/v1"},
        # 自定义
        "OpenAI 兼容":    {"key_ph":"密钥",  "models":["自定义模型"], "url":""},
    }


    def __init__(self):
        super().__init__()
        self.setObjectName("PA")
        lo = QVBoxLayout(self); lo.setContentsMargins(24,10,24,10); lo.setSpacing(4)

        hdr = QHBoxLayout()
        t = QLabel("设置"); t.setObjectName("PT0"); hdr.addWidget(t)
        hdr.addStretch()
        st = QLabel("翻译服务与偏好设置"); st.setObjectName("PT1"); hdr.addWidget(st)
        lo.addLayout(hdr)

        cols = QHBoxLayout(); cols.setSpacing(20)
        cfg = UserConfigManager.load()
        from PyQt5.QtWidgets import QGridLayout, QTextEdit

        # ══════════════════════════════════════════
        # 左列：翻译服务 → AI 助手
        # ══════════════════════════════════════════
        left = QVBoxLayout(); left.setSpacing(2)

        # ── 翻译服务配置 ──
        sl3 = QLabel("翻译服务配置"); sl3.setObjectName("SL"); left.addWidget(sl3)
        self.svc_card = _card()
        svc_outer = QVBoxLayout(self.svc_card)
        svc_outer.setContentsMargins(16,12,16,12); svc_outer.setSpacing(4)
        self.svc_selector = QComboBox()
        self.svc_selector.addItems(list(self.SERVICE_CONFIGS.keys()))
        self.svc_selector.currentTextChanged.connect(self._show_service_config)
        svc_outer.addWidget(self.svc_selector)
        self.svc_layout = QVBoxLayout(); self.svc_layout.setSpacing(2)
        svc_outer.addLayout(self.svc_layout)
        left.addWidget(self.svc_card)

        self.api_inputs = {}
        for svc_name, conf in self.SERVICE_CONFIGS.items():
            key_inp = QLineEdit(); key_inp.setPlaceholderText(f"API Key: {conf['key_ph']}")
            key_inp.setEchoMode(QLineEdit.Password)
            saved = cfg.get(f"api_{svc_name}", "")
            if saved: key_inp.setText(UserConfigManager.decode_sensitive(saved))
            key_inp.editingFinished.connect(self._save)
            self.api_inputs[svc_name] = {"key": key_inp}
            if conf["models"]:
                mc = QComboBox(); mc.setEditable(True)
                mc.addItems(conf["models"])
                saved_m = cfg.get(f"model_{svc_name}", "")
                if saved_m: mc.setCurrentText(saved_m)
                mc.currentTextChanged.connect(self._save)
                self.api_inputs[svc_name]["model"] = mc
            if conf["url"]:
                ui = QLineEdit()
                saved_u = cfg.get(f"url_{svc_name}", "")
                ui.setText(saved_u if saved_u else conf["url"])
                ui.editingFinished.connect(self._save)
                self.api_inputs[svc_name]["url"] = ui

        # ── AI 助手（摘要 / 问答服务） ──
        sl_ai = QLabel("AI 助手"); sl_ai.setObjectName("SL"); left.addWidget(sl_ai)
        ai_card = _card(); ai_lo = QVBoxLayout(ai_card)
        ai_lo.setContentsMargins(16, 12, 16, 12); ai_lo.setSpacing(6)

        ai_desc = QLabel("摘要与问答使用的 AI 服务，默认与翻译服务相同")
        ai_desc.setObjectName("Cap"); ai_desc.setWordWrap(True)
        ai_lo.addWidget(ai_desc)

        self._ai_default_row = QWidget()
        _adr_lo = QHBoxLayout(self._ai_default_row)
        _adr_lo.setContentsMargins(0, 2, 0, 2); _adr_lo.setSpacing(8)
        self._ai_status_label = QLabel("与翻译服务相同")
        self._ai_status_label.setStyleSheet(
            f"font-size:12px;font-weight:500;color:{_C['ok']};background:transparent;")
        _adr_lo.addWidget(self._ai_status_label); _adr_lo.addStretch()
        self._ai_toggle_btn = QPushButton("自定义")
        self._ai_toggle_btn.setObjectName("Gh"); self._ai_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._ai_toggle_btn.setStyleSheet("font-size:11px;padding:3px 10px;")
        self._ai_toggle_btn.clicked.connect(self._toggle_assistant_config)
        _adr_lo.addWidget(self._ai_toggle_btn)
        ai_lo.addWidget(self._ai_default_row)

        self._ai_custom_frame = QWidget()
        _acf_lo = QVBoxLayout(self._ai_custom_frame)
        _acf_lo.setContentsMargins(0, 6, 0, 0); _acf_lo.setSpacing(10)

        for _f_label, _f_attr, _f_type in [
            ("服务",    "_ai_svc_combo",   "combo"),
            ("API Key", "_ai_key_input",   "password"),
            ("模型",    "_ai_model_combo", "combo_edit"),
            ("Base URL","_ai_url_input",   "line"),
        ]:
            _grp = QVBoxLayout(); _grp.setSpacing(3)
            _lbl = QLabel(_f_label); _lbl.setStyleSheet(
                f"font-size:11px;font-weight:500;color:{_C['t2']};background:transparent;padding:0;")
            _grp.addWidget(_lbl)
            if _f_type == "combo":
                w = QComboBox()
                from ui.ai_client import CHAT_SERVICES
                w.addItems([name for name, _, _ in CHAT_SERVICES])
                w.currentTextChanged.connect(self._on_assistant_svc_changed)
            elif _f_type == "password":
                w = QLineEdit(); w.setEchoMode(QLineEdit.Password)
                w.setPlaceholderText("密钥")
                w.editingFinished.connect(self._save_assistant_config)
            elif _f_type == "combo_edit":
                w = QComboBox(); w.setEditable(True)
                w.currentTextChanged.connect(self._save_assistant_config)
            else:
                w = QLineEdit(); w.setPlaceholderText("留空使用默认")
                w.editingFinished.connect(self._save_assistant_config)
            setattr(self, _f_attr, w)
            _grp.addWidget(w)
            _acf_lo.addLayout(_grp)

        _reset_row = QHBoxLayout(); _reset_row.addStretch()
        _reset_btn = QPushButton("恢复默认"); _reset_btn.setObjectName("GhDanger")
        _reset_btn.setCursor(Qt.PointingHandCursor)
        _reset_btn.setStyleSheet("font-size:11px;padding:3px 10px;")
        _reset_btn.clicked.connect(self._reset_assistant_config)
        _reset_row.addWidget(_reset_btn)
        _acf_lo.addLayout(_reset_row)

        self._ai_custom_frame.setVisible(False)
        ai_lo.addWidget(self._ai_custom_frame)
        self._load_assistant_config()
        left.addWidget(ai_card)
        left.addStretch()

        # ══════════════════════════════════════════
        # 右列：偏好 → 提示词 → 术语库 → Zotero
        # ══════════════════════════════════════════
        right = QVBoxLayout(); right.setSpacing(2)

        # ── 偏好设置 ──
        sl_app = QLabel("偏好设置"); sl_app.setObjectName("SL"); right.addWidget(sl_app)
        c = _card(); cl = QVBoxLayout(c); cl.setContentsMargins(16,12,16,12); cl.setSpacing(6)
        self.dark_check = QCheckBox("深色模式"); self.dark_check.toggled.connect(self.dark_mode_changed.emit)
        self.cache_check = QCheckBox("翻译缓存"); self.cache_check.setChecked(True)
        self.ai_check = QCheckBox("AI 布局检测"); self.ai_check.setChecked(True)
        self.font_check = QCheckBox("字体子集化")
        _pref_grid = QGridLayout(); _pref_grid.setSpacing(6)
        _pref_grid.addWidget(self.dark_check, 0, 0)
        _pref_grid.addWidget(self.cache_check, 0, 1)
        _pref_grid.addWidget(self.ai_check, 1, 0)
        _pref_grid.addWidget(self.font_check, 1, 1)
        cl.addLayout(_pref_grid)
        self.theme_row = QWidget(); tr_lo = QHBoxLayout(self.theme_row)
        tr_lo.setContentsMargins(0,2,0,2); tr_lo.setSpacing(6)
        tr_lbl = QLabel("主题色"); tr_lo.addWidget(tr_lbl)
        THEME_COLORS = [
            ("#0071E3","蓝"),("#FF6B6B","红"),("#34C759","绿"),
            ("#AF52DE","紫"),("#FF9F0A","橙"),("#FF2D55","粉"),
            ("#5AC8FA","青"),("#FFD60A","黄"),
        ]
        self._theme_dots = []
        for hex_c, name in THEME_COLORS:
            dot = QPushButton(); dot.setFixedSize(18, 18); dot.setCursor(Qt.PointingHandCursor)
            dot.setToolTip(name); dot.setProperty("hex", hex_c)
            dot.setStyleSheet(
                f"QPushButton{{background:{hex_c};border:2px solid transparent;"
                f"border-radius:9px;}}QPushButton:hover{{border-color:{hex_c};}}")
            dot.clicked.connect(lambda _, h=hex_c: self._set_theme_color(h))
            tr_lo.addWidget(dot); self._theme_dots.append(dot)
        tr_lo.addStretch()
        cl.addWidget(self.theme_row)
        self.theme_row.setVisible(UserConfigManager.load().get("theme_unlocked", False))
        right.addWidget(c)

        # ── 翻译提示词 ──
        from ui.prompt_manager import PromptTemplateManager
        sl4 = QLabel("翻译提示词"); sl4.setObjectName("SL"); right.addWidget(sl4)
        c4 = _card(); cl4 = QVBoxLayout(c4); cl4.setContentsMargins(16,10,16,10); cl4.setSpacing(2)
        pr = QHBoxLayout(); pr.setSpacing(4)
        self.prompt_preset = QComboBox()
        self._refresh_prompt_list()
        self.prompt_preset.currentTextChanged.connect(self._on_prompt_preset)
        pr.addWidget(self.prompt_preset, 1)
        cl4.addLayout(pr)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("提示词… {lang_out} {lang_in} {text}")
        self.prompt_edit.setMaximumHeight(42)
        saved_prompt = cfg.get("prompt", "")
        if saved_prompt: self.prompt_edit.setPlainText(saved_prompt)
        cl4.addWidget(self.prompt_edit)
        btn_row = QHBoxLayout(); btn_row.setSpacing(2)
        for label, slot in [
            ("保存", self._save_prompt_template),
            ("新建", self._new_prompt_template),
            ("导入", self._import_prompts),
            ("导出", self._export_prompts),
        ]:
            b = QPushButton(label); b.setObjectName("Gh"); b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("font-size:11px;padding:2px 6px;"); b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        del_btn = QPushButton("删除"); del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setObjectName("GhDanger"); del_btn.setStyleSheet("font-size:11px;padding:2px 6px;")
        del_btn.clicked.connect(self._delete_prompt_template)
        btn_row.addWidget(del_btn)
        cl4.addLayout(btn_row)
        right.addWidget(c4)

        # ── 术语库 ──
        from ui.glossary_manager import GlossaryManager
        sl5 = QLabel("术语库"); sl5.setObjectName("SL"); right.addWidget(sl5)
        c5 = _card(); cl5 = QVBoxLayout(c5); cl5.setContentsMargins(16,10,16,10); cl5.setSpacing(3)
        gr = QHBoxLayout(); gr.setSpacing(6)
        self.gloss_selector = QComboBox()
        self._refresh_gloss_list()
        self.gloss_selector.currentTextChanged.connect(self._on_gloss_changed)
        gr.addWidget(self.gloss_selector, 1)
        self.gloss_count = QLabel(""); self.gloss_count.setObjectName("Cap")
        self.gloss_count.setStyleSheet("font-size:10px;")
        gr.addWidget(self.gloss_count)
        cl5.addLayout(gr); self._update_gloss_count()
        # 内联添加术语
        _add_row = QHBoxLayout(); _add_row.setSpacing(4)
        self._gloss_src = QLineEdit(); self._gloss_src.setPlaceholderText("原文")
        self._gloss_src.setStyleSheet("font-size:11px;padding:4px 8px;")
        self._gloss_dst = QLineEdit(); self._gloss_dst.setPlaceholderText("译文")
        self._gloss_dst.setStyleSheet("font-size:11px;padding:4px 8px;")
        _add_btn = QPushButton("添加"); _add_btn.setObjectName("Gh")
        _add_btn.setCursor(Qt.PointingHandCursor)
        _add_btn.setStyleSheet("font-size:11px;padding:2px 8px;")
        _add_btn.clicked.connect(self._add_gloss_term)
        _add_row.addWidget(self._gloss_src, 1)
        _add_row.addWidget(self._gloss_dst, 1)
        _add_row.addWidget(_add_btn)
        cl5.addLayout(_add_row)
        gbtn = QHBoxLayout(); gbtn.setSpacing(2)
        for label, slot in [
            ("新建", self._new_glossary), ("导入", self._import_glossary),
            ("导出", self._export_glossary),
        ]:
            b = QPushButton(label); b.setObjectName("Gh"); b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("font-size:11px;padding:2px 6px;"); b.clicked.connect(slot)
            gbtn.addWidget(b)
        gbtn.addStretch()
        gdel = QPushButton("删除"); gdel.setCursor(Qt.PointingHandCursor)
        gdel.setObjectName("GhDanger"); gdel.setStyleSheet("font-size:11px;padding:2px 6px;")
        gdel.clicked.connect(self._delete_glossary); gbtn.addWidget(gdel)
        cl5.addLayout(gbtn)
        right.addWidget(c5)

        # ── Zotero 联动 ──
        sl_zot = QLabel("Zotero 联动"); sl_zot.setObjectName("SL"); right.addWidget(sl_zot)
        zot_card = _card(); zot_lo = QVBoxLayout(zot_card)
        zot_lo.setContentsMargins(14,10,14,10); zot_lo.setSpacing(4)
        self._zot_sbs = QCheckBox("左右并排 (Side by Side)")
        self._zot_dual = QCheckBox("双语对照 (Dual)")
        self._zot_mono = QCheckBox("仅翻译 (Mono)")
        self._zot_keep_copy = QCheckBox("保留本地副本")
        cfg = UserConfigManager.load()
        _zot_modes = cfg.get("zotero_output_modes", ["side_by_side"])
        self._zot_sbs.setChecked("side_by_side" in _zot_modes)
        self._zot_dual.setChecked("dual" in _zot_modes)
        self._zot_mono.setChecked("mono" in _zot_modes)
        self._zot_keep_copy.setChecked(cfg.get("zotero_keep_copy", True))
        _zot_grid = QGridLayout(); _zot_grid.setSpacing(4)
        _zot_grid.addWidget(self._zot_sbs, 0, 0)
        _zot_grid.addWidget(self._zot_dual, 0, 1)
        _zot_grid.addWidget(self._zot_mono, 1, 0)
        _zot_grid.addWidget(self._zot_keep_copy, 1, 1)
        for _cb in (self._zot_sbs, self._zot_dual, self._zot_mono, self._zot_keep_copy):
            _cb.stateChanged.connect(self._save_zotero_modes)
        zot_lo.addLayout(_zot_grid)
        zot_lo.addWidget(_div())
        _auto_row = QHBoxLayout(); _auto_row.setSpacing(6)
        _auto_desc = QLabel("Zotero 插件"); _auto_desc.setObjectName("Cap")
        _auto_row.addWidget(_auto_desc)
        self._zot_status = QLabel(""); self._zot_status.setObjectName("Cap")
        _auto_row.addWidget(self._zot_status); _auto_row.addStretch()
        self._zot_install_btn = QPushButton("一键安装")
        self._zot_install_btn.setObjectName("Gh"); self._zot_install_btn.setCursor(Qt.PointingHandCursor)
        self._zot_install_btn.clicked.connect(self._install_zotero_plugin)
        _auto_row.addWidget(self._zot_install_btn)
        zot_lo.addLayout(_auto_row)
        QTimer.singleShot(500, self._check_zotero_plugin)
        right.addWidget(zot_card)

        # ── 使用指南（紧凑） ──
        sl_guide = QLabel("使用指南"); sl_guide.setObjectName("SL"); right.addWidget(sl_guide)
        guide_card = _card("sm"); guide_lo = QVBoxLayout(guide_card)
        guide_lo.setContentsMargins(12,8,12,8); guide_lo.setSpacing(1)
        for tip in [
            "Google / Bing 无需配置，开箱即用",
            "OpenAI 兼容接口可对接任意第三方服务",
            "Ollama 本地需先启动服务",
            "50 页以上建议开启分块翻译",
        ]:
            tl = QLabel(f"·  {tip}"); tl.setObjectName("Cap")
            tl.setStyleSheet("font-size:10px;padding:1px 0;")
            guide_lo.addWidget(tl)
        guide_lo.addWidget(_div())
        self._kb_labels = []
        kb_grid = QGridLayout(); kb_grid.setHorizontalSpacing(6); kb_grid.setVerticalSpacing(1)
        for i, (key, desc) in enumerate([
            ("Ctrl+滚轮","缩放"), ("← →","切换"), ("页码+回车","跳转"),
        ]):
            kl = QLabel(key); kl.setObjectName("KBKey"); kl.setStyleSheet("font-size:9px;padding:2px 5px;")
            kd = QLabel(desc); kd.setObjectName("Cap"); kd.setStyleSheet("font-size:9px;")
            kb_grid.addWidget(kl, 0, i * 2); kb_grid.addWidget(kd, 0, i * 2 + 1)
            self._kb_labels.append(kl)
        guide_lo.addLayout(kb_grid)
        guide_lo.addWidget(_div())
        _paths_col = QVBoxLayout(); _paths_col.setSpacing(1)
        for _pname, _pfile in [
            ("配置", "~/pdf2zh_gui_config.json"),
            ("历史", "~/pdf2zh_history.json"),
            ("术语库", "~/pdf2zh_glossary_*.csv"),
        ]:
            _pl = QLabel(f"{_pname}  {_pfile}")
            _pl.setObjectName("Cap"); _pl.setStyleSheet("font-size:9px;padding:0;")
            _paths_col.addWidget(_pl)
        guide_lo.addLayout(_paths_col)
        _paths_btn_row = QHBoxLayout(); _paths_btn_row.addStretch()
        open_dir_btn = QPushButton("打开数据目录"); open_dir_btn.setObjectName("Gh")
        open_dir_btn.setCursor(Qt.PointingHandCursor)
        open_dir_btn.setStyleSheet("font-size:10px;padding:2px 6px;")
        open_dir_btn.clicked.connect(lambda: __import__('subprocess').run(['open', str(__import__('pathlib').Path.home())]))
        _paths_btn_row.addWidget(open_dir_btn)
        guide_lo.addLayout(_paths_btn_row)
        right.addWidget(guide_card)
        right.addStretch()

        cols.addLayout(left, 5)
        cols.addLayout(right, 4)
        lo.addLayout(cols)

        # 初始显示第一个服务
        self._show_service_config(self.svc_selector.currentText())

    def _show_service_config(self, svc_name):
        """切换显示选中服务的配置"""
        # 清空当前
        while self.svc_layout.count():
            item = self.svc_layout.takeAt(0)
            w = item.widget()
            if w: w.setParent(None)
            sub = item.layout()
            if sub:
                while sub.count():
                    si = sub.takeAt(0)
                    if si.widget(): si.widget().setParent(None)

        if svc_name not in self.api_inputs:
            return
        inputs = self.api_inputs[svc_name]

        # API Key
        kl = QLabel("API Key"); kl.setObjectName("FL")
        self.svc_layout.addWidget(kl)
        self.svc_layout.addWidget(inputs["key"])
        inputs["key"].setParent(self.svc_card)
        inputs["key"].show()

        # 模型
        if "model" in inputs:
            ml = QLabel("模型"); ml.setObjectName("FL")
            self.svc_layout.addWidget(ml)
            self.svc_layout.addWidget(inputs["model"])
            inputs["model"].setParent(self.svc_card)
            inputs["model"].show()

        # Base URL
        if "url" in inputs:
            ul = QLabel("Base URL"); ul.setObjectName("FL")
            self.svc_layout.addWidget(ul)
            self.svc_layout.addWidget(inputs["url"])
            inputs["url"].setParent(self.svc_card)
            inputs["url"].show()

        # 测试连接按钮
        self.svc_layout.addSpacing(4)
        self._test_label = QLabel("")
        self._test_label.setObjectName("Cap")
        test_btn = QPushButton("测试连接")
        test_btn.setObjectName("Gh"); test_btn.setCursor(Qt.PointingHandCursor)
        test_btn.clicked.connect(lambda: self._test_connection(svc_name))
        test_row = QHBoxLayout(); test_row.addStretch()
        test_row.addWidget(self._test_label)
        test_row.addWidget(test_btn)
        self.svc_layout.addLayout(test_row)

    def _test_connection(self, svc_name):
        """测试翻译服务连接"""
        self._save()  # 先保存，确保 API Key 写入配置
        self._test_label.setText("测试中…")
        self._test_label.setStyleSheet("color:#FF9F0A;font-size:11px;")
        QApplication.processEvents()

        inputs = self.api_inputs.get(svc_name, {})
        key = inputs.get("key")
        key_val = key.text().strip() if key else ""
        url_w = inputs.get("url")
        url_val = url_w.text().strip() if url_w else ""

        try:
            import requests
            # 对于 OpenAI 兼容类服务，测试 /models 端点
            if url_val and ("openai" in url_val or "deepseek" in url_val
                           or "siliconflow" in url_val or "groq" in url_val
                           or "bigmodel" in url_val or "dashscope" in url_val
                           or "localhost" in url_val or "x.ai" in url_val):
                headers = {"Authorization": f"Bearer {key_val}"} if key_val else {}
                r = requests.get(f"{url_val}/models", headers=headers, timeout=10)
                if r.status_code in (200, 401, 403):
                    self._test_label.setText("✅ 连接成功")
                    self._test_label.setStyleSheet(f"color:{_C['ok']};font-size:11px;")
                else:
                    self._test_label.setText(f"⚠️ HTTP {r.status_code}")
                    self._test_label.setStyleSheet(f"color:{_C['t2']};font-size:11px;")
            elif "deepl" in svc_name.lower():
                r = requests.get("https://api-free.deepl.com/v2/usage",
                    headers={"Authorization": f"DeepL-Auth-Key {key_val}"}, timeout=10)
                self._test_label.setText("✅ 连接成功" if r.ok else f"⚠️ {r.status_code}")
                self._test_label.setStyleSheet(f"color:{_C['ok'] if r.ok else _C['t2']};font-size:11px;")
            else:
                self._test_label.setText("✅ 免费服务，无需测试")
                self._test_label.setStyleSheet(f"color:{_C['ok']};font-size:11px;")
        except requests.exceptions.ConnectionError:
            self._test_label.setText("❌ 无法连接")
            self._test_label.setStyleSheet(f"color:{_C['err']};font-size:11px;")
        except Exception as e:
            self._test_label.setText(f"❌ {str(e)[:30]}")
            self._test_label.setStyleSheet(f"color:{_C['err']};font-size:11px;")

    def _refresh_prompt_list(self):
        from ui.prompt_manager import PromptTemplateManager
        self.prompt_preset.blockSignals(True)
        current = self.prompt_preset.currentText()
        self.prompt_preset.clear()
        templates = PromptTemplateManager.load_all()
        self.prompt_preset.addItems(list(templates.keys()))
        idx = self.prompt_preset.findText(current)
        if idx >= 0:
            self.prompt_preset.setCurrentIndex(idx)
        self.prompt_preset.blockSignals(False)

    def _on_prompt_preset(self, text):
        from ui.prompt_manager import PromptTemplateManager
        templates = PromptTemplateManager.load_all()
        val = templates.get(text, "")
        self.prompt_edit.setPlainText(val)
        self._save()

    def _save_prompt_template(self):
        """保存当前内容到选中的模板名"""
        from ui.prompt_manager import PromptTemplateManager
        name = self.prompt_preset.currentText()
        content = self.prompt_edit.toPlainText().strip()
        PromptTemplateManager.save_template(name, content)
        self._refresh_prompt_list()

    def _new_prompt_template(self):
        """新建模板"""
        from ui.prompt_manager import PromptTemplateManager
        name, ok = QLineEdit.staticMetaObject, False  # placeholder
        # 用简单的输入对话框
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "新建模板", "模板名称:")
        if ok and name.strip():
            content = self.prompt_edit.toPlainText().strip()
            PromptTemplateManager.save_template(name.strip(), content)
            self._refresh_prompt_list()
            idx = self.prompt_preset.findText(name.strip())
            if idx >= 0:
                self.prompt_preset.setCurrentIndex(idx)

    def _delete_prompt_template(self):
        """删除用户模板"""
        from ui.prompt_manager import PromptTemplateManager, DEFAULT_TEMPLATES
        name = self.prompt_preset.currentText()
        if name in DEFAULT_TEMPLATES:
            return  # 不能删默认模板
        PromptTemplateManager.delete_template(name)
        self._refresh_prompt_list()

    def _import_prompts(self):
        """从 JSON 文件导入模板"""
        from ui.prompt_manager import PromptTemplateManager
        path, _ = QFileDialog.getOpenFileName(self, "导入模板", "", "JSON (*.json)")
        if path:
            count = PromptTemplateManager.import_from_file(path)
            self._refresh_prompt_list()

    def _export_prompts(self):
        """导出所有模板到 JSON"""
        from ui.prompt_manager import PromptTemplateManager
        path, _ = QFileDialog.getSaveFileName(self, "导出模板", "pdf2zh_prompts.json", "JSON (*.json)")
        if path:
            PromptTemplateManager.export_to_file(path)

    def _set_theme_color(self, hex_color):
        """切换主题色并即时应用"""
        cfg = UserConfigManager.load()
        cfg["theme_color"] = hex_color
        UserConfigManager.save(cfg)
        # 高亮选中的色块
        for dot in self._theme_dots:
            sel = dot.property("hex") == hex_color
            dot.setStyleSheet(
                f"QPushButton{{background:{dot.property('hex')};"
                f"border:2px solid {'#1d1d1f' if sel else 'transparent'};"
                f"border-radius:9px;}}QPushButton:hover{{border-color:{dot.property('hex')};}}")
        # 通知 MainWindow 刷新主题
        self.theme_color_changed.emit(hex_color)

    def _save(self, *args):
        cfg = UserConfigManager.load()
        for svc_name, inputs in self.api_inputs.items():
            key_val = inputs["key"].text().strip()
            cfg[f"api_{svc_name}"] = UserConfigManager.encode_sensitive(key_val) if key_val else ""
            if "model" in inputs:
                cfg[f"model_{svc_name}"] = inputs["model"].currentText().strip()
            if "url" in inputs:
                cfg[f"url_{svc_name}"] = inputs["url"].text().strip()
        cfg["prompt"] = self.prompt_edit.toPlainText().strip()
        UserConfigManager.save(cfg)

    def _save_zotero_modes(self, *args):
        modes = []
        if self._zot_sbs.isChecked(): modes.append("side_by_side")
        if self._zot_dual.isChecked(): modes.append("dual")
        if self._zot_mono.isChecked(): modes.append("mono")
        if not modes:
            modes = ["side_by_side"]
            self._zot_sbs.blockSignals(True)
            self._zot_sbs.setChecked(True)
            self._zot_sbs.blockSignals(False)
        cfg = UserConfigManager.load()
        cfg["zotero_output_modes"] = modes
        cfg["zotero_keep_copy"] = self._zot_keep_copy.isChecked()
        UserConfigManager.save(cfg)

    # ── AI 助手配置 ──

    def _load_assistant_config(self):
        """加载 AI 助手独立配置状态"""
        cfg = UserConfigManager.load()
        is_custom = cfg.get("assistant_custom", False)
        if is_custom:
            self._ai_custom_frame.setVisible(True)
            self._ai_status_label.setText("使用独立配置")
            self._ai_status_label.setStyleSheet(
                f"font-size:12px;font-weight:500;color:{_C['acc']};background:transparent;")
            self._ai_toggle_btn.setVisible(False)
            svc = cfg.get("assistant_service", "")
            if svc:
                idx = self._ai_svc_combo.findText(svc)
                if idx >= 0: self._ai_svc_combo.setCurrentIndex(idx)
            api_raw = cfg.get("assistant_api_key", "")
            if api_raw:
                self._ai_key_input.setText(UserConfigManager.decode_sensitive(api_raw))
            model = cfg.get("assistant_model", "")
            if model: self._ai_model_combo.setCurrentText(model)
            url = cfg.get("assistant_url", "")
            if url: self._ai_url_input.setText(url)
        else:
            self._ai_custom_frame.setVisible(False)
            self._ai_status_label.setText("✓ 使用翻译服务配置")
            self._ai_toggle_btn.setText("自定义")

    def _toggle_assistant_config(self):
        """展开自定义 AI 助手配置"""
        self._ai_custom_frame.setVisible(True)
        self._ai_status_label.setText("使用独立配置")
        self._ai_status_label.setStyleSheet(
            f"font-size:12px;font-weight:500;color:{_C['acc']};background:transparent;")
        self._ai_toggle_btn.setVisible(False)
        # 预填当前翻译服务配置
        from ui.ai_client import detect_service
        svc = detect_service()
        if svc:
            idx = self._ai_svc_combo.findText(svc["name"])
            if idx >= 0:
                self._ai_svc_combo.blockSignals(True)
                self._ai_svc_combo.setCurrentIndex(idx)
                self._ai_svc_combo.blockSignals(False)
            self._ai_key_input.setText(svc.get("api_key", ""))
            self._ai_model_combo.setCurrentText(svc.get("model", ""))
            self._ai_url_input.setText(svc.get("base_url", ""))
        self._on_assistant_svc_changed(self._ai_svc_combo.currentText())
        self._save_assistant_config()

    def _on_assistant_svc_changed(self, svc_name):
        """切换 AI 助手服务时更新模型候选列表"""
        from ui.ai_client import CHAT_SERVICES
        # 查找默认 URL
        default_url = ""
        for name, url, _ in CHAT_SERVICES:
            if name == svc_name:
                default_url = url; break
        if not self._ai_url_input.text().strip() or True:
            self._ai_url_input.setPlaceholderText(default_url or "自定义 URL")
        # 更新模型列表
        cur_model = self._ai_model_combo.currentText()
        self._ai_model_combo.blockSignals(True)
        self._ai_model_combo.clear()
        svc_conf = self.SERVICE_CONFIGS.get(svc_name, {})
        if svc_conf.get("models"):
            self._ai_model_combo.addItems(svc_conf["models"])
        if cur_model:
            self._ai_model_combo.setCurrentText(cur_model)
        self._ai_model_combo.blockSignals(False)
        self._save_assistant_config()

    def _save_assistant_config(self, *args):
        """保存 AI 助手独立配置"""
        if not self._ai_custom_frame.isVisible():
            return
        cfg = UserConfigManager.load()
        cfg["assistant_custom"] = True
        cfg["assistant_service"] = self._ai_svc_combo.currentText()
        key = self._ai_key_input.text().strip()
        cfg["assistant_api_key"] = UserConfigManager.encode_sensitive(key) if key else ""
        cfg["assistant_model"] = self._ai_model_combo.currentText()
        cfg["assistant_url"] = self._ai_url_input.text().strip()
        UserConfigManager.save(cfg)

    def _reset_assistant_config(self):
        """恢复 AI 助手使用翻译服务配置"""
        cfg = UserConfigManager.load()
        for k in ("assistant_custom", "assistant_service", "assistant_api_key",
                   "assistant_model", "assistant_url"):
            cfg.pop(k, None)
        UserConfigManager.save(cfg)
        self._ai_custom_frame.setVisible(False)
        self._ai_status_label.setText("与翻译服务相同")
        self._ai_status_label.setStyleSheet(
            f"font-size:12px;font-weight:500;color:{_C['ok']};background:transparent;")
        self._ai_toggle_btn.setVisible(True)
        # 清空输入
        self._ai_key_input.clear()
        self._ai_model_combo.setCurrentIndex(0)
        self._ai_url_input.clear()

    def _install_zotero_plugin(self):
        """一键安装 pdf2zh Connector 到 Zotero"""
        import glob, shutil, subprocess
        xpi = _res('assets', 'pdf2zh-connector.xpi')
        if not os.path.exists(xpi):
            self._zot_status.setText("插件文件缺失")
            self._zot_status.setStyleSheet("color:#FF3B30;")
            return
        # 查找 Zotero profile 目录
        profiles_dir = os.path.expanduser("~/Library/Application Support/Zotero/Profiles")
        profiles = glob.glob(os.path.join(profiles_dir, "*.default"))
        if not profiles:
            self._zot_status.setText("找不到 Zotero 配置目录")
            self._zot_status.setStyleSheet("color:#FF3B30;")
            return
        profile = profiles[0]
        # 1. 复制 XPI 到 extensions 目录
        ext_dir = os.path.join(profile, "extensions")
        os.makedirs(ext_dir, exist_ok=True)
        dst = os.path.join(ext_dir, "pdf2zh-connector@aarongig.com.xpi")
        shutil.copy2(xpi, dst)
        # 2. 设置 autoDisableScopes=0 允许 profile 级别的扩展自动加载
        prefs_path = os.path.join(profile, "prefs.js")
        pref_line = 'user_pref("extensions.autoDisableScopes", 0);\n'
        try:
            prefs_content = open(prefs_path, 'r', encoding='utf-8').read()
            if 'autoDisableScopes' not in prefs_content:
                with open(prefs_path, 'a', encoding='utf-8') as f:
                    f.write(pref_line)
        except FileNotFoundError:
            with open(prefs_path, 'w', encoding='utf-8') as f:
                f.write(pref_line)
        # 3. 清除启动缓存，强制 Zotero 重新扫描扩展
        cache = os.path.join(profile, "addonStartup.json.lz4")
        if os.path.exists(cache):
            os.remove(cache)
        # 询问是否重启 Zotero
        reply = QMessageBox.question(
            self, "安装成功",
            "pdf2zh Connector 已部署到 Zotero，重启 Zotero 后生效。\n\n现在重启 Zotero？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            subprocess.run(["pkill", "-x", "zotero"], capture_output=True)
            subprocess.run(["pkill", "-x", "Zotero"], capture_output=True)
            QTimer.singleShot(2000, lambda: subprocess.Popen(["open", "-a", "Zotero"]))
            QTimer.singleShot(10000, self._check_zotero_plugin)
            self._zot_status.setText("正在重启 Zotero…")
            self._zot_status.setStyleSheet("color:#0071E3;")
        else:
            self._zot_status.setText("下次启动 Zotero 后生效")
            self._zot_status.setStyleSheet("color:#0071E3;")

    def _check_zotero_plugin(self):
        """检测 pdf2zh Connector 插件状态"""
        if zotero_plugin_installed():
            self._zot_status.setText("已安装")
            self._zot_status.setStyleSheet("color:#34C759;font-weight:600;")
            self._zot_install_btn.hide()
        else:
            self._zot_status.setText("未安装")
            self._zot_install_btn.setText("一键安装")
            self._zot_install_btn.show()
            self._zot_install_btn.setEnabled(True)

    # ── 术语库操作 ──

    def _add_gloss_term(self):
        """内联添加一条术语"""
        src = self._gloss_src.text().strip()
        dst = self._gloss_dst.text().strip()
        if not src or not dst:
            return
        from ui.glossary_manager import GlossaryManager
        GlossaryManager.add_term(src, dst)
        self._gloss_src.clear(); self._gloss_dst.clear()
        self._update_gloss_count()

    def _refresh_gloss_list(self):
        from ui.glossary_manager import GlossaryManager
        self.gloss_selector.blockSignals(True)
        cur = self.gloss_selector.currentText()
        self.gloss_selector.clear()
        all_g = GlossaryManager.load_all_presets()
        self.gloss_selector.addItems(list(all_g.keys()))
        idx = self.gloss_selector.findText(cur)
        if idx >= 0: self.gloss_selector.setCurrentIndex(idx)
        self.gloss_selector.blockSignals(False)

    def _on_gloss_changed(self, name):
        from ui.glossary_manager import GlossaryManager
        GlossaryManager.load_preset(name)
        self._update_gloss_count()

    def _update_gloss_count(self):
        from ui.glossary_manager import GlossaryManager
        n = GlossaryManager.count()
        self.gloss_count.setText(f"{n} 条术语已激活" if n else "未加载术语")

    def _new_glossary(self):
        """新建自定义术语库"""
        from ui.glossary_manager import GlossaryManager
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "新建术语库", "术语库名称:")
        if ok and name.strip():
            name = name.strip()
            # 在用户目录下创建空术语库文件
            import json
            from pathlib import Path
            user_dir = Path.home() / "pdf2zh_glossaries"
            user_dir.mkdir(exist_ok=True)
            fp = user_dir / f"{name}.json"
            fp.write_text(json.dumps({}, indent=2, ensure_ascii=False), encoding="utf-8")
            self._refresh_gloss_list()
            idx = self.gloss_selector.findText(name)
            if idx >= 0:
                self.gloss_selector.setCurrentIndex(idx)

    def _delete_glossary(self):
        """删除用户自定义术语库（不能删预设）"""
        from ui.glossary_manager import GlossaryManager, DEFAULT_GLOSSARIES
        from pathlib import Path
        name = self.gloss_selector.currentText()
        if name in DEFAULT_GLOSSARIES:
            return
        fp = Path.home() / "pdf2zh_glossaries" / f"{name}.json"
        if fp.exists():
            fp.unlink()
        self._refresh_gloss_list()
        self._update_gloss_count()

    def _import_glossary(self):
        from ui.glossary_manager import GlossaryManager
        path, _ = QFileDialog.getOpenFileName(self, "导入术语库", "", "CSV (*.csv);;JSON (*.json)")
        if path:
            if path.endswith('.csv'):
                GlossaryManager.import_csv(path)
            else:
                GlossaryManager.import_json(path)
            self._update_gloss_count()
            self._refresh_gloss_list()

    def _export_glossary(self):
        from ui.glossary_manager import GlossaryManager
        path, _ = QFileDialog.getSaveFileName(self, "导出术语库", "glossary.csv", "CSV (*.csv);;JSON (*.json)")
        if path:
            if path.endswith('.json'):
                GlossaryManager.export_json(path)
            else:
                GlossaryManager.export_csv(path)

    def update_theme(self, c):
        """深色/浅色切换时更新内联样式"""
        self.prompt_edit.setStyleSheet(
            f"font-size:11px;border-radius:6px;background:{c['inp']};color:{c['t1']};"
            f"border:1px solid {c['inp_b']};"
        )
        # 刷新主题色行可见性（可能骰子刚解锁）
        cfg = UserConfigManager.load()
        self.theme_row.setVisible(cfg.get("theme_unlocked", False))


# ═══════════════════════════════════════════════════════════════
#  关于页面
# ═══════════════════════════════════════════════════════════════

class AboutPage(QWidget):
    def __init__(self):
        super().__init__()
        from PyQt5.QtWidgets import QGridLayout
        lo = QVBoxLayout(self); lo.setContentsMargins(32,20,32,20); lo.setSpacing(12)

        # 顶部：名称 + 版本 + GitHub
        top = QHBoxLayout(); top.setSpacing(8)
        ti = _EggLogo("📄", 22)
        ti.setFixedSize(32, 32); ti.setAlignment(Qt.AlignCenter)
        top.addWidget(ti)
        tn = QPushButton("pdf2zh-desktop"); tn.setObjectName("SBLink")
        tn.setStyleSheet("font-size:18px;font-weight:700;padding:0;text-align:left;")
        tn.setCursor(Qt.PointingHandCursor); tn.setFlat(True)
        tn.clicked.connect(lambda: webbrowser.open("https://github.com/AaronGIG/pdf2zh-desktop"))
        top.addWidget(tn)
        tv = QLabel("v2.2.0"); tv.setObjectName("Cap"); top.addWidget(tv)
        tt = QLabel("macOS"); tt.setObjectName("Tag"); tt.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed); top.addWidget(tt)
        top.addStretch()
        gb = QPushButton("GitHub ↗"); gb.setObjectName("Gh"); gb.setCursor(Qt.PointingHandCursor)
        gb.clicked.connect(lambda: webbrowser.open("https://github.com/AaronGIG/pdf2zh-desktop"))
        top.addWidget(gb)
        lo.addLayout(top)

        # 两列布局：左=介绍+增强，右=作者+支持者
        cols = QHBoxLayout(); cols.setSpacing(16)

        # ── 左列 ──
        left = QVBoxLayout(); left.setSpacing(6)

        dc = _card(); dl = QVBoxLayout(dc); dl.setContentsMargins(16,12,16,12); dl.setSpacing(4)
        dt = QLabel("开箱即用的学术 PDF 翻译工具"); dt.setStyleSheet("font-size:12px;font-weight:600;"); dl.addWidget(dt)
        dd = QLabel("保留排版 · 公式无损 · 批量任务 · 历史追踪 · 20+ 翻译服务")
        dd.setObjectName("Cap"); dd.setStyleSheet("font-size:11px;"); dd.setWordWrap(True); dl.addWidget(dd)
        left.addWidget(dc)

        mc = _card(); ml = QVBoxLayout(mc); ml.setContentsMargins(16,10,16,10); ml.setSpacing(3)
        mt = QLabel("macOS 版增强"); mt.setStyleSheet("font-size:12px;font-weight:600;"); ml.addWidget(mt)
        for emoji, text in [
            ("🎨","原生设计 · 深色模式 · 自定义主题色"),
            ("👀","Dual · Mono · Side by Side 预览"),
            ("📖","历史即时预览 · 上下键浏览"),
            ("✂️","智能分块 · 1000+页"),
            ("🖐","触摸板缩放 · 页码跳转"),
            ("📝","术语库 · 提示词模板"),
            ("🍀","每日骰子 · 隐藏彩蛋"),
            ("💬","全时段人文关怀 · 名言语录"),
            ("🚀",".app 双击启动 · Retina"),
        ]:
            r = QHBoxLayout(); r.setSpacing(6)
            e = QLabel(emoji); e.setStyleSheet("font-size:13px;background:transparent;"); e.setFixedWidth(18); r.addWidget(e)
            t2 = QLabel(text); t2.setObjectName("Cap"); t2.setStyleSheet("font-size:11px;"); r.addWidget(t2)
            ml.addLayout(r)
        ml.addWidget(_div())
        te = QLabel("基于 PDFMathTranslate (EMNLP 2025) · PyQt5 · PyMuPDF · OnnxRuntime")
        te.setObjectName("Cap"); te.setStyleSheet("font-size:10px;"); te.setWordWrap(True)
        ml.addWidget(te)
        left.addWidget(mc)
        left.addStretch()

        cols.addLayout(left, 3)

        # ── 右列 ──
        right = QVBoxLayout(); right.setSpacing(6)

        # 作者
        ac = _card(); acl = QHBoxLayout(ac); acl.setContentsMargins(16,12,16,12); acl.setSpacing(10)
        author_av = QLabel()
        author_av.setFixedSize(36, 36)
        avatar_path = _res('assets', 'author_avatar.png')
        if os.path.exists(avatar_path):
            apx = QPixmap(avatar_path).scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            apx.setDevicePixelRatio(2.0)
            author_av.setPixmap(apx)
        else:
            author_av.setText("艾"); author_av.setAlignment(Qt.AlignCenter)
            author_av.setStyleSheet("background:#1a1a2e;border-radius:18px;color:white;font-size:16px;font-weight:700;")
        acl.addWidget(author_av)
        ai = QVBoxLayout(); ai.setSpacing(0)
        an = QLabel("艾伦说"); an.setStyleSheet("font-size:13px;font-weight:700;"); ai.addWidget(an)
        xhs = QLabel("小红书: needsleeeeep"); xhs.setObjectName("Cap"); xhs.setStyleSheet("font-size:11px;"); ai.addWidget(xhs)
        motto = QLabel("希望能做更有意义的事 · 专注交付生产级的垂直学术公共品 🍀")
        motto.setObjectName("Cap"); motto.setStyleSheet("font-size:10px;color:rgba(142,142,147,0.7);"); ai.addWidget(motto)
        acl.addLayout(ai); acl.addStretch()
        xhs_btn = QPushButton("关注 ↗"); xhs_btn.setObjectName("Gh"); xhs_btn.setCursor(Qt.PointingHandCursor)
        xhs_btn.setStyleSheet("font-size:11px;")
        xhs_btn.clicked.connect(lambda: webbrowser.open("https://www.xiaohongshu.com/user/profile/66c6fef7000000001d0315ef"))
        acl.addWidget(xhs_btn)
        right.addWidget(ac)

        # 支持者头像墙
        cc = _card(); ccl = QVBoxLayout(cc); ccl.setContentsMargins(16,12,16,12); ccl.setSpacing(6)
        ct = QLabel("感谢小红书社区支持者 ♡"); ct.setStyleSheet("font-size:11px;font-weight:600;"); ccl.addWidget(ct)

        supporters = [
            "星爷！","卧","Jun warrior","幼儿园鹿小眸","侠禅",
            "ol","幼儿园老大","MX","贝斯特宋","Catherine",
            "不哩不哩左门卫","momo","李善兰","问道不求仙","hml",
            "ThereisTherse","人类与猫","小红薯643C3625","月栖竹","风来",
            "Nick","咕噜咕噜🍗","雾散时分起","大脸咪布爱吃鱼","限定 momo",
            "麦兜","锅的刚","一颗冒泡的卤蛋","我草莓招了",
            "去Nature整点论文","Masker",
            "AI maker趣造","帕克的创业日记","思维汪汪","橘座","小白也想学编程",
            "宛风Vanfeng","小宝の日常","未来百科","你们的万能小卓","碎银几两",
            "创界AIzine","全栈小5","无敌霸王龙","小艾同学","一万块的快乐",
            "学习笔记","三丰不是张","丁一","阿漫AIChat","知命不惧",
            "脱离社畜体制","一瓢清浅","Crazyang","逛逛GitHub","AI视界AIGC",
            "极客梦想家","沐沐子","Topaz","三不沾","EchoAI",
            "阳台吹风","Cursor实战派","简单就好","进击的小学生","AI探索家",
            "科技小飞侠","数字游民","AI能量站","工程师小灰","AI淘金",
            "量子比特","NeonCode","尝试新事物的Cher","有趣的灵魂不需要名字",
            "阿杰的编程日记","小明同学","码农翻身","AI大航海","月亮与六便士",
            "渡己","数码宝贝","悟空AI","追风少年","Tech小确幸",
            "半糖主义","深夜程序员","AI小天才","知行合一","星辰大海",
            "比特流","指尖上的代码","未来可期","云端漫步","AI引路人",
            "秋风扫落叶","编程小王子","日拱一卒","逆风翻盘","AI百宝箱",
            "程序猿日记","数据炼金术","量子纠缠","无限可能","风轻云淡",
            "代码人生","AI学徒","机器之心","清风明月","代码诗人",
            "零一万物","浮生若梦","技术宅","AI造物主","星河万里",
            "小蜗牛","编程少女","数据猎人","逻辑大师","AI前沿",
            "梦想家","代码如诗","量子跃迁","技术探路者","AI新青年",
        ]

        grid = QGridLayout(); grid.setSpacing(3); grid.setContentsMargins(0,0,0,0)
        cols_n = 12
        for i, name in enumerate(supporters):
            avatar = QLabel(name[0])
            avatar.setFixedSize(26, 26); avatar.setAlignment(Qt.AlignCenter)
            h = (hash(name) * 137) % 360
            s = 50 + (hash(name) >> 8) % 20; l2 = 55 + (hash(name) >> 16) % 15
            avatar.setStyleSheet(f"background:hsl({h},{s}%,{l2}%);border-radius:13px;font-size:9px;font-weight:600;color:white;")
            avatar.setToolTip(name)
            grid.addWidget(avatar, i // cols_n, i % cols_n, Qt.AlignCenter)
        ccl.addLayout(grid)
        sub = QLabel("无限迭代，只为更好的服务您")
        sub.setObjectName("Cap"); sub.setAlignment(Qt.AlignCenter); sub.setStyleSheet("font-size:11px;"); ccl.addWidget(sub)
        qq_group_btn = QPushButton("进入 pdf2zh 桌面版交流群"); qq_group_btn.setObjectName("Gh"); qq_group_btn.setCursor(Qt.PointingHandCursor)
        qq_group_btn.setStyleSheet("font-size:11px;")
        def _show_qq_qr():
            QApplication.clipboard().setText("1094195179")
            c = _C
            qr_dlg = QDialog(self)
            qr_dlg.setWindowTitle("加入交流群")
            qr_dlg.setStyleSheet(f"QDialog{{background:{c['bg']};}}")
            qlo = QVBoxLayout(qr_dlg); qlo.setContentsMargins(0, 0, 0, 12); qlo.setSpacing(8)
            qr_label = QLabel()
            qr_label.setAlignment(Qt.AlignCenter)
            qr_path = None
            for candidate in [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'qq_group_qr.png'),
                os.path.join(getattr(sys, '_MEIPASS', ''), 'assets', 'qq_group_qr.png'),
            ]:
                if os.path.exists(candidate):
                    qr_path = candidate
                    break
            if qr_path:
                pix = QPixmap(qr_path)
                # setScaledContents 让图片自动填满 label，不裁切
                qr_label.setPixmap(pix)
                qr_label.setScaledContents(True)
                qr_label.setFixedSize(300, int(300 * pix.height() / pix.width()))
                qr_dlg.setFixedSize(300, int(300 * pix.height() / pix.width()) + 40)
            else:
                qr_label.setText("请用 QQ 搜索群号 1094195179")
                qr_label.setStyleSheet(f"font-size:13px;color:{c['t2']};padding:30px;")
                qr_dlg.setFixedSize(300, 100)
            qlo.addWidget(qr_label)
            tip = QLabel("群号 1094195179 已复制到剪贴板")
            tip.setAlignment(Qt.AlignCenter)
            tip.setStyleSheet(f"font-size:11px;color:{c['acc']};")
            qlo.addWidget(tip)
            qr_dlg.exec_()
        qq_group_btn.clicked.connect(_show_qq_qr)
        ccl.addWidget(qq_group_btn, 0, Qt.AlignCenter)
        right.addWidget(cc)
        right.addStretch()

        cols.addLayout(right, 7)

        lo.addLayout(cols)


# ═══════════════════════════════════════════════════════════════
#  主窗口
# ═══════════════════════════════════════════════════════════════

# ── 桌面宠物：小黑猫 ──────────────────────────────────────────

class _NekoCat(QWidget):
    """会走来走去的小黑猫彩蛋 — 多种行为模式"""

    # 行为模式
    WALK, RUN, SIT, SLEEP = 0, 1, 2, 3

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(48, 36)
        self._frame = 0
        self._dir = 1
        self._mode = self.WALK
        self._speed = 2
        self._sit_counter = 0
        self._step_timer = QTimer(self)
        self._step_timer.timeout.connect(self._on_step)
        self.setCursor(Qt.PointingHandCursor)
        self.hide()

    def start_walk(self):
        """从窗口一侧走到另一侧"""
        parent = self.parentWidget()
        if not parent:
            return
        import random
        pw, ph = parent.width(), parent.height()
        self._dir = random.choice([1, -1])
        y = ph - 50
        if self._dir == 1:
            self._x = float(-self.width())
            self._x_end = float(pw + self.width())
        else:
            self._x = float(pw + self.width())
            self._x_end = float(-self.width())
        # 随机选行为
        roll = random.random()
        if roll < 0.60:
            self._mode = self.WALK; self._speed = 1.5
        elif roll < 0.80:
            self._mode = self.SIT; self._speed = 1.5
            # 走到中间附近时会停下来坐一会儿
            self._sit_x = pw * random.uniform(0.3, 0.7)
            self._sit_counter = 0
        else:
            self._mode = self.RUN; self._speed = 4
        self.move(int(self._x), y)
        self.show(); self.raise_()
        self._step_timer.start(40)  # 25fps

    def _on_step(self):
        self._frame += 1
        # SIT 模式：到达坐下点后停下来
        if self._mode == self.SIT and self._sit_counter > 0:
            self._sit_counter -= 1
            if self._sit_counter == 0:
                self._mode = self.WALK  # 坐完了继续走
            self.update()
            return
        if self._mode == self.SIT and \
           abs(self._x - self._sit_x) < 5 and self._sit_counter == 0:
            self._sit_counter = 100  # 坐 4 秒
            self.update()
            return
        self._x += self._dir * self._speed
        self.move(int(self._x), self.y())
        self.update()
        if (self._dir == 1 and self._x > self._x_end) or \
           (self._dir == -1 and self._x < self._x_end):
            self._step_timer.stop()
            self.hide()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        if self._dir < 0:
            p.translate(self.width(), 0)
            p.scale(-1, 1)
        cat = QColor(35, 35, 35)
        eye = QColor(180, 210, 50)
        is_sitting = (self._mode == self.SIT and self._sit_counter > 0)
        # ── 尾巴 ──
        p.setPen(QPen(cat, 3, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        tail = QPainterPath()
        sway = 2 if (self._frame // 4) % 2 == 0 else -2
        if is_sitting:
            # 坐着：尾巴自然弯曲放在身后
            tail.moveTo(6, 22); tail.cubicTo(2, 20, -2, 16, 2, 12)
        else:
            tail.moveTo(8, 16); tail.cubicTo(4, 12 + sway, 2, 8 + sway, 5, 4)
        p.drawPath(tail)
        # ── 身体 ──
        p.setPen(Qt.NoPen); p.setBrush(cat)
        if is_sitting:
            p.drawEllipse(10, 12, 20, 18)  # 坐姿：更圆
        else:
            p.drawEllipse(8, 14, 24, 14)
        # ── 头 ──
        if is_sitting:
            p.drawEllipse(22, 2, 17, 16)
        else:
            p.drawEllipse(25, 4, 16, 15)
        # ── 耳朵 ──
        hx = 22 if is_sitting else 25
        ear1 = QPainterPath()
        ear1.moveTo(hx+3, 4); ear1.lineTo(hx+5, -3); ear1.lineTo(hx+8, 3)
        ear1.closeSubpath(); p.drawPath(ear1)
        ear2 = QPainterPath()
        ear2.moveTo(hx+9, 2); ear2.lineTo(hx+12, -4); ear2.lineTo(hx+14, 2)
        ear2.closeSubpath(); p.drawPath(ear2)
        # ── 眼睛 ──
        ex = 27 if is_sitting else 30
        ey = 7 if is_sitting else 9
        p.setBrush(eye)
        if is_sitting and (self._frame // 30) % 3 == 0:
            # 坐着时偶尔眯眼
            p.setPen(QPen(eye, 2)); p.setBrush(Qt.NoBrush)
            p.drawLine(ex, ey+2, ex+4, ey+2)
            p.drawLine(ex+6, ey+2, ex+10, ey+2)
            p.setPen(Qt.NoPen)
        else:
            p.drawEllipse(ex, ey, 4, 4)
            p.drawEllipse(ex+6, ey, 4, 4)
            p.setBrush(QColor(10, 10, 10))
            p.drawEllipse(ex+1, ey+1, 2, 2)
            p.drawEllipse(ex+7, ey+1, 2, 2)
        # ── 腿 ──
        p.setPen(QPen(cat, 3, Qt.SolidLine, Qt.RoundCap))
        if is_sitting:
            # 坐姿：前腿伸直，后腿收起
            p.drawLine(18, 28, 16, 34)
            p.drawLine(24, 28, 26, 34)
        else:
            phase = self._frame % 4
            o = [(2,-2,-1,1),(-1,1,2,-2),(-2,2,1,-1),(1,-1,-2,2)][phase]
            p.drawLine(14, 27, 14+o[0], 34)
            p.drawLine(20, 27, 20+o[1], 34)
            p.drawLine(25, 27, 25+o[2], 34)
            p.drawLine(30, 27, 30+o[3], 34)
        p.end()

    def enterEvent(self, e):
        """鼠标悬停 → 疯狂加速"""
        if self._step_timer.isActive():
            self._mode = self.RUN
            self._speed = 6
            self._sit_counter = 0
            self._step_timer.setInterval(15)

    def leaveEvent(self, e):
        """鼠标离开 → 恢复正常速度"""
        if self._step_timer.isActive() and self._mode == self.RUN:
            self._speed = 1.5
            self._step_timer.setInterval(40)

    def mousePressEvent(self, e):
        """单击 → 喵一声"""
        try:
            import subprocess
            subprocess.Popen(["afplay", "/System/Library/Sounds/Pop.aiff"])
        except Exception:
            pass

    def mouseDoubleClickEvent(self, e):
        """双击 → 直接消失"""
        self._step_timer.stop()
        self.hide()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_dark = False
        self.setWindowTitle("")
        self.setMinimumSize(900,600)
        self.setUnifiedTitleAndToolBarOnMac(True)
        # App 图标
        _icon_path = _res('assets', 'app_icon.png')
        if os.path.exists(_icon_path):
            self.setWindowIcon(QIcon(_icon_path))
        # 启动时占满屏幕 90%
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            w = int(geo.width() * 0.92)
            h = int(geo.height() * 0.90)
            self.resize(w, h)
            self.move(geo.x() + (geo.width() - w) // 2,
                      geo.y() + (geo.height() - h) // 2)

        central = QWidget(); central.setObjectName("Central"); self.setCentralWidget(central)
        root = QHBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # 侧边栏
        sb = QWidget(); sb.setObjectName("Sidebar"); sb.setFixedWidth(220)
        self.sidebar = sb
        sbl = QVBoxLayout(sb); sbl.setContentsMargins(16,24,16,16); sbl.setSpacing(4)

        # Logo: pdf2zh/desktop — 📄 彩蛋 + 可点击标题
        logo_row = QHBoxLayout(); logo_row.setSpacing(10); logo_row.setContentsMargins(4,0,0,0)
        logo_icon = _EggLogo("📄", 28)
        logo_icon.setFixedSize(36, 36); logo_icon.setAlignment(Qt.AlignCenter)
        logo_row.addWidget(logo_icon)
        logo_text = QVBoxLayout(); logo_text.setSpacing(0)
        logo_name = QPushButton("pdf2zh-desktop"); logo_name.setObjectName("SBLink")
        logo_name.setStyleSheet("font-size:15px;font-weight:700;letter-spacing:-0.2px;padding:0;text-align:left;")
        logo_name.setCursor(Qt.PointingHandCursor); logo_name.setFlat(True)
        logo_name.clicked.connect(lambda: webbrowser.open("https://github.com/AaronGIG/pdf2zh-desktop"))
        logo_sub = QLabel("macOS Edition"); logo_sub.setObjectName("Cap")
        logo_text.addWidget(logo_name); logo_text.addWidget(logo_sub)
        logo_row.addLayout(logo_text); logo_row.addStretch()
        sbl.addLayout(logo_row)
        sbl.addSpacing(16); sbl.addWidget(_div()); sbl.addSpacing(12)

        self.nav = []
        for icon, label in [("🌐","翻译"),("📖","阅读"),("🔧","设置"),("💡","关于")]:
            b = SB(icon, label)
            b.clicked.connect(lambda l=label: self.switch(l))
            sbl.addWidget(b); self.nav.append((label, b))
        sbl.addStretch()

        vl = QLabel("v2.2.0 · macOS"); vl.setObjectName("Cap"); vl.setAlignment(Qt.AlignCenter)
        vl.setStyleSheet("font-size:10px;")
        sbl.addWidget(vl)
        # 底部链接 — 独立按钮，支持 hover 变色
        import webbrowser
        link_row = QHBoxLayout(); link_row.setSpacing(0)
        link_row.setContentsMargins(8,0,8,4); link_row.addStretch()
        for text, url in [
            ("GitHub", "https://github.com/AaronGIG/pdf2zh-desktop"),
            ("小红书", "https://www.xiaohongshu.com/user/profile/66c6fef7000000001d0315ef"),
            ("Feedback", "https://github.com/AaronGIG/pdf2zh-desktop/issues"),
            ("Star ⭐", "https://github.com/AaronGIG/pdf2zh-desktop"),
        ]:
            lb = QPushButton(text); lb.setObjectName("SBLink"); lb.setCursor(Qt.PointingHandCursor)
            lb.clicked.connect(lambda _, u=url: webbrowser.open(u))
            link_row.addWidget(lb)
            if text != "Star ⭐":
                sep = QLabel("·"); sep.setObjectName("SBSep")
                link_row.addWidget(sep)
        link_row.addStretch()
        sbl.addLayout(link_row)
        root.addWidget(sb)

        # 内容区
        self.stack = QStackedWidget()
        self.pages = {}
        tp = TranslatePage(); rp = ReaderPage()
        sp = SettingsPage(); ap = AboutPage()
        for name, page in [("翻译",tp),("阅读",rp),("设置",sp),("关于",ap)]:
            self.stack.addWidget(page); self.pages[name] = page
        root.addWidget(self.stack)

        # 信号连接
        sp.dark_mode_changed.connect(self._toggle_dark)
        sp.theme_color_changed.connect(self._set_accent)
        tp.translation_done.connect(self._on_translate_done)
        rp.fullscreen_changed.connect(self._on_reader_fullscreen)

        # 恢复上次窗口状态
        cfg = UserConfigManager.load()
        self.switch("翻译"); self._apply()
        _install_tip_filter(QApplication.instance())
        # 去掉所有 QComboBox 下拉框的系统矩形外框
        for combo in self.findChildren(QComboBox):
            _fix_combo_popup(combo)

        # 恢复窗口尺寸和位置
        if cfg.get("window_geometry"):
            try:
                from PyQt5.QtCore import QByteArray
                geo = QByteArray.fromHex(cfg["window_geometry"].encode())
                self.restoreGeometry(geo)
            except Exception:
                pass

        # 静默预加载阅读页：用户点击时已渲染好，无闪烁
        QTimer.singleShot(100, self._preload_reader)

        # ── 小黑猫彩蛋 ──
        self._neko = _NekoCat(self)
        self._neko_timer = QTimer(self)
        self._neko_timer.timeout.connect(self._maybe_spawn_cat)
        self._neko_timer.start(1_200_000)  # 每 20 分钟出来一次
        QTimer.singleShot(3_000, lambda: self._neko.start_walk())  # 启动 3 秒出来

        # ── 凌晨 3:30 彩蛋：披星戴月 ──
        from datetime import datetime
        now = datetime.now()
        if now.hour == 3 and 25 <= now.minute <= 35:
            QTimer.singleShot(800, self._midnight_bloom)

    # ─────────────────────────────────────────────
    #  凌晨 3:30 彩蛋 — 烟花 + 暖心寄语
    # ─────────────────────────────────────────────
    def _maybe_spawn_cat(self):
        """每 20 分钟让小黑猫出来走一趟"""
        if self._neko.isVisible():
            return
        self._neko.start_walk()

    def _midnight_bloom(self):
        """全屏烟花 10 秒 → 暖心寄语浮层"""
        import random, math
        from PyQt5.QtCore import QPropertyAnimation, QPoint, QEasingCurve

        fireworks = ["🎆","🎇","✨","💫","⭐","🌟","🌠","💛","🧡","💜","💙","🤍"]
        self._bloom_anims = []  # prevent GC

        def _burst():
            """一轮烟花：从随机位置爆开"""
            cx = random.randint(int(self.width() * 0.15), int(self.width() * 0.85))
            cy = random.randint(int(self.height() * 0.15), int(self.height() * 0.55))
            center = QPoint(cx, cy)
            for _ in range(random.randint(12, 20)):
                lbl = QLabel(random.choice(fireworks), self)
                lbl.setStyleSheet(f"font-size:{random.randint(16, 36)}px;background:transparent;")
                lbl.move(center); lbl.show(); lbl.raise_()
                angle = random.uniform(0, 2 * math.pi)
                dist = random.randint(80, 300)
                end = QPoint(cx + int(math.cos(angle) * dist),
                             cy + int(math.sin(angle) * dist))
                anim = QPropertyAnimation(lbl, b"pos")
                anim.setDuration(random.randint(900, 1800))
                anim.setStartValue(center); anim.setEndValue(end)
                anim.setEasingCurve(QEasingCurve.OutQuad)
                anim.finished.connect(lbl.deleteLater)
                anim.start()
                self._bloom_anims.append(anim)

        # 10 秒内间歇放烟花（每 400–700ms 一轮）
        total_bursts = 18
        for i in range(total_bursts):
            delay = int(i * 550 + random.randint(0, 150))
            QTimer.singleShot(delay, _burst)

        # 10 秒后显示暖心寄语
        QTimer.singleShot(10500, self._midnight_message)

    def _midnight_message(self):
        """暖心寄语浮层"""
        import random
        messages = [
            ("披星戴月的你，终将凯旋。",
             "但现在，请先好好休息。\n"
             "没有什么比你的健康更重要了。\n"
             "科研之外，还有很多美好的事物在等着你。"),
            ("凌晨三点半的你，一定很努力。",
             "但再重要的事，也比不上你自己。\n"
             "把未完成的留给明天精力充沛的自己吧。\n"
             "这个世界需要健康的你。"),
            ("夜深了，星星都在为你亮着。",
             "你已经比大多数人都努力了。\n"
             "允许自己休息，不是放弃，是为了走更远的路。\n"
             "照顾好自己，才能照顾好你在乎的一切。"),
            ("这个时间还在学习的你，了不起。",
             "但了不起的人更要爱惜自己。\n"
             "身体是一切的根基，请好好善待它。\n"
             "早点睡，明天的你会感谢今晚的决定。"),
            ("深夜的坚持让人敬佩。",
             "但真正的强者，懂得在该休息时放下。\n"
             "你的才华不会因为一晚的休息而消失。\n"
             "去睡吧，梦里什么都有。"),
        ]
        title, body = random.choice(messages)

        # 半透明遮罩 + 居中卡片
        overlay = QWidget(self)
        overlay.setGeometry(self.rect())
        overlay.setStyleSheet("background:rgba(0,0,0,0.55);")
        overlay.show(); overlay.raise_()

        card = QFrame(overlay)
        card.setStyleSheet(
            "QFrame{background:rgba(255,255,255,0.95);border-radius:20px;}"
            if not self.is_dark else
            "QFrame{background:rgba(40,40,45,0.95);border-radius:20px;}"
        )
        card.setFixedSize(420, 280)
        card.move((self.width() - 420) // 2, (self.height() - 280) // 2)
        card.show()

        cl = QVBoxLayout(card); cl.setContentsMargins(32, 28, 32, 24); cl.setSpacing(12)

        moon = QLabel("🌙"); moon.setStyleSheet("font-size:36px;background:transparent;")
        moon.setAlignment(Qt.AlignCenter); cl.addWidget(moon)

        tc = "color:#1d1d1f;" if not self.is_dark else "color:#f5f5f7;"
        tl = QLabel(title)
        tl.setStyleSheet(f"font-size:18px;font-weight:700;{tc}background:transparent;")
        tl.setAlignment(Qt.AlignCenter); tl.setWordWrap(True); cl.addWidget(tl)

        bl = QLabel(body)
        bl.setStyleSheet(f"font-size:13px;line-height:1.6;{tc}background:transparent;")
        bl.setAlignment(Qt.AlignCenter); bl.setWordWrap(True); cl.addWidget(bl)

        cl.addStretch()
        close_btn = QPushButton("晚安，去休息了 🌙")
        close_btn.setObjectName("Pr"); close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("font-size:14px;padding:10px 24px;")
        close_btn.clicked.connect(overlay.deleteLater)
        cl.addWidget(close_btn, alignment=Qt.AlignCenter)

        # 点击遮罩也可关闭
        overlay.mousePressEvent = lambda e: overlay.deleteLater()

    def switch(self, label):
        # 预加载中 → 延迟切换（避免冲突）
        if getattr(self, '_preloading', False):
            QTimer.singleShot(50, lambda: self.switch(label))
            return
        keys = list(self.pages.keys())
        idx = keys.index(label) if label in keys else 0
        # 阅读页：先刷新列表，再显示（避免 showEvent 用旧数据加载后又被 refresh 清掉）
        if label == "阅读":
            self.pages["阅读"].refresh()
        self.stack.setCurrentIndex(idx)
        for n, b in self.nav: b.set_active(n == label)

    def _preload_reader(self):
        """静默预加载阅读页：冻结画面 → 切到阅读页获取真实尺寸 → 渲染 → 切回"""
        self._preloading = True
        rp = self.pages["阅读"]
        rp.refresh()
        if rp.list_w.count() == 0:
            self._preloading = False
            return
        # 冻结画面（布局仍正常计算，只是不绘制）
        self.setUpdatesEnabled(False)
        self.stack.setCurrentIndex(list(self.pages.keys()).index("阅读"))
        # 下一帧：布局已稳定，加载 + 渲染
        QTimer.singleShot(0, self._preload_step2)

    def _preload_step2(self):
        rp = self.pages["阅读"]
        rp.list_w.setCurrentRow(0)  # → _on_select → load_pdf
        # 再等一帧让 splitter 稳定
        QTimer.singleShot(30, self._preload_step3)

    def _preload_step3(self):
        rp = self.pages["阅读"]
        rp.preview._last_fit_zoom = -1
        rp.preview._fit_and_render()
        # 切回翻译页，解冻
        self.stack.setCurrentIndex(0)
        self.setUpdatesEnabled(True)
        self._preloading = False
        self.repaint()

    def _toggle_dark(self, dark):
        self.is_dark = dark
        # 淡入淡出过渡
        from PyQt5.QtCore import QPropertyAnimation
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(150)
        anim.setStartValue(1.0); anim.setEndValue(0.85)
        anim.finished.connect(lambda: self._finish_theme_switch(anim))
        self._theme_anim = anim  # prevent GC
        anim.start()

    def _finish_theme_switch(self, prev_anim):
        self._apply()
        from PyQt5.QtCore import QPropertyAnimation
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(200)
        anim.setStartValue(0.85); anim.setEndValue(1.0)
        self._theme_anim = anim
        anim.start()

    def _set_accent(self, hex_color):
        """应用自定义主题色"""
        self._custom_accent = hex_color
        self._apply()

    def _apply(self):
        global _C
        c = dict(D if self.is_dark else L)  # 拷贝，避免修改原始
        # 应用自定义主题色（需已解锁）
        cfg = UserConfigManager.load()
        acc = getattr(self, '_custom_accent', None) or cfg.get("theme_color")
        if acc and cfg.get("theme_unlocked"):
            r, g, b = int(acc[1:3],16), int(acc[3:5],16), int(acc[5:7],16)
            c["acc"] = acc; c["acc_h"] = acc; c["acc_p"] = acc
            c["acc_l"] = f"rgba({r},{g},{b},0.12)"
            c["acc_g"] = f"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {acc},stop:1 {acc})"
            c["sb_act"] = f"rgba({r},{g},{b},0.15)"
            c["dz_b"] = f"rgba({r},{g},{b},0.25)"
            c["tag_bg"] = f"rgba({r},{g},{b},0.10)"; c["tag_fg"] = acc
            c["pv_l_bg"] = f"rgba({r},{g},{b},0.10)"; c["pv_l_fg"] = acc
            c["link_h"] = acc
        _C = c
        self.setStyleSheet(S(c))
        # 强制设置 QPalette，修复内联 setStyleSheet 覆盖问题
        from PyQt5.QtGui import QPalette
        pal = self.palette()
        pal.setColor(QPalette.WindowText, QColor(c["t1"]))
        pal.setColor(QPalette.Text, QColor(c["t1"]))
        pal.setColor(QPalette.ButtonText, QColor(c["t1"]))
        pal.setColor(QPalette.PlaceholderText, QColor(c["t3"]))
        pal.setColor(QPalette.Base, QColor(c["inp"]))
        pal.setColor(QPalette.Window, QColor(c["bg"]))
        pal.setColor(QPalette.AlternateBase, QColor(c["bg2"]))
        pal.setColor(QPalette.ToolTipBase, QColor(c["elev"]))
        pal.setColor(QPalette.ToolTipText, QColor(c["t1"]))
        pal.setColor(QPalette.Highlight, QColor(c["acc"]))
        pal.setColor(QPalette.HighlightedText, QColor("white"))
        self.setPalette(pal)
        QApplication.instance().setPalette(pal)
        # 通知子页面更新内联样式
        for page in self.pages.values():
            if hasattr(page, 'update_theme'):
                page.update_theme(c)

    def _on_reader_fullscreen(self, fs):
        """全屏阅读：隐藏/显示侧边栏"""
        self.sidebar.setVisible(not fs)

    def closeEvent(self, event):
        """保存窗口几何尺寸和当前页面"""
        cfg = UserConfigManager.load()
        cfg["window_geometry"] = bytes(self.saveGeometry().toHex()).decode()
        # 保存当前页面
        for name, page in self.pages.items():
            if self.stack.currentWidget() is page:
                cfg["last_page"] = name; break
        UserConfigManager.save(cfg)
        event.accept()

    def _on_translate_done(self, output_files):
        reader = self.pages["阅读"]
        reader.set_output_files(output_files)
        QTimer.singleShot(600, lambda: self.switch("阅读"))
        # 翻译完成后把窗口提到前台（用户可能切走了）
        QTimer.singleShot(700, lambda: (self.raise_(), self.activateWindow()))


class Pdf2zhApp(QApplication):
    """单实例 QApplication：第二个实例把文件发给第一个实例后退出"""
    file_opened = pyqtSignal(str)
    _SERVER_NAME = "com.aarongig.pdf2zh.single"

    def __init__(self, argv):
        super().__init__(argv)
        from PyQt5.QtNetwork import QLocalServer, QLocalSocket
        self._pending_file = None

        # 尝试连接已有实例
        sock = QLocalSocket()
        sock.connectToServer(self._SERVER_NAME)
        if sock.waitForConnected(500):
            # 已有实例在运行 → 把文件路径发过去，然后退出
            for arg in argv[1:]:
                if arg.lower().endswith('.pdf') and os.path.isfile(arg):
                    sock.write(arg.encode('utf-8'))
                    sock.waitForBytesWritten(1000)
            sock.disconnectFromServer()
            sys.exit(0)

        # 我是第一个实例 → 启动 server 监听
        QLocalServer.removeServer(self._SERVER_NAME)
        self._server = QLocalServer()
        self._server.listen(self._SERVER_NAME)
        self._server.newConnection.connect(self._on_new_connection)

    def _on_new_connection(self):
        conn = self._server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(1000)
            data = conn.readAll().data().decode('utf-8', errors='ignore')
            conn.close()
            if data and data.lower().endswith('.pdf'):
                self.file_opened.emit(data)

    def event(self, e):
        if e.type() == e.FileOpen:
            path = e.file()
            if path and path.lower().endswith('.pdf'):
                self.file_opened.emit(path)
                return True
        return super().event(e)


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = Pdf2zhApp(sys.argv); app.setStyle("Fusion")
    w = MainWindow(); w.show()

    # 文件打开事件 → 送到翻译页
    def _on_file_open(path):
        tp = w.pages.get("翻译")
        if tp:
            tp.on_files_added([path])
            w.switch("翻译")
            w.raise_()
            w.activateWindow()
    app.file_opened.connect(_on_file_open)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

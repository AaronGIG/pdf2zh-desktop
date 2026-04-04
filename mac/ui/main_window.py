"""
pdf2zh for Mac — 完整版主窗口
全功能适配: 三种预览模式 / 分块翻译 / 页码范围 / 历史记录 / 20+翻译服务
"""

import sys
import os
import webbrowser
import time
import fitz


def _res(*parts):
    """获取资源文件路径，兼容 PyInstaller 打包和开发环境"""
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, *parts)
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), *parts)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QProgressBar, QFileDialog,
    QStackedWidget, QFrame, QScrollArea, QGraphicsDropShadowEffect,
    QCheckBox, QListWidget, QListWidgetItem, QLineEdit, QSpinBox,
    QSizePolicy, QSlider, QSplitter, QTabBar, QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize, QEvent
from PyQt5.QtGui import QColor, QDragEnterEvent, QDropEvent, QImage, QPixmap, QScreen, QIcon

from ui.config_manager import UserConfigManager, HistoryManager
from ui.translate_worker import (
    TranslateWorker, LANG_MAP, SERVICE_MAP, PAGE_PRESETS,
    OUTPUT_MODES, parse_page_range, detect_zotero_source,
    get_zotero_item_key, zotero_auto_link, zotero_plugin_installed,
    build_service_envs
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
    "pv_bg":"#E8E8ED","pv_tb":"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #FBFBFD,stop:1 #F2F2F7)",
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
        tx, ty = pos.x() + 8 + pad, pos.y() + 14 + pad
        tw, th = tip.width() - pad * 2, tip.height() - pad * 2
        tip._grab_and_blur(tx, ty, tw, th)
        tip.move(pos.x() + 8, pos.y() + 14)
        tip.show()
        tip.update()

    @classmethod
    def hide_tip(cls):
        if cls._inst: cls._inst.hide()


def _install_tip_filter(app):
    """安装全局 tooltip 拦截"""
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
    #SB{{background:transparent;border:none;border-radius:7px;padding:6px 12px;text-align:left;font-size:13px;color:{c["t2"]};letter-spacing:0.2px;}}
    #SB:hover{{background:{c["sb_hov"]};color:{c["t1"]};}}
    #SB[active="true"]{{background:{c["sb_act"]};color:{c["acc"]};font-weight:600;}}
    #SBLink{{background:transparent;border:none;font-size:10px;color:{c["link"]};padding:1px 3px;}}
    #SBLink:hover{{color:{c["acc"]};}}
    /* ── 按钮 ── */
    #Pr{{background:{c["acc_g"]};color:white;border:none;border-radius:12px;padding:12px 32px;font-size:15px;font-weight:600;}}
    #Pr:hover{{background:{c["acc_h"]};}}#Pr:pressed{{background:{c["acc_p"]};}}
    #Pr:disabled{{background:{c["bg3"]};color:{c["t4"]};}}
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
    QComboBox{{background:{c["inp"]};border:1px solid {c["inp_b"]};border-radius:8px;padding:8px 14px;font-size:13px;min-height:22px;color:{c["t1"]};}}
    QComboBox:hover{{border-color:{c["brd_s"]};}}QComboBox:focus{{border-color:{c["acc"]};}}
    QComboBox::drop-down{{border:none;width:32px;subcontrol-origin:padding;subcontrol-position:center right;}}
    QComboBox::down-arrow{{image:none;border-left:5px solid transparent;border-right:5px solid transparent;border-top:6px solid {c["acc"]};margin-right:10px;}}
    QComboBox QAbstractItemView{{background:{c["elev"]};border:1px solid {c["brd_s"]};border-radius:8px;padding:4px;selection-background-color:{c["acc"]};selection-color:white;color:{c["t1"]};}}
    QLineEdit{{background:{c["inp"]};border:1px solid {c["inp_b"]};border-radius:8px;padding:8px 14px;font-size:13px;color:{c["t1"]};}}
    QLineEdit:focus{{border-color:{c["acc"]};background:{c["elev"]};}}
    QLineEdit[readOnly="true"]{{color:{c["t2"]};}}
    QSpinBox{{background:{c["inp"]};border:1px solid {c["inp_b"]};border-radius:8px;padding:6px 10px;font-size:13px;color:{c["t1"]};}}
    QSpinBox:focus{{border-color:{c["acc"]};}}
    QTextEdit{{background:{c["inp"]};color:{c["t1"]};border:1px solid {c["inp_b"]};border-radius:8px;}}
    QTextEdit:focus{{border-color:{c["acc"]};}}
    /* ── 进度条 ── */
    QProgressBar{{background:{c["bg3"]};border:none;border-radius:3px;max-height:6px;min-height:6px;font-size:1px;}}
    QProgressBar::chunk{{background:{c["acc_g"]};border-radius:3px;}}
    /* ── 卡片 ── */
    #Card{{background:{c["card"]};border:0.5px solid {c["card_b"]};border-radius:14px;}}
    #Card:hover{{border-color:{c["acc"]};}}
    #DZ{{background:{c["dz_bg"]};border:2px dashed {c["dz_b"]};border-radius:16px;}}
    #DZ:hover{{border-color:{c["acc"]};}}
    /* ── 列表 ── */
    QListWidget{{background:transparent;border:none;outline:none;}}
    QListWidget::item{{background:{c["card"]};border:0.5px solid {c["card_b"]};border-radius:10px;padding:4px 10px;margin:2px 0;}}
    QListWidget::item:selected{{background:{c["acc"]};color:white;border-color:{c["acc"]};}}
    QListWidget::item:hover:!selected{{background:{c["bg2"]};}}
    /* ── 滚动条 ── */
    QScrollArea{{border:none;background:transparent;}}
    QScrollBar:vertical{{background:transparent;width:7px;margin:4px 1px;}}
    QScrollBar::handle:vertical{{background:{c["scr"]};border-radius:3px;min-height:40px;}}
    QScrollBar::handle:vertical:hover{{background:{c["scr_h"]};}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical,QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{{height:0;background:transparent;}}
    QScrollBar:horizontal{{height:0;}}
    /* ── 复选框 ── */
    QCheckBox{{spacing:10px;font-size:13px;}}
    QCheckBox::indicator{{width:20px;height:20px;border-radius:6px;border:1.5px solid {c["brd_s"]};background:{c["elev"]};}}
    QCheckBox::indicator:hover{{border-color:{c["acc"]};}}
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


def _div():
    d = QFrame(); d.setObjectName("Div"); d.setFrameShape(QFrame.HLine); return d

def _card(blur=24, y=4, a=12):
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
        self.setMinimumHeight(100); self.setMaximumHeight(140); self.setCursor(Qt.PointingHandCursor)
        lo = QHBoxLayout(self); lo.setAlignment(Qt.AlignCenter); lo.setSpacing(16)
        lo.setContentsMargins(32,20,32,20)
        ic = QLabel("📥"); ic.setStyleSheet("font-size:36px;background:transparent;"); lo.addWidget(ic)
        txt = QVBoxLayout(); txt.setSpacing(3)
        t = QLabel("将 PDF 拖放至此处"); t.setObjectName("DZTitle"); txt.addWidget(t)
        s = QLabel("或点击浏览 · 支持批量"); s.setObjectName("DZSub"); txt.addWidget(s)
        lo.addLayout(txt); lo.addStretch()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e):
        import glob
        fs = []
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p.lower().endswith('.pdf'):
                fs.append(p)
            elif os.path.isdir(p):
                fs.extend(glob.glob(os.path.join(p, '**', '*.pdf'), recursive=True))
        if fs: self.files_dropped.emit(fs)
    def mousePressEvent(self, e):
        fs, _ = QFileDialog.getOpenFileNames(self, "选择 PDF", "", "PDF (*.pdf)")
        if fs: self.files_dropped.emit(fs)


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
        self.thumb_container = QWidget()
        self.thumb_layout = QVBoxLayout(self.thumb_container)
        self.thumb_layout.setContentsMargins(4,6,4,6); self.thumb_layout.setSpacing(4)
        self.thumb_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.thumb_scroll.setWidget(self.thumb_container)
        self.thumb_scroll.setVisible(False)
        self.body_splitter.addWidget(self.thumb_scroll)

        # 主视图容器
        self._main_view = QWidget()
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
        self.scroll.setVisible(False)  # 默认连续模式，隐藏单页
        _mv_lo.addWidget(self.scroll)

        # 主视图 — 连续滚动模式（默认显示）
        self.cont_scroll = QScrollArea(); self.cont_scroll.setWidgetResizable(True)
        self.cont_scroll.setObjectName("PA"); self.cont_scroll.setVisible(True)
        self.cont_container = QWidget()
        self.cont_layout = QVBoxLayout(self.cont_container)
        self.cont_layout.setContentsMargins(0,0,0,0); self.cont_layout.setSpacing(4)
        self.cont_layout.setAlignment(Qt.AlignHCenter)
        self.cont_scroll.setWidget(self.cont_container)
        self.cont_scroll.verticalScrollBar().valueChanged.connect(self._on_cont_scroll)
        _mv_lo.addWidget(self.cont_scroll)
        self._cont_page_widgets = []

        self.body_splitter.addWidget(self._main_view)
        self.body_splitter.setSizes([140, 800])
        self.body_splitter.setCollapsible(0, True)   # 缩略图可折叠
        self.body_splitter.setCollapsible(1, False)
        # 拖拽缩略图面板宽度时自动重建缩略图
        self.body_splitter.splitterMoved.connect(self._on_thumb_panel_resized)
        self.body_widget = self.body_splitter  # 兼容引用
        lo.addWidget(self.body_splitter)

        # 空状态
        self.empty = QWidget(); self.empty.setObjectName("PA")
        el = QVBoxLayout(self.empty); el.setAlignment(Qt.AlignCenter); el.setSpacing(12)
        ic = QLabel(); ic.setFixedSize(72,72); ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet(f"background:{_C['acc_l']};border-radius:22px;font-size:32px;")
        ic.setText("👀"); self._empty_icon = ic; el.addWidget(ic, alignment=Qt.AlignCenter)
        m = QLabel("翻译完成后在此预览"); m.setStyleSheet("font-size:16px;font-weight:600;"); m.setAlignment(Qt.AlignCenter); el.addWidget(m)
        s = QLabel("支持 Dual · Mono · Side by Side 三种模式切换"); s.setObjectName("Cap"); s.setAlignment(Qt.AlignCenter); el.addWidget(s)
        s2 = QLabel("← 也可点击左侧历史记录直接打开"); s2.setObjectName("Cap"); s2.setStyleSheet("font-size:11px;"); s2.setAlignment(Qt.AlignCenter); el.addWidget(s2)
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
        except Exception as e:
            self.page_widget.setText(f"加载失败: {e}")

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
        """页码输入框回车跳转"""
        try:
            n = int(self.page_input.text()) - 1
            if self.doc and 0 <= n < len(self.doc):
                self.current_page = n; self.render_page()
        except ValueError:
            pass
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
    def _toggle_fullscreen(self):
        self._is_fullscreen = not self._is_fullscreen
        self.fs_btn.setText("退出" if self._is_fullscreen else "全屏")
        self.fs_btn.setProperty("active", self._is_fullscreen)
        self.fs_btn.style().unpolish(self.fs_btn); self.fs_btn.style().polish(self.fs_btn)
        self.hist_btn.setVisible(self._is_fullscreen)
        self.fullscreen_toggled.emit(self._is_fullscreen)
        QTimer.singleShot(80, self._on_resize_done)

    def _on_thumb_panel_resized(self):
        """拖拽缩略图面板后重建缩略图"""
        if not hasattr(self, '_thumb_resize_timer'):
            self._thumb_resize_timer = QTimer(); self._thumb_resize_timer.setSingleShot(True)
            self._thumb_resize_timer.timeout.connect(self._rebuild_thumbs_fit)
        self._thumb_resize_timer.start(200)

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
        """渲染所有页面到连续滚动容器"""
        if not self.doc:
            return
        # 清空旧内容
        for w in self._cont_page_widgets:
            w.setParent(None)
        self._cont_page_widgets = []

        dpr = QApplication.instance().devicePixelRatio() if QApplication.instance() else 2.0
        for i in range(len(self.doc)):
            pg = self.doc[i]
            render_zoom = self.zoom * dpr
            mat = fitz.Matrix(render_zoom, render_zoom)
            pix = pg.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            qpix = QPixmap.fromImage(img)
            qpix.setDevicePixelRatio(dpr)
            lbl = QLabel()
            lbl.setPixmap(qpix)
            lbl.setFixedSize(int(pix.width / dpr), int(pix.height / dpr))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background:transparent;")
            self.cont_layout.addWidget(lbl, alignment=Qt.AlignHCenter)
            self._cont_page_widgets.append(lbl)
        self._update_page_display()

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
        self._empty_icon.setStyleSheet(f"background:{c['acc_l']};border-radius:22px;font-size:32px;")
        self._thumb_color = c['acc']
        if self._thumb_labels:
            self._highlight_thumb(self.current_page)


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

        # 拖拽区
        self.drop = DropZone(); self.drop.files_dropped.connect(self.on_files_added); lo.addWidget(self.drop)

        # 文件列表 + 操作按钮
        flist_w = QWidget(); flist_w.setVisible(False)
        self._flist_container = flist_w
        fl = QVBoxLayout(flist_w); fl.setContentsMargins(0,0,0,0); fl.setSpacing(4)
        self.flist = QListWidget(); self.flist.setMaximumHeight(120)
        self.flist.setSelectionMode(QListWidget.ExtendedSelection)
        fl.addWidget(self.flist)
        fbtn_row = QHBoxLayout(); fbtn_row.setSpacing(6)
        self._fcount_label = QLabel(""); self._fcount_label.setObjectName("Cap")
        fbtn_row.addWidget(self._fcount_label)
        fbtn_row.addStretch()
        fdel = QPushButton("删除选中"); fdel.setObjectName("TB"); fdel.setCursor(Qt.PointingHandCursor)
        fdel.setStyleSheet("font-size:11px;padding:2px 8px;")
        fdel.clicked.connect(self._remove_selected_files)
        fbtn_row.addWidget(fdel)
        fclr = QPushButton("清空"); fclr.setObjectName("GhDanger"); fclr.setCursor(Qt.PointingHandCursor)
        fclr.setStyleSheet("font-size:11px;padding:2px 8px;")
        fclr.clicked.connect(self._clear_files)
        fbtn_row.addWidget(fclr)
        fl.addLayout(fbtn_row)
        lo.addWidget(flist_w)

        # ── Zotero 提示条（检测到 Zotero 来源时显示）──
        self._zotero_hint = QFrame()
        self._zotero_hint.setStyleSheet(
            "background:#e8f0fe;border-radius:6px;padding:6px 10px;"
        )
        _zh_lo = QHBoxLayout(self._zotero_hint)
        _zh_lo.setContentsMargins(8,4,8,4); _zh_lo.setSpacing(0)
        _zh_lbl = QLabel("📚 检测到 Zotero 文献，译文将自动保存回原位")
        _zh_lbl.setStyleSheet("font-size:11px;color:#1a56db;background:transparent;")
        _zh_lo.addWidget(_zh_lbl)
        self._zotero_hint.setVisible(False)
        lo.addWidget(self._zotero_hint)

        # ── 配置卡片 ──
        card = _card()
        cl = QVBoxLayout(card); cl.setContentsMargins(20,16,20,16); cl.setSpacing(0)

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
        self.fmt_combo.setCurrentIndex(2)  # 默认：左右并排
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

        # ── 进度卡片 ──
        self.prog_card = _card(28, 6, 14)
        self.prog_card.setVisible(False)
        pc_lo = QVBoxLayout(self.prog_card)
        pc_lo.setContentsMargins(20, 14, 20, 14)
        pc_lo.setSpacing(8)

        # 第一行：状态图标 + 标题 + 百分比
        row1 = QHBoxLayout(); row1.setSpacing(10)
        self.prog_icon = QLabel("⏳"); self.prog_icon.setObjectName("ProgIcon")
        row1.addWidget(self.prog_icon)
        self.prog_label = QLabel("正在翻译…"); self.prog_label.setObjectName("ProgLabel")
        row1.addWidget(self.prog_label)
        row1.addStretch()
        self.prog_pct = QLabel("0%"); self.prog_pct.setObjectName("ProgPct")
        row1.addWidget(self.prog_pct)
        pc_lo.addLayout(row1)

        # 进度条
        self.prog_bar = QProgressBar(); self.prog_bar.setRange(0, 100)
        self.prog_bar.setObjectName("ProgBar")
        pc_lo.addWidget(self.prog_bar)

        self.prog_tip = QLabel(""); self.prog_tip.setObjectName("ProgTip")
        pc_lo.addWidget(self.prog_tip)

        # 第二行：详情 + 取消按钮
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

        lo.addWidget(self.prog_card)

        # ── 开始按钮 ──
        br = QHBoxLayout(); br.setSpacing(10)
        br.addStretch()
        self.go_btn = QPushButton("开始翻译"); self.go_btn.setObjectName("Pr")
        self.go_btn.setFixedWidth(200); self.go_btn.setFixedHeight(48)
        self.go_btn.setEnabled(False)
        self.go_btn.clicked.connect(self._start)
        br.addWidget(self.go_btn)
        # 骰子（无提示，让用户自己探索）
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

    def _update_fcount(self):
        n = self.flist.count()
        if n > 0:
            self._flist_container.setVisible(True)
            self.go_btn.setEnabled(True)
            self._fcount_label.setText(f"共 {n} 个文件")
        else:
            self._flist_container.setVisible(False)
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

        self._save_config()
        self.pending_files = files

        output_dir = os.path.expanduser("~/Documents/pdf2zh_files")
        os.makedirs(output_dir, exist_ok=True)

        self.go_btn.setEnabled(False); self.go_btn.setText("翻译中…")
        self.prog_card.setVisible(True); self.prog_bar.setValue(0)
        self.prog_pct.setText("0%")
        self.prog_label.setText("正在翻译…")
        self.prog_icon.setText("⏳")
        self.prog_tip.setText("")

        envs = build_service_envs(self.svc_combo.currentText())
        self.worker = TranslateWorker(
            file_path=files[0],
            output_dir=output_dir,
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
        self.worker.finished.connect(self._on_done)
        self.worker.error.connect(self._on_err)
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

    def _on_done(self, output_files):
        self.prog_bar.setValue(100); self.prog_pct.setText("100%")
        self.prog_label.setText("翻译完成")
        self.prog_icon.setText("✅")

        # 关怀消息
        from ui.caring import get_caring_message, get_session_tip
        caring = get_caring_message()
        if caring:
            self.prog_detail.setText(f"{caring[0]} {caring[2]}")
            self.prog_tip.setText(caring[1])
        else:
            self.prog_detail.setText("输出至 ~/Documents/pdf2zh_files")
            self.prog_tip.setText(get_session_tip())

        self.go_btn.setEnabled(True); self.go_btn.setText("开始翻译")
        self.stop_btn.setVisible(False)
        if self.worker:
            self.worker.wait(2000)
            self.worker.deleteLater()
            self.worker = None

        # 保存历史
        HistoryManager.add_record({
            "file": {"name": os.path.basename(self.pending_files[0]), "path": self.pending_files[0]},
            "translation": {
                "service": self.svc_combo.currentText(),
                "lang_in": self.src_combo.currentText(),
                "lang_out": self.tgt_combo.currentText(),
            },
            "output_files": output_files,
            "status": "success",
        })
        self.translation_done.emit(output_files)

        # Zotero 回写：把用户选定格式的译文复制回 Zotero 原位 + 自动关联附件
        try:
            zotero_dir = detect_zotero_source(self.pending_files[0])
            if zotero_dir:
                import shutil
                cfg = UserConfigManager.load()
                modes = cfg.get("zotero_output_modes", ["side_by_side"])
                keep_copy = cfg.get("zotero_keep_copy", True)
                item_key = get_zotero_item_key(self.pending_files[0])
                copied = []
                linked = []
                for mode in modes:
                    src = output_files.get(mode)
                    if src and os.path.exists(src):
                        dst = os.path.join(zotero_dir, os.path.basename(src))
                        if os.path.abspath(src) != os.path.abspath(dst):
                            shutil.copy2(src, dst)
                            copied.append(os.path.basename(dst))
                            if not keep_copy:
                                try:
                                    os.remove(src)
                                except OSError:
                                    pass
                        # 尝试通过 pdf2zh Connector 插件自动关联附件
                        if item_key:
                            mode_label = {"side_by_side": "并排", "dual": "双语", "mono": "译文"}.get(mode, mode)
                            ok, msg = zotero_auto_link(item_key, dst, f"翻译 ({mode_label})")
                            if ok:
                                linked.append(mode_label)
                if linked:
                    self.prog_detail.setText(f"已关联到 Zotero: {', '.join(linked)}")
                elif copied:
                    self.prog_detail.setText(f"已保存到 Zotero: {', '.join(copied)}")
                    # 插件未安装时，仅定位到对应条目
                    if item_key:
                        try:
                            import subprocess
                            subprocess.Popen(["open", f"zotero://select/library/items/{item_key}"])
                        except Exception:
                            pass
        except Exception:
            pass

        # 骰子系统：累加今日翻译页数（带签名）
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

    def _on_err(self, msg):
        self.prog_icon.setText("❌")
        self.prog_label.setText("翻译出错")
        self.prog_pct.setText("!")
        self.prog_detail.setText(msg)
        self.prog_bar.setValue(0)
        self.go_btn.setEnabled(True); self.go_btn.setText("重试翻译")
        self.stop_btn.setVisible(False)
        if self.worker:
            self.worker.wait(2000)
            self.worker.deleteLater()
            self.worker = None

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

        # 历史列表
        self.list_w = QListWidget()
        self.list_w.setObjectName("HistList")
        self.list_w.setFocusPolicy(Qt.StrongFocus)
        self.list_w.setSelectionMode(QListWidget.SingleSelection)
        self.list_w.currentItemChanged.connect(self._on_select)
        self.list_w.itemClicked.connect(lambda item: self._on_select(item, None))
        self.list_w.installEventFilter(self)
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
        records = HistoryManager.load()
        if not records:
            item = QListWidgetItem("暂无翻译记录")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QColor(_C["t3"]))
            self.list_w.addItem(item)
            return
        for r in records:
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
            item.setSizeHint(QSize(0, 44))
            self.list_w.addItem(item)
            # 自定义 widget 双行布局
            w = QWidget(); wl = QVBoxLayout(w)
            wl.setContentsMargins(2,2,2,2); wl.setSpacing(0)
            l1 = QLabel(f"{status} {fname}"); l1.setStyleSheet(f"font-size:12px;color:{_C['t1']};background:transparent;")
            l2 = QLabel(f"{svc} · {lang_in}→{lang_out} · {ts[5:]}")
            l2.setStyleSheet(f"font-size:11px;color:{_C['t2']};background:transparent;")
            wl.addWidget(l1); wl.addWidget(l2)
            w._l1 = l1; w._l2 = l2  # 存引用，选中时变色用
            self.list_w.setItemWidget(item, w)

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
        # 国际服务
        "OpenAI":          {"key_ph":"sk-...", "models":["gpt-4o","gpt-4o-mini","gpt-4-turbo","gpt-3.5-turbo","o1","o1-mini","o1-pro"], "url":"https://api.openai.com/v1"},
        "Azure OpenAI":    {"key_ph":"密钥",  "models":["gpt-4o","gpt-4-turbo","gpt-35-turbo"], "url":"https://YOUR_RESOURCE.openai.azure.com"},
        "DeepL":           {"key_ph":"密钥",  "models":[], "url":""},
        "Gemini":          {"key_ph":"密钥",  "models":["gemini-pro","gemini-1.5-pro","gemini-1.5-flash","gemini-2.0-flash"], "url":""},
        "Groq":            {"key_ph":"密钥",  "models":["llama-3.1-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768","llama-3.3-70b-versatile"], "url":"https://api.groq.com/openai/v1"},
        # 国产大模型
        "DeepSeek":        {"key_ph":"密钥",  "models":["deepseek-chat","deepseek-reasoner","deepseek-coder"], "url":"https://api.deepseek.com/v1"},
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

        # ══════════════════════════════════════════
        # 左列：翻译服务 → 提示词 → 术语库
        # ══════════════════════════════════════════
        left = QVBoxLayout(); left.setSpacing(2)

        # ── 翻译服务配置（选择器在卡片内部）──
        sl3 = QLabel("翻译服务配置"); sl3.setObjectName("SL"); left.addWidget(sl3)
        self.svc_card = _card()
        svc_outer = QVBoxLayout(self.svc_card)
        svc_outer.setContentsMargins(12,8,12,8); svc_outer.setSpacing(4)
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

        # ── 翻译提示词 ──
        from ui.prompt_manager import PromptTemplateManager
        from PyQt5.QtWidgets import QTextEdit
        sl4 = QLabel("翻译提示词"); sl4.setObjectName("SL"); left.addWidget(sl4)
        c4 = _card(); cl4 = QVBoxLayout(c4); cl4.setContentsMargins(12,8,12,8); cl4.setSpacing(2)

        pr = QHBoxLayout(); pr.setSpacing(4)
        self.prompt_preset = QComboBox()
        self._refresh_prompt_list()
        self.prompt_preset.currentTextChanged.connect(self._on_prompt_preset)
        pr.addWidget(self.prompt_preset, 1)
        cl4.addLayout(pr)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("提示词内容… 占位符: {lang_out} {lang_in} {text}")
        self.prompt_edit.setMaximumHeight(52)
        saved_prompt = cfg.get("prompt", "")
        if saved_prompt:
            self.prompt_edit.setPlainText(saved_prompt)
        cl4.addWidget(self.prompt_edit)

        btn_row = QHBoxLayout(); btn_row.setSpacing(2)
        for label, slot in [
            ("保存", self._save_prompt_template),
            ("新建", self._new_prompt_template),
            ("导入", self._import_prompts),
            ("导出", self._export_prompts),
        ]:
            b = QPushButton(label); b.setObjectName("Gh"); b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("font-size:11px;padding:2px 6px;")
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        del_btn = QPushButton("删除"); del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setObjectName("GhDanger"); del_btn.setStyleSheet("font-size:11px;padding:2px 6px;")
        del_btn.clicked.connect(self._delete_prompt_template)
        btn_row.addWidget(del_btn)
        cl4.addLayout(btn_row)

        hint = QLabel("{lang_out}=目标语言  {lang_in}=源语言  {text}=原文 · {{v*}} 保留公式 · Google/Bing 不使用提示词")
        hint.setObjectName("Cap"); hint.setWordWrap(True); hint.setStyleSheet("font-size:10px;")
        cl4.addWidget(hint)
        left.addWidget(c4)

        # ── 术语库 ──
        from ui.glossary_manager import GlossaryManager
        sl5 = QLabel("术语库"); sl5.setObjectName("SL"); left.addWidget(sl5)
        c5 = _card(); cl5 = QVBoxLayout(c5); cl5.setContentsMargins(12,8,12,8); cl5.setSpacing(2)

        gr = QHBoxLayout(); gr.setSpacing(6)
        self.gloss_selector = QComboBox()
        self._refresh_gloss_list()
        self.gloss_selector.currentTextChanged.connect(self._on_gloss_changed)
        gr.addWidget(self.gloss_selector, 1)
        self.gloss_count = QLabel(""); self.gloss_count.setObjectName("Cap")
        self.gloss_count.setStyleSheet("font-size:10px;")
        gr.addWidget(self.gloss_count)
        cl5.addLayout(gr)
        self._update_gloss_count()

        gbtn = QHBoxLayout(); gbtn.setSpacing(2)
        for label, slot in [
            ("新建", self._new_glossary),
            ("导入", self._import_glossary),
            ("导出", self._export_glossary),
        ]:
            b = QPushButton(label); b.setObjectName("Gh"); b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("font-size:11px;padding:2px 6px;"); b.clicked.connect(slot)
            gbtn.addWidget(b)
        gbtn.addStretch()
        gdel = QPushButton("删除"); gdel.setCursor(Qt.PointingHandCursor)
        gdel.setObjectName("GhDanger"); gdel.setStyleSheet("font-size:11px;padding:2px 6px;")
        gdel.clicked.connect(self._delete_glossary)
        gbtn.addWidget(gdel)
        cl5.addLayout(gbtn)

        hint2 = QLabel("翻译完成后自动替换匹配术语，支持 CSV/JSON 导入")
        hint2.setObjectName("Cap"); hint2.setWordWrap(True); hint2.setStyleSheet("font-size:10px;")
        cl5.addWidget(hint2)
        left.addWidget(c5)
        left.addStretch()

        cols.addLayout(left, 5)

        # ══════════════════════════════════════════
        # 右列：外观偏好 → 快捷键 → 使用指南
        # ══════════════════════════════════════════
        right = QVBoxLayout(); right.setSpacing(2)

        # ── 外观与偏好 ──
        sl_app = QLabel("外观与偏好"); sl_app.setObjectName("SL"); right.addWidget(sl_app)
        c = _card(); cl = QVBoxLayout(c); cl.setContentsMargins(12,8,12,8); cl.setSpacing(4)
        self.dark_check = QCheckBox("深色模式"); self.dark_check.toggled.connect(self.dark_mode_changed.emit)
        cl.addWidget(self.dark_check)

        # ── 主题色选择（骰子 3x6 解锁）──
        self.theme_row = QWidget(); tr_lo = QHBoxLayout(self.theme_row)
        tr_lo.setContentsMargins(0,2,0,2); tr_lo.setSpacing(6)
        tr_lbl = QLabel("主题色"); tr_lbl.setStyleSheet("font-size:12px;")
        tr_lo.addWidget(tr_lbl)
        THEME_COLORS = [
            ("#0071E3", "蓝"),  ("#FF6B6B", "红"),  ("#34C759", "绿"),
            ("#AF52DE", "紫"),  ("#FF9F0A", "橙"),  ("#FF2D55", "粉"),
            ("#5AC8FA", "青"),  ("#FFD60A", "黄"),
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
        # 检查解锁状态
        cfg_theme = UserConfigManager.load()
        self.theme_row.setVisible(cfg_theme.get("theme_unlocked", False))

        cl.addWidget(_div())
        self.cache_check = QCheckBox("翻译缓存"); self.cache_check.setChecked(True); cl.addWidget(self.cache_check)
        self.ai_check = QCheckBox("AI 布局检测"); self.ai_check.setChecked(True); cl.addWidget(self.ai_check)
        self.font_check = QCheckBox("字体子集化"); cl.addWidget(self.font_check)
        right.addWidget(c)

        # ── 快捷键 & 操作（两列紧凑网格）──
        kb_card = _card(); kb_lo = QVBoxLayout(kb_card)
        kb_lo.setContentsMargins(12,8,12,8); kb_lo.setSpacing(3)
        kb_t = QLabel("快捷键 & 操作"); kb_t.setStyleSheet("font-size:12px;font-weight:600;"); kb_lo.addWidget(kb_t)
        kb_lo.addWidget(_div())
        from PyQt5.QtWidgets import QGridLayout
        kb_grid = QGridLayout(); kb_grid.setHorizontalSpacing(12); kb_grid.setVerticalSpacing(3)
        shortcuts = [
            ("Ctrl+滚轮", "缩放预览"),
            ("双指捏合", "触控板缩放"),
            ("← →", "切换面板"),
            ("↑↓/滚轮", "翻页浏览"),
            ("页码+回车", "跳转页码"),
            ("适宽/适页", "最佳排版"),
        ]
        self._kb_labels = []
        for i, (key, desc) in enumerate(shortcuts):
            row, col = divmod(i, 2)
            kl = QLabel(key); kl.setObjectName("KBKey")
            kd = QLabel(desc); kd.setObjectName("Cap"); kd.setStyleSheet("font-size:11px;")
            kb_grid.addWidget(kl, row, col * 2)
            kb_grid.addWidget(kd, row, col * 2 + 1)
            self._kb_labels.append(kl)
        kb_lo.addLayout(kb_grid)
        right.addWidget(kb_card)

        # ── 快速指南 & 性能建议（合并为一张卡）──
        guide_card = _card(); guide_lo = QVBoxLayout(guide_card)
        guide_lo.setContentsMargins(12,8,12,8); guide_lo.setSpacing(2)
        gl = QLabel("快速指南"); gl.setStyleSheet("font-size:12px;font-weight:600;"); guide_lo.addWidget(gl)
        guide_lo.addWidget(_div())
        for tip in [
            "Google / Bing 翻译无需配置，开箱即用",
            "OpenAI 兼容接口可对接任意第三方服务",
            "Ollama 本地模型需先启动 Ollama 服务",
            "DeepSeek / 智谱等国产模型性价比高",
            "Base URL 末尾不要加斜杠 /",
        ]:
            tl = QLabel(f"·  {tip}"); tl.setObjectName("Cap"); tl.setStyleSheet("font-size:11px;")
            guide_lo.addWidget(tl)
        guide_lo.addSpacing(2)
        pl = QLabel("性能建议"); pl.setStyleSheet("font-size:12px;font-weight:600;"); guide_lo.addWidget(pl)
        guide_lo.addWidget(_div())
        for tip in [
            "50 页以上建议开启分块翻译",
            "线程数推荐 8–16，过高可能触发限流",
            "Ollama 本地翻译不受并发限制",
            "翻译服务不稳定时可降低线程数重试",
        ]:
            tl = QLabel(f"·  {tip}"); tl.setObjectName("Cap"); tl.setStyleSheet("font-size:11px;")
            guide_lo.addWidget(tl)
        right.addWidget(guide_card)

        # ── 数据管理 ──
        dm_card = _card(); dm_lo = QVBoxLayout(dm_card)
        dm_lo.setContentsMargins(12,8,12,8); dm_lo.setSpacing(3)
        dml = QLabel("数据管理"); dml.setStyleSheet("font-size:12px;font-weight:600;"); dm_lo.addWidget(dml)
        dm_lo.addWidget(_div())
        for info in [
            "配置文件: ~/pdf2zh_gui_config.json",
            "翻译历史: ~/pdf2zh_history.json",
            "术语库目录: ~/pdf2zh_glossaries/",
        ]:
            il = QLabel(f"·  {info}"); il.setObjectName("Cap"); il.setStyleSheet("font-size:10px;")
            dm_lo.addWidget(il)
        dm_btn_row = QHBoxLayout(); dm_btn_row.setSpacing(4)
        open_dir_btn = QPushButton("打开数据目录"); open_dir_btn.setObjectName("Gh")
        open_dir_btn.setCursor(Qt.PointingHandCursor); open_dir_btn.setStyleSheet("font-size:11px;padding:2px 6px;")
        open_dir_btn.clicked.connect(lambda: __import__('subprocess').run(['open', str(__import__('pathlib').Path.home())]))
        dm_btn_row.addWidget(open_dir_btn); dm_btn_row.addStretch()
        dm_lo.addLayout(dm_btn_row)
        right.addWidget(dm_card)

        # ── Zotero 译文输出 ──
        zot_card = _card(); zot_lo = QVBoxLayout(zot_card)
        zot_lo.setContentsMargins(12,8,12,8); zot_lo.setSpacing(3)
        zot_title = QLabel("Zotero 译文输出"); zot_title.setStyleSheet("font-size:12px;font-weight:600;")
        zot_lo.addWidget(zot_title); zot_lo.addWidget(_div())
        zot_desc = QLabel("从 Zotero 拖入的文献，翻译后自动放回原位")
        zot_desc.setObjectName("Cap"); zot_desc.setStyleSheet("font-size:11px;"); zot_desc.setWordWrap(True)
        zot_lo.addWidget(zot_desc)
        self._zot_sbs = QCheckBox("左右并排 (Side by Side)")
        self._zot_dual = QCheckBox("双语对照 (Dual)")
        self._zot_mono = QCheckBox("仅翻译 (Mono)")
        cfg = UserConfigManager.load()
        _zot_modes = cfg.get("zotero_output_modes", ["side_by_side"])
        self._zot_sbs.setChecked("side_by_side" in _zot_modes)
        self._zot_dual.setChecked("dual" in _zot_modes)
        self._zot_mono.setChecked("mono" in _zot_modes)
        for _cb in (self._zot_sbs, self._zot_dual, self._zot_mono):
            _cb.setStyleSheet("font-size:11px;")
            _cb.stateChanged.connect(self._save_zotero_modes)
            zot_lo.addWidget(_cb)
        zot_lo.addWidget(_div())
        self._zot_keep_copy = QCheckBox("同时保留一份到本地输出目录")
        self._zot_keep_copy.setStyleSheet("font-size:11px;")
        self._zot_keep_copy.setChecked(cfg.get("zotero_keep_copy", True))
        self._zot_keep_copy.stateChanged.connect(self._save_zotero_modes)
        zot_lo.addWidget(self._zot_keep_copy)
        # ── 自动关联附件（pdf2zh Connector 插件） ──
        zot_lo.addWidget(_div())
        zot_auto_title = QLabel("自动关联附件"); zot_auto_title.setStyleSheet("font-size:11px;font-weight:600;")
        zot_lo.addWidget(zot_auto_title)
        zot_auto_desc = QLabel("安装插件后，翻译完成自动将译文添加为 Zotero 附件，无需手动操作")
        zot_auto_desc.setObjectName("Cap"); zot_auto_desc.setStyleSheet("font-size:10px;"); zot_auto_desc.setWordWrap(True)
        zot_lo.addWidget(zot_auto_desc)
        _zot_btn_row = QHBoxLayout(); _zot_btn_row.setSpacing(6)
        self._zot_install_btn = QPushButton("一键安装到 Zotero")
        self._zot_install_btn.setObjectName("Gh")
        self._zot_install_btn.setCursor(Qt.PointingHandCursor)
        self._zot_install_btn.setStyleSheet("font-size:11px;padding:3px 8px;")
        self._zot_install_btn.clicked.connect(self._install_zotero_plugin)
        self._zot_status = QLabel("")
        self._zot_status.setStyleSheet("font-size:10px;")
        _zot_btn_row.addWidget(self._zot_install_btn)
        _zot_btn_row.addWidget(self._zot_status)
        _zot_btn_row.addStretch()
        zot_lo.addLayout(_zot_btn_row)
        # 检测插件状态
        QTimer.singleShot(500, self._check_zotero_plugin)
        right.addWidget(zot_card)

        right.addStretch()

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

    def _install_zotero_plugin(self):
        """一键安装 pdf2zh Connector 到 Zotero"""
        import glob, shutil, subprocess
        xpi = _res('assets', 'pdf2zh-connector.xpi')
        if not os.path.exists(xpi):
            self._zot_status.setText("插件文件缺失")
            self._zot_status.setStyleSheet("font-size:10px;color:#FF3B30;")
            return
        # 查找 Zotero profile 目录
        profiles_dir = os.path.expanduser("~/Library/Application Support/Zotero/Profiles")
        profiles = glob.glob(os.path.join(profiles_dir, "*.default"))
        if not profiles:
            self._zot_status.setText("找不到 Zotero 配置目录")
            self._zot_status.setStyleSheet("font-size:10px;color:#FF3B30;")
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
            self._zot_status.setStyleSheet("font-size:10px;color:#0071E3;")
        else:
            self._zot_status.setText("下次启动 Zotero 后生效")
            self._zot_status.setStyleSheet("font-size:10px;color:#0071E3;")

    def _check_zotero_plugin(self):
        """检测 pdf2zh Connector 插件状态"""
        if zotero_plugin_installed():
            self._zot_status.setText("已安装")
            self._zot_status.setStyleSheet("font-size:10px;color:#34C759;font-weight:600;")
            self._zot_install_btn.setText("已安装")
            self._zot_install_btn.setEnabled(False)
        else:
            self._zot_status.setText("")
            self._zot_install_btn.setText("一键安装到 Zotero")
            self._zot_install_btn.setEnabled(True)

    # ── 术语库操作 ──
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
        tv = QLabel("v2.0.0"); tv.setObjectName("Cap"); top.addWidget(tv)
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
        sub = QLabel("感谢每一位支持者 · 欢迎加入我们")
        sub.setObjectName("Cap"); sub.setAlignment(Qt.AlignCenter); sub.setStyleSheet("font-size:11px;"); ccl.addWidget(sub)
        xhs_community_btn = QPushButton("小红书社区链接 · 点击复制口令"); xhs_community_btn.setObjectName("Gh"); xhs_community_btn.setCursor(Qt.PointingHandCursor)
        xhs_community_btn.setStyleSheet("font-size:11px;")
        _xhs_code = '4【复制完整口令→启动小红书】 5月2日开放，"pdf2zh桌面版使用问题交流"精彩不容错过 MU2035 :/#d🥞🥒😂🥩🥖🥮🍕😚😏🐭😷🍕'
        def _copy_xhs_code():
            QApplication.clipboard().setText(_xhs_code)
            xhs_community_btn.setText("已复制 ✓ 打开小红书粘贴即可")
            QTimer.singleShot(2000, lambda: xhs_community_btn.setText("小红书社区链接 · 点击复制口令"))
        xhs_community_btn.clicked.connect(_copy_xhs_code)
        ccl.addWidget(xhs_community_btn, 0, Qt.AlignCenter)
        right.addWidget(cc)
        right.addStretch()

        cols.addLayout(right, 7)

        lo.addLayout(cols)


# ═══════════════════════════════════════════════════════════════
#  主窗口
# ═══════════════════════════════════════════════════════════════

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

        vl = QLabel("v2.0.0 · macOS"); vl.setObjectName("Cap"); vl.setAlignment(Qt.AlignCenter)
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

        self.switch("翻译"); self._apply()
        _install_tip_filter(QApplication.instance())

        # 静默预加载阅读页：用户点击时已渲染好，无闪烁
        QTimer.singleShot(100, self._preload_reader)

        # ── 凌晨 3:30 彩蛋：披星戴月 ──
        from datetime import datetime
        now = datetime.now()
        if now.hour == 3 and 25 <= now.minute <= 35:
            QTimer.singleShot(800, self._midnight_bloom)

    # ─────────────────────────────────────────────
    #  凌晨 3:30 彩蛋 — 烟花 + 暖心寄语
    # ─────────────────────────────────────────────
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
        self.is_dark = dark; self._apply()

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

    def _on_translate_done(self, output_files):
        reader = self.pages["阅读"]
        reader.set_output_files(output_files)
        QTimer.singleShot(600, lambda: self.switch("阅读"))


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

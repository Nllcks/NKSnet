import math
import random
from datetime import datetime
import os

from PySide6.QtCore import (
    Qt, QSize, QTimer, Property, QPointF, QPoint, QEasingCurve, QPropertyAnimation,
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QPainter, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QGraphicsBlurEffect,
    QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QPushButton,
    QTabWidget, QVBoxLayout, QWidget, QCheckBox, QSpacerItem, QSizePolicy,
    QGraphicsOpacityEffect,
)

from worker import SpeedTestWorker, AdblockWorker
from utils import detect_isp, load_history, load_settings, save_result


# ── Tema ─────────────────────────────────────────────────────────────
BG = "#0a0a0a"
CARD = "#141414"
WHITE = "#ffffff"
GRAY = "#888888"
DIM = "#333333"


def _font(size=10, bold=False):
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    return f


# ── Fundo animado com geometria ─────────────────────────────────────

class Particle:
    def __init__(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.vx = random.uniform(-0.15, 0.15)
        self.vy = random.uniform(-0.15, 0.15)
        self.size = random.uniform(1.0, 2.5)
        self.alpha = random.uniform(8, 24)


class BackgroundWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.particles = []
        self.angle = 0.0
        self._init_particles()

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._update_scene)
        self._timer.start()

    def _init_particles(self):
        self.particles = [Particle(self.width() or 600, self.height() or 680) for _ in range(40)]

    def _update_scene(self):
        self.angle += 0.003
        w = max(self.width(), 1)
        h = max(self.height(), 1)
        for p in self.particles:
            p.x += p.vx
            p.y += p.vy
            if p.x < 0:
                p.x = w
            if p.x > w:
                p.x = 0
            if p.y < 0:
                p.y = h
            if p.y > h:
                p.y = 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Linhas geometricas sutis
        painter.setPen(QPen(QColor(255, 255, 255, 14), 0.5))
        cx, cy = w * 0.5, h * 0.5
        for i in range(6):
            a = self.angle + i * (math.pi / 3)
            x2 = cx + math.cos(a) * w * 0.7
            y2 = cy + math.sin(a) * w * 0.7
            painter.drawLine(QPointF(cx, cy), QPointF(x2, y2))

        # Circulos concentricos
        for r in range(1, 5):
            painter.setPen(QPen(QColor(255, 255, 255, 8), 0.5))
            painter.drawEllipse(QPointF(cx, cy), r * 80, r * 80)

        # Particulas
        for p in self.particles:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(p.alpha)))
            painter.drawEllipse(QPointF(p.x, p.y), p.size, p.size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if len(self.particles) < 40:
            self._init_particles()


# ── Overlay com gradiente radial (blur escuro) ──────────────────────

class BlurOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._opacity = 1.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c = self.rect().center()
        r = max(self.width(), self.height()) * 0.65
        grad = QRadialGradient(c, r)
        a = self._opacity
        grad.setColorAt(0.0, QColor(0, 0, 0, int(255 * a)))
        grad.setColorAt(0.35, QColor(5, 5, 5, int(255 * a)))
        grad.setColorAt(0.6, QColor(10, 10, 10, int(255 * a)))
        grad.setColorAt(0.8, QColor(15, 15, 15, int(255 * a)))
        grad.setColorAt(1.0, QColor(20, 20, 20, int(255 * a)))
        painter.fillRect(self.rect(), grad)


# ── Gauge circular (download) ───────────────────────────────────────

class CircularButton(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 260)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

        self._state = "idle"
        self._phase = ""
        self._progress = 0.0
        self._target = 0.0
        self._hover = False
        self._mouse_pos = None

        self._dl_speed = 0.0
        self._dl_target = 0.0
        self._ul_speed = 0.0
        self._ul_target = 0.0
        self._ping = 0.0
        self._jitter = 0.0

        self._anim = QTimer(self)
        self._anim.setInterval(16)
        self._anim.timeout.connect(self._tick)
        self._anim.start()

    @Property(str)
    def state(self):
        return self._state

    @state.setter
    def state(self, v):
        self._state = v
        self.update()

    @Property(float)
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, v):
        self._target = v

    def set_dl(self, v):
        self._dl_target = v

    def set_ul(self, v):
        self._ul_target = v

    def set_ping(self, v):
        self._ping = v
        self.update()

    def set_jitter(self, v):
        self._jitter = v
        self.update()

    def _tick(self):
        diff = self._target - self._progress
        if abs(diff) < 0.05:
            if self._progress != self._target:
                self._progress = self._target
                self.update()
        else:
            self._progress += diff * 0.04
            self.update()

        changed = False
        d = self._dl_target - self._dl_speed
        if abs(d) > 0.01:
            self._dl_speed += d * 0.03
            changed = True
        elif self._dl_speed != self._dl_target:
            self._dl_speed = self._dl_target
            changed = True

        u = self._ul_target - self._ul_speed
        if abs(u) > 0.01:
            self._ul_speed += u * 0.03
            changed = True
        elif self._ul_speed != self._ul_target:
            self._ul_speed = self._ul_target
            changed = True

        if changed:
            self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._mouse_pos = None
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.position()
        self.update()
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(18, 18, -18, -18)
        c = rect.center()

        if self._state == "idle":
            self._paint_idle(painter, rect, c)
        elif self._state == "testing":
            self._paint_testing(painter, rect, c)
        else:
            self._paint_done(painter, rect, c)

    def _paint_mouse_glow(self, painter, rect):
        if self._hover and self._mouse_pos:
            glow = QRadialGradient(self._mouse_pos, rect.width() * 0.55)
            glow.setColorAt(0.0, QColor(255, 255, 255, 30))
            glow.setColorAt(0.6, QColor(255, 255, 255, 8))
            glow.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(glow)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect)

    def _paint_idle(self, painter, rect, center):
        self._paint_mouse_glow(painter, rect)
        pen = QPen(QColor(WHITE), 2.5)
        painter.setPen(pen)
        painter.drawEllipse(rect)
        painter.setPen(QColor(WHITE))
        painter.setFont(_font(20, True))
        painter.drawText(rect, Qt.AlignCenter, "INICIAR")

    @staticmethod
    def _progress_color(t: float) -> QColor:
        if t < 0.5:
            lt = t / 0.5
            r = 229 + (255 - 229) * lt
            g = 57 + (193 - 57) * lt
            b = 53 + (7 - 53) * lt
        else:
            lt = (t - 0.5) / 0.5
            r = 255 + (76 - 255) * lt
            g = 193 + (175 - 193) * lt
            b = 7 + (80 - 7) * lt
        return QColor(int(r), int(g), int(b))

    def _paint_testing(self, painter, rect, center):
        self._paint_mouse_glow(painter, rect)
        pen = QPen(QColor(DIM), 3)
        painter.setPen(pen)
        painter.drawEllipse(rect)

        t = self._progress / 100.0
        span = int(-self._progress / 100.0 * 360 * 16)
        pen = QPen(self._progress_color(t), 5, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 90 * 16, span)

        if self._phase == "ping":
            val = f"{self._ping:.0f}" if self._ping > 0 else "--"
            lbl = "PING (ms)"
        else:
            val = f"{self._dl_speed:.1f}" if self._dl_speed > 0 else "0.0"
            lbl = "DOWNLOAD"

        painter.setPen(QColor(WHITE))
        painter.setFont(_font(34, True))
        painter.drawText(rect.adjusted(0, -24, 0, -24), Qt.AlignCenter, val)

        painter.setPen(QColor(GRAY))
        painter.setFont(_font(10))
        painter.drawText(rect.adjusted(0, 16, 0, 16), Qt.AlignCenter, lbl)

    def _paint_done(self, painter, rect, center):
        self._paint_mouse_glow(painter, rect)
        pen = QPen(self._progress_color(1.0), 4)
        painter.setPen(pen)
        painter.drawEllipse(rect)

        painter.setPen(QColor(WHITE))
        painter.setFont(_font(38, True))
        painter.drawText(rect.adjusted(0, -32, 0, -32), Qt.AlignCenter,
                         f"{self._dl_speed:.1f}")

        painter.setPen(QColor(GRAY))
        painter.setFont(_font(11, True))
        painter.drawText(rect.adjusted(0, 0, 0, 0), Qt.AlignCenter, "DOWNLOAD")

        painter.setPen(QColor(GRAY))
        painter.setFont(_font(11))
        painter.drawText(rect.adjusted(0, 18, 0, 18), Qt.AlignCenter, "Mbps")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._state == "idle":
            c = self.parent()
            while c and not hasattr(c, "start_test"):
                c = c.parent()
            if c:
                c.start_test()
        super().mousePressEvent(event)


# ── Gauge de upload ─────────────────────────────────────────────────

class UploadGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 260)
        self.setMouseTracking(True)
        self._progress = 0.0
        self._target = 0.0
        self._speed = 0.0
        self._target_speed = 0.0
        self._hover = False
        self._mouse_pos = None

        self._anim = QTimer(self)
        self._anim.setInterval(16)
        self._anim.timeout.connect(self._tick)
        self._anim.start()

    @Property(float)
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, v):
        self._target = v

    def set_speed(self, v):
        self._target_speed = v

    def reset(self):
        self._progress = 0.0
        self._target = 0.0
        self._speed = 0.0
        self._target_speed = 0.0
        self.update()

    def _tick(self):
        diff = self._target - self._progress
        if abs(diff) < 0.05:
            if self._progress != self._target:
                self._progress = self._target
                self.update()
        else:
            self._progress += diff * 0.04
            self.update()

        d = self._target_speed - self._speed
        if abs(d) > 0.01:
            self._speed += d * 0.03
            self.update()
        elif self._speed != self._target_speed:
            self._speed = self._target_speed
            self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._mouse_pos = None
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.position()
        self.update()
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(18, 18, -18, -18)

        if self._hover and self._mouse_pos:
            glow = QRadialGradient(self._mouse_pos, rect.width() * 0.55)
            glow.setColorAt(0.0, QColor(255, 255, 255, 20))
            glow.setColorAt(0.6, QColor(255, 255, 255, 5))
            glow.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(glow)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect)

        pen = QPen(QColor(DIM), 3)
        painter.setPen(pen)
        painter.drawEllipse(rect)

        t = self._progress / 100.0
        span = int(-self._progress / 100.0 * 360 * 16)
        r = int(66 + (76 - 66) * t)
        g = int(165 + (175 - 165) * t)
        b = int(245 + (80 - 245) * t)
        pen = QPen(QColor(r, g, b), 5, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 90 * 16, span)

        val = f"{self._speed:.1f}" if self._speed > 0 else "0.0"
        painter.setPen(QColor(WHITE))
        painter.setFont(_font(34, True))
        painter.drawText(rect.adjusted(0, -24, 0, -24), Qt.AlignCenter, val)

        painter.setPen(QColor(GRAY))
        painter.setFont(_font(10))
        painter.drawText(rect.adjusted(0, 16, 0, 16), Qt.AlignCenter, "UPLOAD")

        painter.setPen(QColor(GRAY))
        painter.setFont(_font(9))
        painter.drawText(rect.adjusted(0, 32, 0, 32), Qt.AlignCenter, "Mbps")


# ── Container dos gauges ───────────────────────────────────────────

class GaugeContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(544, 260)

        self.circle = CircularButton(self)
        self.upload = UploadGauge(self)
        self.upload.setVisible(False)

        self._slide = 0.0
        self._target_slide = 0.0

        self._anim = QTimer(self)
        self._anim.setInterval(16)
        self._anim.timeout.connect(self._tick)
        self._anim.start()

    def start_test(self):
        self.circle.state = "idle"
        self.circle._dl_speed = 0
        self.circle._dl_target = 0
        self.circle._ul_speed = 0
        self.circle._ul_target = 0
        self.circle._ping = 0
        self.circle._jitter = 0
        self.circle.progress = 0
        self.circle._target = 0
        self.circle._progress = 0
        self.upload.reset()
        self.upload.setVisible(False)
        self._target_slide = 0.0

        c = self.parent()
        while c and not hasattr(c, "start_test"):
            c = c.parent()
        if c:
            c.start_test()

    def slide_to_upload(self):
        self._slide = 1.0
        self._target_slide = 1.0
        self._layout_children()

    def reset_all(self):
        self.circle._dl_speed = 0
        self.circle._ul_speed = 0
        self.circle._ping = 0
        self.circle._jitter = 0
        self.circle._target = 0
        self.circle._progress = 0
        self.circle._phase = ""
        self.circle.state = "idle"
        self.upload.reset()
        self.upload.setVisible(False)
        self._target_slide = 0.0
        self._slide = 0.0
        self._layout_children()

    def _tick(self):
        diff = self._target_slide - self._slide
        if abs(diff) < 0.005:
            if self._slide != self._target_slide:
                self._slide = self._target_slide
                self._layout_children()
        else:
            self._slide += diff * 0.10
            self._layout_children()

    def _layout_children(self):
        w = self.width()
        h = self.height()
        cs = 260
        gap = 24
        center_x = (w - cs) // 2
        left_x = 0

        cx = int(center_x + (left_x - center_x) * self._slide)
        cy = (h - cs) // 2
        self.circle.move(cx, cy)

        if self._slide > 0.01:
            ux = cx + cs + gap
            self.upload.move(ux, cy)
            self.upload.setVisible(True)
        else:
            self.upload.setVisible(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_children()


# ── Dialog de historico ─────────────────────────────────────────────

class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historico de Testes")
        self.setFixedSize(560, 520)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG}; color: {WHITE}; }}
            QListWidget {{
                background-color: {CARD}; color: {WHITE};
                border: 2px solid {DIM}; border-radius: 8px;
                font-family: 'Segoe UI'; font-size: 11pt; padding: 4px;
            }}
            QListWidget::item {{
                padding: 14px 12px;
                border-bottom: 2px solid {DIM};
                font-size: 11pt;
            }}
            QListWidget::item:selected {{
                background-color: {DIM}; color: {WHITE};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Historico de Testes")
        title.setStyleSheet(f"color: {WHITE}; font-size: 18pt; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setWordWrap(True)
        layout.addWidget(self.list_widget)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE}; color: {BG};
                font-weight: bold; border-radius: 6px; padding: 10px 32px;
                font-size: 11pt;
            }}
            QPushButton:hover {{ background-color: {GRAY}; }}
        """)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)

        self._load()

    def _load(self):
        history = load_history()
        if not history:
            self.list_widget.addItem("Nenhum teste encontrado.")
            return
        for entry in reversed(history):
            ts = datetime.fromtimestamp(entry["timestamp"]).strftime("%d/%m/%Y %H:%M")
            dl = entry['download']
            ul = entry['upload']
            ping = entry['ping']
            text = (
                f"  {ts}\n"
                f"  Download: {dl:.1f} Mbps    Upload: {ul:.1f} Mbps    Ping: {ping:.1f} ms"
            )
            item = QListWidgetItem(text)
            sz = item.sizeHint()
            sz.setHeight(sz.height() + 20)
            item.setSizeHint(sz)
            self.list_widget.addItem(item)


# ── Dialog de configuracoes ─────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuracoes")
        self.setFixedSize(360, 200)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG}; color: {WHITE}; }}
            QLabel {{ color: {WHITE}; font-size: 11pt; }}
            QCheckBox {{ color: {WHITE}; font-size: 11pt; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px; border-radius: 3px;
                border: 2px solid {GRAY};
            }}
            QCheckBox::indicator:checked {{ background-color: {WHITE}; border-color: {WHITE}; }}
        """)

        self.settings = load_settings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Configuracoes")
        title.setStyleSheet(f"color: {WHITE}; font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)

        self.auto_start_cb = QCheckBox("Iniciar teste automaticamente ao abrir")
        self.auto_start_cb.setChecked(self.settings.get("auto_start", False))
        layout.addWidget(self.auto_start_cb)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE}; color: {BG};
                font-weight: bold; border-radius: 4px; padding: 6px 20px; min-width: 80px;
            }}
            QPushButton:hover {{ background-color: {GRAY}; }}
            QPushButton[text="Cancel"] {{ background-color: {DIM}; color: {WHITE}; }}
            QPushButton[text="Cancel"]:hover {{ background-color: #444; }}
        """)
        btn_box.accepted.connect(self._save_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _save_and_accept(self):
        self.settings["auto_start"] = self.auto_start_cb.isChecked()
        save_settings(self.settings)
        self.accept()


# ── Painel lateral deslizante ──────────────────────────────────────

class SidePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._open = False
        self._anim = None
        self._hover = False
        self._mouse_pos = None
        self.setMouseTracking(True)
        self.setFixedWidth(240)

        self.setStyleSheet(f"""
            background-color: {CARD};
            border: none;
            border-left: 1px solid {DIM};
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        cab = QWidget()
        cab.setFixedHeight(56)
        cab.setStyleSheet(f"background-color: {BG};")
        cab_layout = QHBoxLayout(cab)
        cab_layout.setContentsMargins(16, 0, 16, 0)
        titulo = QLabel("Opcoes")
        titulo.setStyleSheet(f"color: {WHITE}; font-size: 14pt; font-weight: bold;")
        cab_layout.addWidget(titulo)
        cab_layout.addStretch()
        btn_fechar = QPushButton("\u2716")
        btn_fechar.setFixedSize(28, 28)
        btn_fechar.setCursor(Qt.PointingHandCursor)
        btn_fechar.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {GRAY}; font-size: 12pt; border: none; }}
            QPushButton:hover {{ color: {WHITE}; }}
        """)
        btn_fechar.clicked.connect(self.close_panel)
        cab_layout.addWidget(btn_fechar)
        layout.addWidget(cab)

        def _criar_btn(texto, callback):
            btn = QPushButton(texto)
            btn.setFixedHeight(48)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {WHITE};
                    font-size: 12pt; text-align: left; padding: 0 20px;
                    border: none; border-radius: 0;
                }}
                QPushButton:hover {{ background-color: {DIM}; }}
            """)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        _criar_btn("Historico", lambda: (self.close_panel(), self._open_history()))
        _criar_btn("Configuracoes", lambda: (self.close_panel(), self._open_settings()))
        layout.addStretch()

        self.hide()

    def _open_history(self):
        mw = self.window()
        if hasattr(mw, "_show_history"):
            mw._show_history()

    def _open_settings(self):
        mw = self.window()
        if hasattr(mw, "_show_settings"):
            mw._show_settings()

    def toggle(self):
        if self._open:
            self.close_panel()
        else:
            self.open_panel()

    def open_panel(self):
        self._open = True
        self.show()
        self.raise_()
        pw = self.parent().width()
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setStartValue(QPoint(pw, 0))
        self._anim.setEndValue(QPoint(pw - self.width(), 0))
        self._anim.start()

    def close_panel(self):
        if not self._open:
            return
        self._open = False
        pw = self.parent().width()
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.InCubic)
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(pw, 0))
        self._anim.finished.connect(self._on_close_done)
        self._anim.start()

    def _on_close_done(self):
        self.hide()

    def enterEvent(self, event):
        self._hover = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._mouse_pos = None
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.position()
        self.update()
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(CARD))
        painter.drawRoundedRect(self.rect().adjusted(1, 0, 0, 0), 8, 8)

        if self._hover and self._mouse_pos:
            r = max(self.width(), self.height()) * 0.6
            glow = QRadialGradient(self._mouse_pos, r)
            glow.setColorAt(0.0, QColor(255, 255, 255, 25))
            glow.setColorAt(0.5, QColor(255, 255, 255, 6))
            glow.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(glow)
            painter.setPen(Qt.NoPen)
            painter.drawRect(self.rect())

        super().paintEvent(event)


# ── Gauge do Adblock Tester ───────────────────────────────────────

class AdblockGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 260)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

        self._state = "idle"
        self._progress = 0.0
        self._target = 0.0
        self._result = 0.0
        self._total = 0
        self._blocked = 0
        self._hover = False
        self._mouse_pos = None

        self._anim = QTimer(self)
        self._anim.setInterval(16)
        self._anim.timeout.connect(self._tick)
        self._anim.start()

    def _tick(self):
        diff = self._target - self._progress
        if abs(diff) < 0.05:
            if self._progress != self._target:
                self._progress = self._target
                self.update()
        else:
            self._progress += diff * 0.04
            self.update()

    def reset(self):
        self._state = "idle"
        self._progress = 0.0
        self._target = 0.0
        self._result = 0.0
        self._total = 0
        self._blocked = 0
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._mouse_pos = None
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.position()
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._state == "idle":
            c = self.parent()
            while c and not hasattr(c, "start_test"):
                c = c.parent()
            if c:
                c.start_test()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(18, 18, -18, -18)

        if self._state == "idle":
            self._paint_idle(painter, rect)
        elif self._state == "testing":
            self._paint_testing(painter, rect)
        else:
            self._paint_done(painter, rect)

    def _paint_glow(self, painter, rect):
        if self._hover and self._mouse_pos:
            g = QRadialGradient(self._mouse_pos, rect.width() * 0.55)
            g.setColorAt(0.0, QColor(255, 255, 255, 30))
            g.setColorAt(0.6, QColor(255, 255, 255, 8))
            g.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(g)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect)

    def _paint_idle(self, painter, rect):
        self._paint_glow(painter, rect)
        painter.setPen(QPen(QColor(WHITE), 2.5))
        painter.drawEllipse(rect)
        painter.setPen(QColor(WHITE))
        painter.setFont(_font(20, True))
        painter.drawText(rect, Qt.AlignCenter, "TESTAR")

    def _paint_testing(self, painter, rect):
        self._paint_glow(painter, rect)
        painter.setPen(QPen(QColor(DIM), 3))
        painter.drawEllipse(rect)

        t = self._progress / 100.0
        span = int(-self._progress / 100.0 * 360 * 16)
        r = int(66 + (139 - 66) * t)
        g = int(165 + (92 - 165) * t)
        b = int(245 + (246 - 245) * t)
        painter.setPen(QPen(QColor(r, g, b), 5, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 90 * 16, span)

        val = f"{self._progress:.0f}%"
        painter.setPen(QColor(WHITE))
        painter.setFont(_font(34, True))
        painter.drawText(rect.adjusted(0, -12, 0, -12), Qt.AlignCenter, val)

    def _paint_done(self, painter, rect):
        self._paint_glow(painter, rect)

        painter.setPen(QPen(QColor(DIM), 3))
        painter.drawEllipse(rect)

        t = min(self._result / 100.0, 1.0)
        span = int(-self._result / 100.0 * 360 * 16)
        r = int(66 + (34 - 66) * t)
        g = int(165 + (197 - 165) * t)
        b = int(245 + (94 - 245) * t)
        painter.setPen(QPen(QColor(r, g, b), 5, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 90 * 16, span)

        painter.setPen(QColor(WHITE))
        painter.setFont(_font(46, True))
        painter.drawText(rect, Qt.AlignCenter, f"{self._result:.0f}%")


# ── Widget da tab Adblock Tester ───────────────────────────────────

class AdblockTesterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._timeout_timer = None
        self._build_ui()
        self._connect_worker()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.subtitle = QLabel("Teste de bloqueio de anuncios")
        self.subtitle.setStyleSheet(f"color: {GRAY}; font-size: 10pt;")
        self.subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.subtitle)

        layout.addSpacing(16)

        self.gauge = AdblockGauge(self)
        layout.addWidget(self.gauge, alignment=Qt.AlignCenter)

        layout.addSpacing(14)

        self.lbl_result = QLabel("")
        self.lbl_result.setStyleSheet(
            f"color: {WHITE}; font-size: 15pt; font-weight: bold;"
        )
        self.lbl_result.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_result)

        self.lbl_detail = QLabel("")
        self.lbl_detail.setStyleSheet(f"color: {GRAY}; font-size: 10pt;")
        self.lbl_detail.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_detail)

        layout.addSpacing(12)

        self.btn_retry = QPushButton("TESTAR NOVAMENTE")
        self.btn_retry.setCursor(Qt.PointingHandCursor)
        self.btn_retry.setFixedSize(220, 40)
        self.btn_retry.setVisible(False)
        self.btn_retry.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE}; color: {BG};
                font-size: 11pt; font-weight: bold;
                border-radius: 20px; border: none;
            }}
            QPushButton:hover {{ background-color: {GRAY}; }}
        """)
        self.btn_retry.clicked.connect(self.start_test)
        layout.addWidget(self.btn_retry, alignment=Qt.AlignCenter)

        layout.addStretch()

    def _connect_worker(self):
        self.worker = AdblockWorker()
        self.worker.progress.connect(self._on_progress)
        self.worker.result.connect(self._on_result)
        self.worker.error.connect(self._on_error)

    def start_test(self):
        if self.worker.isRunning():
            return
        if self._timeout_timer:
            self._timeout_timer.stop()
            self._timeout_timer = None
        self.worker = AdblockWorker()
        self._connect_worker()
        self.gauge.reset()
        self.gauge._state = "testing"
        self.btn_retry.setVisible(False)
        self.lbl_result.setText("")
        self.lbl_detail.setText("")
        self.subtitle.setText("Testando bloqueio de anuncios...")
        self.worker.start()
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.setInterval(5000)
        self._timeout_timer.timeout.connect(self._timeout_test)
        self._timeout_timer.start()

    def _timeout_test(self):
        if self.worker.isRunning():
            self.worker.cancel()

    def _on_progress(self, pct):
        self.gauge._target = pct
        self.gauge._state = "testing"
        if pct > 5:
            self.subtitle.setText("Testando DNS...")

    def _on_result(self, pct, total, blocked):
        if self._timeout_timer:
            self._timeout_timer.stop()
            self._timeout_timer = None
        self.gauge._result = pct
        self.gauge._progress = pct
        self.gauge._target = pct
        self.gauge._state = "done"
        self.lbl_result.setText(f"{pct:.0f}% dos anuncios bloqueados")
        self.subtitle.setText("Teste concluido!")
        self.btn_retry.setVisible(True)

    def _on_error(self, msg):
        self.subtitle.setText(f"Erro: {msg}")
        self.gauge._state = "idle"


# ── Splash de inicializacao ───────────────────────────────────────

class SplashOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 1.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._step = 0
        self._max_steps = 32

    def start_fade(self):
        self._step = 0
        self._timer.start()

    def _tick(self):
        self._step += 1
        t = min(self._step / self._max_steps, 1.0)
        self._opacity = 1.0 - t
        self.update()
        if self._step >= self._max_steps:
            self._timer.stop()
            self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        a = int(255 * self._opacity)
        painter.fillRect(self.rect(), QColor(10, 10, 10, a))
        ta = int(255 * self._opacity)
        painter.setPen(QColor(255, 255, 255, ta))
        painter.setFont(QFont("Segoe UI", 54, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, "NKSnet")


# ── Janela principal ───────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NKS Speedtest")
        self.setFixedSize(600, 680)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        self._apply_theme()

        # Fundo animado
        self.bg = BackgroundWidget(self.centralWidget())
        self.bg.setGeometry(central.rect())
        self.bg.lower()

        self.root = QVBoxLayout(central)
        self.root.setContentsMargins(24, 16, 24, 16)
        self.root.setSpacing(0)

        # ── Topo: logo + menu ──────────────────────────────────────
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)

        logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
        self.logo_label = QLabel()
        if os.path.isfile(logo_path):
            pix = QPixmap(logo_path).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pix)
        else:
            self.logo_label.setText("NKS")
            self.logo_label.setStyleSheet(f"color: {WHITE}; font-size: 18pt; font-weight: bold;")
        self.logo_label.setFixedHeight(32)
        top_layout.addWidget(self.logo_label)

        top_layout.addSpacing(8)

        self.title_label = QLabel("SPEEDTEST")
        self.title_label.setStyleSheet(f"color: {WHITE}; font-size: 18pt; font-weight: bold; letter-spacing: 2px;")
        top_layout.addWidget(self.title_label)

        top_layout.addStretch()

        self.menu_btn = QPushButton("\u2630")
        self.menu_btn.setFixedSize(36, 36)
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {WHITE};
                font-size: 18pt; border: none; border-radius: 18px;
            }}
            QPushButton:hover {{ background-color: {DIM}; }}
        """)
        self.menu_btn.clicked.connect(self._show_menu)
        top_layout.addWidget(self.menu_btn)

        self.root.addLayout(top_layout)
        self.root.addSpacing(10)

        # ── Abas ────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background: transparent; border: none; }}
            QTabBar::tab {{
                background: transparent; color: {GRAY};
                padding: 6px 18px; margin-right: 2px;
                font-size: 10pt; font-weight: bold;
                border: none; border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{ color: {WHITE}; border-bottom: 2px solid {WHITE}; }}
            QTabBar::tab:hover {{ color: {WHITE}; }}
        """)

        # ── Aba Speedtest ───────────────────────────────────────────
        st_tab = QWidget()
        st_layout = QVBoxLayout(st_tab)
        st_layout.setContentsMargins(0, 0, 0, 0)
        st_layout.setSpacing(0)

        self.subtitle = QLabel("Teste sua conexao com a internet")
        self.subtitle.setStyleSheet(f"color: {GRAY}; font-size: 10pt;")
        self.subtitle.setAlignment(Qt.AlignCenter)
        st_layout.addWidget(self.subtitle)

        st_layout.addSpacing(10)

        self.gauge_container = GaugeContainer()
        st_layout.addWidget(self.gauge_container, alignment=Qt.AlignCenter)

        st_layout.addSpacing(8)

        self.btn_retry = QPushButton("TESTAR NOVAMENTE")
        self.btn_retry.setCursor(Qt.PointingHandCursor)
        self.btn_retry.setFixedSize(220, 40)
        self.btn_retry.setVisible(False)
        self.btn_retry.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE}; color: {BG};
                font-size: 11pt; font-weight: bold;
                border-radius: 20px; border: none;
            }}
            QPushButton:hover {{ background-color: {GRAY}; }}
        """)
        self.btn_retry.clicked.connect(self._on_retry)
        st_layout.addWidget(self.btn_retry, alignment=Qt.AlignCenter)

        st_layout.addSpacing(8)

        self.info_widget = QWidget()
        info_layout = QVBoxLayout(self.info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        row_dl = QHBoxLayout()
        row_dl.setAlignment(Qt.AlignCenter)
        self.lbl_dl = QLabel("Download:  -- Mbps")
        self.lbl_dl.setStyleSheet(f"color: {WHITE}; font-size: 12pt;")
        row_dl.addWidget(self.lbl_dl)
        info_layout.addLayout(row_dl)

        row_ul = QHBoxLayout()
        row_ul.setAlignment(Qt.AlignCenter)
        self.lbl_ul = QLabel("Upload:   -- Mbps")
        self.lbl_ul.setStyleSheet(f"color: {WHITE}; font-size: 12pt;")
        row_ul.addWidget(self.lbl_ul)
        info_layout.addLayout(row_ul)

        row_ping = QHBoxLayout()
        row_ping.setAlignment(Qt.AlignCenter)
        self.lbl_ping = QLabel("Ping: -- ms     Jitter: -- ms")
        self.lbl_ping.setStyleSheet(f"color: {GRAY}; font-size: 10pt;")
        row_ping.addWidget(self.lbl_ping)
        info_layout.addLayout(row_ping)

        st_layout.addWidget(self.info_widget)
        st_layout.addStretch()

        self.tabs.addTab(st_tab, "SPEEDTEST")

        # ── Aba Adblock Tester ──────────────────────────────────────
        self.adblock_tester = AdblockTesterWidget()
        self.tabs.addTab(self.adblock_tester, "ADBLOCK TESTER")

        self.root.addWidget(self.tabs)

        # ── Rodape: ISP com overlay blur ───────────────────────────
        self.footer = QWidget()
        self.footer.setObjectName("footer")
        self.footer.setStyleSheet(f"""
            #footer {{
                background-color: {CARD}; border-radius: 8px; padding: 8px;
                border: 1px solid rgba(255,255,255,30);
            }}
        """)
        footer_layout = QVBoxLayout(self.footer)
        footer_layout.setContentsMargins(14, 10, 14, 10)
        footer_layout.setSpacing(2)

        isp_row = QHBoxLayout()
        self.lbl_isp = QLabel("Detectando ISP...")
        self.lbl_isp.setStyleSheet(f"color: {GRAY}; font-size: 10pt;")
        isp_row.addWidget(self.lbl_isp)
        isp_row.addStretch()
        self.btn_blur = QPushButton("\u25C9")
        self.btn_blur.setFixedSize(24, 24)
        self.btn_blur.setCursor(Qt.PointingHandCursor)
        self.btn_blur.setToolTip("Alternar efeito blur")
        self.btn_blur.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {WHITE};
                font-size: 12pt; border: none; border-radius: 12px;
            }}
            QPushButton:hover {{ background-color: {DIM}; }}
        """)
        self.btn_blur.clicked.connect(self._toggle_blur)
        isp_row.addWidget(self.btn_blur)
        footer_layout.addLayout(isp_row)

        self.lbl_cidade = QLabel("")
        self.lbl_cidade.setStyleSheet(f"color: {GRAY}; font-size: 9pt;")
        footer_layout.addWidget(self.lbl_cidade)

        server_row = QHBoxLayout()
        self.lbl_server = QLabel("Servidor: --")
        self.lbl_server.setStyleSheet(f"color: {GRAY}; font-size: 9pt;")
        server_row.addWidget(self.lbl_server)
        server_row.addStretch()
        footer_layout.addLayout(server_row)

        self.root.addWidget(self.footer)

        # Overlay escuro com gradiente radial (efeito blur)
        self.footer_blur = BlurOverlay(self.footer)
        self.footer_blur.setGeometry(0, 0, self.footer.width(), self.footer.height())

        self.btn_blur.raise_()

        orig_resize = self.footer.resizeEvent
        def _on_footer_resize(event):
            orig_resize(event)
            self.footer_blur.setGeometry(0, 0, self.footer.width(), self.footer.height())
            self.btn_blur.raise_()
        self.footer.resizeEvent = _on_footer_resize

        # Atualiza bg ao redimensionar
        central.resizeEvent = self._on_central_resize

        # ── Worker ─────────────────────────────────────────────────
        self.worker = SpeedTestWorker()
        self.worker.progress.connect(self._on_progress)
        self.worker.ping_result.connect(self._on_ping)
        self.worker.download_result.connect(self._on_download)
        self.worker.upload_result.connect(self._on_upload)
        self.worker.jitter_result.connect(self._on_jitter)
        self.worker.server_info.connect(self._on_server_info)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)

        self._isp_data = {}
        self._upload_started = False
        self._detect_isp()

        self.panel = SidePanel(self.centralWidget())
        self.panel.setGeometry(0, 0, central.width(), central.height())
        self.panel.lower()

        settings = load_settings()
        if settings.get("auto_start"):
            QTimer.singleShot(500, self.start_test)

        # ── Splash de inicializacao ─────────────────────────────────
        self.splash = SplashOverlay(central)
        self.splash.setGeometry(central.rect())
        self.splash.raise_()
        QTimer.singleShot(2500, self.splash.start_fade)

    def _on_central_resize(self, event):
        QWidget.resizeEvent(self.centralWidget(), event)
        r = self.centralWidget().rect()
        self.bg.setGeometry(r)
        if hasattr(self, "splash"):
            self.splash.setGeometry(r)

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {BG}; }}
            #central {{ background-color: transparent; }}
        """)

    def _show_menu(self):
        self.panel.raise_()
        self.panel.toggle()

    def _show_history(self):
        dlg = HistoryDialog(self)
        dlg.exec()

    def _show_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def _detect_isp(self):
        data = detect_isp()
        self._isp_data = data
        isp = data.get("isp", "Nao disponivel")
        cidade = f"{data.get('city', '')}, {data.get('region', '')}".strip(", ")
        self.lbl_isp.setText(f"{isp}")
        self.lbl_cidade.setText(f"{cidade}" if cidade else "")

    def _toggle_blur(self):
        blur = self.footer_blur
        visible = not blur.isHidden()
        target = 0.0 if visible else 1.0
        start = blur._opacity
        steps = 20
        idx = [0]

        if not visible:
            blur.show()
            blur.raise_()
            self.btn_blur.raise_()
            blur._opacity = 0.0
            blur.update()

        def tick():
            idx[0] += 1
            t = min(idx[0] / steps, 1.0)
            blur._opacity = start + (target - start) * t
            blur.update()
            if idx[0] >= steps:
                blur._opacity = target
                blur.update()
                if target == 0.0:
                    blur.hide()
                timer.stop()

        timer = QTimer(self)
        timer.setInterval(16)
        timer.timeout.connect(tick)
        timer.start()

        self.btn_blur.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {WHITE if visible else DIM};
                font-size: 12pt; border: none; border-radius: 12px;
            }}
            QPushButton:hover {{ background-color: {DIM}; }}
        """)

    def _on_server_info(self, data):
        sponsor = data.get("sponsor", data.get("name", "--"))
        self.lbl_server.setText(f"{sponsor}")

    def _on_retry(self):
        self.start_test()

    def start_test(self):
        if self.worker.isRunning():
            return

        self._upload_started = False
        self.btn_retry.setVisible(False)
        self.gauge_container.reset_all()

        self.lbl_dl.setText("Download:  -- Mbps")
        self.lbl_ul.setText("Upload:   -- Mbps")
        self.lbl_ping.setText("Ping: -- ms     Jitter: -- ms")

        c = self.gauge_container.circle
        c.state = "testing"
        c.progress = 0
        c._target = 0
        c._progress = 0
        c._dl_target = 0
        c._ul_target = 0
        c._dl_speed = 0
        c._ul_speed = 0
        c._phase = "ping"
        self.subtitle.setText("Testando ping...")

        self.worker.start()

    def _on_progress(self, phase, pct):
        circle = self.gauge_container.circle
        circle._phase = phase

        if phase == "download":
            self._upload_started = False
            circle.progress = pct
            self.subtitle.setText("Testando download...")
        elif phase == "upload":
            if not self._upload_started:
                self._upload_started = True
                self.gauge_container.slide_to_upload()
                self.gauge_container.upload.reset()
            self.gauge_container.upload.progress = pct
            self.subtitle.setText("Testando upload...")
        elif phase == "concluido":
            self.subtitle.setText("Teste concluido!")

    def _on_ping(self, v):
        self.gauge_container.circle.set_ping(v)
        self.lbl_ping.setText(f"Ping: {v:.0f} ms     Jitter: -- ms")

    def _on_download(self, v):
        self.gauge_container.circle.set_dl(v)
        self.gauge_container.circle.progress = min(v / 200.0 * 100, 100)
        self.lbl_dl.setText(f"Download:  {v:.1f} Mbps")

    def _on_upload(self, v):
        self.gauge_container.circle.set_ul(v)
        self.gauge_container.upload.set_speed(v)
        self.gauge_container.upload.progress = min(v / 100.0 * 100, 100)
        self.lbl_ul.setText(f"Upload:  {v:.1f} Mbps")

    def _on_jitter(self, v):
        circle = self.gauge_container.circle
        self.lbl_ping.setText(
            f"Ping: {circle._ping:.0f} ms     "
            f"Jitter: {v:.1f} ms"
        )

    def _on_error(self, msg):
        self.subtitle.setText(f"Erro: {msg}")
        self.gauge_container.circle.state = "idle"
        self.lbl_isp.setText(f"{msg}")

    def _on_finished(self):
        self.gauge_container.circle.state = "done"
        self.gauge_container.circle._target = 100
        self.gauge_container.circle._progress = 100
        self.btn_retry.setVisible(True)
        self.subtitle.setText("Teste concluido!")

        save_result(
            self.gauge_container.circle._ping,
            self.gauge_container.circle._jitter,
            self.gauge_container.circle._dl_speed,
            self.gauge_container.circle._ul_speed,
            self._isp_data,
        )

    def closeEvent(self, event):
        self.worker.cancel()
        self.worker.wait(2000)
        super().closeEvent(event)

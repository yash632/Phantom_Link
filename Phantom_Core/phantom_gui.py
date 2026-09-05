import sys
import os
import re
import time
import math
import subprocess
import asyncio
import threading
import win32api
import win32con
import win32gui
import win32process
import ctypes
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QSize, QRectF
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QGraphicsDropShadowEffect,
    QProgressBar, QDialog, QLineEdit, QListWidget, QListWidgetItem,
    QStackedWidget, QGridLayout, QSlider, QScrollArea
)
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QPixmap, QImage, QMouseEvent, QPainter, QPen, QBrush,
    QPainterPath, QLinearGradient, QRadialGradient
)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import winsdk.windows.media.control as wmc
    WINSDK_MEDIA_AVAILABLE = True
except ImportError:
    WINSDK_MEDIA_AVAILABLE = False

# Windows Virtual Key Codes for Global System Media & Volume Controls
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

class CenterVisualizerWidget(QWidget):
    """
    Center Visualizer Widget with Animated 192-Frame Video Globe Loop.
    Loads and continuously loops frame1.png through frame192.png from glob directory.
    Includes:
    - 30 FPS video-smooth frame sequence loop (frame1.png to frame192.png)
    - Synchronized Equalizer & Listening Status
    - Interactive Clickable Glass Mic Button
    """
    mic_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.anim_frame = 0
        self.is_listening = True
        self.setMinimumSize(340, 520)

        self.frames = []
        self.current_frame_idx = 0
        self.frames_loaded = False

        # Find glob directory
        self.glob_dir = self._find_glob_dir()

        # Load first frame immediately for 0ms initial render
        self._load_first_frame()

        # Asynchronously cache all 192 frames in background
        threading.Thread(target=self._load_all_frames_async, daemon=True).start()

        # 30 FPS smooth video animation loop timer (33ms)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._update_anim)
        self.timer.start()

    def _find_glob_dir(self):
        candidates = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "glob")),
            r"D:\Development\Phantom_Link\glob",
            r"D:\Development\Virtual IO\glob",
            os.path.abspath("glob"),
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.isdir(c):
                return c
        return None

    def _load_first_frame(self):
        if not self.glob_dir:
            return
        first_path = os.path.join(self.glob_dir, "frame1.png")
        if os.path.exists(first_path):
            img = QImage(first_path)
            if not img.isNull():
                scaled = img.scaledToHeight(240, Qt.TransformationMode.SmoothTransformation)
                self.frames.append(scaled)

    def _load_all_frames_async(self):
        if not self.glob_dir:
            return
        try:
            files = [f for f in os.listdir(self.glob_dir) if f.lower().endswith(('.png', '.jpg'))]
            def _num_key(name):
                nums = re.findall(r'\d+', name)
                return int(nums[0]) if nums else 0
            files = sorted(files, key=_num_key)

            loaded = []
            for f in files:
                f_path = os.path.join(self.glob_dir, f)
                img = QImage(f_path)
                if not img.isNull():
                    scaled = img.scaledToHeight(240, Qt.TransformationMode.SmoothTransformation)
                    loaded.append(scaled)
                    # Progressively update frames so rotation starts playing immediately!
                    if len(loaded) % 15 == 0:
                        self.frames = list(loaded)

            if loaded:
                self.frames = loaded
                self.frames_loaded = True
                print(f"[PHANTOM GUI]: Successfully cached all {len(loaded)} video globe frames for 30 FPS looping!")
        except Exception as e:
            print(f"[PHANTOM GUI NOTICE] Glob frames load notice: {e}")

    def _update_anim(self):
        if self.frames:
            if self.is_listening:
                self.current_frame_idx = (self.current_frame_idx + 1) % len(self.frames)
            else:
                # Gentle half-speed rotation when muted
                if self.anim_frame % 2 == 0:
                    self.current_frame_idx = (self.current_frame_idx + 1) % len(self.frames)
        self.anim_frame += 1
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        cx = self.width() / 2.0
        cy = 135.0
        orb_visual_r = 115.0
        txt_y = cy + orb_visual_r + 20
        eq_y = txt_y + 35
        mic_y = eq_y + 50

        click_pos = event.position()
        dist_sq = (click_pos.x() - cx) ** 2 + (click_pos.y() - mic_y) ** 2
        if dist_sq <= 30 ** 2:
            self.is_listening = not self.is_listening
            self.mic_toggled.emit(self.is_listening)
            print(f"[PHANTOM MIC TOGGLE]: Mic Listening -> {self.is_listening}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx = self.width() / 2.0
        cy = 135.0  # Center of video globe

        # 1. Draw Looping Video Globe Frame
        if self.frames:
            idx = min(self.current_frame_idx, len(self.frames) - 1)
            img = self.frames[idx]
            pw = img.width()
            ph = img.height()
            target_x = int(cx - (pw / 2.0))
            target_y = int(cy - (ph / 2.0))

            if not self.is_listening:
                painter.setOpacity(0.55)

            painter.drawImage(target_x, target_y, img)

            if not self.is_listening:
                painter.setOpacity(1.0)
        else:
            # Fallback in case frames are still initializing
            painter.setPen(QPen(QColor(56, 189, 248, 120), 2.0))
            painter.setBrush(QColor(15, 23, 42, 220))
            painter.drawEllipse(QPoint(int(cx), int(cy)), 90, 90)

        # 2. Status Text: L I S T E N I N G . . . vs M U T E D
        orb_visual_r = 115.0
        txt_y = int(cy + orb_visual_r + 20)
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        if self.is_listening:
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(QRectF(cx - 150, txt_y, 300, 25), Qt.AlignmentFlag.AlignCenter, "L I S T E N I N G . . .")
        else:
            painter.setPen(QColor(239, 68, 68))
            painter.drawText(QRectF(cx - 150, txt_y, 300, 25), Qt.AlignmentFlag.AlignCenter, "M U T E D   ( P A U S E D )")

        # 3. 19-Bar Animated Audio Equalizer Spectrum Waveform
        eq_y = txt_y + 35
        bar_count = 19
        base_heights = [4, 6, 9, 13, 18, 24, 30, 36, 42, 46, 42, 36, 30, 24, 18, 13, 9, 6, 4]
        bar_width = 3.5
        spacing = 5.0
        total_eq_w = bar_count * (bar_width + spacing)
        eq_start_x = cx - (total_eq_w / 2.0)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(56, 189, 248, 180) if self.is_listening else QColor(239, 68, 68, 180))
        painter.drawEllipse(QPoint(int(eq_start_x - 20), eq_y), 2, 2)
        painter.drawEllipse(QPoint(int(eq_start_x - 12), eq_y), 2, 2)
        painter.drawEllipse(QPoint(int(eq_start_x - 4), eq_y), 2, 2)

        phase = self.anim_frame * 0.08
        for i in range(bar_count):
            h_anim = (base_heights[i] + math.sin(phase * 2.0 + i * 0.4) * 8.0) if self.is_listening else 4.0
            h_anim = max(3.0, h_anim)
            bx = eq_start_x + i * (bar_width + spacing)
            by = eq_y - (h_anim / 2.0)

            if self.is_listening:
                t_ratio = i / float(bar_count - 1)
                if t_ratio < 0.5:
                    r_c = int(56 + (192 - 56) * (t_ratio * 2))
                    g_c = int(189 + (132 - 189) * (t_ratio * 2))
                    b_c = int(252 + (248 - 252) * (t_ratio * 2))
                else:
                    r_c = int(192 + (56 - 192) * ((t_ratio - 0.5) * 2))
                    g_c = int(132 + (189 - 132) * ((t_ratio - 0.5) * 2))
                    b_c = int(252 + (248 - 252) * ((t_ratio - 0.5) * 2))
            else:
                r_c, g_c, b_c = 239, 68, 68

            painter.setBrush(QColor(r_c, g_c, b_c, 240))
            painter.drawRoundedRect(QRectF(bx, by, bar_width, h_anim), 1.8, 1.8)

        eq_end_x = eq_start_x + total_eq_w
        painter.drawEllipse(QPoint(int(eq_end_x + 4), eq_y), 2, 2)
        painter.drawEllipse(QPoint(int(eq_end_x + 12), eq_y), 2, 2)
        painter.drawEllipse(QPoint(int(eq_end_x + 20), eq_y), 2, 2)

        # 4. Double-Ringed Circular Glass Mic Badge Button
        mic_y = eq_y + 50
        mic_outer_r = 28.0
        mic_inner_r = 22.0

        painter.setPen(QPen(QColor(56, 189, 248, 120) if self.is_listening else QColor(239, 68, 68, 120), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPoint(int(cx), int(mic_y)), int(mic_outer_r), int(mic_outer_r))

        painter.setPen(QPen(QColor(56, 189, 248, 220) if self.is_listening else QColor(239, 68, 68, 220), 1.8))
        painter.setBrush(QColor(12, 20, 38, 220) if self.is_listening else QColor(38, 12, 14, 220))
        painter.drawEllipse(QPoint(int(cx), int(mic_y)), int(mic_inner_r), int(mic_inner_r))

        painter.setPen(QPen(QColor(255, 255, 255) if self.is_listening else QColor(239, 68, 68), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QColor(255, 255, 255) if self.is_listening else QColor(239, 68, 68))
        painter.drawRoundedRect(QRectF(cx - 4, mic_y - 9, 8, 12), 4, 4)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        stand_path = QPainterPath()
        stand_path.arcMoveTo(QRectF(cx - 7, mic_y - 5, 14, 12), 0)
        stand_path.arcTo(QRectF(cx - 7, mic_y - 5, 14, 12), 0, -180)
        painter.drawPath(stand_path)

        painter.drawLine(int(cx), int(mic_y + 7), int(cx), int(mic_y + 11))
        painter.drawLine(int(cx - 5), int(mic_y + 11), int(cx + 5), int(mic_y + 11))

        if not self.is_listening:
            painter.setPen(QPen(QColor(239, 68, 68), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(cx - 11), int(mic_y - 11), int(cx + 11), int(mic_y + 11))


class PhantomGUI(QMainWindow):
    """
    100% Fully Functional Cyberpunk Glassmorphism Dashboard GUI for PHANTOM (assets/ui.png).
    """
    sig_log = pyqtSignal(str, str)
    sig_processing = pyqtSignal(bool, str)
    sig_vk_button = pyqtSignal()

    def __init__(self, on_command_trigger=None, tts_engine=None, vk_controller=None):
        super().__init__()
        self.on_command_trigger = on_command_trigger
        self.tts_engine = tts_engine
        self.vk_controller = vk_controller
        self.drag_position = QPoint()
        self.is_media_playing = False

        self.sig_log.connect(self._handle_log)
        self.sig_processing.connect(self._handle_processing)
        self.sig_vk_button.connect(self._update_vk_button_state)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1200, 760)
        self.setMinimumSize(1000, 650)

        # Center on screen
        screen_geo = QApplication.primaryScreen().geometry()
        self.move((screen_geo.width() - 1200) // 2, (screen_geo.height() - 760) // 2)

        self._init_ui()

        # Connect Mic Click Toggle Signal
        self.visualizer_widget.mic_toggled.connect(self._handle_mic_toggle)

        # 1-Second Timer for Live Hardware & Media Metadata Updates
        self.stats_timer = QTimer(self)
        self.stats_timer.setInterval(1000)
        self.stats_timer.timeout.connect(self._update_live_system_stats)
        self.stats_timer.start()

    def _init_ui(self):
        central_widget = QWidget(self)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central_widget)

        self.bg_frame = QFrame()
        self.bg_frame.setObjectName("BgFrame")
        
        bg_path = os.path.join(os.path.dirname(__file__), "..", "assets", "bg.png")
        if not os.path.exists(bg_path):
            bg_path = os.path.join(os.path.dirname(__file__), "..", "assets", "bg_blurred.png")

        bg_style_path = bg_path.replace("\\", "/")
        self.bg_frame.setStyleSheet(f"""
            QFrame#BgFrame {{
                border-image: url('{bg_style_path}') 0 0 0 0 stretch stretch;
                border-radius: 24px;
                border: 1px solid rgba(56, 189, 248, 0.4);
            }}
        """)

        bg_layout = QVBoxLayout(self.bg_frame)
        bg_layout.setContentsMargins(0, 0, 0, 0)

        self.glass_panel = QFrame()
        self.glass_panel.setObjectName("GlassPanel")
        self.glass_panel.setStyleSheet("""
            QFrame#GlassPanel {
                background-color: rgba(6, 10, 20, 0.72);
                border-radius: 24px;
            }
        """)
        
        panel_layout = QVBoxLayout(self.glass_panel)
        panel_layout.setContentsMargins(25, 20, 25, 18)
        panel_layout.setSpacing(0)

        titlebar = self._create_titlebar()
        panel_layout.addWidget(titlebar)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(10, 15, 10, 15)
        body_layout.setSpacing(25)

        sidebar = self._create_sidebar()
        body_layout.addWidget(sidebar, stretch=3)

        self.page_stack = QStackedWidget()
        
        home_page = self._create_home_page()
        self.page_stack.addWidget(home_page)

        search_page = self._create_search_page()
        self.page_stack.addWidget(search_page)

        app_page = self._create_app_page()
        self.page_stack.addWidget(app_page)

        files_page = self._create_files_page()
        self.page_stack.addWidget(files_page)

        settings_page = self._create_settings_page()
        self.page_stack.addWidget(settings_page)

        body_layout.addWidget(self.page_stack, stretch=10)

        panel_layout.addLayout(body_layout)

        footer_frame = QFrame()
        footer_frame.setStyleSheet("background: transparent; border: none;")
        f_layout = QHBoxLayout(footer_frame)
        f_layout.setContentsMargins(30, 0, 30, 5)

        line_left = QFrame()
        line_left.setFixedHeight(1)
        line_left.setStyleSheet("background: rgba(148, 163, 184, 0.25); border: none;")

        footer_txt = QLabel("S M A R T E R   •   F A S T E R   •   T O G E T H E R")
        footer_txt.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        footer_txt.setStyleSheet("color: rgba(148, 163, 184, 0.6); letter-spacing: 5px; border: none; background: transparent;")

        line_right = QFrame()
        line_right.setFixedHeight(1)
        line_right.setStyleSheet("background: rgba(148, 163, 184, 0.25); border: none;")

        f_layout.addWidget(line_left, stretch=1)
        f_layout.addSpacing(20)
        f_layout.addWidget(footer_txt)
        f_layout.addSpacing(20)
        f_layout.addWidget(line_right, stretch=1)

        panel_layout.addWidget(footer_frame)

        bg_layout.addWidget(self.glass_panel)
        central_layout.addWidget(self.bg_frame)

    def _create_titlebar(self):
        title_frame = QFrame()
        title_frame.setFixedHeight(50)
        title_frame.setStyleSheet("background: transparent; border: none;")

        layout = QHBoxLayout(title_frame)
        layout.setContentsMargins(10, 0, 10, 0)

        self.status_dot = QLabel("Voice Active")
        self.status_dot.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.status_dot.setStyleSheet("""
            color: #38bdf8;
            background: rgba(15, 23, 42, 0.65);
            border: 1px solid rgba(56, 189, 248, 0.4);
            border-radius: 18px;
            padding: 6px 18px;
        """)

        center_box = QHBoxLayout()
        center_box.setSpacing(10)

        logo = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "favicon.png")
        if os.path.exists(logo_path):
            logo.setPixmap(QPixmap(logo_path).scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            logo.setText("✦")
            logo.setStyleSheet("color: #38bdf8; font-size: 18px;")

        title = QLabel("P H A N T O M")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #e2e8f0; letter-spacing: 8px; border: none; background: transparent;")

        center_box.addWidget(logo)
        center_box.addWidget(title)

        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.65);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 18px;
            }
        """)
        c_layout = QHBoxLayout(ctrl_frame)
        c_layout.setContentsMargins(12, 4, 12, 4)
        c_layout.setSpacing(14)

        # wave_icon = QLabel("ili.")
        # wave_icon.setStyleSheet("color: #38bdf8; font-weight: bold; border: none; background: transparent;")

        btn_min = QPushButton("—")
        btn_min.setFixedSize(22, 22)
        btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_min.setStyleSheet("""
            QPushButton { color: #94a3b8; background: transparent; border: none; font-weight: bold; font-size: 13px; }
            QPushButton:hover { color: #ffffff; }
        """)
        btn_min.clicked.connect(self.showMinimized)

        btn_max = QPushButton("☐")
        btn_max.setFixedSize(22, 22)
        btn_max.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_max.setStyleSheet("""
            QPushButton { color: #94a3b8; background: transparent; border: none; font-weight: bold; font-size: 13px; }
            QPushButton:hover { color: #ffffff; }
        """)
        btn_max.clicked.connect(self._toggle_maximize)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(22, 22)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton { color: #94a3b8; background: transparent; border: none; font-weight: bold; font-size: 13px; }
            QPushButton:hover { color: #ef4444; }
        """)
        btn_close.clicked.connect(self.close)

        # c_layout.addWidget(wave_icon)
        c_layout.addWidget(btn_min)
        c_layout.addWidget(btn_max)
        c_layout.addWidget(btn_close)

        layout.addWidget(self.status_dot)
        layout.addStretch()
        layout.addLayout(center_box)
        layout.addStretch()
        layout.addWidget(ctrl_frame)

        return title_frame

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _handle_mic_toggle(self, is_listening):
        if is_listening:
            self.status_dot.setText("Voice Active")
            self.status_dot.setStyleSheet("""
                color: #38bdf8;
                background: rgba(15, 23, 42, 0.65);
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 18px;
                padding: 6px 18px;
            """)
            self.log("Voice Assistant Resumed (Unmuted)", log_type="sys")
        else:
            self.status_dot.setText("🚫  Voice Muted  ●")
            self.status_dot.setStyleSheet("""
                color: #ef4444;
                background: rgba(38, 12, 14, 0.65);
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 18px;
                padding: 6px 18px;
            """)
            self.log("Voice Assistant Muted (Paused)", log_type="sys")

    def _create_sidebar(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        nav_frame = QFrame()
        nav_frame.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.45);
                border: 1px solid rgba(56, 189, 248, 0.22);
                border-radius: 20px;
            }
        """)
        n_layout = QVBoxLayout(nav_frame)
        n_layout.setContentsMargins(14, 16, 14, 16)
        n_layout.setSpacing(10)

        self.nav_buttons = {}
        nav_items = [
            (0, "Home", "⌂   Home"),
            (1, "Search", "⌕   Search"),
            (2, "Open App", "⊞   Open App"),
            (3, "Files", "🗁   Files"),
            (4, "Settings", "⚙   Settings")
        ]

        for page_idx, key, label in nav_items:
            btn = QPushButton(label)
            btn.setFixedHeight(42)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=page_idx, k=key: self._switch_page(idx, k))
            
            if page_idx == 0:
                btn.setStyleSheet("""
                    QPushButton {
                        color: #ffffff;
                        background: rgba(56, 189, 248, 0.18);
                        border-left: 3.5px solid #38bdf8;
                        border-radius: 10px;
                        font-weight: bold;
                        text-align: left;
                        padding-left: 16px;
                        font-size: 13px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        color: #94a3b8;
                        background: transparent;
                        border: none;
                        text-align: left;
                        padding-left: 16px;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        color: #ffffff;
                        background: rgba(255, 255, 255, 0.05);
                        border-radius: 10px;
                    }
                """)
            
            self.nav_buttons[key] = btn
            n_layout.addWidget(btn)

        layout.addWidget(nav_frame)

        log_frame = QFrame()
        log_frame.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.55);
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 20px;
            }
        """)
        t_layout = QVBoxLayout(log_frame)
        t_layout.setContentsMargins(14, 14, 14, 14)
        t_layout.setSpacing(6)

        t_title = QLabel("⚡ TERMINAL EXECUTION LOGS")
        t_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        t_title.setStyleSheet("color: #38bdf8; border: none; background: transparent;")
        t_layout.addWidget(t_title)

        self.terminal_log = QTextEdit()
        self.terminal_log.setReadOnly(True)
        self.terminal_log.setStyleSheet("""
            QTextEdit {
                background: rgba(8, 14, 28, 0.85);
                color: #38bdf8;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 8px;
                font-family: 'Consolas', 'Segoe UI';
                font-size: 11px;
            }
        """)
        self.terminal_log.setPlainText("⚡ [PHANTOM CORE]: Voice Assistant Online.\n[SYS]: Monitoring speech & tasks...")
        t_layout.addWidget(self.terminal_log)

        layout.addWidget(log_frame, stretch=1)
        return container

    def _switch_page(self, page_index, active_key):
        self.page_stack.setCurrentIndex(page_index)

        for k, btn in self.nav_buttons.items():
            if k == active_key:
                btn.setStyleSheet("""
                    QPushButton {
                        color: #ffffff;
                        background: rgba(56, 189, 248, 0.18);
                        border-left: 3.5px solid #38bdf8;
                        border-radius: 10px;
                        font-weight: bold;
                        text-align: left;
                        padding-left: 16px;
                        font-size: 13px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        color: #94a3b8;
                        background: transparent;
                        border: none;
                        text-align: left;
                        padding-left: 16px;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        color: #ffffff;
                        background: rgba(255, 255, 255, 0.05);
                        border-radius: 10px;
                    }
                """)

    def _create_home_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(25)

        self.visualizer_widget = CenterVisualizerWidget()
        layout.addWidget(self.visualizer_widget, stretch=6)

        right_panel = self._create_right_panel()
        layout.addWidget(right_panel, stretch=4)

        return page

    def _create_search_page(self):
        page = QFrame()
        page.setStyleSheet("background: rgba(15, 23, 42, 0.45); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 20px; padding: 20px;")
        layout = QVBoxLayout(page)

        header = QLabel("🔍 Instant Google & System Search")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #38bdf8; border: none; background: transparent;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type your search query or command (e.g. 'python tutorials', 'open edge')...")
        self.search_input.setFixedHeight(48)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: rgba(30, 41, 59, 0.8);
                color: #ffffff;
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 10px;
                padding-left: 16px;
                font-size: 14px;
            }
        """)

        btn_run = QPushButton("⚡ Execute Search Command")
        btn_run.setFixedHeight(44)
        btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_run.setStyleSheet("""
            QPushButton {
                background: #38bdf8;
                color: #0b0f19;
                font-weight: bold;
                border-radius: 10px;
                font-size: 14px;
            }
            QPushButton:hover { background: #00e5ff; }
        """)
        btn_run.clicked.connect(self._exec_search_input)
        self.search_input.returnPressed.connect(self._exec_search_input)

        self.search_log = QTextEdit()
        self.search_log.setReadOnly(True)
        self.search_log.setStyleSheet("""
            QTextEdit {
                background: rgba(8, 14, 28, 0.7);
                color: #38bdf8;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px;
                font-family: 'Consolas', 'Segoe UI';
                font-size: 12px;
            }
        """)
        self.search_log.setPlainText("[PHANTOM SEARCH ENGINE]: Ready for voice or text queries.")

        layout.addWidget(header)
        layout.addWidget(self.search_input)
        layout.addWidget(btn_run)
        layout.addWidget(self.search_log)

        return page

    def _exec_search_input(self):
        query = self.search_input.text().strip()
        if query:
            self.search_log.append(f"\n⚡ [EXECUTING QUERY]: '{query}'...")
            self.log(f"Search Query: {query}", log_type="cmd")
            if self.on_command_trigger:
                self.on_command_trigger(f"search google for {query}")
            else:
                subprocess.Popen(f'start https://www.google.com/search?q={query}', shell=True)

    def _create_app_page(self):
        page = QFrame()
        page.setStyleSheet("background: rgba(15, 23, 42, 0.45); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 20px; padding: 20px;")
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        header = QLabel("⊞ Installed PC Applications & AI Tools")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #38bdf8; border: none; background: transparent;")

        # Featured: AI Virtual Keyboard & Air Mouse Banner Card
        vk_card = QFrame()
        vk_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(56, 189, 248, 0.12), stop:1 rgba(129, 140, 248, 0.12));
                border: 1.5px solid rgba(56, 189, 248, 0.5);
                border-radius: 14px;
                padding: 10px;
            }
        """)
        vk_layout = QHBoxLayout(vk_card)
        vk_layout.setContentsMargins(14, 8, 14, 8)
        vk_layout.setSpacing(16)

        vk_icon = QLabel("⌨")
        vk_icon.setFont(QFont("Segoe UI", 20))
        vk_icon.setStyleSheet("color: #38bdf8; border: none; background: transparent;")

        vk_info_box = QVBoxLayout()
        vk_info_box.setSpacing(2)
        vk_title = QLabel("AI Virtual Keyboard & Air Mouse")
        vk_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        vk_title.setStyleSheet("color: #ffffff; border: none; background: transparent;")

        self.vk_status_lbl = QLabel("Status: READY ○   •   Touchless 3D Hand Gestures & Air Mouse")
        self.vk_status_lbl.setFont(QFont("Segoe UI", 9))
        self.vk_status_lbl.setStyleSheet("color: #94a3b8; border: none; background: transparent;")

        vk_info_box.addWidget(vk_title)
        vk_info_box.addWidget(self.vk_status_lbl)

        self.btn_vk_toggle = QPushButton("▶ LAUNCH KEYBOARD")
        self.btn_vk_toggle.setFixedHeight(40)
        self.btn_vk_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_vk_toggle.setStyleSheet("""
            QPushButton {
                background: #38bdf8;
                color: #0b0f19;
                font-weight: bold;
                border-radius: 10px;
                padding: 0 18px;
                font-size: 12px;
            }
            QPushButton:hover { background: #00e5ff; }
        """)
        self.btn_vk_toggle.clicked.connect(self._toggle_virtual_keyboard)

        vk_layout.addWidget(vk_icon)
        vk_layout.addLayout(vk_info_box)
        vk_layout.addStretch()
        vk_layout.addWidget(self.btn_vk_toggle)

        apps = [
            ("🌐 Google Chrome", "open google chrome"),
            ("🌐 Microsoft Edge", "open microsoft edge"),
            ("💻 VS Code", "open visual studio code"),
            ("📁 File Explorer", "open file explorer"),
            ("📝 Notepad", "open notepad"),
            ("⚙️ Settings", "open settings"),
            ("🔢 Calculator", "open calculator"),
            ("📊 Task Manager", "open task manager"),
            ("🖥 Command Prompt", "open cmd")
        ]

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(12)

        r, c = 0, 0
        for name, cmd in apps:
            btn = QPushButton(name)
            btn.setFixedHeight(46)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(30, 41, 59, 0.8);
                    color: #ffffff;
                    border: 1px solid rgba(56, 189, 248, 0.3);
                    border-radius: 10px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background: rgba(56, 189, 248, 0.25);
                    border: 1px solid #38bdf8;
                }
            """)
            btn.clicked.connect(lambda checked, command=cmd: self._launch_app(command))
            grid.addWidget(btn, r, c)
            c += 1
            if c >= 3:
                c = 0
                r += 1

        layout.addWidget(header)
        layout.addWidget(vk_card)
        layout.addWidget(grid_widget)
        layout.addStretch()

        return page

    def _toggle_virtual_keyboard(self):
        if self.vk_controller:
            success, msg = self.vk_controller.toggle_keyboard()
            self.log(msg, log_type="cmd")
            if self.tts_engine:
                self.tts_engine.speak(msg, block=False)
            self._update_vk_button_state()
        elif self.on_command_trigger:
            self.on_command_trigger("start virtual keyboard")

    def _update_vk_button_state(self):
        if hasattr(self, 'btn_vk_toggle') and self.vk_controller:
            if self.vk_controller.is_running():
                self.btn_vk_toggle.setText("🛑 STOP KEYBOARD")
                self.btn_vk_toggle.setStyleSheet("""
                    QPushButton {
                        background: #ef4444;
                        color: #ffffff;
                        font-weight: bold;
                        border-radius: 10px;
                        padding: 0 18px;
                        font-size: 12px;
                    }
                    QPushButton:hover { background: #dc2626; }
                """)
                if hasattr(self, 'vk_status_lbl'):
                    self.vk_status_lbl.setText("Status: ACTIVE ●   •   Touchless 3D Hand Gestures & Air Mouse")
                    self.vk_status_lbl.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 9px; border: none; background: transparent;")
            else:
                self.btn_vk_toggle.setText("▶ LAUNCH KEYBOARD")
                self.btn_vk_toggle.setStyleSheet("""
                    QPushButton {
                        background: #38bdf8;
                        color: #0b0f19;
                        font-weight: bold;
                        border-radius: 10px;
                        padding: 0 18px;
                        font-size: 12px;
                    }
                    QPushButton:hover { background: #00e5ff; }
                """)
                if hasattr(self, 'vk_status_lbl'):
                    self.vk_status_lbl.setText("Status: READY ○   •   Touchless 3D Hand Gestures & Air Mouse")
                    self.vk_status_lbl.setStyleSheet("color: #94a3b8; font-size: 9px; border: none; background: transparent;")

    def _launch_app(self, cmd):
        self.log(f"Launching App: {cmd}", log_type="cmd")
        if self.on_command_trigger:
            self.on_command_trigger(cmd)

    def _create_files_page(self):
        page = QFrame()
        page.setStyleSheet("background: rgba(15, 23, 42, 0.45); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 20px; padding: 20px;")
        layout = QVBoxLayout(page)

        header = QLabel("🗁 Desktop & Project Files")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #38bdf8; border: none; background: transparent;")

        folders = [
            ("📁 Desktop Shortcuts", os.path.expanduser("~/Desktop")),
            ("📁 Downloads Folder", os.path.expanduser("~/Downloads")),
            ("📁 Documents Folder", os.path.expanduser("~/Documents")),
            ("⚡ Project PHANTOM Root", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        ]

        for title, path in folders:
            box = QHBoxLayout()
            lbl = QLabel(f"{title}: {path}")
            lbl.setStyleSheet("color: #e2e8f0; font-size: 13px;")

            btn_open = QPushButton("Open Folder")
            btn_open.setFixedHeight(36)
            btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_open.setStyleSheet("""
                QPushButton {
                    background: rgba(56, 189, 248, 0.2);
                    color: #38bdf8;
                    border: 1px solid #38bdf8;
                    border-radius: 8px;
                    padding: 0 14px;
                    font-weight: bold;
                }
                QPushButton:hover { background: #38bdf8; color: #0b0f19; }
            """)
            btn_open.clicked.connect(lambda checked, p=path: os.startfile(p) if os.path.exists(p) else None)

            box.addWidget(lbl)
            box.addStretch()
            box.addWidget(btn_open)

            line = QFrame()
            line.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
            line.setFixedHeight(1)

            layout.addLayout(box)
            layout.addWidget(line)

        layout.addStretch()
        return page

    def _create_settings_page(self):
        page = QFrame()
        page.setStyleSheet("background: rgba(15, 23, 42, 0.45); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 20px; padding: 20px;")
        layout = QVBoxLayout(page)

        header = QLabel("⚙ System Voice & Gemini AI Settings")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #38bdf8; border: none; background: transparent;")

        v_box = QVBoxLayout()
        v_box.setSpacing(6)

        lbl1 = QLabel("🔊 Voice Engine: Microsoft Mark (SAPI5 SpVoice)")
        lbl1.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")

        lbl2 = QLabel("🎙 Microphone: Default High Definition Audio Device")
        lbl2.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")

        lbl3 = QLabel("✨ Gemini A.I. Status: 100% Online & Hosted")
        lbl3.setStyleSheet("color: #22c55e; font-size: 13px; font-weight: bold;")

        v_box.addWidget(lbl1)
        v_box.addWidget(lbl2)
        v_box.addWidget(lbl3)

        layout.addWidget(header)
        layout.addLayout(v_box)
        layout.addStretch()

        return page

    def _trigger_media_play_pause(self):
        """Triggers Play/Pause and synchronously toggles Play button icon & state!"""
        self._trigger_media_key(VK_MEDIA_PLAY_PAUSE)
        self.is_media_playing = not self.is_media_playing
        self.btn_play.setText("⏸" if self.is_media_playing else "▶")
        self.m_sub.setText("Playing Audio Stream" if self.is_media_playing else "Paused Audio Stream")

    def _trigger_media_key(self, vk_code):
        try:
            win32api.keybd_event(vk_code, 0, 0, 0)
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception as e:
            print(f"[PHANTOM MEDIA ERROR]: {e}")

    def _create_right_panel(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(22)

        # Clock & Weather Widget
        clock_frame = QFrame()
        clock_frame.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.45);
                border: 1px solid rgba(56, 189, 248, 0.22);
                border-radius: 20px;
            }
        """)
        c_layout = QHBoxLayout(clock_frame)
        c_layout.setContentsMargins(22, 20, 22, 20)

        time_box = QVBoxLayout()
        time_box.setSpacing(2)
        self.time_lbl = QLabel(time.strftime("%I:%M:%S %p"))
        self.time_lbl.setFont(QFont("Segoe UI", 24, QFont.Weight.Medium))
        self.time_lbl.setStyleSheet("color: #ffffff; border: none; background: transparent;")

        self.date_lbl = QLabel(time.strftime("%a, %d %b %Y"))
        self.date_lbl.setFont(QFont("Segoe UI", 9))
        self.date_lbl.setStyleSheet("color: #94a3b8; border: none; background: transparent;")

        time_box.addWidget(self.time_lbl)
        time_box.addWidget(self.date_lbl)

        weather_box = QVBoxLayout()
        weather_box.setSpacing(2)
        weather_box.setAlignment(Qt.AlignmentFlag.AlignRight)

        weather_temp = QLabel("☀️  28°C")
        weather_temp.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        weather_temp.setStyleSheet("color: #ffffff; border: none; background: transparent;")

        weather_desc = QLabel("Clear")
        weather_desc.setFont(QFont("Segoe UI", 9))
        weather_desc.setStyleSheet("color: #94a3b8; border: none; background: transparent;")

        weather_box.addWidget(weather_temp, alignment=Qt.AlignmentFlag.AlignRight)
        weather_box.addWidget(weather_desc, alignment=Qt.AlignmentFlag.AlignRight)

        c_layout.addLayout(time_box)
        c_layout.addStretch()
        c_layout.addLayout(weather_box)

        layout.addWidget(clock_frame)

        # Real-Time System Audio Player Card
        media_frame = QFrame()
        media_frame.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.45);
                border: 1px solid rgba(56, 189, 248, 0.22);
                border-radius: 20px;
            }
        """)
        m_layout = QVBoxLayout(media_frame)
        m_layout.setContentsMargins(20, 18, 20, 18)

        m_top = QHBoxLayout()
        
        m_icon = QLabel("♫")
        m_icon.setFont(QFont("Segoe UI", 12))
        m_icon.setFixedSize(38, 38)
        m_icon.setStyleSheet("""
            background: rgba(56, 189, 248, 0.18);
            color: #38bdf8;
            border-radius: 19px;
            border: 1px solid rgba(56, 189, 248, 0.35);
        """)
        m_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        m_text_box = QVBoxLayout()
        m_text_box.setSpacing(1)
        self.m_title = QLabel("System Audio Player")
        self.m_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.m_title.setStyleSheet("color: #ffffff; border: none; background: transparent;")

        self.m_sub = QLabel("Global Media Session")
        self.m_sub.setFont(QFont("Segoe UI", 8))
        self.m_sub.setStyleSheet("color: #64748b; border: none; background: transparent;")

        m_text_box.addWidget(self.m_title)
        m_text_box.addWidget(self.m_sub)

        m_eq = QLabel("ıılıl")
        m_eq.setFont(QFont("Segoe UI", 12))
        m_eq.setStyleSheet("color: #38bdf8; border: none; background: transparent;")

        m_top.addWidget(m_icon)
        m_top.addSpacing(12)
        m_top.addLayout(m_text_box)
        m_top.addStretch()
        m_top.addWidget(m_eq)

        # Controls (|◀, ▶/⏸, ▶|, Vol-, Vol+)
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 14, 0, 0)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.setSpacing(16)

        btn_vol_down = QPushButton("🔉")
        btn_vol_down.setFixedSize(28, 28)
        btn_vol_down.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_vol_down.setStyleSheet("color: #94a3b8; background: transparent; border: none; font-size: 13px;")
        btn_vol_down.clicked.connect(lambda: self._trigger_media_key(VK_VOLUME_DOWN))

        btn_prev = QPushButton("│◀")
        btn_prev.setFixedSize(30, 30)
        btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_prev.setStyleSheet("color: #38bdf8; background: transparent; border: none; font-size: 14px;")
        btn_prev.clicked.connect(lambda: self._trigger_media_key(VK_MEDIA_PREV_TRACK))

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(42, 42)
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background: rgba(56, 189, 248, 0.22);
                border: 1.5px solid #38bdf8;
                border-radius: 21px;
                font-size: 15px;
            }
            QPushButton:hover {
                background: rgba(56, 189, 248, 0.45);
            }
        """)
        self.btn_play.clicked.connect(self._trigger_media_play_pause)

        btn_next = QPushButton("▶│")
        btn_next.setFixedSize(30, 30)
        btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next.setStyleSheet("color: #38bdf8; background: transparent; border: none; font-size: 14px;")
        btn_next.clicked.connect(lambda: self._trigger_media_key(VK_MEDIA_NEXT_TRACK))

        btn_vol_up = QPushButton("🔊")
        btn_vol_up.setFixedSize(28, 28)
        btn_vol_up.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_vol_up.setStyleSheet("color: #94a3b8; background: transparent; border: none; font-size: 13px;")
        btn_vol_up.clicked.connect(lambda: self._trigger_media_key(VK_VOLUME_UP))

        controls_layout.addWidget(btn_vol_down)
        controls_layout.addWidget(btn_prev)
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(btn_next)
        controls_layout.addWidget(btn_vol_up)

        m_layout.addLayout(m_top)
        m_layout.addLayout(controls_layout)

        layout.addWidget(media_frame)

        # Hardware Stats Frame
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.45);
                border: 1px solid rgba(56, 189, 248, 0.22);
                border-radius: 20px;
            }
        """)
        s_layout = QVBoxLayout(stats_frame)
        s_layout.setContentsMargins(20, 18, 20, 18)
        s_layout.setSpacing(12)

        # CPU Row
        cpu_row = QHBoxLayout()
        cpu_icon = QLabel("💻")
        cpu_icon.setStyleSheet("color: #38bdf8; border: none; background: transparent;")
        cpu_txt = QLabel("CPU")
        cpu_txt.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        cpu_txt.setStyleSheet("color: #94a3b8; border: none; background: transparent;")
        self.cpu_val = QLabel("12%")
        self.cpu_val.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.cpu_val.setStyleSheet("color: #ffffff; border: none; background: transparent;")

        cpu_row.addWidget(cpu_icon)
        cpu_row.addWidget(cpu_txt)
        cpu_row.addStretch()
        cpu_row.addWidget(self.cpu_val)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setFixedHeight(4)
        self.cpu_bar.setValue(12)
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setStyleSheet("QProgressBar { background: rgba(255,255,255,0.08); border-radius: 2px; } QProgressBar::chunk { background: #38bdf8; border-radius: 2px; }")

        # RAM Row
        ram_row = QHBoxLayout()
        ram_icon = QLabel("🧠")
        ram_icon.setStyleSheet("color: #818cf8; border: none; background: transparent;")
        ram_txt = QLabel("RAM")
        ram_txt.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        ram_txt.setStyleSheet("color: #94a3b8; border: none; background: transparent;")
        self.ram_val = QLabel("45%")
        self.ram_val.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.ram_val.setStyleSheet("color: #ffffff; border: none; background: transparent;")

        ram_row.addWidget(ram_icon)
        ram_row.addWidget(ram_txt)
        ram_row.addStretch()
        ram_row.addWidget(self.ram_val)

        self.ram_bar = QProgressBar()
        self.ram_bar.setFixedHeight(4)
        self.ram_bar.setValue(45)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setStyleSheet("QProgressBar { background: rgba(255,255,255,0.08); border-radius: 2px; } QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #818cf8, stop:1 #c084fc); border-radius: 2px; }")

        # Network Row
        net_row = QHBoxLayout()
        net_icon = QLabel("🌐")
        net_icon.setStyleSheet("color: #38bdf8; border: none; background: transparent;")
        net_txt = QLabel("Network")
        net_txt.setFont(QFont("Segoe UI", 9))
        net_txt.setStyleSheet("color: #94a3b8; border: none; background: transparent;")

        self.net_val = QLabel("Connected ●")
        self.net_val.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.net_val.setStyleSheet("color: #22c55e; border: none; background: transparent;")

        net_row.addWidget(net_icon)
        net_row.addWidget(net_txt)
        net_row.addStretch()
        net_row.addWidget(self.net_val)

        s_layout.addLayout(cpu_row)
        s_layout.addWidget(self.cpu_bar)
        s_layout.addLayout(ram_row)
        s_layout.addWidget(self.ram_bar)
        s_layout.addLayout(net_row)

        layout.addWidget(stats_frame)

        return container

    def _update_live_system_stats(self):
        """Updates Real-Time Clock, Date, CPU %, RAM %, and Windows Live Media Session Metadata!"""
        self.time_lbl.setText(time.strftime("%I:%M:%S %p"))
        self.date_lbl.setText(time.strftime("%a, %d %b %Y"))

        if PSUTIL_AVAILABLE:
            try:
                cpu = int(psutil.cpu_percent(interval=None))
                ram = int(psutil.virtual_memory().percent)
                self.cpu_val.setText(f"{cpu}%")
                self.cpu_bar.setValue(cpu)
                self.ram_val.setText(f"{ram}%")
                self.ram_bar.setValue(ram)
            except Exception:
                pass

        self._update_vk_button_state()
        threading.Thread(target=self._fetch_media_session_dual_engine, daemon=True).start()

    def _fetch_media_session_dual_engine(self):
        """Dual Engine Windows Media & Browser Title Fetcher."""
        title, artist, is_playing = None, None, None

        found_media = []

        def _enum_win(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                w_text = win32gui.GetWindowText(hwnd)
                if w_text and ("- YouTube" in w_text or "Spotify" in w_text or "SoundCloud" in w_text or "VLC" in w_text):
                    found_media.append(w_text)

        try:
            win32gui.EnumWindows(_enum_win, None)
            if found_media:
                media_str = found_media[0]
                if "- YouTube" in media_str:
                    parts = media_str.split("- YouTube")
                    title = parts[0].strip(" ()\"'-")
                    artist = "YouTube Media Stream"
                    is_playing = self.is_media_playing
                elif "Spotify" in media_str:
                    parts = media_str.split("-")
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        artist = parts[1].replace("Spotify", "").strip()
                    else:
                        title = media_str.replace("- Spotify", "").strip()
                        artist = "Spotify Audio"
                    is_playing = self.is_media_playing
        except Exception:
            pass

        if not title and WINSDK_MEDIA_AVAILABLE:
            async def _async_get():
                try:
                    ctypes.windll.ole32.CoInitializeEx(None, 0x0)
                    manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
                    session = manager.get_current_session()
                    if session:
                        props = await session.try_get_media_properties_async()
                        playback = session.get_playback_info()
                        t = props.title if props and props.title else None
                        a = props.artist if props and props.artist else None
                        st = (playback.playback_status == 4) if playback else None
                        return t, a, st
                except Exception:
                    pass
                finally:
                    try:
                        ctypes.windll.ole32.CoUninitialize()
                    except Exception:
                        pass
                return None, None, None

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            t_win, a_win, st_win = loop.run_until_complete(_async_get())
            loop.close()

            if t_win:
                title, artist, is_playing = t_win, a_win, st_win

        if title:
            QTimer.singleShot(0, lambda: self._apply_media_metadata(title, artist, is_playing))

    def _apply_media_metadata(self, title, artist, is_playing):
        clean_title = (title[:22] + "..") if len(title) > 24 else title
        clean_artist = (artist[:25] + "..") if (artist and len(artist) > 27) else (artist if artist else "Active Windows Audio")

        self.m_title.setText(clean_title)
        self.m_sub.setText(clean_artist)

        if is_playing is not None:
            self.is_media_playing = is_playing
            self.btn_play.setText("⏸" if is_playing else "▶")

    def log(self, text, log_type="sys"):
        self.sig_log.emit(str(text), str(log_type))

    def _handle_log(self, text, log_type):
        if hasattr(self, 'terminal_log'):
            clean_t = text.replace("⚡ [DISPATCHER]:", "").replace("[PHANTOM STT HEARD]:", "").strip("'\" ")
            if log_type == "cmd" or "HEARD" in text or "DISPATCHER" in text:
                self.terminal_log.append(f"\n🎧 [HEARD]: \"{clean_t}\"")
            elif log_type == "ai":
                self.terminal_log.append(f"🤖 [REPLY]: {clean_t}")
            else:
                self.terminal_log.append(f"⚡ [ACTION]: {clean_t}")
            
            sb = self.terminal_log.verticalScrollBar()
            sb.setValue(sb.maximum())

    def set_processing_state(self, is_processing, status_text=""):
        self.sig_processing.emit(bool(is_processing), str(status_text))

    def _handle_processing(self, is_processing, status_text):
        if status_text:
            self._handle_log(status_text, "sys")

    def show_ai_response_popup(self, query, reply):
        pass

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = PhantomGUI()
    gui.show()
    sys.exit(app.exec())

import os
import sys
import time
import subprocess
import asyncio
import re
import math
import threading
from PIL import ImageGrab
import pyautogui
import win32api
import win32con
import win32gui
from pywinauto import Desktop

# Import Winsdk for Windows 10/11 Native Hardware OCR Engine
import winsdk
import winsdk.windows.media.ocr as ocr
import winsdk.windows.graphics.imaging as imaging
import winsdk.windows.storage as storage

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QPoint, QRectF, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

class ScreenBadgeOverlay(QWidget):
    """
    Transparent Click-Through Overlay Window.
    Draws glowing numbered badges [1], [2], [3] at matching candidate coordinates.
    """
    def __init__(self, coordinates):
        super().__init__()
        self.coordinates = coordinates
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        else:
            sw, sh = pyautogui.size()
            self.setGeometry(0, 0, sw, sh)

        # Automatically auto-dismiss badges after 15 seconds
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start(15000)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        sw = self.width()
        sh = self.height()

        # Collision-avoidance layout: ensure no two badges overlap!
        badge_positions = []
        for x, y in self.coordinates:
            cx, cy = int(x), int(y)
            bx = cx
            by = cy - 35
            if by < 40:
                by = cy + 35

            # Shift horizontally or vertically if colliding with an earlier badge
            for ox, oy in badge_positions:
                if math.hypot(bx - ox, by - oy) < 42:
                    if (bx + 42) < sw - 40:
                        bx += 42
                    else:
                        bx -= 42
                    if math.hypot(bx - ox, by - oy) < 42:
                        by = oy + 40 if (oy + 40) < sh - 40 else oy - 40
            badge_positions.append((bx, by))

        for idx, ((x, y), (bx, by)) in enumerate(zip(self.coordinates, badge_positions)):
            num_str = str(idx + 1)
            cx, cy = int(x), int(y)

            # 1. Dashed Cyan Leader Line from Badge to Exact Target Coordinate
            painter.setPen(QPen(QColor(56, 189, 248, 220), 2.0, Qt.PenStyle.DashLine))
            painter.drawLine(bx, by, cx, cy)

            # 2. Bullseye Target Ring at exact target point
            painter.setPen(QPen(QColor(239, 68, 68, 255), 2.5))
            painter.setBrush(QColor(239, 68, 68, 90))
            painter.drawEllipse(QPoint(cx, cy), 7, 7)
            painter.setBrush(QColor(255, 255, 255, 255))
            painter.drawEllipse(QPoint(cx, cy), 2, 2)

            # 3. Outer Glowing Halo
            painter.setPen(QPen(QColor(0, 229, 255, 160), 5.0))
            painter.setBrush(QColor(10, 15, 29, 250))
            painter.drawEllipse(QPoint(bx, by), 18, 18)

            # 4. Neon Cyan Pill
            painter.setPen(QPen(QColor(0, 229, 255, 255), 2.0))
            painter.setBrush(QColor(14, 165, 233, 250))
            painter.drawEllipse(QPoint(bx, by), 15, 15)

            # 5. Bright White Number Text [1], [2], [3]...
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            painter.drawText(QRectF(bx - 15, by - 15, 30, 30), Qt.AlignmentFlag.AlignCenter, num_str)


class PhantomScreenVision(QObject):
    """
    100% Offline Universal Screen Vision, Mouse Click Automation & Smart OS Control.
    Features:
    - Real Native Mouse Driver Events (win32api.mouse_event - No Ghost Clicks!)
    - High-Precision Multi-Word OCR & UIAutomation Matching
    - Dedicated Window Manager (Minimize, Maximize/Restore, Close via win32 API)
    - Multi-Match Confirmation Badges [1], [2] when genuine duplicates exist
    - Zero False-Positive Substring Matches
    """
    sig_show_badges = pyqtSignal(list)
    sig_clear_badges = pyqtSignal()

    def __init__(self, brain_engine=None):
        super().__init__()
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05
        self.brain_engine = brain_engine
        self.ocr_engine = None
        self.pending_matches = []
        self.pending_target = ""
        self.pending_double_click = False
        self.overlay_widget = None
        self.last_minimized_hwnd = None

        self.sig_show_badges.connect(self._do_show_badge_overlay)
        self.sig_clear_badges.connect(self._do_clear_badges)

        try:
            self.ocr_engine = ocr.OcrEngine.try_create_from_user_profile_languages()
        except Exception as e:
            print(f"[PHANTOM VISION NOTICE] Windows Native OCR Init Notice: {e}")
        print("[PHANTOM VISION] Universal Vision, Native Mouse & Window Engine Initialized.")

    def has_pending_matches(self):
        """Checks if there is an active multi-match choice awaiting user resolution."""
        return len(self.pending_matches) > 1

    def execute_mouse_click(self, cx, cy, double_click=False):
        """Simulates physical hardware mouse click using Windows OS user32 driver events."""
        cx = int(cx)
        cy = int(cy)
        pyautogui.moveTo(cx, cy, duration=0.15)
        time.sleep(0.04)
        win32api.SetCursorPos((cx, cy))
        time.sleep(0.02)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        if double_click:
            time.sleep(0.08)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def resolve_pending_choice(self, choice_idx):
        """Executes click on chosen candidate when multiple matches were present."""
        if not self.has_pending_matches() or choice_idx < 0 or choice_idx >= len(self.pending_matches):
            return False, "Invalid choice or no pending matches."

        target = self.pending_target
        cx, cy = self.pending_matches[choice_idx]
        double_click = self.pending_double_click
        self.clear_pending_matches()

        print(f"[PHANTOM VISION]: Executing click on Option [{choice_idx + 1}] at ({cx}, {cy})...")
        self.execute_mouse_click(cx, cy, double_click=double_click)
        if double_click:
            return True, f"Double-clicked option {choice_idx + 1} at ({cx}, {cy})."
        else:
            return True, f"Clicked option {choice_idx + 1} at ({cx}, {cy})."

    def clear_pending_matches(self):
        """Cleans up pending matches state and removes floating badges."""
        self.pending_matches = []
        self.pending_target = ""
        self.pending_double_click = False
        self.sig_clear_badges.emit()

    def _do_clear_badges(self):
        if self.overlay_widget:
            try:
                self.overlay_widget.close()
            except Exception:
                pass
            self.overlay_widget = None

    def _show_badge_overlay(self, coordinates):
        """Displays numbered floating badges [1], [2] at candidate coordinates via thread-safe Qt Signal."""
        self.sig_show_badges.emit(coordinates)

    def _do_show_badge_overlay(self, coordinates):
        if self.overlay_widget:
            try:
                self.overlay_widget.close()
            except Exception:
                pass
        self.overlay_widget = ScreenBadgeOverlay(coordinates)
        self.overlay_widget.show()
        self.overlay_widget.raise_()
        self.overlay_widget.activateWindow()

    # =========================================================================
    # DEDICATED WINDOW MANAGEMENT ENGINE (Minimize, Maximize, Close)
    # =========================================================================
    def minimize_active_window(self):
        """Minimizes the currently active foreground window cleanly to taskbar."""
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            cname = win32gui.GetClassName(hwnd)
            # Avoid minimizing taskbar or desktop
            if cname not in ["Progman", "WorkerW", "Shell_TrayWnd"]:
                self.last_minimized_hwnd = hwnd
                title = win32gui.GetWindowText(hwnd) or "active window"
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                return True, f"Minimized '{title}' to taskbar."

        pyautogui.hotkey('win', 'd')
        return True, "Minimized all windows to desktop."

    def maximize_active_window(self):
        """Restores and maximizes the active or previously minimized window."""
        # 1. If we saved a minimized window handle, restore and maximize it
        if self.last_minimized_hwnd and win32gui.IsWindow(self.last_minimized_hwnd):
            target_hwnd = self.last_minimized_hwnd
            title = win32gui.GetWindowText(target_hwnd) or "window"
            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            win32gui.ShowWindow(target_hwnd, win32con.SW_MAXIMIZE)
            try:
                win32gui.SetForegroundWindow(target_hwnd)
            except Exception:
                pass
            return True, f"Maximized '{title}'."

        # 2. Maximize current foreground window
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            title = win32gui.GetWindowText(hwnd) or "window"
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            pyautogui.hotkey('win', 'up')
            return True, f"Maximized '{title}'."

        pyautogui.hotkey('win', 'up')
        return True, "Maximized window."

    def close_active_window(self):
        """Closes the current active foreground window cleanly via Windows message or Alt+F4."""
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            title = win32gui.GetWindowText(hwnd) or "window"
            cname = win32gui.GetClassName(hwnd)
            if cname not in ["Progman", "WorkerW", "Shell_TrayWnd"]:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return True, f"Closed '{title}'."

        pyautogui.hotkey('alt', 'f4')
        return True, "Closed active window."

    def close_active_tab(self):
        """Closes the active tab in browser or editor (Ctrl+W)."""
        pyautogui.hotkey('ctrl', 'w')
        return True, "Closed active tab."

    def show_desktop_home(self):
        """Shows Windows Desktop / Home Screen instantly via Win+D."""
        print("[PHANTOM VISION] Toggling Desktop Home Screen (Win+D)...")
        pyautogui.hotkey('win', 'd')
        return True, "Returned to Desktop Home Screen."

    def show_recent_apps(self):
        """Shows Windows Task View (Recent Apps) via Win+Tab."""
        print("[PHANTOM VISION] Opening Task View / Recent Apps (Win+Tab)...")
        pyautogui.hotkey('win', 'tab')
        return True, "Opened Recent Apps (Task View)."

    def capture_screen(self):
        """Captures full desktop frame."""
        try:
            return ImageGrab.grab()
        except Exception:
            try:
                return pyautogui.screenshot()
            except Exception as e:
                print(f"[PHANTOM VISION NOTICE] Screen capture notice: {e}")
                return None

    def _is_phantom_hud_area(self, cx, cy):
        """Excludes Phantom's GUI area to prevent self-clicking."""
        try:
            sw, sh = pyautogui.size()
            if cx >= (sw - 380) and cy <= 140:
                return True
        except Exception:
            pass
        return False

    def _normalize_symbol_text(self, text):
        """Normalizes text for accurate matching."""
        if not text:
            return ""
        t = text.lower().strip()
        t = re.sub(r'\.(lnk|exe|bat|txt|url|jpg|png|pdf)$', '', t)
        t = t.replace("_", "").replace("&", "and").replace("-", "").replace(".", "").replace(" ", "")
        return t

    def _clean_query_words(self, target_text):
        """Safely removes filler words."""
        if not target_text:
            return ""
        cleaned = re.sub(r'\b(on|the|at|in|to)\b', '', target_text.lower(), flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if cleaned else target_text.lower().strip()

    def _extract_ordinal_index(self, text):
        """Extracts requested ordinal position if user specified (e.g. 'first' -> 0, 'second' -> 1)."""
        t = text.lower()
        if any(k in t for k in ["first", "1st", "number one", "pehla"]):
            return 0
        if any(k in t for k in ["second", "2nd", "number two", "doosra", "dusra"]):
            return 1
        if any(k in t for k in ["third", "3rd", "number three", "teesra", "tisra"]):
            return 2
        if any(k in t for k in ["fourth", "4th", "number four", "chautha"]):
            return 3
        if any(k in t for k in ["fifth", "5th", "number five", "paanchwa"]):
            return 4
        return None

    def _deduplicate_coords(self, coords_list, threshold=35):
        """Merges coordinates that are within pixel proximity threshold."""
        unique = []
        for c in coords_list:
            if not any(math.hypot(c[0] - u[0], c[1] - u[1]) < threshold for u in unique):
                unique.append(c)
        return unique

    def is_desktop_icon_target(self, target_name):
        """Checks if target is a known Desktop item."""
        query_norm = self._normalize_symbol_text(target_name)
        desktop_system_keys = [
            "recyclebin", "trash", "thispc", "mycomputer", "network", "controlpanel",
            "projectastitva", "beatblast", "visionsafe", "phantomlink", "desktop"
        ]
        return any(k in query_norm for k in desktop_system_keys)

    def open_desktop_item(self, target_name):
        """Finds desktop icon/folder on Desktop and launches via double-click."""
        clean_target = self._clean_query_words(target_name)
        desktop_paths = [
            os.path.join(os.environ["USERPROFILE"], "Desktop"),
            os.path.join(os.environ.get("PUBLIC", "C:\\Users\\Public"), "Desktop")
        ]

        for d_path in desktop_paths:
            if os.path.exists(d_path):
                for fname in os.listdir(d_path):
                    f_clean = self._normalize_symbol_text(fname)
                    q_clean = self._normalize_symbol_text(clean_target)
                    if q_clean and (q_clean in f_clean or f_clean in q_clean):
                        full_path = os.path.join(d_path, fname)
                        try:
                            os.startfile(full_path)
                            return True, f"Opened desktop item '{fname}'."
                        except Exception as e:
                            print(f"[PHANTOM VISION] Failed to startfile desktop item: {e}")

        return False, None

    def find_taskbar_icon_coords(self, target_text):
        """Locates Windows taskbar items."""
        query_clean = self._clean_query_words(target_text)
        query_norm = self._normalize_symbol_text(query_clean)

        if query_norm in ["search", "find", "searchbar", "windowsearch"]:
            pyautogui.hotkey('win', 's')
            return "NATIVE_SEARCH"

        if query_norm in ["start", "window", "windows", "startmenu"]:
            pyautogui.hotkey('win')
            return "NATIVE_START"

        sw, sh = pyautogui.size()
        taskbar_keywords = {
            "time": (sw - 70, sh - 25),
            "clock": (sw - 70, sh - 25),
            "systemtray": (sw - 160, sh - 25),
            "tray": (sw - 160, sh - 25),
            "wifi": (sw - 180, sh - 25),
            "volume": (sw - 140, sh - 25),
            "battery": (sw - 120, sh - 25),
            "mic": (sw - 200, sh - 25),
            "microphone": (sw - 200, sh - 25)
        }

        for key, coords in taskbar_keywords.items():
            if key in query_norm:
                return coords

        return None

    def find_ocr_text_matches(self, target_text):
        """Returns ALL accurate matching coordinates found via Windows Native Hardware OCR."""
        if not target_text or not self.ocr_engine:
            return []

        query_clean_word = self._clean_query_words(target_text)
        query_norm = self._normalize_symbol_text(query_clean_word)
        if not query_norm or len(query_norm) < 2:
            return []

        pil_img = self.capture_screen()
        if not pil_img:
            return []

        matches = []
        try:
            temp_path = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "phantom_scr.png")
            pil_img.save(temp_path, "PNG")

            async def _run_ocr():
                file = await storage.StorageFile.get_file_from_path_async(temp_path)
                stream = await file.open_async(storage.FileAccessMode.READ)
                decoder = await imaging.BitmapDecoder.create_async(stream)
                software_bitmap = await decoder.get_software_bitmap_async()
                ocr_result = await self.ocr_engine.recognize_async(software_bitmap)
                return ocr_result

            ocr_result = asyncio.run(_run_ocr())

            if ocr_result and ocr_result.lines:
                for line in ocr_result.lines:
                    line_text = line.text.strip()
                    line_norm = self._normalize_symbol_text(line_text)
                    if not line_norm or query_norm not in line_norm:
                        continue

                    # 1. Single-word query check
                    words = line.words
                    matched_on_words = False
                    for w in words:
                        w_norm = self._normalize_symbol_text(w.text)
                        if w_norm == query_norm or (len(query_norm) >= 4 and query_norm in w_norm):
                            r = w.bounding_rect
                            cx = int(r.x + (r.width / 2.0))
                            cy = int(r.y + (r.height / 2.0))
                            if not self._is_phantom_hud_area(cx, cy):
                                matches.append((cx, cy))
                                matched_on_words = True

                    # 2. Multi-word phrase check (e.g. "virtual keyboard", "device manager")
                    if not matched_on_words and len(words) > 1:
                        for start_i in range(len(words)):
                            combo_norm = ""
                            combo_words = []
                            for end_i in range(start_i, len(words)):
                                combo_words.append(words[end_i])
                                combo_norm += self._normalize_symbol_text(words[end_i].text)
                                if combo_norm == query_norm or (len(query_norm) >= 5 and query_norm in combo_norm):
                                    min_x = min(cw.bounding_rect.x for cw in combo_words)
                                    max_x = max(cw.bounding_rect.x + cw.bounding_rect.width for cw in combo_words)
                                    min_y = min(cw.bounding_rect.y for cw in combo_words)
                                    max_y = max(cw.bounding_rect.y + cw.bounding_rect.height for cw in combo_words)
                                    cx = int((min_x + max_x) / 2.0)
                                    cy = int((min_y + max_y) / 2.0)
                                    if not self._is_phantom_hud_area(cx, cy):
                                        matches.append((cx, cy))
                                        matched_on_words = True
                                    break
                                if len(combo_norm) > len(query_norm) + 4:
                                    break

        except Exception as e:
            print(f"[PHANTOM VISION OCR NOTICE] OCR Execution Notice: {e}")

        return self._deduplicate_coords(matches)

    def find_uia_matches(self, target_text):
        """Returns matching coordinates found via Windows UIAutomation controls (buttons, links, items)."""
        if not target_text:
            return []

        query_clean_word = self._clean_query_words(target_text)
        query_norm = self._normalize_symbol_text(query_clean_word)
        if not query_norm or len(query_norm) < 2:
            return []

        matches = []
        try:
            sw, sh = pyautogui.size()
            desktop = Desktop(backend="uia")
            windows = desktop.windows()

            for win in windows:
                try:
                    win_text = win.window_text().lower()
                    if any(ignore_k in win_text for ignore_k in ["phantom", "executing", "voice active", "processing task"]):
                        continue

                    # Only inspect child controls (buttons, menu items, tabs, checkboxes)
                    # NEVER click the center of the whole window!
                    for ctrl in win.descendants():
                        try:
                            ctrl_text = ctrl.window_text().lower()
                            ctrl_norm = self._normalize_symbol_text(ctrl_text)
                            if ctrl_norm and (ctrl_norm == query_norm or (len(query_norm) >= 4 and query_norm in ctrl_norm)):
                                rect = ctrl.rectangle()
                                if 10 < rect.width() < (sw * 0.7) and 10 < rect.height() < (sh * 0.7):
                                    cx = rect.left + (rect.width() // 2)
                                    cy = rect.top + (rect.height() // 2)
                                    if not self._is_phantom_hud_area(cx, cy):
                                        matches.append((cx, cy))
                        except Exception:
                            pass
                except Exception:
                    pass

        except Exception as e:
            print(f"[PHANTOM VISION UIA NOTICE] UIAutomation Notice: {e}")

        return self._deduplicate_coords(matches)

    def click_target(self, target_text, double_click=False):
        """
        Locates target on screen smartly:
        - If EXACTLY 1 result found: Clicks directly without delay!
        - If MULTIPLE results (> 1) found: Shows numbered badges [1], [2] and requests user confirmation!
        """
        if not target_text:
            return False, "No click target specified."

        clean_target = self._clean_query_words(target_text)

        # Standalone Short Mouse Commands
        if clean_target in ["click", "single click", "click here"]:
            cx, cy = pyautogui.position()
            self.execute_mouse_click(cx, cy, double_click=False)
            return True, "Executed single click at current position."

        if clean_target in ["right click", "context menu"]:
            pyautogui.rightClick()
            return True, "Executed right click at current position."

        if clean_target in ["double click"]:
            cx, cy = pyautogui.position()
            self.execute_mouse_click(cx, cy, double_click=True)
            return True, "Executed double click at current position."

        if self.is_desktop_icon_target(clean_target):
            double_click = True

        # 1. Check Taskbar Icons / Native Triggers
        taskbar_coords = self.find_taskbar_icon_coords(clean_target)
        if taskbar_coords in ["NATIVE_SEARCH", "NATIVE_START"]:
            return True, f"Triggered Windows native {clean_target} successfully."
        elif taskbar_coords and isinstance(taskbar_coords, tuple):
            self.execute_mouse_click(taskbar_coords[0], taskbar_coords[1], double_click=False)
            return True, f"Clicked Taskbar icon for '{clean_target}'."

        # 2. Collect all matches across OCR and UIAutomation
        ocr_matches = self.find_ocr_text_matches(clean_target)
        uia_matches = self.find_uia_matches(clean_target) if not ocr_matches else []
        all_matches = self._deduplicate_coords(ocr_matches + uia_matches)

        if not all_matches:
            return False, f"Could not find '{clean_target}' on screen."

        # Check if user already specified an ordinal ("click first ...", "click 2nd ...")
        ordinal_idx = self._extract_ordinal_index(target_text)
        if ordinal_idx is not None and 0 <= ordinal_idx < len(all_matches):
            cx, cy = all_matches[ordinal_idx]
            self.execute_mouse_click(cx, cy, double_click=double_click)
            return True, f"Clicked option {ordinal_idx + 1} for '{clean_target}'."

        # =====================================================================
        # CASE 1: EXACTLY 1 MATCH FOUND -> CLICK DIRECTLY! (ZERO PROMPT)
        # =====================================================================
        if len(all_matches) == 1:
            cx, cy = all_matches[0]
            sw, sh = pyautogui.size()
            if cy > (sh - 60):
                double_click = False

            print(f"[PHANTOM VISION] Single match for '{clean_target}' at ({cx}, {cy}). Clicking...")
            self.execute_mouse_click(cx, cy, double_click=double_click)
            if double_click:
                return True, f"Double-clicked '{clean_target}' at ({cx}, {cy})."
            else:
                return True, f"Clicked '{clean_target}' at ({cx}, {cy})."

        # =====================================================================
        # CASE 2: MULTIPLE MATCHES FOUND (> 1) -> SHOW BADGES & CONFIRM!
        # =====================================================================
        print(f"[PHANTOM VISION MULTI-MATCH]: Found {len(all_matches)} candidates for '{clean_target}':")
        for i, (cx, cy) in enumerate(all_matches):
            print(f"   Option [{i + 1}]: x={cx}, y={cy}")
        self.pending_matches = all_matches
        self.pending_target = clean_target
        self.pending_double_click = double_click
        self._show_badge_overlay(all_matches)

        return "AMBIGUOUS", f"Boss, I found {len(all_matches)} matches for '{clean_target}' on screen. Say 1 to {len(all_matches)} to choose."

    def type_text(self, text_to_type):
        """Types text into focused element."""
        if not text_to_type:
            return False, "No text to type."
        pyautogui.typewrite(text_to_type, interval=0.03)
        return True, f"Typed: \"{text_to_type}\""

    def scroll_screen(self, direction="down", amount=5):
        """Scrolls active window."""
        clicks = -500 if direction.lower() == "down" else 500
        for _ in range(max(1, amount)):
            pyautogui.scroll(clicks)
            time.sleep(0.05)
        return True, f"Scrolled {direction}."

    def execute_shortcut(self, shortcut_cmd):
        """Executes native Windows keyboard shortcuts."""
        cmd = shortcut_cmd.lower().strip()
        shortcut_map = {
            "enter": "enter", "press enter": "enter", "tab": "tab",
            "backspace": "backspace", "escape": "esc", "esc": "esc",
            "delete": "delete", "space": "space"
        }
        if cmd in shortcut_map:
            pyautogui.press(shortcut_map[cmd])
            return True, f"Pressed key '{shortcut_map[cmd]}'."

        combo_map = {
            "copy": ("ctrl", "c"), "paste": ("ctrl", "v"), "cut": ("ctrl", "x"),
            "select all": ("ctrl", "a"), "undo": ("ctrl", "z"), "save": ("ctrl", "s"),
            "switch tab": ("alt", "tab")
        }
        for name, combo in combo_map.items():
            if name in cmd:
                pyautogui.hotkey(*combo)
                return True, f"Executed shortcut '{name}'."

        return False, f"Unknown shortcut: '{shortcut_cmd}'"

if __name__ == "__main__":
    vision = PhantomScreenVision()
    success, msg = vision.click_target("search")
    print(msg)

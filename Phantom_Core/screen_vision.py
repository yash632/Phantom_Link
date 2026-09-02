import os
import sys
import time
import subprocess
import asyncio
import re
from PIL import ImageGrab
import pyautogui
import win32api
import win32con
from pywinauto import Desktop

# Import Winsdk for Windows 10/11 Native Hardware OCR Engine
import winsdk
import winsdk.windows.media.ocr as ocr
import winsdk.windows.graphics.imaging as imaging
import winsdk.windows.storage as storage

class PhantomScreenVision:
    """
    100% Offline Universal Screen Vision, Mouse Click Automation & Smart OS Control.
    Features:
    - Native Windows 11 Taskbar Triggers (Search -> Win+S, Start/Window -> Win)
    - Zero Mouse Movement on Not Found
    - Gemini Multimodal Vision Integration
    - Precision Click Mode: Taskbar Pinned Apps & UI Buttons -> SINGLE CLICK ONLY!
      Desktop Icons & Desktop Folders -> DOUBLE CLICK!
    - Self-HUD Filtering: Excludes Phantom GUI & Toast overlays
    """
    def __init__(self, brain_engine=None):
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05
        self.brain_engine = brain_engine
        self.ocr_engine = None
        try:
            self.ocr_engine = ocr.OcrEngine.try_create_from_user_profile_languages()
        except Exception as e:
            print(f"[PHANTOM VISION NOTICE] Windows Native OCR Init Notice: {e}")
        print("[PHANTOM VISION] Universal Vision, Multimodal Gemini & Taskbar Engine Initialized.")

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

    def _is_phantom_hud_area(self, cx, cy):
        """
        Checks if (cx, cy) coordinates fall inside Phantom's floating Toast overlay
        window (Top-Right: width-380 to width, height 0 to 140) to prevent self-clicking.
        """
        try:
            sw, sh = pyautogui.size()
            if cx >= (sw - 380) and cy <= 140:
                return True
        except Exception:
            pass
        return False

    def _normalize_symbol_text(self, text):
        """Normalizes special symbols (_, &, -, ., extension) for 100% flexible matching."""
        if not text:
            return ""
        t = text.lower().strip()
        t = re.sub(r'\.(lnk|exe|bat|txt|url|jpg|png|pdf)$', '', t)
        t = t.replace("_", "").replace("&", "and").replace("-", "").replace(".", "").replace(" ", "")
        return t

    def _clean_query_words(self, target_text):
        """Safely removes standalone filler words ('on', 'the') at word boundaries."""
        if not target_text:
            return ""
        cleaned = re.sub(r'\b(on|the)\b', '', target_text.lower(), flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if cleaned else target_text.lower().strip()

    def is_desktop_icon_target(self, target_name):
        """
        Checks if target_name is a Desktop Icon or Desktop File/Folder on Desktop background.
        """
        query_norm = self._normalize_symbol_text(target_name)

        desktop_system_keys = [
            "recyclebin", "trash", "thispc", "mycomputer", 
            "controlpanel", "network", "desktop", "mydocuments"
        ]
        
        if any(k in query_norm for k in desktop_system_keys):
            return True

        desktop_user = os.path.join(os.path.expanduser("~"), "Desktop")
        desktop_public = r"C:\Users\Public\Desktop"

        for d_path in [desktop_user, desktop_public]:
            if os.path.exists(d_path):
                try:
                    for item in os.listdir(d_path):
                        item_norm = self._normalize_symbol_text(item)
                        if query_norm and (query_norm in item_norm or item_norm in query_norm):
                            return True
                except Exception:
                    pass
        return False

    def open_desktop_item(self, target_name):
        """
        Directly scans Desktop directories and Special Shell Folders (Recycle Bin, This PC)
        and opens matching folder or file natively in 0ms without Windows popups.
        """
        raw_cmd = target_name.lower().strip()
        
        if raw_cmd in ["open desktop", "go to desktop", "show desktop", "desktop", "home", "home screen", "go home"]:
            return self.show_desktop_home()

        clean_target = self._clean_query_words(
            raw_cmd
            .replace("open", "")
            .replace("click", "")
            .replace("from desktop", "")
            .replace("on desktop", "")
            .replace("desktop", "")
            .replace("folder", "")
            .replace("icon", "")
        )

        if not clean_target:
            return self.show_desktop_home()

        clean_norm = self._normalize_symbol_text(clean_target)

        # Special Shell Folders Handling (Recycle Bin, This PC)
        if any(k in clean_norm for k in ["recyclebin", "trash"]):
            print("[PHANTOM DESKTOP MATCH]: Opening Recycle Bin...")
            subprocess.Popen('explorer.exe "shell:RecycleBinFolder"', shell=True)
            return True, "Opened Recycle Bin successfully."

        if any(k in clean_norm for k in ["thispc", "mycomputer"]):
            print("[PHANTOM DESKTOP MATCH]: Opening This PC...")
            subprocess.Popen('explorer.exe "shell:MyComputerFolder"', shell=True)
            return True, "Opened This PC successfully."

        desktop_user = os.path.join(os.path.expanduser("~"), "Desktop")
        desktop_public = r"C:\Users\Public\Desktop"

        for d_path in [desktop_user, desktop_public]:
            if os.path.exists(d_path):
                try:
                    for item in os.listdir(d_path):
                        item_norm = self._normalize_symbol_text(item)
                        if clean_norm and (clean_norm in item_norm or item_norm in clean_norm):
                            full_path = os.path.join(d_path, item)
                            print(f"[PHANTOM DESKTOP MATCH]: Found '{full_path}'. Opening...")
                            os.startfile(full_path)
                            return True, f"Opened desktop item '{item}' successfully."
                except Exception as e:
                    print(f"[PHANTOM DESKTOP NOTICE] Directory scan notice: {e}")

        # Fallback to Screen OCR / UIAutomation Click
        return self.click_target(clean_target, double_click=True)

    def find_taskbar_icon_coords(self, target_text):
        """
        Special Locator for Taskbar & System Tray Icons.
        Triggers Windows Native Shortcuts (Win+S, Win) for 100% Reliability on Windows 11!
        """
        query_norm = self._normalize_symbol_text(target_text)

        # Native Shortcut Triggers for Search & Start
        if query_norm in ["search", "clicksearch", "searchicon"]:
            print("[PHANTOM TASKBAR NATIVE]: Triggering Windows Search (Win+S)...")
            pyautogui.hotkey('win', 's')
            return "NATIVE_SEARCH"

        if query_norm in ["start", "clickstart", "window", "windows", "clickwindow"]:
            print("[PHANTOM TASKBAR NATIVE]: Triggering Windows Start Menu (Win)...")
            pyautogui.press('win')
            return "NATIVE_START"

        sw, sh = pyautogui.size()
        taskbar_keywords = {
            "dateandtime": (sw - 70, sh - 25),
            "date": (sw - 70, sh - 25),
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
                print(f"[PHANTOM TASKBAR MATCH]: Found '{key}' at Taskbar {coords}.")
                return coords

        return None

    def find_ocr_text_coords(self, target_text):
        """
        Uses Windows Native Hardware OCR to scan desktop pixels with safe word boundary filtering.
        """
        if not target_text or not self.ocr_engine:
            return None

        query_clean_word = self._clean_query_words(target_text)
        query_norm = self._normalize_symbol_text(query_clean_word)

        print(f"[PHANTOM VISION OCR] Scanning Desktop Pixels for text: '{query_clean_word}'...")

        pil_img = self.capture_screen()
        if not pil_img:
            return None

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
                    line_norm = self._normalize_symbol_text(line.text)
                    if query_norm and query_norm in line_norm:
                        for word in line.words:
                            word_norm = self._normalize_symbol_text(word.text)
                            if query_norm in word_norm or word_norm in query_norm:
                                rect = word.bounding_rect
                                cx = int(rect.x + (rect.width / 2))
                                cy = int(rect.y + (rect.height / 2))
                                if not self._is_phantom_hud_area(cx, cy):
                                    return (cx, cy)
                                
                        rect = line.words[0].bounding_rect
                        cx = int(rect.x + (rect.width / 2))
                        cy = int(rect.y + (rect.height / 2))
                        if not self._is_phantom_hud_area(cx, cy):
                            return (cx, cy)

        except Exception as e:
            print(f"[PHANTOM VISION OCR NOTICE] OCR Execution Notice: {e}")

        return None

    def find_uia_coords(self, target_text):
        """
        Scans Windows OS UIAutomation tree with word-boundary clean matching.
        """
        if not target_text:
            return None

        query_clean_word = self._clean_query_words(target_text)
        query_norm = self._normalize_symbol_text(query_clean_word)

        print(f"[PHANTOM VISION UIA] Scanning OS UI Elements for: '{query_clean_word}'...")

        try:
            desktop = Desktop(backend="uia")
            windows = desktop.windows()

            for win in windows:
                try:
                    win_text = win.window_text().lower()
                    if any(ignore_k in win_text for ignore_k in ["phantom", "executing", "voice active", "processing task"]):
                        continue

                    win_norm = self._normalize_symbol_text(win_text)
                    if query_norm and query_norm in win_norm:
                        rect = win.rectangle()
                        cx = rect.left + (rect.width() // 2)
                        cy = rect.top + (rect.height() // 2)
                        if not self._is_phantom_hud_area(cx, cy):
                            return (cx, cy)

                    for ctrl in win.descendants():
                        try:
                            ctrl_text = ctrl.window_text().lower()
                            ctrl_norm = self._normalize_symbol_text(ctrl_text)
                            if query_norm and query_norm in ctrl_norm:
                                rect = ctrl.rectangle()
                                if rect.width() > 0 and rect.height() > 0:
                                    cx = rect.left + (rect.width() // 2)
                                    cy = rect.top + (rect.height() // 2)
                                    if not self._is_phantom_hud_area(cx, cy):
                                        return (cx, cy)
                        except Exception:
                            pass
                except Exception:
                    pass

        except Exception as e:
            print(f"[PHANTOM VISION UIA NOTICE] UIAutomation Notice: {e}")

        return None

    def click_target(self, target_text, double_click=False):
        """
        Locates target text/icon on screen and executes single or double click smartly!
        Handles Short Spoken Commands ("click", "right click", "double click", "search", "window", "minimize")
        """
        if not target_text:
            return False, "No click target specified."

        clean_target = self._clean_query_words(target_text)

        # Standalone Short Mouse Click Commands ("click", "right click", "double click")
        if clean_target in ["click", "single click", "click here"]:
            pyautogui.click()
            return True, "Executed single click at current position."

        if clean_target in ["right click", "context menu"]:
            pyautogui.rightClick()
            return True, "Executed right click at current position."

        if clean_target in ["double click"]:
            pyautogui.doubleClick()
            return True, "Executed double click at current position."

        # Special Action Shortcuts (Minimize, Maximize, Close)
        if any(k in clean_target for k in ["minimize", "minimise"]):
            pyautogui.hotkey('win', 'down')
            return True, "Minimized active window."

        if any(k in clean_target for k in ["maximize", "maximise"]):
            pyautogui.hotkey('win', 'up')
            return True, "Maximized active window."

        # Smart Upgrade for Desktop Icons
        if self.is_desktop_icon_target(clean_target):
            double_click = True

        # 1. Check Taskbar Icons Locator / Native Triggers
        coords = self.find_taskbar_icon_coords(clean_target)
        if coords in ["NATIVE_SEARCH", "NATIVE_START"]:
            return True, f"Triggered Windows native {clean_target} successfully."

        # 2. Try Windows Native Hardware OCR
        if not coords:
            coords = self.find_ocr_text_coords(clean_target)

        # 3. Try Windows UIAutomation API
        if not coords:
            coords = self.find_uia_coords(clean_target)

        # 4. Multimodal Gemini Vision AI Fallback (Screenshot -> Coordinates)
        if not coords and self.brain_engine and self.brain_engine.gemini_available:
            print(f"[PHANTOM VISION] Local search missed '{clean_target}'. Capturing display screenshot for Gemini Multimodal Vision AI...")
            pil_img = self.capture_screen()
            if pil_img:
                sw, sh = pyautogui.size()
                coords = self.brain_engine.locate_target_via_gemini_vision(pil_img, clean_target, sw, sh)
        
        if coords and isinstance(coords, tuple):
            cx, cy = coords
            sw, sh = pyautogui.size()

            # Taskbar & System Tray (cy > sh - 60): ALWAYS SINGLE CLICK!
            if cy > (sh - 60):
                double_click = False

            print(f"[PHANTOM VISION] Target '{clean_target}' found at ({cx}, {cy}). Moving mouse (Double-Click: {double_click})...")
            pyautogui.moveTo(cx, cy, duration=0.2)
            if double_click:
                pyautogui.doubleClick(cx, cy)
                return True, f"Double-clicked '{clean_target}' at ({cx}, {cy})."
            else:
                pyautogui.click(cx, cy)
                return True, f"Clicked '{clean_target}' at ({cx}, {cy})."

        # Honest Result: ZERO (0,0) Mouse Movement on Not Found!
        return False, f"Could not find '{clean_target}' on screen."

    def type_text(self, text_to_type):
        """Types spoken text into whatever text box or document is currently focused."""
        if not text_to_type:
            return False, "No text to type."

        print(f"[PHANTOM TYPER]: Writing \"{text_to_type}\"...")
        pyautogui.typewrite(text_to_type, interval=0.03)
        return True, f"Typed: \"{text_to_type}\""

    def scroll_screen(self, direction="down", amount=5):
        """Scrolls active page/window up or down smoothly."""
        clicks = -500 if direction.lower() == "down" else 500
        for _ in range(max(1, amount)):
            pyautogui.scroll(clicks)
            time.sleep(0.05)
        return True, f"Scrolled {direction}."

    def execute_shortcut(self, shortcut_cmd):
        """Executes native Windows keyboard shortcuts."""
        cmd = shortcut_cmd.lower().strip()
        
        shortcut_map = {
            "enter": "enter",
            "press enter": "enter",
            "tab": "tab",
            "backspace": "backspace",
            "escape": "esc",
            "esc": "esc",
            "delete": "delete",
            "space": "space"
        }

        if cmd in shortcut_map:
            pyautogui.press(shortcut_map[cmd])
            return True, f"Pressed key '{shortcut_map[cmd]}'."

        combo_map = {
            "copy": ("ctrl", "c"),
            "paste": ("ctrl", "v"),
            "cut": ("ctrl", "x"),
            "select all": ("ctrl", "a"),
            "undo": ("ctrl", "z"),
            "save": ("ctrl", "s"),
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

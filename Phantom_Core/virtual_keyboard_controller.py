import subprocess
import sys
import os
import atexit

class VirtualKeyboardController:
    """
    Subprocess Lifecycle Manager for AI Virtual Keyboard & Air Mouse.
    Isolates Tkinter & OpenCV from PyQt6 to prevent thread/event loop lockups.
    """
    def __init__(self, script_path=None):
        if script_path is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            self.script_path = os.path.join(base_dir, "virtual_keyboard.py")
        else:
            self.script_path = script_path
        
        self.process = None
        atexit.register(self.stop_keyboard)

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def start_keyboard(self):
        if self.is_running():
            return True, "Virtual Keyboard is already running."

        if not os.path.exists(self.script_path):
            return False, f"virtual_keyboard.py not found at {self.script_path}"

        try:
            cwd = os.path.dirname(self.script_path)
            # Launch in an independent process with Python
            self.process = subprocess.Popen(
                [sys.executable, self.script_path],
                cwd=cwd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            print(f"✨ [VIRTUAL KEYBOARD]: Subprocess started with PID {self.process.pid}")
            return True, "AI Virtual Keyboard and Air Mouse started."
        except Exception as e:
            print(f"[VIRTUAL KEYBOARD ERROR]: {e}")
            return False, f"Failed to start Virtual Keyboard: {e}"

    def stop_keyboard(self):
        if not self.is_running():
            return True, "Virtual Keyboard is not running."

        try:
            print(f"🛑 [VIRTUAL KEYBOARD]: Stopping process PID {self.process.pid}...")
            self.process.terminate()
            try:
                self.process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            return True, "Virtual Keyboard stopped."
        except Exception as e:
            print(f"[VIRTUAL KEYBOARD STOP ERROR]: {e}")
            self.process = None
            return False, f"Error stopping Virtual Keyboard: {e}"

    def toggle_keyboard(self):
        if self.is_running():
            return self.stop_keyboard()
        else:
            return self.start_keyboard()

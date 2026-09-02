import sys
import time
import pyautogui
import win32api
import win32con

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

class PhantomOSControl:
    """
    100% OFFLINE Universal OS Action Executer.
    Handles Voice Dictation Typing, Scrolling, Keyboard Shortcuts, and System Keypresses.
    """
    def __init__(self):
        print("[PHANTOM OS CONTROL] Initializing Universal OS Action Engine...")

    def type_text(self, text_to_type):
        """Types spoken text into whatever input field is currently active."""
        if not text_to_type:
            return False, "No text provided to type."

        print(f"[PHANTOM TYPING]: \"{text_to_type}\"")
        pyautogui.typewrite(text_to_type, interval=0.01)
        return True, f"Typed: '{text_to_type}'"

    def scroll(self, direction="down", amount=500):
        """Scrolls the active window up or down."""
        if direction.lower() in ["up", "top"]:
            pyautogui.scroll(amount)
            return True, "Scrolled up."
        else:
            pyautogui.scroll(-amount)
            return True, "Scrolled down."

    def press_shortcut(self, command):
        """Executes native Windows keyboard shortcuts."""
        cmd = command.lower().strip()

        if "copy" in cmd:
            pyautogui.hotkey('ctrl', 'c')
            return True, "Copied selection."
        elif "paste" in cmd:
            pyautogui.hotkey('ctrl', 'v')
            return True, "Pasted selection."
        elif "select all" in cmd:
            pyautogui.hotkey('ctrl', 'a')
            return True, "Selected all."
        elif "save" in cmd:
            pyautogui.hotkey('ctrl', 's')
            return True, "Saved document."
        elif "undo" in cmd:
            pyautogui.hotkey('ctrl', 'z')
            return True, "Undone last action."
        elif "enter" in cmd:
            pyautogui.press('enter')
            return True, "Pressed Enter."
        elif "backspace" in cmd:
            pyautogui.press('backspace')
            return True, "Pressed Backspace."
        elif "tab" in cmd:
            pyautogui.press('tab')
            return True, "Pressed Tab."
        elif "escape" in cmd or "esc" in cmd:
            pyautogui.press('esc')
            return True, "Pressed Escape."

        return False, f"Unknown shortcut command: {command}"

if __name__ == "__main__":
    os_ctrl = PhantomOSControl()
    success, msg = os_ctrl.type_text("Hello Phantom!")
    print(msg)

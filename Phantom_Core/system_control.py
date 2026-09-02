import os
import sys
import subprocess
import pyautogui

class PhantomSystemControl:
    """
    100% Offline Windows Hardware System Controls Engine.
    Includes:
    - Volume Up / Down / Mute
    - Brightness Increase / Decrease / Level Setting (0-100%)
    - Mouse Actions (Right Click, Double Click, Scroll Up, Scroll Down)
    - Lock PC, Minimize All, Task View
    """
    def __init__(self):
        self.current_brightness = 50

    def adjust_brightness(self, action="increase", level=None):
        """Adjusts Windows Screen Brightness natively via PowerShell WMI."""
        try:
            if level is not None:
                new_brightness = max(0, min(100, level))
            elif action == "increase":
                new_brightness = min(100, self.current_brightness + 20)
            elif action == "decrease":
                new_brightness = max(0, self.current_brightness - 20)
            else:
                new_brightness = 50

            self.current_brightness = new_brightness
            ps_cmd = f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {new_brightness})"
            subprocess.run(["powershell", "-Command", ps_cmd], creationflags=subprocess.CREATE_NO_WINDOW)
            return True, f"Brightness set to {new_brightness}%."
        except Exception as e:
            return False, f"Brightness adjustment error: {e}"

    def execute_control(self, command_text):
        """Executes OS hardware system control commands."""
        cmd = command_text.lower().strip()

        # 1. Right Click / Double Click / Mouse Controls
        if "right click" in cmd:
            pyautogui.rightClick()
            return True, "Executed Right Click."

        if "double click" in cmd:
            pyautogui.doubleClick()
            return True, "Executed Double Click."

        if "scroll down" in cmd or "scroll down page" in cmd:
            pyautogui.scroll(-500)
            return True, "Scrolled Down."

        if "scroll up" in cmd or "scroll up page" in cmd:
            pyautogui.scroll(500)
            return True, "Scrolled Up."

        # 2. Brightness Controls
        if "brightness" in cmd:
            if "increase" in cmd or "up" in cmd or "raise" in cmd or "more" in cmd:
                return self.adjust_brightness("increase")
            elif "decrease" in cmd or "down" in cmd or "lower" in cmd or "less" in cmd:
                return self.adjust_brightness("decrease")
            elif any(char.isdigit() for char in cmd):
                digits = int(''.join(filter(str.isdigit, cmd)))
                return self.adjust_brightness(level=digits)
            else:
                return self.adjust_brightness("increase")

        # 3. Volume Controls
        if "volume up" in cmd or "increase volume" in cmd:
            for _ in range(5):
                pyautogui.press("volumeup")
            return True, "Volume increased."

        if "volume down" in cmd or "decrease volume" in cmd:
            for _ in range(5):
                pyautogui.press("volumedown")
            return True, "Volume decreased."

        if "mute" in cmd or "unmute" in cmd:
            pyautogui.press("volumemute")
            return True, "Volume muted / unmuted."

        # 4. System Lock & Windows Shortcuts
        if "lock" in cmd:
            subprocess.run("rundll32.exe user32.dll,LockWorkStation")
            return True, "Locked Windows PC."

        if "minimize" in cmd:
            pyautogui.hotkey('win', 'down')
            return True, "Minimized active window."

        return False, f"Unknown system control command: '{command_text}'"

if __name__ == "__main__":
    sys_ctrl = PhantomSystemControl()
    success, msg = sys_ctrl.execute_control("increase brightness")
    print(msg)

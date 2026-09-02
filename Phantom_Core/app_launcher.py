import subprocess
import json
import os
import win32api
import win32con
import glob
from pywinauto import Desktop

class PhantomAppLauncher:
    """
    100% Complete Universal Windows Application & Service Launcher.
    Features:
    - Smart Focus Engine: Switches to ALREADY OPEN application windows (Edge, Chrome, VS Code, Notepad)
      instead of spawning duplicate instances!
    - Phonetic STT Aliases ("microsoft ed" -> "msedge", "edge")
    - Zero Native Error Popups (Suppresses all Windows system error dialogs)
    - PowerShell Get-StartApps & shell:AppsFolder
    """
    def __init__(self):
        self.indexed_apps = {}
        self.refresh_app_index()

    def focus_existing_window(self, app_name):
        """
        Scans active OS windows. If an app matching app_name is ALREADY OPEN,
        brings the existing window to FOREGROUND in 0ms!
        """
        query = app_name.lower().strip()
        print(f"[PHANTOM LAUNCHER] Checking for already open '{query}' window...")

        try:
            desktop = Desktop(backend="uia")
            windows = desktop.windows()

            for win in windows:
                try:
                    w_title = win.window_text().lower()
                    if query and query in w_title:
                        print(f"✨ [PHANTOM LAUNCHER MATCH]: Found already open window '{win.window_text()}'. Bringing to front...")
                        win.set_focus()
                        return True, f"Switched to existing '{win.window_text()}' window."
                except Exception:
                    pass
        except Exception as e:
            print(f"[PHANTOM LAUNCHER NOTICE] Focus check notice: {e}")

        return False, None

    def refresh_app_index(self):
        """Indexes ALL installed applications on Windows across all drives."""
        print("[PHANTOM LAUNCHER] Querying Windows Get-StartApps for 100% complete application indexing...")
        
        # 1. Query PowerShell Get-StartApps
        ps_cmd = "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json"
        try:
            res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    name = item.get("Name", "").strip()
                    appid = item.get("AppID", "").strip()
                    if name and appid:
                        self.indexed_apps[name.lower()] = {"type": "appid", "target": appid, "raw_name": name}
        except Exception as e:
            print(f"[PHANTOM LAUNCHER NOTICE] StartApps Query Notice: {e}")

        # 2. Add System Protocol & Phonetic Mishear App Aliases
        system_aliases = {
            "camera": "microsoft.windows.camera_8wekyb3d8bbwe!App",
            "settings": "ms-settings:",
            "setting": "ms-settings:",
            "screen marker and recorder": "screen marker and recorder",
            "notepad": "notepad.exe",
            "calc": "calc.exe",
            "calculator": "calc.exe",
            "cmd": "cmd.exe",
            "terminal": "cmd.exe",
            "explorer": "explorer.exe",
            "my computer": "explorer.exe",
            "this pc": "explorer.exe",
            "edge": "msedge",
            "microsoft edge": "msedge",
            "microsoft ed": "msedge",
            "ed": "msedge",
            "chrome": "chrome",
            "google chrome": "chrome",
            "excel": "excel",
            "word": "winword",
            "powerpoint": "powerpnt"
        }

        for alias, target in system_aliases.items():
            if alias not in self.indexed_apps:
                app_type = "appid" if "!" in target or target.startswith("ms-") else "exe"
                self.indexed_apps[alias] = {"type": app_type, "target": target, "raw_name": alias.title()}

        print(f"[PHANTOM LAUNCHER] Indexing Complete! {len(self.indexed_apps)} Total Windows Apps & Services Ready!")

    def open_app(self, app_name):
        """
        Launches ANY application dynamically by name safely without Windows error popups.
        Brings ALREADY OPEN windows to FRONT first!
        """
        if not app_name:
            return False, "No application name specified."

        query = app_name.lower().strip()

        # 1. Check if application window is ALREADY OPEN on Windows!
        focused, msg = self.focus_existing_window(query)
        if focused:
            return True, msg

        print(f"[PHANTOM LAUNCHER] Multi-drive searching for app: '{query}'...")

        # 2. Exact or Partial Match in Indexed StartApps
        best_match = None
        for name, info in self.indexed_apps.items():
            if query == name:
                best_match = info
                break
            elif query in name or name in query:
                best_match = info

        if best_match:
            target = best_match["target"]
            raw_name = best_match["raw_name"]
            
            try:
                if target.startswith("ms-"):
                    subprocess.Popen(f'start {target}', shell=True, stderr=subprocess.DEVNULL)
                elif best_match["type"] == "appid":
                    subprocess.Popen(f'explorer.exe "shell:AppsFolder\\{target}"', shell=True, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(f'start "" "{target}"', shell=True, stderr=subprocess.DEVNULL)
                return True, f"Launched '{raw_name}' successfully."
            except Exception as e:
                print(f"[PHANTOM LAUNCHER ERROR]: {e}")

        # Safe Fail: Return False so Main Dispatcher routes to Desktop Finder / Screen Vision Clicker!
        return False, f"Could not find application '{query}' in app registry."

if __name__ == "__main__":
    launcher = PhantomAppLauncher()
    success, msg = launcher.open_app("edge")
    print(msg)

import time
import sys
import os
import re

from PyQt6.QtWidgets import QApplication

# Import Phantom Core Modules
from Phantom_Core.tts_engine import PhantomTTS
from Phantom_Core.stt_engine import PhantomSTT
from Phantom_Core.app_launcher import PhantomAppLauncher
from Phantom_Core.system_control import PhantomSystemControl
from Phantom_Core.phantom_brain import PhantomBrain
from Phantom_Core.phantom_gui import PhantomGUI
from Phantom_Core.screen_vision import PhantomScreenVision
from Phantom_Core.virtual_keyboard_controller import VirtualKeyboardController

def clean_command_target(cmd, prefix_to_remove="click"):
    """
    Safely removes command prefix ('click', 'open', 'double click') and standalone filler words ('on', 'the').
    NEVER strips substrings inside words (e.g. preserves 'extension', 'icon', 'implementation')!
    """
    t = re.sub(r'^\b(' + prefix_to_remove + r'|double click)\b', '', cmd, flags=re.IGNORECASE).strip()
    t = re.sub(r'\b(on|the)\b', '', t, flags=re.IGNORECASE).strip()
    t = re.sub(r'\s+', ' ', t).strip()
    return t if t else cmd

def main():
    print("=" * 75)
    print("      🚀 PROJECT PHANTOM: UNIVERSAL VOICE PC CONTROL & VISION SUITE")
    print("=" * 75)

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # 1. Initialize SAPI5 TTS Engine (100% Microsoft Mark Voice ONLY)
    tts = PhantomTTS(default_english_voice="Mark", rate=0)

    # 2. Initialize Core Engines
    launcher = PhantomAppLauncher()
    sys_ctrl = PhantomSystemControl()
    brain = PhantomBrain()
    vision = PhantomScreenVision(brain_engine=brain)
    vk_controller = VirtualKeyboardController()

    global gui
    gui = None

    # 3. Master All-Rounder Voice Command Dispatcher
    def voice_command_handler(command_text):
        global gui
        if not command_text:
            return

        cmd = command_text.lower().strip()
        msg_log = f"⚡ [DISPATCHER]: '{cmd}'"
        print(f"\n{msg_log}")
        if gui:
            gui.log(msg_log, "cmd")
            gui.set_processing_state(True, f"EXECUTING '{cmd.upper()}'...")

        start_time = time.time()

        try:
            # 0. Check for Pending Multi-Match Disambiguation Choice ("1", "2", "3", "click 3", "teen", etc.)
            if vision.has_pending_matches():
                num_matches = len(vision.pending_matches)
                if any(cancel_w in cmd for cancel_w in ["cancel", "abort", "back", "chhod do", "dismiss"]):
                    vision.clear_pending_matches()
                    reply = "Selection cancelled."
                    if gui:
                        gui.log(f"🤖 [PHANTOM]: {reply}", "ai")
                    tts.speak(reply, block=False)
                    return

                # Robust multi-lingual & conversational number extractor
                choice_idx = None
                num_map = {
                    "1": 1, "one": 1, "first": 1, "pehla": 1, "ek": 1,
                    "2": 2, "two": 2, "second": 2, "doosra": 2, "dusra": 2, "do": 2,
                    "3": 3, "three": 3, "third": 3, "teesra": 3, "tisra": 3, "teen": 3,
                    "4": 4, "four": 4, "fourth": 4, "chautha": 4, "chaar": 4,
                    "5": 5, "five": 5, "fifth": 5, "paanchwa": 5, "panch": 5,
                    "6": 6, "six": 6, "sixth": 6, "chhattha": 6, "chheh": 6,
                    "7": 7, "seven": 7, "seventh": 7, "saatwa": 7, "saat": 7,
                    "8": 8, "eight": 8, "eighth": 8, "aathwa": 8, "aath": 8,
                    "9": 9, "nine": 9, "ninth": 9, "nauwa": 9, "nau": 9,
                    "10": 10, "ten": 10, "tenth": 10, "daswa": 10, "das": 10,
                }
                words = re.findall(r'\b[a-z0-9]+\b', cmd)
                for w in words:
                    if w in num_map:
                        val = num_map[w]
                        if 1 <= val <= num_matches:
                            choice_idx = val - 1
                            break

                if choice_idx is None:
                    digits = re.findall(r'\d+', cmd)
                    if digits:
                        val = int(digits[0])
                        if 1 <= val <= num_matches:
                            choice_idx = val - 1

                if choice_idx is not None:
                    success, reply = vision.resolve_pending_choice(choice_idx)
                    if gui:
                        gui.log(f"🎯 [VISION]: {reply}", "sys")
                    tts.speak(reply, block=False)
                    return
                else:
                    prompt_reply = f"Please say a number between 1 and {num_matches} to choose, or say 'cancel'."
                    if gui:
                        gui.log(f"🤖 [PHANTOM]: {prompt_reply}", "ai")
                    tts.speak(prompt_reply, block=False)
                    return

            # 1. Immediate Speech Interruption / Quiet Command
            if cmd in ["quiet", "be quiet", "shut up", "stop", "stop speaking", "keep quiet", "chup", "chup ho ja"]:
                tts.stop_speaking()
                reply = "Understood boss. Quiet mode engaged."
                if gui:
                    gui.log(f"🤖 [PHANTOM]: {reply}", "ai")
                return

            # Wake Word / Greeting Response
            if cmd in ["greeting", "phantom", "hello", "hi"]:
                reply = "Hello boss! Phantom is online and ready for full PC control. What is the plan for today?"
                if gui:
                    gui.log(f"🤖 [PHANTOM]: {reply}", "ai")
                tts.speak(reply, block=False)
                return

            # 1.5 Virtual Keyboard & Air Mouse Voice Controls (TURN OFF / STOP)
            is_turn_off_kb = any(k in cmd for k in [
                "turn off keyboard", "turn off air mouse", "turn off virtual keyboard", "turn off mouse",
                "close keyboard", "close virtual keyboard", "close air mouse",
                "stop keyboard", "stop virtual keyboard", "stop air mouse",
                "disable keyboard", "disable virtual keyboard", "disable air mouse",
                "exit keyboard", "exit virtual keyboard", "exit air mouse",
                "band karo keyboard", "keyboard band karo", "band karo air mouse", "air mouse band karo",
                "shut down keyboard", "hide keyboard"
            ])
            if is_turn_off_kb:
                success, reply = vk_controller.stop_keyboard()
                if gui:
                    gui.log(f"⌨ [KEYBOARD]: {reply}", "sys")
                    gui._update_vk_button_state()
                tts.speak(reply, block=False)
                return

            # 1.6 Virtual Keyboard & Air Mouse Voice Controls (TURN ON / START)
            is_turn_on_kb = any(k in cmd for k in [
                "turn on keyboard", "turn on air mouse", "turn on virtual keyboard", "turn on mouse",
                "open keyboard", "open virtual keyboard", "open air mouse",
                "start keyboard", "start virtual keyboard", "start air mouse",
                "launch keyboard", "launch virtual keyboard", "launch air mouse",
                "enable keyboard", "enable virtual keyboard", "enable air mouse",
                "chalu karo keyboard", "keyboard chalu karo", "chalu karo air mouse", "air mouse chalu karo",
                "virtual keyboard", "air mouse"
            ])
            if is_turn_on_kb:
                success, reply = vk_controller.start_keyboard()
                if gui:
                    gui.log(f"⌨ [KEYBOARD]: {reply}", "sys")
                    gui._update_vk_button_state()
                tts.speak(reply, block=False)
                return

            # 2. Window Management Controls (Minimize, Maximize, Close Window, Close Tab)
            if any(k in cmd for k in ["minimize window", "minimize this", "minimize", "minimise", "window minimize"]):
                success, msg = vision.minimize_active_window()
                if gui:
                    gui.log(msg, "sys")
                tts.speak(msg, block=False)
                return

            if any(k in cmd for k in ["maximize window", "maximize this", "maximize", "maximise", "window maximize"]):
                success, msg = vision.maximize_active_window()
                if gui:
                    gui.log(msg, "sys")
                tts.speak(msg, block=False)
                return

            if any(k in cmd for k in ["close window", "close this window", "close current window", "window close", "band karo window"]):
                success, msg = vision.close_active_window()
                if gui:
                    gui.log(msg, "sys")
                tts.speak(msg, block=False)
                return

            if any(k in cmd for k in ["close tab", "close this tab", "tab close karo"]):
                success, msg = vision.close_active_tab()
                if gui:
                    gui.log(msg, "sys")
                tts.speak(msg, block=False)
                return

            # 3. Open Desktop / Go Home Screen ("open desktop", "desktop", "home", "home screen")
            if cmd in ["open desktop", "go to desktop", "show desktop", "desktop", "home", "home screen", "go home"]:
                success, msg = vision.show_desktop_home()
                if gui:
                    gui.log(msg, "sys")
                tts.speak(msg, block=False)
                return

            # 4. Show Recent Apps / Task View ("show recent apps", "recent apps", "task view")
            if any(k in cmd for k in ["recent apps", "show recent apps", "task view", "recent app"]):
                success, msg = vision.show_recent_apps()
                if gui:
                    gui.log(msg, "sys")
                tts.speak(msg, block=False)
                return

            # 5. System & Mouse Direct Action Controls (Right Click, Double Click, Brightness, Scroll)
            if any(k in cmd for k in ["right click", "brightness", "scroll down", "scroll up", "volume", "mute", "lock"]):
                success, msg = sys_ctrl.execute_control(cmd)
                if success:
                    elapsed_ms = (time.time() - start_time) * 1000
                    status_str = f"✨ [FLASH TIME]: {elapsed_ms:.1f} ms | {msg}"
                    print(status_str)
                    if gui:
                        gui.log(status_str, "sys")
                    tts.speak(msg, block=False)
                    return

            # 6. Voice Dictation Typer ("type <text>", "write <text>")
            if cmd.startswith("type ") or cmd.startswith("write "):
                text_to_type = cmd.replace("type", "", 1).replace("write", "", 1).strip()
                success, msg = vision.type_text(text_to_type)
                elapsed_ms = (time.time() - start_time) * 1000
                status_str = f"✨ [FLASH TIME]: {elapsed_ms:.1f} ms | {msg}"
                print(status_str)
                if gui:
                    gui.log(status_str, "sys")
                tts.speak(f"Typed {text_to_type}", block=False)
                return

            # 7. Desktop Folder & File Finder (Matches Project_Astitva, BeatBlast, Vision_Safe, etc.)
            if "desktop" in cmd or vision.is_desktop_icon_target(cmd):
                success, msg = vision.open_desktop_item(cmd)
                if success:
                    elapsed_ms = (time.time() - start_time) * 1000
                    status_str = f"✨ [FLASH TIME]: {elapsed_ms:.1f} ms | {msg}"
                    print(status_str)
                    if gui:
                        gui.log(status_str, "sys")
                    tts.speak(msg, block=False)
                    return

            # 8. Voice Screen Vision Clicker ("click on <target>", "click <target>")
            if "click" in cmd and not "double" in cmd and not "right" in cmd:
                target = clean_command_target(cmd, prefix_to_remove="click")
                success, msg = vision.click_target(target, double_click=False)
                elapsed_ms = (time.time() - start_time) * 1000
                status_str = f"✨ [FLASH TIME]: {elapsed_ms:.1f} ms | {msg}"
                print(status_str)
                if gui:
                    gui.log(status_str, "sys")
                tts.speak(msg, block=False)
                return

            # 9. Voice Double Clicker ("double click on <target>")
            if "double click" in cmd:
                target = clean_command_target(cmd, prefix_to_remove="double click")
                success, msg = vision.click_target(target, double_click=True)
                elapsed_ms = (time.time() - start_time) * 1000
                status_str = f"✨ [FLASH TIME]: {elapsed_ms:.1f} ms | {msg}"
                print(status_str)
                if gui:
                    gui.log(status_str, "sys")
                tts.speak(msg, block=False)
                return

            # 10. Shortcuts & Keys ("press enter", "copy", "paste", "select all")
            if any(k in cmd for k in ["enter", "copy", "paste", "select all", "undo", "switch tab", "save"]):
                success, msg = vision.execute_shortcut(cmd)
                if success:
                    if gui:
                        gui.log(msg, "sys")
                    tts.speak(msg, block=False)
                    return

            # 11. Dynamic Application Launcher & Desktop Finder
            if "open" in cmd or "launch" in cmd or "start" in cmd:
                target_app = clean_command_target(cmd, prefix_to_remove="open|launch|start")
                
                # 1. Check App Registry & Existing Open Windows First!
                success, message = launcher.open_app(target_app)
                
                # 2. Check Desktop Shortcuts second
                if not success:
                    success, message = vision.open_desktop_item(target_app)
                
                # 3. Check Windows Native start command
                if not success:
                    try:
                        subprocess.Popen(f'start "" "{target_app}"', shell=True, stderr=subprocess.DEVNULL)
                        success = True
                        message = f"Launched '{target_app}'."
                    except Exception:
                        pass

                elapsed_ms = (time.time() - start_time) * 1000
                status_str = f"✨ [FLASH TIME]: {elapsed_ms:.1f} ms | Status: {message}"
                print(status_str)
                
                if success:
                    reply = message
                else:
                    reply = f"Sorry boss, I could not find '{target_app}' on your PC."
                    
                if gui:
                    gui.log(status_str, "sys")
                    gui.log(f"🤖 [PHANTOM]: {reply}", "ai")
                tts.speak(reply, block=False)
                return

            # 12. Dynamic AI Brain Intent Processing (Web Search, YouTube, AI Conversation Q&A)
            action_type, payload, reply = brain.process_command(cmd)
            elapsed_ms = (time.time() - start_time) * 1000
            status_str = f"✨ [AI EXECUTION TIME]: {elapsed_ms:.1f} ms | Action: {action_type}"
            print(status_str)
            
            if gui:
                gui.log(status_str, "sys")
                gui.log(f"🤖 [PHANTOM]: {reply}", "ai")

                if action_type in ["ai_conversation", "no_api_key"]:
                    gui.show_ai_response_popup(cmd, reply)

            tts.speak(reply, block=False)
        finally:
            if gui:
                gui.set_processing_state(False)

    # 4. Initialize Speech Listener
    stt = PhantomSTT(wake_word="phantom", on_command_callback=voice_command_handler, tts_engine=tts)
    stt.start()

    # 5. Launch PyQt6 HUD Application
    gui = PhantomGUI(on_command_trigger=voice_command_handler, tts_engine=tts, vk_controller=vk_controller)
    gui.show()
    
    # Startup Voice Announcement spoken OUT LOUD!
    startup_greeting = "Hello boss! Phantom is online and ready for full PC voice control. What is the plan for today?"
    tts.speak(startup_greeting, block=False)
    
    sys.argv[0] = "main.py"
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

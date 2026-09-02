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

    # 3. Master All-Rounder Voice Command Dispatcher
    def voice_command_handler(command_text):
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

            # 2. Direct Window Controls (Minimize, Maximize, Close) - TOP PRIORITY MATCHING!
            if any(k in cmd for k in ["minimize", "minimise", "maximize", "maximise", "close window"]):
                success, msg = vision.click_target(cmd)
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
                
                # If target was not found directly, trigger Gemini Action Planner!
                if not success and brain.gemini_available:
                    print(f"[PHANTOM DISPATCHER] Target '{target}' not found directly. Requesting Gemini Step-by-Step Directions...")
                    steps = brain.get_action_steps(cmd)
                    if steps:
                        for step in steps:
                            act = step.get("action")
                            tgt = step.get("target", "")
                            if act == "click":
                                vision.click_target(tgt, double_click=False)
                            elif act == "double_click":
                                vision.click_target(tgt, double_click=True)
                            elif act == "open_desktop":
                                vision.show_desktop_home()
                            elif act == "type":
                                vision.type_text(tgt)
                            elif act == "shortcut":
                                vision.execute_shortcut(tgt)
                            elif act == "scroll":
                                vision.scroll_screen(tgt)
                        tts.speak(f"Executed Gemini steps for {cmd}", block=False)
                        return

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

            # 11. Dynamic Application Launcher & Desktop Finder Fallback
            if "open" in cmd or "launch" in cmd or "start" in cmd:
                target_app = clean_command_target(cmd, prefix_to_remove="open|launch|start")
                
                # Check Desktop Finder first
                success, message = vision.open_desktop_item(target_app)
                if not success:
                    # Check App Registry & Existing Open Windows!
                    success, message = launcher.open_app(target_app)
                
                # If still not found, try Screen Vision Clicker
                if not success:
                    success, message = vision.click_target(target_app, double_click=True)

                elapsed_ms = (time.time() - start_time) * 1000
                status_str = f"✨ [FLASH TIME]: {elapsed_ms:.1f} ms | Status: {message}"
                print(status_str)
                
                if success:
                    reply = message
                else:
                    reply = f"Sorry boss, I could not find {target_app} on PC."
                    
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
    global gui
    gui = PhantomGUI(on_command_trigger=voice_command_handler, tts_engine=tts)
    gui.show()
    
    # Startup Voice Announcement spoken OUT LOUD!
    startup_greeting = "Hello boss! Phantom is online and ready for full PC voice control. What is the plan for today?"
    tts.speak(startup_greeting, block=False)
    
    sys.argv[0] = "main.py"
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

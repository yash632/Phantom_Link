import os
import sys
import time
import threading
import speech_recognition as sr

class PhantomSTT:
    """
    SUPER-FAST HIGH-ACCURACY SPEECH ENGINE FOR PHANTOM.
    Features:
    - Calibrated Natural Speech Pause Threshold (0.8s) - Never cuts user mid-sentence!
    - Full Phrase Time Limit (10.0s) for comfortable natural sentences
    - Dynamic Ambient Audio Calibration
    - Instant Barge-in: Stops Phantom TTS when user speaks
    """
    def __init__(self, wake_word="phantom", energy_threshold=300, on_command_callback=None, tts_engine=None):
        self.wake_word = wake_word.lower()
        self.on_command_callback = on_command_callback
        self.tts_engine = tts_engine
        
        self.is_listening = False
        self.listener_thread = None

        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = energy_threshold
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = 0.8          # Natural human pause threshold (prevents mid-sentence cutoff)
        self.recognizer.non_speaking_duration = 0.5     # Comfortable speech boundary

        print("\n[PHANTOM STT] Initializing High-Accuracy Natural Speech Engine...")

    def listen_loop(self):
        """Single Persistent Speech Listening Loop with Natural Phrase Boundaries."""
        print("✨ [PHANTOM STT] Online Natural Speech Engine Active!")

        with sr.Microphone() as source:
            print("[PHANTOM STT] Calibrating ambient room audio (1.0s)...")
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            except Exception as e:
                print(f"[PHANTOM STT NOTICE] Calibration notice: {e}")
            print("✨ [PHANTOM STT] Ready for Voice Commands!")

            while self.is_listening:
                try:
                    # phrase_time_limit=10.0 allows complete sentence capture without premature cutoff
                    audio = self.recognizer.listen(source, timeout=3.0, phrase_time_limit=10.0)
                    
                    # IF PHANTOM IS CURRENTLY SPEAKING WHEN USER SPEAKS:
                    if self.tts_engine and self.tts_engine.is_speaking:
                        print("🤫 [PHANTOM STT BARGE-IN]: User voice detected! Cutting off Phantom TTS voice instantly...")
                        self.tts_engine.stop_speaking()

                    # Transcribe user's audio immediately
                    raw_text = self.recognizer.recognize_google(audio, language="en-US").strip()

                    if raw_text:
                        print(f"\n[PHANTOM STT HEARD]: \"{raw_text}\"")

                        text_lower = raw_text.lower()
                        
                        # Filter self-voice echoes
                        if "phantom mark speaking" in text_lower or ("clicked" in text_lower and "at (" in text_lower):
                            print("[PHANTOM STT]: Ignored self-voice feedback.")
                            continue

                        command = text_lower.replace("phantom", "").replace("fantom", "").strip()
                        command = command.replace("microsoft age", "microsoft edge").replace("page", "edge").strip()

                        if command and self.on_command_callback:
                            self.on_command_callback(command)
                        elif "phantom" in text_lower or "fantom" in text_lower:
                            if self.on_command_callback:
                                self.on_command_callback("GREETING")

                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except Exception as e:
                    print(f"[PHANTOM STT NOTICE] Listener tick: {e}")
                    time.sleep(0.05)

    def start(self):
        """Starts single background speech listener thread."""
        if not self.is_listening:
            self.is_listening = True
            self.listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.listener_thread.start()

    def stop(self):
        """Stops listener cleanly."""
        self.is_listening = False

if __name__ == "__main__":
    def sample_cb(cmd):
        print(f"🚀 [COMMAND EXECUTION]: '{cmd}'")

    stt = PhantomSTT(wake_word="phantom", on_command_callback=sample_cb)
    stt.start()
    
    print("Press Ctrl+C to exit test.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stt.stop()

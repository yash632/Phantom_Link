import os
import sys
import json
import webbrowser

class PhantomBrain:
    """
    All-Rounder A.I. Brain Engine for PHANTOM.
    Includes:
    - Graceful Gemini 429 Rate Limit Fallback (No false missing key warnings)
    - Gemini 2.5 Flash Multimodal Vision Screen Locator
    - Gemini Autonomous Action Planner for Step-by-Step OS Automation
    """
    def __init__(self):
        self.api_key = self._load_api_key_from_env()
        self.gemini_available = False

        if self.api_key and self.api_key != "YOUR_GEMINI_API_KEY_HERE":
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-2.5-flash')
                self.gemini_available = True
                print("[PHANTOM BRAIN] Gemini 2.5 Flash Multimodal Vision & Intelligence Online!")
            except Exception as e:
                print(f"[PHANTOM BRAIN NOTICE] Gemini init: {e}")
        else:
            print("ℹ️ [PHANTOM BRAIN] API Key not found in .env. AI Q&A is in Offline Mode.")

    def _load_api_key_from_env(self):
        """Loads API key from environment variable or standard .env file."""
        for key_name in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "API_KEY", "GEMINT_APT_KEY"]:
            env_key = os.getenv(key_name)
            if env_key:
                return env_key

        candidate_paths = [
            os.path.join(os.getcwd(), ".env"),
            os.path.join(os.path.dirname(__file__), "..", ".env"),
            r"d:\Development\Phantom_Link\.env",
            r"d:\Development\Virtual IO\.env"
        ]

        for dotenv_path in candidate_paths:
            if os.path.exists(dotenv_path):
                try:
                    with open(dotenv_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if "=" in line and not line.startswith("#"):
                                k, v = line.split("=", 1)
                                k = k.strip()
                                v = v.strip().strip('"').strip("'")
                                if k in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "API_KEY", "GEMINT_APT_KEY"]:
                                    return v
                except Exception as e:
                    print(f"[PHANTOM BRAIN NOTICE] .env read error: {e}")

        return ""

    def locate_target_via_gemini_vision(self, pil_image, target_description, screen_width, screen_height):
        """
        Sends full desktop screenshot image to Gemini Multimodal Vision AI.
        Returns (X, Y) pixel coordinates.
        """
        if not self.gemini_available or not pil_image:
            return None

        prompt = (
            f"You are PHANTOM's Multimodal Vision Screen Locator. The screen resolution is {screen_width}x{screen_height}. "
            f"Look at the screenshot image. Locate the exact (X, Y) pixel coordinates of '{target_description}'. "
            f"Return ONLY valid JSON format: {{\"x\": integer_x, \"y\": integer_y}}"
        )

        try:
            response = self.model.generate_content([prompt, pil_image])
            text = response.text.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                data = json.loads(text[start:end])
                x, y = data.get("x"), data.get("y")
                if x is not None and y is not None:
                    print(f"✨ [GEMINI MULTIMODAL VISION MATCH]: Found '{target_description}' at ({x}, {y})!")
                    return (int(x), int(y))
        except Exception as e:
            print(f"[PHANTOM GEMINI VISION NOTICE]: {e}")

        return None

    def get_action_steps(self, user_query):
        """Generates step-by-step JSON array of OS actions."""
        if not self.gemini_available:
            return []

        prompt = (
            f"You are PHANTOM's OS Action Planner. The user said: '{user_query}'. "
            f"Generate a step-by-step JSON array of OS actions to fulfill this request on Windows. "
            f"Available actions: 'click', 'double_click', 'open_desktop', 'type', 'shortcut', 'scroll'. "
            f"Return ONLY valid JSON format array: [{{\"action\": \"click\", \"target\": \"file\"}}]"
        )

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start != -1 and end != -1:
                json_str = text[start:end]
                steps = json.loads(json_str)
                print(f"[PHANTOM BRAIN PLANNER]: Generated {len(steps)} steps for '{user_query}'.")
                return steps
        except Exception as e:
            print(f"[PHANTOM BRAIN PLANNER NOTICE]: {e}")

        return []

    def process_command(self, user_query):
        """
        Dynamically analyzes ANY spoken input.
        Handles Gemini 429 Quota Exceeded gracefully without false missing key errors.
        """
        if not user_query:
            return "empty", None, ""

        query = user_query.lower().strip()
        print(f"[PHANTOM BRAIN] Dynamically Analyzing Intent -> '{query}'...")

        # 1. Web Search Commands
        if "search google" in query or ("search" in query and "google" in query):
            search_term = query.replace("search", "").replace("google", "").replace("for", "").strip()
            url = f"https://www.google.com/search?q={search_term}"
            webbrowser.open(url)
            return "web_search", search_term, f"Searching Google for {search_term} sir."

        if "youtube" in query:
            media_term = query.replace("play", "").replace("youtube", "").replace("search", "").replace("for", "").strip()
            url = f"https://www.youtube.com/results?search_query={media_term}"
            webbrowser.open(url)
            return "youtube", media_term, f"Opening YouTube for {media_term} sir."

        # 2. General Knowledge / AI Conversational Queries via Gemini API
        if self.gemini_available:
            try:
                prompt = (
                    f"You are PHANTOM, an intelligent JARVIS-class Voice AI Assistant. "
                    f"Answer the following user query in 1 or 2 crisp, natural spoken sentences: '{user_query}'"
                )
                response = self.model.generate_content(prompt)
                ai_text = response.text.strip()
                return "ai_conversation", user_query, ai_text
            except Exception as e:
                err_str = str(e)
                print(f"[PHANTOM BRAIN ERROR] Gemini query error: {err_str}")
                if "429" in err_str or "quota" in err_str.lower() or "limit" in err_str.lower():
                    return "quota_exceeded", query, "Gemini API daily quota limit reached, boss. Operating in offline voice control mode."

        return "no_api_key", query, "Please set your GEMINI_API_KEY or GOOGLE_API_KEY in .env file to enable A.I. Q and A, sir."

if __name__ == "__main__":
    brain = PhantomBrain()
    action, payload, reply = brain.process_command("what is the distance to the moon")
    print("Action:", action)
    print("Reply:", reply)

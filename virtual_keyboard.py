import cv2
import mediapipe as mp
import pyautogui
import winsound
import tkinter as tk
import threading
import time
import math
import collections

import os
from PIL import Image, ImageTk

pyautogui.FAILSAFE = False

class TopRow3DDipVirtualKeyboard:
    def __init__(self):
        self.is_running = True
        self.last_action_time = {}
        self.global_last_action = 0.0

        # EMA Landmark Smoothing
        self.smoothed_landmarks = {}
        self.ema_alpha = 0.48

        # Dynamic Tap Impulse (Velocity Strike) State Tracking
        self.finger_y_history = collections.defaultdict(lambda: collections.deque(maxlen=6))
        self.finger_states = collections.defaultdict(lambda: 'READY')
        self.last_strike_time = collections.defaultdict(float)
        self.peak_pre_strike_y = collections.defaultdict(lambda: 0.0)

        # Thumb Space State
        self.thumb_y_history = collections.defaultdict(lambda: collections.deque(maxlen=6))
        self.thumb_states = collections.defaultdict(lambda: 'READY')

        # Gestures & Selection States
        self.index_are_touching = False
        self.thumbs_are_touching = False
        self.last_backspace_time = 0.0

        # Visual Feedback, Window Movement & Mouse Mode States
        self.finger_status = {}
        self.last_triggered_key = ""
        self.flash_display_time = 0.0
        self.hud_visible = True
        self.drag_x = 0
        self.drag_y = 0

        # Virtual Mouse States & EMA Jitter Filter
        self.mouse_mode_active = False
        self.dpi_speed = 5.5
        self.prev_pinch_pt = None
        self.is_pinching = False
        self.smooth_mouse_dx = 0.0
        self.smooth_mouse_dy = 0.0
        self.mouse_alpha = 0.35

        # Virtual Mouse Click & Toggle Drag States
        self.mouse_middle_state = 'READY'
        self.mouse_ring_state = 'READY'
        self.pinky_thumb_state = 'READY'
        self.drag_mode_active = False
        self.last_middle_click_time = 0.0
        self.middle_click_count = 0
        self.mouse_middle_y_hist = collections.deque(maxlen=6)
        self.mouse_ring_y_hist = collections.deque(maxlen=6)
        self.mouse_index_y_hist = collections.deque(maxlen=6)

        # Setup Floating HUD UI
        self.setup_ui()

        self.latest_display_frame = None

        # Start Camera & AI Hand Tracking Pipeline Thread
        self.camera_thread = threading.Thread(target=self.run_cv_pipeline, daemon=True)
        self.camera_thread.start()

        # Start Dedicated Display Thread (Prevents UI hold/drag from blocking camera capture)
        self.display_thread = threading.Thread(target=self.run_display_pipeline, daemon=True)
        self.display_thread.start()

    # =========================================================================
    # 1. FLOATING OVERLAY UI (Transparent, Draggable & Single Active Key Display)
    # =========================================================================
    def setup_ui(self):
        self.root = tk.Tk()
        self.root.title("AI Virtual Keyboard & Mouse Edition")

        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)

        TRANS_COLOR = "#000001"
        self.root.wm_attributes("-transparentcolor", TRANS_COLOR)
        self.root.configure(bg=TRANS_COLOR)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w, win_h = 980, 175
        x_pos = int((screen_w - win_w) / 2)
        y_pos = screen_h - win_h - 45
        self.root.geometry(f"{win_w}x{win_h}+{x_pos}+{y_pos}")

        self.canvas = tk.Canvas(self.root, bg=TRANS_COLOR, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Drag-to-Move Mouse Bindings
        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)

        # Show/Hide Hotkey Binding (F9)
        self.root.bind_all("<F9>", lambda event: self.toggle_hud())

        # Runtime DPI Control Hotkeys (F8: Decrease DPI, F10: Increase DPI)
        self.root.bind_all("<F8>", lambda event: self.adjust_dpi(-0.5))
        self.root.bind_all("<F10>", lambda event: self.adjust_dpi(0.5))

        self.update_ui_loop()

    def adjust_dpi(self, delta):
        self.dpi_speed = round(max(0.5, min(10.0, self.dpi_speed + delta)), 1)
        print(f"[INFO] A.I. Virtual Mouse DPI set to: {self.dpi_speed}x")

    def start_move(self, event):
        self.drag_x = event.x
        self.drag_y = event.y

    def do_move(self, event):
        x = self.root.winfo_x() + (event.x - self.drag_x)
        y = self.root.winfo_y() + (event.y - self.drag_y)
        self.root.geometry(f"+{x}+{y}")

    def toggle_hud(self):
        self.hud_visible = not self.hud_visible
        if not self.hud_visible:
            print("[INFO] HUD Collapsed to Mini Pill (Press F9 or Click Pill to Show)")
        else:
            print("[INFO] HUD Expanded")

    def update_ui_loop(self):
        if not self.is_running:
            return

        self.root.attributes("-topmost", True)
        self.canvas.delete("all")

        now = time.time()
        is_flashing = (now - self.flash_display_time) < 0.35

        # If Collapsed / Hidden mode: render a sleek floating mini pill
        if not self.hud_visible:
            self.draw_rounded_rect(390, 2, 590, 28, 12, "#1e1e2e", "#40a02b")
            self.canvas.create_text(490, 15, text="⌨ SHOW KEYBOARD (F9)", font=("Segoe UI", 9, "bold"), fill="#a6e3a1")
            self.root.after(50, self.update_ui_loop)
            return

        # 0. Render Photorealistic / Clean Mouse HUD Pill when 1 Hand is detected (Mouse Mode)
        if self.mouse_mode_active:
            if self.drag_mode_active:
                pill_bg = "#3a080c"   # Deep dark crimson background
                pill_bdr = "#ff3344"  # Vibrant neon red outline
                pill_txt = "#ff6677"  # Bright high-contrast red text
                action_tag = "✊ DRAG MODE ACTIVE (SELECT/DRAG)"
            elif (now - self.flash_display_time) < 1.2 and self.last_triggered_key:
                pill_bg = "#1e1e2e"
                pill_bdr = "#04a5e5"
                pill_txt = "#89dceb"
                action_tag = f"✨ ACTION: {self.last_triggered_key}"
            elif self.is_pinching:
                pill_bg = "#1e1e2e"
                pill_bdr = "#40a02b"
                pill_txt = "#a6e3a1"
                action_tag = "🤏 PINCH MOVING"
            else:
                pill_bg = "#1e1e2e"
                pill_bdr = "#04a5e5"
                pill_txt = "#89dceb"
                action_tag = "🖐 PINCH TO MOVE"

            # Ultra-wide pill bounds (60 to 920 = 860px wide) so text never clips
            self.draw_rounded_rect(60, 2, 920, 28, 12, pill_bg, pill_bdr)
            mouse_status = f"🖱 MOUSE ACTIVE   •   DPI: {self.dpi_speed}x   •   {action_tag}   •   [F8: DPI- | F10: DPI+]"
            self.canvas.create_text(490, 15, text=mouse_status, font=("Segoe UI", 9, "bold"), fill=pill_txt)

            self.root.after(20, self.update_ui_loop)
            return

        # 1. Header Drag & Control Handle Bar (Sleek Modern Pill)
        self.draw_rounded_rect(330, 2, 650, 28, 12, "#1e1e2e", "#45475a")
        self.canvas.create_text(490, 15, text="⠿ DRAG TO MOVE   •   [F9] HIDE HUD", font=("Segoe UI", 9, "bold"), fill="#cdd6f4")

        finger_columns = [
            ('L_PINKY', 'L Pinky', 'Q', 'A', 'Z'),
            ('L_RING', 'L Ring', 'W', 'S', 'X'),
            ('L_MIDDLE', 'L Mid', 'E', 'D', 'C'),
            ('L_INDEX', 'L Index', 'R', 'F', 'V'),
            ('R_INDEX', 'R Index', 'U', 'J', 'M'),
            ('R_MIDDLE', 'R Mid', 'I', 'K', ','),
            ('R_RING', 'R Ring', 'O', 'L', '.'),
            ('R_PINKY', 'R Pinky', 'P', ';', '/')
        ]

        start_x = 42
        box_w = 78
        gap = 36
        box_h = 60
        start_y = 40

        for idx, (f_id, f_label, def_top, def_mid, def_low) in enumerate(finger_columns):
            x = start_x + idx * (box_w + gap)
            f_data = self.finger_status.get(f_id, {
                'key': def_mid, 
                'top_key': def_top, 
                'mid_key': def_mid, 
                'low_key': def_low, 
                'row': 'MID', 
                'flex': 0.0, 
                'active': False, 
                'stretched': False
            })

            active_key = f_data.get('key', def_mid)
            active_row = f_data.get('row', 'MID')
            is_active = f_data.get('active', False)
            is_stretched = f_data.get('stretched', False)
            is_key_flashing = is_flashing and (self.last_triggered_key == active_key)

            # Dip bounce animation on strike
            f_dip = 8 if is_active else 0
            by1 = start_y + f_dip
            by2 = by1 + box_h
            bx1 = x
            bx2 = x + box_w
            cx = (bx1 + bx2) / 2

            # Empty string fill="" for 100% transparent inside fill!
            if is_active or is_key_flashing:
                bg_col, txt_col, bdr_col = "#a6e3a1", "#11111b", "#40a02b"  # Solid Neon Green Press
            elif is_stretched:
                bg_col, txt_col, bdr_col = "", "#fab387", "#fe640b"  # 100% Transparent Orange Stretch
            elif active_row == 'TOP':
                bg_col, txt_col, bdr_col = "", "#89dceb", "#04a5e5"  # 100% Transparent Cyan Top
            elif active_row == 'MID':
                bg_col, txt_col, bdr_col = "", "#a6e3a1", "#40a02b"  # 100% Transparent Emerald Mid
            else:  # LOW
                bg_col, txt_col, bdr_col = "", "#b4befe", "#7287fd"  # 100% Transparent Lavender Low

            # 1. Compact Active Key Box (100% Transparent Inside Fill)
            self.draw_rounded_rect(bx1, by1, bx2, by2, 10, bg_col, bdr_col)

            # High contrast glowing text (18pt)
            self.canvas.create_text(cx, by1 + 22, text=active_key, font=("Segoe UI", 18, "bold"), fill=txt_col)

            # 2. Row Tag & Finger Label
            row_tag = f"[{active_row}]" if not is_stretched else "[STRETCH]"
            self.canvas.create_text(cx, by1 + 45, text=row_tag, font=("Segoe UI", 7, "bold"), fill=txt_col)
            self.canvas.create_text(cx, by2 + 14, text=f_label, font=("Segoe UI", 8, "bold"), fill="#cdd6f4")

        if is_flashing:
            if self.last_triggered_key == 'ENTER':
                toast_text = "✨ ENTER KEY"
                t_bg, t_bdr = "#cba6f7", "#8839ef"
            else:
                toast_text = f"TYPED: [{self.last_triggered_key}]"
                t_bg, t_bdr = "#f9e2af", "#df8e1d"

            self.draw_rounded_rect(340, 2, 640, 28, 6, t_bg, t_bdr)
            self.canvas.create_text(490, 15, text=toast_text, font=("Segoe UI", 11, "bold"), fill="#11111b")

        self.root.after(20, self.update_ui_loop)

    def draw_anatomical_finger(self, x, y, width, height, finger_label, active_key, row_name, is_active, is_stretched, is_flashing):
        """Draws a solid 100% visible realistic human finger with fingernail, DIP/PIP joint creases, fingertip key badge, and dip animation."""
        dip_offset = 14 if is_active else 0
        fy1 = y + dip_offset
        fy2 = y + height + dip_offset
        fx1 = x
        fx2 = x + width
        fcx = x + width / 2

        # Organic warm skin tones & state highlights
        if is_active or is_flashing:
            skin_bg, skin_bdr = "#a6e3a1", "#40a02b"  # Vibrant Green Strike Highlight
            badge_bg, badge_txt = "#11111b", "#a6e3a1"
        elif is_stretched:
            skin_bg, skin_bdr = "#fab387", "#fe640b"  # Stretch Reach
            badge_bg, badge_txt = "#11111b", "#fe640b"
        else:
            skin_bg, skin_bdr = "#e0ac69", "#b07c4b"  # Natural Human Skin Tone & Shading

            if row_name == 'TOP':
                badge_bg, badge_txt = "#89dceb", "#11111b"  # Cyan Top Row Badge
            elif row_name == 'MID':
                badge_bg, badge_txt = "#a6e3a1", "#11111b"  # Emerald Mid Row Badge
            else:  # LOW
                badge_bg, badge_txt = "#b4befe", "#11111b"  # Soft Lavender Low Row Badge

        # 1. Finger Main Body (Capsule / Rounded Polygon)
        self.draw_rounded_rect(fx1, fy1, fx2, fy2, 20, skin_bg, skin_bdr)

        # 2. Realistic Fingernail on Fingertip
        nail_w = int(width * 0.52)
        nail_x1 = fx1 + int((width - nail_w) / 2)
        nail_x2 = nail_x1 + nail_w
        nail_y1 = fy1 + 6
        nail_y2 = fy1 + 26
        self.draw_rounded_rect(nail_x1, nail_y1, nail_x2, nail_y2, 8, "#fce8e0", "#c88b52")

        # 3. Anatomical Joint Crease Lines (DIP & PIP Joints)
        dip_j_y = fy1 + int(height * 0.40)
        pip_j_y = fy1 + int(height * 0.68)
        self.canvas.create_line(fx1 + 8, dip_j_y, fx2 - 8, dip_j_y, fill=skin_bdr, width=2)
        self.canvas.create_line(fx1 + 6, pip_j_y, fx2 - 6, pip_j_y, fill=skin_bdr, width=2)

        # 4. Floating Active Key Badge directly on Fingertip
        badge_w = int(width * 0.90)
        badge_x1 = fx1 + int((width - badge_w) / 2)
        badge_x2 = badge_x1 + badge_w
        badge_y1 = fy1 + 30
        badge_y2 = fy1 + 78

        self.draw_rounded_rect(badge_x1, badge_y1, badge_x2, badge_y2, 10, badge_bg, skin_bdr)
        font_sz = 14 if active_key == 'SPACE' else 20
        self.canvas.create_text(fcx, (badge_y1 + badge_y2) / 2, text=active_key, font=("Segoe UI", font_sz, "bold"), fill=badge_txt)

        # 5. Row Tag & Finger Label
        row_tag = f"[{row_name}]" if not is_stretched else "[STRETCH]"
        tag_col = "#11111b" if (is_active or is_flashing) else "#4a2e18"
        self.canvas.create_text(fcx, fy1 + 88, text=row_tag, font=("Segoe UI", 8, "bold"), fill=tag_col)
        self.canvas.create_text(fcx, fy2 + 14, text=finger_label, font=("Segoe UI", 8, "bold"), fill="#cdd6f4")

    def draw_rounded_rect(self, x1, y1, x2, y2, r, fill, outline):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1
        ]
        return self.canvas.create_polygon(points, smooth=True, fill=fill, outline=outline, width=2)

    # =========================================================================
    # 2. KEYSTROKE EMISSION
    # =========================================================================
    def trigger_action(self, action_name, action_id="GLOBAL"):
        if not action_name or action_name == '-':
            return

        now = time.time()
        if (now - self.last_action_time.get(action_id, 0.0) < 0.22) or (now - self.global_last_action < 0.08):
            return

        self.last_action_time[action_id] = now
        self.global_last_action = now
        self.flash_display_time = now
        self.last_triggered_key = action_name

        threading.Thread(target=lambda: winsound.Beep(1500, 40), daemon=True).start()

        print(f"[KEYBOARD] Action: [{action_name}]")
        try:
            if action_name == 'SPACE':
                pyautogui.press('space')
            elif action_name == 'BACKSPACE':
                pyautogui.press('backspace')
            elif action_name == 'ENTER':
                pyautogui.press('enter')
            else:
                pyautogui.press(action_name.lower())
        except Exception as e:
            print(f"Key trigger error: {e}")

    # =========================================================================
    # 3. GEOMETRY & 3D JOINT ANGLE HELPERS
    # =========================================================================
    def dist(self, p1, p2):
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    def calculate_3d_angle(self, a, b, c):
        """Calculates angle ABC in 3D degrees (MCP -> PIP -> TIP)"""
        ba = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
        bc = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
        dot = ba[0]*bc[0] + ba[1]*bc[1] + ba[2]*bc[2]
        mag_ba = math.sqrt(ba[0]**2 + ba[1]**2 + ba[2]**2)
        mag_bc = math.sqrt(bc[0]**2 + bc[1]**2 + bc[2]**2)
        if mag_ba * mag_bc == 0:
            return 180.0
        cosine = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
        return math.degrees(math.acos(cosine))

    def apply_ema_smoothing(self, hand_id, raw_landmarks):
        if hand_id not in self.smoothed_landmarks:
            self.smoothed_landmarks[hand_id] = [[lm.x, lm.y, lm.z] for lm in raw_landmarks]
            return self.smoothed_landmarks[hand_id]

        smoothed = []
        for i, lm in enumerate(raw_landmarks):
            prev = self.smoothed_landmarks[hand_id][i]
            sx = self.ema_alpha * lm.x + (1 - self.ema_alpha) * prev[0]
            sy = self.ema_alpha * lm.y + (1 - self.ema_alpha) * prev[1]
            sz = self.ema_alpha * lm.z + (1 - self.ema_alpha) * prev[2]
            smoothed.append([sx, sy, sz])

        self.smoothed_landmarks[hand_id] = smoothed
        return smoothed

    # =========================================================================
    # 4. CV TRACKING PIPELINE (3D JOINT FLEXION & DIP)
    # =========================================================================
    def run_cv_pipeline(self):
        mp_hands = mp.solutions.hands
        mp_draw = mp.solutions.drawing_utils
        
        hands = mp_hands.Hands(
            max_num_hands=2,
            min_detection_confidence=0.70,
            min_tracking_confidence=0.70
        )

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[ERROR] Webcam could not be opened.")
            return

        # Window display handled in dedicated run_display_pipeline thread

        print("[INFO] AI Virtual Keyboard (3D Flex Dip - Top Row) Active!")

        finger_tips = {
            'INDEX': 8,
            'MIDDLE': 12,
            'RING': 16,
            'PINKY': 20,
        }

        while self.is_running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            # Daylight & glare compensation: Normalize brightness & contrast via CLAHE on L-channel
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l_chan, a_chan, b_chan = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l_chan)
            balanced_bgr = cv2.cvtColor(cv2.merge((cl, a_chan, b_chan)), cv2.COLOR_LAB2BGR)
            rgb_frame = cv2.cvtColor(balanced_bgr, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb_frame)
            now = time.time()

            current_status = {}
            assigned_hands = {}

            if results.multi_hand_landmarks:
                detected = []
                for idx, raw_lms in enumerate(results.multi_hand_landmarks):
                    conf = 1.0
                    if results.multi_handedness and idx < len(results.multi_handedness):
                        conf = results.multi_handedness[idx].classification[0].score

                    if conf < 0.60:
                        continue  # Skip low-confidence artifacts/reflections

                    smooth_lms = self.apply_ema_smoothing(idx, raw_lms.landmark)
                    # Use center of palm (wrist + MCPs)
                    mean_x = (smooth_lms[0][0] + smooth_lms[5][0] + smooth_lms[17][0]) / 3
                    detected.append((mean_x, smooth_lms, raw_lms, conf))

                # Discard duplicate / phantom second hand detections on the same physical hand
                if len(detected) >= 2:
                    wrist_dist = self.dist(detected[0][1][0], detected[1][1][0])
                    palm_dist = self.dist(detected[0][1][9], detected[1][1][9])
                    # If two detections are physically overlapping (wrist < 0.20 or palm < 0.18), keep only the higher confidence one
                    if wrist_dist < 0.20 or palm_dist < 0.18:
                        if detected[1][3] > detected[0][3]:
                            detected = [detected[1]]
                        else:
                            detected = [detected[0]]

                detected.sort(key=lambda x: x[0])
                if len(detected) == 1:
                    # In mirrored view: Left side of image (x < 0.52) is User's LEFT hand
                    label = "Left" if detected[0][0] < 0.52 else "Right"
                    assigned_hands[label] = (detected[0][0], detected[0][1], detected[0][2])
                elif len(detected) >= 2:
                    assigned_hands["Left"] = (detected[0][0], detected[0][1], detected[0][2])
                    assigned_hands["Right"] = (detected[1][0], detected[1][1], detected[1][2])
            else:
                self.smoothed_landmarks.clear()

            # Global hand scale reference
            ref_hand_scale = 0.20
            if assigned_hands:
                scales = [max(0.08, self.dist(h_data[1][0], h_data[1][9])) for h_data in assigned_hands.values()]
                ref_hand_scale = sum(scales) / len(scales)

            # -----------------------------------------------------------------
            # A.I. VIRTUAL MOUSE PIPELINE (Active ONLY when 1 Hand is Visible)
            # -----------------------------------------------------------------
            if len(assigned_hands) == 1:
                self.mouse_mode_active = True
                single_hand_data = list(assigned_hands.values())[0]
                smooth_lms = single_hand_data[1]

                thumb_tip = smooth_lms[4]
                index_tip = smooth_lms[8]
                pinch_dist = self.dist(thumb_tip, index_tip) / ref_hand_scale
                
                # Pinch-to-Move (Relative physical mouse behavior with zero jump)
                if pinch_dist < 0.14:
                    raw_x = (thumb_tip[0] + index_tip[0]) / 2
                    raw_y = (thumb_tip[1] + index_tip[1]) / 2

                    if not self.is_pinching:
                        # 1. ANCHOR FRAME: Initialize anchor position when pinch begins (ZERO MOUSE JUMP)
                        self.is_pinching = True
                        self.prev_pinch_pt = (raw_x, raw_y)
                        self.smooth_mouse_dx = 0.0
                        self.smooth_mouse_dy = 0.0
                    else:
                        # 2. PINCH DRAG: Pure relative delta from previous pinched frame
                        if self.prev_pinch_pt is not None:
                            raw_dx = (raw_x - self.prev_pinch_pt[0]) * 1600.0 * (self.dpi_speed / 2.5)
                            raw_dy = (raw_y - self.prev_pinch_pt[1]) * 1600.0 * (self.dpi_speed / 2.5)

                            # Smooth relative delta
                            self.smooth_mouse_dx = self.smooth_mouse_dx * (1 - self.mouse_alpha) + raw_dx * self.mouse_alpha
                            self.smooth_mouse_dy = self.smooth_mouse_dy * (1 - self.mouse_alpha) + raw_dy * self.mouse_alpha

                            if abs(self.smooth_mouse_dx) > 0.8 or abs(self.smooth_mouse_dy) > 0.8:
                                pyautogui.moveRel(int(self.smooth_mouse_dx), int(self.smooth_mouse_dy), _pause=False)

                        self.prev_pinch_pt = (raw_x, raw_y)

                    # Visual feedback on camera preview
                    cx, cy = int(raw_x * w), int(raw_y * h)
                    cv2.circle(frame, (cx, cy), 18, (0, 255, 0), cv2.FILLED)
                    cv2.putText(frame, f"MOUSE PINCH [{self.dpi_speed}x]", (cx - 65, cy - 22), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                else:
                    self.is_pinching = False
                    self.prev_pinch_pt = None
                    self.smooth_mouse_dx = 0.0
                    self.smooth_mouse_dy = 0.0
                # -------------------------------------------------------------
                # 1. TOGGLE DRAG-AND-DROP MODE (Pinky + Thumb Touch)
                # -------------------------------------------------------------
                pinky_tip_pt = smooth_lms[20]
                pinky_thumb_dist = self.dist(thumb_tip, pinky_tip_pt) / ref_hand_scale
                pinky_index_dist = self.dist(index_tip, pinky_tip_pt) / ref_hand_scale

                if pinky_thumb_dist < 0.14 and self.pinky_thumb_state == 'READY':
                    self.pinky_thumb_state = 'TOUCHED'
                    self.drag_mode_active = not self.drag_mode_active
                    # Flush click histories so hand curling does not trigger clicks
                    self.mouse_middle_y_hist.clear()
                    self.mouse_ring_y_hist.clear()
                    self.mouse_index_y_hist.clear()
                    self.mouse_middle_state = 'READY'
                    self.mouse_ring_state = 'READY'

                    if self.drag_mode_active:
                        pyautogui.mouseDown()
                        self.flash_display_time = now
                        self.last_triggered_key = "DRAG MODE ON (SELECTING)"
                        threading.Thread(target=lambda: winsound.Beep(1600, 45), daemon=True).start()
                        print("[INFO] TOGGLE DRAG MODE: ON (MouseDown)")
                    else:
                        pyautogui.mouseUp()
                        self.flash_display_time = now
                        self.last_triggered_key = "DRAG MODE OFF (RELEASED)"
                        threading.Thread(target=lambda: winsound.Beep(1000, 45), daemon=True).start()
                        print("[INFO] TOGGLE DRAG MODE: OFF (MouseUp)")
                elif pinky_thumb_dist >= 0.20:
                    self.pinky_thumb_state = 'READY'

                # Visual overlay feedback for Toggle Drag Mode
                if self.drag_mode_active:
                    cv2.putText(frame, "[DRAG MODE ON - SELECTING]", (15, h - 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.70, (255, 255, 0), 2)

                # -------------------------------------------------------------
                # 2. VIRTUAL MOUSE CLICK GESTURES (Disabled during Drag Mode & Pinky Pinch):
                #    - Middle Finger Dip -> 1x Left Click / 2x Double Click / 3x Triple Click (Isolated)
                #    - Ring Finger Dip -> Right Click (Isolated)
                # -------------------------------------------------------------
                is_pinky_in_gesture = (pinky_thumb_dist < 0.26) or (pinky_index_dist < 0.24) or (self.pinky_thumb_state == 'TOUCHED')

                if not self.drag_mode_active and not is_pinky_in_gesture:
                    middle_tip_pt = smooth_lms[12]
                    middle_mcp_pt = smooth_lms[9]
                    ring_tip_pt = smooth_lms[16]
                    ring_mcp_pt = smooth_lms[13]
                    index_mcp_pt = smooth_lms[5]

                    mid_rel_y = (middle_tip_pt[1] - middle_mcp_pt[1]) / ref_hand_scale
                    rng_rel_y = (ring_tip_pt[1] - ring_mcp_pt[1]) / ref_hand_scale
                    idx_rel_y = (index_tip[1] - index_mcp_pt[1]) / ref_hand_scale

                    self.mouse_middle_y_hist.append((mid_rel_y, now))
                    self.mouse_ring_y_hist.append((rng_rel_y, now))
                    self.mouse_index_y_hist.append((idx_rel_y, now))

                    # Evaluate Middle Finger Multi-Tap (1x Left, 2x Double, 3x Triple Click)
                    m_vel, m_dy = 0.0, 0.0
                    if len(self.mouse_middle_y_hist) >= 3:
                        m_dt = self.mouse_middle_y_hist[-1][1] - self.mouse_middle_y_hist[0][1]
                        m_dy = self.mouse_middle_y_hist[-1][0] - self.mouse_middle_y_hist[0][0]
                        m_vel = (m_dy / m_dt) if m_dt > 0.001 else 0.0

                    r_vel, r_dy = 0.0, 0.0
                    if len(self.mouse_ring_y_hist) >= 3:
                        r_dt = self.mouse_ring_y_hist[-1][1] - self.mouse_ring_y_hist[0][1]
                        r_dy = self.mouse_ring_y_hist[-1][0] - self.mouse_ring_y_hist[0][0]
                        r_vel = (r_dy / r_dt) if r_dt > 0.001 else 0.0

                    # Isolation check: Middle must move downward while Ring is NOT dipping simultaneously
                    is_mid_isolated = (m_vel - r_vel > 0.35) and (m_dy > r_dy + 0.008) and (r_dy < 0.016) and (pinch_dist > 0.16)

                    if m_vel > 0.88 and m_dy > 0.018 and is_mid_isolated and self.mouse_middle_state == 'READY':
                        self.mouse_middle_state = 'DIPPED'
                        cx, cy = int(middle_tip_pt[0] * w), int(middle_tip_pt[1] * h)

                        # Track Multi-Tap interval (< 0.38s)
                        if (now - self.last_middle_click_time) < 0.38:
                            self.middle_click_count += 1
                        else:
                            self.middle_click_count = 1

                        self.last_middle_click_time = now
                        self.flash_display_time = now

                        if self.middle_click_count == 1:
                            pyautogui.click()
                            self.last_triggered_key = "LEFT CLICK"
                            cv2.circle(frame, (cx, cy), 24, (0, 255, 0), cv2.FILLED)
                            cv2.putText(frame, "LEFT CLICK", (cx - 40, cy - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)
                            threading.Thread(target=lambda: winsound.Beep(1800, 35), daemon=True).start()
                        elif self.middle_click_count == 2:
                            pyautogui.click(clicks=2)
                            self.last_triggered_key = "DOUBLE CLICK"
                            cv2.circle(frame, (cx, cy), 24, (255, 255, 0), cv2.FILLED)
                            cv2.putText(frame, "DOUBLE CLICK", (cx - 50, cy - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 0), 2)
                            threading.Thread(target=lambda: winsound.Beep(2000, 35), daemon=True).start()
                        elif self.middle_click_count >= 3:
                            pyautogui.click(clicks=3)
                            self.last_triggered_key = "TRIPLE CLICK"
                            self.middle_click_count = 0  # Reset after triple click
                            cv2.circle(frame, (cx, cy), 24, (0, 255, 255), cv2.FILLED)
                            cv2.putText(frame, "TRIPLE CLICK", (cx - 50, cy - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
                            threading.Thread(target=lambda: winsound.Beep(2200, 45), daemon=True).start()
                    elif m_vel < 0.25 or m_dy < 0.005 or (now - self.last_middle_click_time > 0.25):
                        self.mouse_middle_state = 'READY'

                    # Isolation check: Ring must move downward while Middle is NOT dipping simultaneously
                    is_ring_isolated = (r_vel - m_vel > 0.35) and (r_dy > m_dy + 0.008) and (m_dy < 0.016) and (pinch_dist > 0.16)

                    if r_vel > 0.88 and r_dy > 0.018 and is_ring_isolated and self.mouse_ring_state == 'READY':
                        self.mouse_ring_state = 'DIPPED'
                        pyautogui.rightClick()
                        self.flash_display_time = now
                        self.last_triggered_key = "RIGHT CLICK"

                        cx, cy = int(ring_tip_pt[0] * w), int(ring_tip_pt[1] * h)
                        cv2.circle(frame, (cx, cy), 24, (255, 0, 255), cv2.FILLED)
                        cv2.putText(frame, "RIGHT CLICK", (cx - 45, cy - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 0, 255), 2)
                        threading.Thread(target=lambda: winsound.Beep(1400, 40), daemon=True).start()
                    elif r_vel < 0.25 or r_dy < 0.005 or (now - self.flash_display_time > 0.25):
                        self.mouse_ring_state = 'READY'
                else:
                    # While dragging or pinky pinching, keep click states primed and histories clear
                    self.mouse_middle_y_hist.clear()
                    self.mouse_ring_y_hist.clear()
                    self.mouse_index_y_hist.clear()
                    self.mouse_middle_state = 'READY'
                    self.mouse_ring_state = 'READY'
            else:
                # Disable Mouse Mode when 2 hands (or 0 hands) are present -> Enable Keyboard Typing Mode
                if self.drag_mode_active:
                    pyautogui.mouseUp()
                    self.drag_mode_active = False

                self.mouse_mode_active = False
                self.is_pinching = False
                self.prev_pinch_pt = None
                self.smooth_mouse_dx = 0.0
                self.smooth_mouse_dy = 0.0

            # -------------------------------------------------------------
            # GESTURE 1: ENTER (Both index Touch -> Enter)
            # -------------------------------------------------------------
            is_enter_active = False
            if "Left" in assigned_hands and "Right" in assigned_hands:
                wrist_l = assigned_hands["Left"][1][0]
                wrist_r = assigned_hands["Right"][1][0]
                # True physical hand separation check: Wrists must be clearly separated
                if self.dist(wrist_l, wrist_r) > 0.20:
                    l_index = assigned_hands["Left"][1][8]
                    r_index = assigned_hands["Right"][1][8]
                    if (self.dist(l_index, r_index) / ref_hand_scale) < 0.28:
                        is_enter_active = True
                        cx1, cy1 = int(l_index[0] * w), int(l_index[1] * h)
                        cx2, cy2 = int(r_index[0] * w), int(r_index[1] * h)
                        cv2.line(frame, (cx1, cy1), (cx2, cy2), (200, 100, 255), 4)
                        cv2.circle(frame, (int((cx1+cx2)/2), int((cy1+cy2)/2)), 24, (200, 100, 255), cv2.FILLED)
                        cv2.putText(frame, "ENTER KEY", (int((cx1+cx2)/2) - 60, int((cy1+cy2)/2) - 25),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (200, 100, 255), 2)

                        if not self.index_are_touching:
                            self.index_are_touching = True
                            self.trigger_action('ENTER', 'ENTER_TRIGGER')
                    else:
                        self.index_are_touching = False
                else:
                    self.index_are_touching = False

            # -------------------------------------------------------------
            # GESTURE 2: BACKSPACE (Both thumbs Touch Deliberately)
            # -------------------------------------------------------------
            is_backspace_active = False
            if not is_enter_active:
                if "Left" in assigned_hands and "Right" in assigned_hands:
                    wrist_l = assigned_hands["Left"][1][0]
                    wrist_r = assigned_hands["Right"][1][0]
                    if self.dist(wrist_l, wrist_r) > 0.20:
                        l_thumb = assigned_hands["Left"][1][4]
                        r_thumb = assigned_hands["Right"][1][4]
                        thumb_contact_dist = self.dist(l_thumb, r_thumb) / ref_hand_scale

                        if thumb_contact_dist < 0.25:
                            is_backspace_active = True
                            cx1, cy1 = int(l_thumb[0] * w), int(l_thumb[1] * h)
                            cx2, cy2 = int(r_thumb[0] * w), int(r_thumb[1] * h)
                            cv2.line(frame, (cx1, cy1), (cx2, cy2), (0, 0, 255), 4)
                            cv2.circle(frame, (int((cx1+cx2)/2), int((cy1+cy2)/2)), 22, (0, 0, 255), cv2.FILLED)
                            cv2.putText(frame, "BACKSPACE", (int((cx1+cx2)/2) - 60, int((cy1+cy2)/2) - 25),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                            if not self.thumbs_are_touching:
                                self.thumbs_are_touching = True
                                self.trigger_action('BACKSPACE', 'BACKSPACE_TRIGGER')
                                self.last_backspace_time = time.time()
                            else:
                                if time.time() - self.last_backspace_time > 0.30:
                                    self.trigger_action('BACKSPACE', 'BACKSPACE_TRIGGER')
                                    self.last_backspace_time = time.time()
                        else:
                            self.thumbs_are_touching = False
                    else:
                        self.thumbs_are_touching = False

            # Render hand landmarks connections on camera frame
            if self.mouse_mode_active:
                for hand_label, (mean_x, smooth_lms, raw_lms) in assigned_hands.items():
                    mp_draw.draw_landmarks(frame, raw_lms, mp_hands.HAND_CONNECTIONS)
                    wrist_pt = smooth_lms[0]
                    cv2.putText(frame, "[MOUSE MODE ACTIVE]", (int(wrist_pt[0]*w) - 65, int(wrist_pt[1]*h) + 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 200, 0), 2)

            # -----------------------------------------------------------------
            # CORE MATRIX: DYNAMIC TAP IMPULSE (VELOCITY STRIKE) ENGINE (Keyboard Mode Only)
            # -----------------------------------------------------------------
            if not self.mouse_mode_active and not is_enter_active and not is_backspace_active:
                for hand_label, (mean_x, smooth_lms, raw_lms) in assigned_hands.items():
                    mp_draw.draw_landmarks(frame, raw_lms, mp_hands.HAND_CONNECTIONS)
                    hand_prefix = 'L' if hand_label == "Left" else 'R'
                    hand_scale = max(0.08, self.dist(smooth_lms[0], smooth_lms[9]))
                    wrist_pt = smooth_lms[0]
                    now = time.time()

                    # Hand Label Tag on Camera
                    cv2.putText(frame, f"[{hand_label.upper()} HAND]", (int(wrist_pt[0]*w) - 45, int(wrist_pt[1]*h) + 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

                    # 1. Track downward velocity / impulse for each finger
                    finger_velocities = {}
                    finger_deltas = {}
                    for f_name, tip_idx in finger_tips.items():
                        f_id = f"{hand_prefix}_{f_name}"
                        mcp = smooth_lms[tip_idx - 3]
                        tip = smooth_lms[tip_idx]

                        # Relative tip Y position to MCP (knuckle)
                        rel_y = (tip[1] - mcp[1]) / hand_scale
                        f_hist = self.finger_y_history[f_id]
                        f_hist.append((rel_y, now))

                        v_down = 0.0
                        delta_y = 0.0
                        if len(f_hist) >= 3:
                            dt = f_hist[-1][1] - f_hist[0][1]
                            delta_y = f_hist[-1][0] - f_hist[0][0]
                            if dt > 0.001:
                                v_down = delta_y / dt

                        finger_velocities[f_name] = v_down
                        finger_deltas[f_name] = delta_y

                    # 2. Inward Flexion Thumb Spacebar (Thumb Tip 4 -> Index MCP 5 distance contraction)
                    thumb_tip = smooth_lms[4]
                    index_mcp = smooth_lms[5]
                    t_id = f"THUMB_{hand_label}"
                    
                    # Distance between thumb tip (4) and Index MCP (5) normalized by hand scale
                    thumb_palm_dist = self.dist(thumb_tip, index_mcp) / hand_scale
                    t_hist = self.thumb_y_history[t_id]
                    t_hist.append((thumb_palm_dist, now))

                    if len(t_hist) >= 3:
                        t_dt = t_hist[-1][1] - t_hist[0][1]
                        # Inward contraction: initial dist MINUS current dist (positive = moving INWARD towards palm)
                        t_inward_delta = t_hist[0][0] - t_hist[-1][0]
                        t_inward_vel = (t_inward_delta / t_dt) if t_dt > 0.001 else 0.0

                        # Require fast high-velocity strike (jhatka strike)
                        if t_inward_vel > 0.68 and t_inward_delta > 0.016 and self.thumb_states[t_id] == 'READY':
                            self.thumb_states[t_id] = 'DIPPED'
                            self.trigger_action('SPACE', 'SPACE_THUMB')
                            cx, cy = int(thumb_tip[0] * w), int(thumb_tip[1] * h)
                            cv2.circle(frame, (cx, cy), 22, (0, 255, 255), cv2.FILLED)
                            cv2.putText(frame, "SPACE", (cx - 30, cy - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        elif t_inward_vel < 0.20 or t_inward_delta < 0.005 or (time.time() - self.last_action_time.get('SPACE_THUMB', 0.0) > 0.22):
                            self.thumb_states[t_id] = 'READY'

                    # 3. Process each finger with Dynamic Tap Strike Trigger
                    for f_name, tip_idx in finger_tips.items():
                        f_id = f"{hand_prefix}_{f_name}"
                        tip_pos = smooth_lms[tip_idx]
                        mcp_pos = smooth_lms[tip_idx - 3]

                        v_down = finger_velocities[f_name]
                        delta_y = finger_deltas[f_name]

                        # Isolated impulse: Strike speed minus other fingers' motion
                        other_vels = [v for fn, v in finger_velocities.items() if fn != f_name]
                        baseline_vel = max(0.0, sum(other_vels) / len(other_vels)) if other_vels else 0.0
                        strike_impulse = v_down - baseline_vel

                        # Horizontal reach for Index Finger (Stretch threshold set to 0.32 for natural hand fan-out)
                        norm_x = (tip_pos[0] - mcp_pos[0]) / hand_scale
                        is_stretched = False

                        # PRE-STRIKE TARGET LOCKING: Track highest elevation (minimum Y) before dip
                        tap_state_id = f"TAP_{f_id}"
                        if self.finger_states[tap_state_id] == 'READY' and v_down <= 0.10:
                            self.peak_pre_strike_y[f_id] = rel_y
                        elif f_id not in self.peak_pre_strike_y:
                            self.peak_pre_strike_y[f_id] = rel_y
                        else:
                            self.peak_pre_strike_y[f_id] = min(self.peak_pre_strike_y[f_id], f_hist[0][0] if len(f_hist) >= 3 else rel_y)

                        start_rel_y = self.peak_pre_strike_y[f_id]

                        # 3-Tier Palm-Scaled Anatomical Row Thresholds (Relaxed & Calibrated)
                        row_tiers = {
                            'PINKY': (-0.50, -0.16),
                            'RING': (-0.55, -0.18),
                            'MIDDLE': (-0.58, -0.20),
                            'INDEX': (-0.55, -0.18)
                        }
                        top_t, mid_t = row_tiers[f_name]

                        if start_rel_y < top_t:
                            row_name = 'TOP'
                        elif start_rel_y < mid_t:
                            row_name = 'MID'
                        else:
                            row_name = 'LOW'

                        if hand_label == "Left":
                            if f_name == "PINKY":
                                curr_top, curr_mid, curr_low = "Q", "A", "Z"
                            elif f_name == "RING":
                                curr_top, curr_mid, curr_low = "W", "S", "X"
                            elif f_name == "MIDDLE":
                                curr_top, curr_mid, curr_low = "E", "D", "C"
                            elif f_name == "INDEX":
                                is_stretched = (norm_x > 0.22)
                                if is_stretched:
                                    curr_top, curr_mid, curr_low = "T", "G", "B"
                                else:
                                    curr_top, curr_mid, curr_low = "R", "F", "V"
                        else:  # Right Hand
                            if f_name == "INDEX":
                                is_stretched = (norm_x < -0.22)
                                if is_stretched:
                                    curr_top, curr_mid, curr_low = "Y", "H", "N"
                                else:
                                    curr_top, curr_mid, curr_low = "U", "J", "M"
                            elif f_name == "MIDDLE":
                                curr_top, curr_mid, curr_low = "I", "K", ","
                            elif f_name == "RING":
                                curr_top, curr_mid, curr_low = "O", "L", "."
                            elif f_name == "PINKY":
                                curr_top, curr_mid, curr_low = "P", ";", "/"

                        if row_name == 'TOP':
                            key_name = curr_top
                        elif row_name == 'MID':
                            key_name = curr_mid
                        else:
                            key_name = curr_low

                        tap_state_id = f"TAP_{f_id}"
                        is_active_now = False

                        # Adaptive Strike Trigger: Light & Sensitive Tapping Across All 3 Rows
                        if row_name == 'LOW':
                            min_impulse, min_delta = 0.70, 0.011
                        elif row_name == 'MID':
                            min_impulse, min_delta = 0.70, 0.011
                        else:
                            min_impulse, min_delta = 0.75, 0.012

                        if strike_impulse > min_impulse and delta_y > min_delta:
                            if self.finger_states[tap_state_id] == 'READY':
                                self.finger_states[tap_state_id] = 'STRUCK'
                                self.last_strike_time[tap_state_id] = now
                                is_active_now = True
                                self.trigger_action(key_name, f_id)

                                # Draw Big Hit Circle
                                cx, cy = int(tip_pos[0] * w), int(tip_pos[1] * h)
                                if row_name == 'TOP':
                                    hit_col = (255, 200, 0)
                                elif row_name == 'MID':
                                    hit_col = (0, 255, 0)
                                else:
                                    hit_col = (255, 120, 255)

                                cv2.circle(frame, (cx, cy), 16, hit_col, cv2.FILLED)
                                cv2.putText(frame, f"[{key_name}]", (cx - 16, cy - 16), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, hit_col, 2)
                        elif delta_y < 0.007 or (now - self.last_strike_time[tap_state_id] > 0.18):
                            self.finger_states[tap_state_id] = 'READY'
                            self.peak_pre_strike_y[f_id] = rel_y

                        current_status[f_id] = {
                            'key': key_name,
                            'top_key': curr_top,
                            'mid_key': curr_mid,
                            'low_key': curr_low,
                            'row': row_name,
                            'flex': min(1.0, max(0.0, strike_impulse / 2.0)),
                            'active': is_active_now,
                            'stretched': is_stretched
                        }

                        # Draw Compact Sleek Finger Badge & Row Tag on Camera
                        cx, cy = int(tip_pos[0] * w), int(tip_pos[1] * h)
                        if is_active_now:
                            badge_color = (0, 255, 0)
                        elif is_stretched:
                            badge_color = (255, 180, 0)
                        elif row_name == 'TOP':
                            badge_color = (0, 200, 255) # Cyan for Top Row
                        elif row_name == 'MID':
                            badge_color = (120, 255, 120) # Bright Green for Home/Mid Row
                        else:
                            badge_color = (230, 100, 255) # Lavender/Pink for Lower Row

                        # Sleek small 8px circle badge
                        cv2.circle(frame, (cx, cy), 8, badge_color, cv2.FILLED)
                        cv2.putText(frame, key_name, (cx - 5, cy - 11),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

                        # Compact row label under finger
                        cv2.putText(frame, row_name, (cx - 10, cy + 15), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, badge_color, 1)

                        # Show stretch guide text on Index finger
                        if f_name == "INDEX" and is_stretched:
                            cv2.putText(frame, "STRETCH", (cx - 18, cy + 26), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 200, 0), 1)

            self.finger_status = current_status

            # Header info in Camera Window
            cv2.rectangle(frame, (0, 0), (w, 42), (20, 20, 20), cv2.FILLED)
            if is_enter_active:
                status_str = "✨ ENTER KEY ACTIVE"
                status_col = (200, 100, 255)
            elif is_backspace_active:
                status_str = "🔴 BACKSPACE ACTIVE"
                status_col = (0, 0, 255)
            else:
                status_str = "🟢 DYNAMIC AUTO-CALIBRATED QWERTY: Mid-Row Active | Tap to Type"
                status_col = (0, 255, 0)
            
            cv2.putText(frame, status_str, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.38, status_col, 2)

            self.latest_display_frame = frame
            time.sleep(0.005)

        cap.release()

    def run_display_pipeline(self):
        win_title = "AI Virtual Keyboard (3-Row QWERTY Edition)"
        cv2.namedWindow(win_title, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(win_title, cv2.WND_PROP_TOPMOST, 1)

        while self.is_running:
            if self.latest_display_frame is not None:
                cv2.imshow(win_title, self.latest_display_frame)
            key = cv2.waitKey(10)
            if key & 0xFF == 27:
                self.close_app()
                break
            time.sleep(0.005)

        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    def close_app(self):
        self.is_running = False
        self.root.destroy()

if __name__ == "__main__":
    app = TopRow3DDipVirtualKeyboard()
    app.root.mainloop()

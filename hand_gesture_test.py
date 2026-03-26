import argparse
import math
import random
import signal
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import mediapipe as mp
import pyautogui
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

SMOOTHING = 0.16
SCREEN_MARGIN = 0.015
CURSOR_GAIN = 1.95
CURSOR_RESPONSE_EXPONENT = 0.7
ANCHOR_SMOOTHING = 0.35
VELOCITY_BOOST = 1.2
VELOCITY_CLAMP = 0.18
PINCH_DOWN_THRESHOLD = 0.075
PINCH_UP_THRESHOLD = 0.12
PINCH_MIN_HOLD = 0.02
CLICK_COOLDOWN = 0.16
PINCH_REARM_DELAY = 0.05
POINT_CLICK_HOLD_TIME = 0.11
FIST_HOLD_TIME = 0.12
PEACE_TWIST_ANGLE_THRESHOLD = 0.42
PALM_VERTICAL_SWIPE_THRESHOLD = 0.11
THREE_FINGER_SWIPE_THRESHOLD = 0.11
SWIPE_WINDOW_SECONDS = 0.35
SWIPE_COOLDOWN_SECONDS = 0.65
FIST_TIP_DISTANCE_THRESHOLD = 0.23
PINCH_SCALE_FLOOR = 0.06
PEACE_SPREAD_THRESHOLD = 0.045
EYE_HORIZONTAL_MIN = 0.32
EYE_HORIZONTAL_MAX = 0.68
EYE_VERTICAL_MIN = 0.3
EYE_VERTICAL_MAX = 0.7
TWO_HAND_SCENE_HOLD_TIME = 5.0
TWO_HAND_SCENE_COOLDOWN = 3.0
CALL_SIGN_HOLD_TIME = 0.9
CALL_SIGN_COOLDOWN = 2.0

RUNNING = True

LEFT_IRIS = (468, 469, 470, 471, 472)
RIGHT_IRIS = (473, 474, 475, 476, 477)


def handle_exit_signal(signum, _frame):
    global RUNNING
    print(f"Received signal {signum}. Exiting Stark mode cleanly.", flush=True)
    RUNNING = False


def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def average_point(points):
    x = sum(point.x for point in points) / len(points)
    y = sum(point.y for point in points) / len(points)
    return x, y


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def apply_cursor_gain(value):
    centered = (value - 0.5) * CURSOR_GAIN
    scaled = abs(centered) ** CURSOR_RESPONSE_EXPONENT
    shifted = 0.5 + math.copysign(scaled, centered)
    return clamp(shifted, 0.0, 1.0)


def normalize_range(value, minimum, maximum):
    if maximum <= minimum:
        return 0.5
    return clamp((value - minimum) / (maximum - minimum), 0.0, 1.0)


def finger_extended(landmarks, tip_idx, pip_idx):
    return landmarks[tip_idx].y < landmarks[pip_idx].y


def thumb_extended(landmarks):
    return distance(landmarks[4], landmarks[2]) > distance(landmarks[3], landmarks[2])


def is_open_palm(landmarks):
    return all(
        finger_extended(landmarks, tip_idx, pip_idx)
        for tip_idx, pip_idx in ((8, 6), (12, 10), (16, 14), (20, 18))
    )


def is_peace_sign(landmarks):
    return (
        finger_extended(landmarks, 8, 6)
        and finger_extended(landmarks, 12, 10)
        and not finger_extended(landmarks, 16, 14)
        and not finger_extended(landmarks, 20, 18)
        and distance(landmarks[8], landmarks[12]) >= PEACE_SPREAD_THRESHOLD
    )


def is_closed_fist(landmarks):
    wrist = landmarks[0]
    curled_fingers = all(
        not finger_extended(landmarks, tip_idx, pip_idx)
        for tip_idx, pip_idx in ((8, 6), (12, 10), (16, 14), (20, 18))
    )
    average_tip_distance = sum(distance(landmarks[idx], wrist) for idx in (8, 12, 16, 20)) / 4.0
    return curled_fingers and average_tip_distance < FIST_TIP_DISTANCE_THRESHOLD and not thumb_extended(landmarks)


def is_three_finger_gesture(landmarks):
    return (
        finger_extended(landmarks, 8, 6)
        and finger_extended(landmarks, 12, 10)
        and finger_extended(landmarks, 16, 14)
        and not finger_extended(landmarks, 20, 18)
    )


def is_index_point_gesture(landmarks):
    return (
        finger_extended(landmarks, 8, 6)
        and not finger_extended(landmarks, 12, 10)
        and not finger_extended(landmarks, 16, 14)
        and not finger_extended(landmarks, 20, 18)
    )


def is_call_sign_gesture(landmarks):
    return (
        thumb_extended(landmarks)
        and not finger_extended(landmarks, 8, 6)
        and not finger_extended(landmarks, 12, 10)
        and not finger_extended(landmarks, 16, 14)
        and finger_extended(landmarks, 20, 18)
    )


def palm_rotation_angle(landmarks):
    index_mcp = landmarks[5]
    pinky_mcp = landmarks[17]
    return math.atan2(pinky_mcp.y - index_mcp.y, pinky_mcp.x - index_mcp.x)


def iris_center(landmarks, indices):
    return average_point([landmarks[index] for index in indices])


def compute_eye_anchor(face_landmarks):
    if len(face_landmarks) < 478:
        return None

    left_iris_x, left_iris_y = iris_center(face_landmarks, LEFT_IRIS)
    right_iris_x, right_iris_y = iris_center(face_landmarks, RIGHT_IRIS)

    left_ratio_x = normalize_range(left_iris_x, face_landmarks[33].x, face_landmarks[133].x)
    right_ratio_x = normalize_range(right_iris_x, face_landmarks[362].x, face_landmarks[263].x)
    left_ratio_y = normalize_range(left_iris_y, face_landmarks[159].y, face_landmarks[145].y)
    right_ratio_y = normalize_range(right_iris_y, face_landmarks[386].y, face_landmarks[374].y)

    average_x = (left_ratio_x + right_ratio_x) / 2.0
    average_y = (left_ratio_y + right_ratio_y) / 2.0

    anchor_x = normalize_range(average_x, EYE_HORIZONTAL_MIN, EYE_HORIZONTAL_MAX)
    anchor_y = normalize_range(average_y, EYE_VERTICAL_MIN, EYE_VERTICAL_MAX)
    return anchor_x, anchor_y


class GestureController:
    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()
        self.cursor_x = self.screen_width / 2
        self.cursor_y = self.screen_height / 2
        self.filtered_anchor_x = 0.5
        self.filtered_anchor_y = 0.5
        self.last_filtered_anchor_x = 0.5
        self.last_filtered_anchor_y = 0.5
        self.is_pinched = False
        self.pinch_started_at = None
        self.last_pinch_release_at = 0.0
        self.last_click_at = 0.0
        self.pinch_history = deque(maxlen=4)
        self.point_started_at = None
        self.fist_started_at = None
        self.dragging = False
        self.swipe_history = deque()
        self.last_tab_swipe_at = 0.0
        self.last_vertical_swipe_at = 0.0
        self.last_three_finger_swipe_at = 0.0

    def move_cursor(self, anchor_x, anchor_y):
        self.filtered_anchor_x += (anchor_x - self.filtered_anchor_x) * ANCHOR_SMOOTHING
        self.filtered_anchor_y += (anchor_y - self.filtered_anchor_y) * ANCHOR_SMOOTHING
        velocity_x = clamp(self.filtered_anchor_x - self.last_filtered_anchor_x, -VELOCITY_CLAMP, VELOCITY_CLAMP)
        velocity_y = clamp(self.filtered_anchor_y - self.last_filtered_anchor_y, -VELOCITY_CLAMP, VELOCITY_CLAMP)
        self.last_filtered_anchor_x = self.filtered_anchor_x
        self.last_filtered_anchor_y = self.filtered_anchor_y

        boosted_anchor_x = clamp(self.filtered_anchor_x + velocity_x * VELOCITY_BOOST, 0.0, 1.0)
        boosted_anchor_y = clamp(self.filtered_anchor_y + velocity_y * VELOCITY_BOOST, 0.0, 1.0)

        clipped_x = clamp(boosted_anchor_x, SCREEN_MARGIN, 1.0 - SCREEN_MARGIN)
        clipped_y = clamp(boosted_anchor_y, SCREEN_MARGIN, 1.0 - SCREEN_MARGIN)
        normalized_x = (clipped_x - SCREEN_MARGIN) / (1.0 - 2.0 * SCREEN_MARGIN)
        normalized_y = (clipped_y - SCREEN_MARGIN) / (1.0 - 2.0 * SCREEN_MARGIN)
        normalized_x = apply_cursor_gain(normalized_x)
        normalized_y = apply_cursor_gain(normalized_y)
        target_x = normalized_x * self.screen_width
        target_y = normalized_y * self.screen_height
        self.cursor_x += (target_x - self.cursor_x) * SMOOTHING
        self.cursor_y += (target_y - self.cursor_y) * SMOOTHING
        pyautogui.moveTo(self.cursor_x, self.cursor_y)

    def update_swipe_history(self, now, anchor_x, anchor_y):
        self.swipe_history.append((now, anchor_x, anchor_y))
        while self.swipe_history and now - self.swipe_history[0][0] > SWIPE_WINDOW_SECONDS:
            self.swipe_history.popleft()

    def process_pinch(self, pinch_distance, scale, now):
        scaled_pinch = pinch_distance / max(scale, PINCH_SCALE_FLOOR)
        self.pinch_history.append(scaled_pinch)
        averaged_pinch = sum(self.pinch_history) / len(self.pinch_history)

        if not self.is_pinched and averaged_pinch <= PINCH_DOWN_THRESHOLD:
            if now - self.last_pinch_release_at >= PINCH_REARM_DELAY:
                self.is_pinched = True
                self.pinch_started_at = now
        elif self.is_pinched and averaged_pinch >= PINCH_UP_THRESHOLD:
            pinch_started_at = self.pinch_started_at or now
            self.is_pinched = False
            self.pinch_started_at = None
            self.last_pinch_release_at = now
            if now - pinch_started_at >= PINCH_MIN_HOLD and now - self.last_click_at >= CLICK_COOLDOWN:
                pyautogui.click()
                self.last_click_at = now

    def process_point_click(self, index_point, now):
        if index_point:
            if self.point_started_at is None:
                self.point_started_at = now
            elif now - self.point_started_at >= POINT_CLICK_HOLD_TIME and now - self.last_click_at >= CLICK_COOLDOWN:
                pyautogui.click()
                self.last_click_at = now
                self.point_started_at = now + 999
        else:
            self.point_started_at = None

    def process_drag(self, fist_closed, now):
        if fist_closed:
            if self.fist_started_at is None:
                self.fist_started_at = now
            elif not self.dragging and now - self.fist_started_at >= FIST_HOLD_TIME:
                pyautogui.mouseDown()
                self.dragging = True
        else:
            self.fist_started_at = None
            if self.dragging:
                pyautogui.mouseUp()
                self.dragging = False

    def process_swipes(self, peace_sign, peace_angle, open_palm, three_finger):
        if len(self.swipe_history) < 2:
            return

        _, start_x, start_y = self.swipe_history[0]
        _, end_x, end_y = self.swipe_history[-1]
        delta_x = end_x - start_x
        delta_y = end_y - start_y
        now = time.time()

        if peace_sign and now - self.last_tab_swipe_at >= SWIPE_COOLDOWN_SECONDS:
            if peace_angle <= -PEACE_TWIST_ANGLE_THRESHOLD:
                if delta_x >= 0:
                    pyautogui.hotkey("ctrl", "tab")
                else:
                    pyautogui.hotkey("ctrl", "shift", "tab")
                self.last_tab_swipe_at = now
                self.swipe_history.clear()
                return
            if peace_angle >= PEACE_TWIST_ANGLE_THRESHOLD:
                if delta_x <= 0:
                    pyautogui.hotkey("ctrl", "shift", "tab")
                else:
                    pyautogui.hotkey("ctrl", "tab")
                self.last_tab_swipe_at = now
                self.swipe_history.clear()
                return

        if open_palm and now - self.last_vertical_swipe_at >= SWIPE_COOLDOWN_SECONDS:
            if abs(delta_y) >= PALM_VERTICAL_SWIPE_THRESHOLD and abs(delta_y) > abs(delta_x) * 1.2:
                if delta_y < 0:
                    pyautogui.hotkey("ctrl", "up")
                else:
                    pyautogui.hotkey("ctrl", "down")
                self.last_vertical_swipe_at = now
                self.swipe_history.clear()
                return

        if three_finger and now - self.last_three_finger_swipe_at >= SWIPE_COOLDOWN_SECONDS:
            if abs(delta_x) >= THREE_FINGER_SWIPE_THRESHOLD and abs(delta_x) > abs(delta_y) * 1.15:
                if delta_x > 0:
                    pyautogui.hotkey("ctrl", "right")
                else:
                    pyautogui.hotkey("ctrl", "left")
                self.last_three_finger_swipe_at = now
                self.swipe_history.clear()

    def shutdown(self):
        if self.dragging:
            pyautogui.mouseUp()
            self.dragging = False


class SceneTriggerController:
    def __init__(self):
        self.two_hand_started_at = None
        self.last_scene_action_at = 0.0
        self.call_sign_started_at = None
        self.last_lock_action_at = 0.0

    def _run_command(self, command):
        try:
            subprocess.run(command, check=False)
        except Exception as exc:
            print(f"Failed startup-scene command {command}: {exc}", flush=True)

    def _speak_focus_mode_line(self):
        lines = [
            "Focus mode on. Let's get started, sir.",
            "Very good. Focus mode engaged, sir.",
            "Right then. Focus mode on. Let's begin, sir.",
            "Focus mode active. Time to work, sir.",
        ]
        try:
            subprocess.run(["say", random.choice(lines)], check=False)
        except Exception as exc:
            print(f"Failed focus mode voice line: {exc}", flush=True)

    def _play_guilt_tripping_on_spotify(self):
        self._run_command(["open", "-a", "Spotify"])
        time.sleep(1.2)
        try:
            subprocess.run(
                ["open", "-a", "Spotify", "spotify:track:3yKgOMlm0LFpm9T2AhGWJJ"],
                check=False,
            )
        except Exception as exc:
            print(f"Failed Spotify track launch: {exc}", flush=True)

    def _open_startup_scene(self):
        self._speak_focus_mode_line()
        self._play_guilt_tripping_on_spotify()
        self._run_command(["open", "-a", "Google Chrome"])
        time.sleep(0.8)
        self._run_command(["open", "-a", "Google Chrome", "https://web.whatsapp.com"])
        time.sleep(0.25)
        self._run_command(["open", "-a", "Google Chrome", "https://www.youtube.com"])
        time.sleep(0.25)
        self._run_command(["open", "-a", "Visual Studio Code"])

    def _lock_screen(self):
        try:
            pyautogui.hotkey("ctrl", "command", "q")
        except Exception as exc:
            print(f"Failed to lock screen: {exc}", flush=True)

    def poll(self, hands, primary_hand, now):
        if len(hands) < 2:
            self.two_hand_started_at = None
        else:
            if self.two_hand_started_at is None:
                self.two_hand_started_at = now
            elif now - self.two_hand_started_at >= TWO_HAND_SCENE_HOLD_TIME and now - self.last_scene_action_at >= TWO_HAND_SCENE_COOLDOWN:
                self._open_startup_scene()
                self.last_scene_action_at = now
                self.two_hand_started_at = now + 999

        if primary_hand and is_call_sign_gesture(primary_hand):
            if self.call_sign_started_at is None:
                self.call_sign_started_at = now
            elif now - self.call_sign_started_at >= CALL_SIGN_HOLD_TIME and now - self.last_lock_action_at >= CALL_SIGN_COOLDOWN:
                self._lock_screen()
                self.last_lock_action_at = now
                self.call_sign_started_at = now + 999
        else:
            self.call_sign_started_at = None

    def close(self):
        return


def build_parser():
    parser = argparse.ArgumentParser(description="Stark mode controller")
    parser.add_argument("--headless", action="store_true", help="Disable the preview window.")
    parser.add_argument("--show-preview", action="store_true", help="Show the camera preview window.")
    parser.add_argument("--mode", choices=("hand", "advanced"), default="hand", help="Cursor control mode.")
    return parser


def create_hand_landmarker(model_path):
    base_options = python.BaseOptions(model_asset_path=str(model_path))
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.6,
        min_tracking_confidence=0.5,
    )
    return vision.HandLandmarker.create_from_options(options)


def create_face_landmarker(model_path):
    base_options = python.BaseOptions(model_asset_path=str(model_path))
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False,
    )
    return vision.FaceLandmarker.create_from_options(options)


def draw_preview(frame, hand_landmarks_list, face_landmarks, controller, gesture_label, mode_label):
    preview = frame.copy()
    for hand_landmarks in hand_landmarks_list or []:
        for landmark in hand_landmarks:
            x = int(landmark.x * preview.shape[1])
            y = int(landmark.y * preview.shape[0])
            cv2.circle(preview, (x, y), 4, (0, 255, 0), -1)
    if face_landmarks:
        for index in LEFT_IRIS + RIGHT_IRIS:
            landmark = face_landmarks[index]
            x = int(landmark.x * preview.shape[1])
            y = int(landmark.y * preview.shape[0])
            cv2.circle(preview, (x, y), 3, (255, 180, 0), -1)

    cv2.putText(preview, f"Mode: {mode_label}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)
    cv2.putText(preview, gesture_label, (20, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 220, 255), 2)
    cv2.putText(
        preview,
        f"Cursor: {int(controller.cursor_x)}, {int(controller.cursor_y)}",
        (20, 108),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
    )
    if controller.dragging:
        cv2.putText(preview, "Dragging", (20, 142), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 80, 255), 2)
    cv2.imshow("Stark Mode", preview)


def main():
    global RUNNING

    parser = build_parser()
    args = parser.parse_args()
    show_preview = args.show_preview and not args.headless

    signal.signal(signal.SIGINT, handle_exit_signal)
    signal.signal(signal.SIGTERM, handle_exit_signal)

    project_root = Path(__file__).resolve().parent
    hand_model_path = project_root / "public" / "hand_landmarker.task"
    face_model_path = project_root / "backend" / "face_landmarker.task"
    if not hand_model_path.exists():
        raise FileNotFoundError(f"Missing hand landmark model at {hand_model_path}")
    if args.mode == "advanced" and not face_model_path.exists():
        raise FileNotFoundError(f"Missing face landmark model at {face_model_path}")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Unable to access the webcam for Stark mode.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    controller = GestureController()
    scene_trigger = SceneTriggerController()
    hand_landmarker = create_hand_landmarker(hand_model_path)
    face_landmarker = create_face_landmarker(face_model_path) if args.mode == "advanced" else None
    timestamp_ms = 0

    try:
        while RUNNING:
            success, frame = cap.read()
            if not success:
                time.sleep(0.02)
                continue

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            timestamp_ms += 1

            hand_result = hand_landmarker.detect_for_video(mp_image, timestamp_ms)
            face_result = face_landmarker.detect_for_video(mp_image, timestamp_ms) if face_landmarker else None

            gesture_label = "No input"
            hand_landmarks_list = list(hand_result.hand_landmarks or [])
            hand_landmarks = hand_landmarks_list[0] if hand_landmarks_list else None
            face_landmarks = face_result.face_landmarks[0] if face_result and face_result.face_landmarks else None
            now = time.time()
            scene_trigger.poll(hand_landmarks_list, hand_landmarks, now)
            two_hand_priority = len(hand_landmarks_list) >= 2

            cursor_anchor = None
            hand_anchor = None
            if args.mode == "advanced" and face_landmarks:
                cursor_anchor = compute_eye_anchor(face_landmarks)
                if cursor_anchor:
                    gesture_label = "Eye tracking"

            if cursor_anchor is None and hand_landmarks:
                hand_anchor = average_point((hand_landmarks[0], hand_landmarks[5], hand_landmarks[17]))
                cursor_anchor = hand_anchor
                gesture_label = "Hand tracking"
            elif hand_landmarks:
                hand_anchor = average_point((hand_landmarks[0], hand_landmarks[5], hand_landmarks[17]))

            if cursor_anchor is not None:
                controller.move_cursor(*cursor_anchor)
            else:
                controller.swipe_history.clear()

            if hand_landmarks and not two_hand_priority:
                pinch_distance = distance(hand_landmarks[4], hand_landmarks[8])
                palm_scale = distance(hand_landmarks[5], hand_landmarks[17])
                open_palm = is_open_palm(hand_landmarks)
                peace_sign = is_peace_sign(hand_landmarks)
                index_point = is_index_point_gesture(hand_landmarks)
                call_sign = is_call_sign_gesture(hand_landmarks)
                three_finger = is_three_finger_gesture(hand_landmarks)
                peace_angle = palm_rotation_angle(hand_landmarks)
                fist_closed = is_closed_fist(hand_landmarks)

                if peace_sign:
                    swipe_anchor = average_point((hand_landmarks[8], hand_landmarks[12]))
                elif three_finger:
                    swipe_anchor = average_point((hand_landmarks[8], hand_landmarks[12], hand_landmarks[16]))
                else:
                    swipe_anchor = hand_anchor
                if swipe_anchor is not None:
                    controller.update_swipe_history(now, *swipe_anchor)

                controller.process_pinch(pinch_distance, palm_scale, now)
                controller.process_point_click(index_point, now)
                controller.process_drag(fist_closed, now)
                controller.process_swipes(peace_sign, peace_angle, open_palm, three_finger)

                if controller.dragging or fist_closed:
                    gesture_label = "Closed fist drag"
                elif call_sign:
                    gesture_label = "Call sign lock"
                elif peace_sign:
                    gesture_label = "Peace sign twist"
                elif index_point:
                    gesture_label = "Point click"
                elif three_finger:
                    gesture_label = "Three-finger swipe"
                elif open_palm:
                    gesture_label = "Open palm swipe"
                elif controller.is_pinched:
                    gesture_label = "Pinch"
            elif two_hand_priority:
                controller.process_drag(False, now)
                controller.process_point_click(False, now)
                controller.is_pinched = False
                controller.pinch_started_at = None
                controller.swipe_history.clear()
                gesture_label = "Two-hand startup"
            else:
                controller.process_drag(False, now)
                controller.process_point_click(False, now)
                controller.is_pinched = False
                controller.pinch_started_at = None
                controller.swipe_history.clear()

            if show_preview:
                draw_preview(
                    frame,
                    hand_landmarks_list,
                    face_landmarks,
                    controller,
                    gesture_label,
                    "advanced" if args.mode == "advanced" else "hand",
                )
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    RUNNING = False

    finally:
        controller.shutdown()
        scene_trigger.close()
        cap.release()
        if show_preview:
            cv2.destroyAllWindows()
        hand_landmarker.close()
        if face_landmarker:
            face_landmarker.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Stark mode crashed: {exc}", file=sys.stderr, flush=True)
        raise

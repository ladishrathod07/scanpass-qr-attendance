"""
Real-Time OpenCV Webcam Scanner Module
Detects 2D Quick Response (QR) codes in live video frames using cv2.QRCodeDetector,
validates payload against SQLite database, prevents duplicate proxy logging,
and renders real-time graphical feedback HUD on the video stream.
"""

import cv2
import time
import sys
import numpy as np
from datetime import datetime
from database import record_attendance, get_student, init_db


def run_scanner(camera_index: int = 0, entry_type: str = "Classroom Attendance"):
    """
    Launches a standalone OpenCV window with live webcam feed:
    - Locates QR code finder patterns
    - Highlights detected bounding box in real-time
    - Checks SQLite database and logs check-in timestamp
    - Enforces duplicate scan cooldown to avoid false re-triggers
    - Press 'q' to exit, 'c' to toggle mode (Classroom vs Library)
    """
    init_db()
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"[ERROR] Could not open webcam at index {camera_index}.")
        print("[INFO] If running on a system without a built-in camera, use the Streamlit Web Dashboard to upload ID cards or test with images.")
        return

    # Set camera resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    detector = cv2.QRCodeDetector()

    # Feedback state
    last_detected_time = 0
    feedback_text = "READY TO SCAN QR ID"
    feedback_subtext = f"Mode: {entry_type} | Press 'q' to quit | 'c' to toggle mode"
    feedback_color = (180, 180, 180) # Gray BGR
    cooldown_dict = {} # roll_no -> last_scan_timestamp

    print(f"==================================================")
    print(f"  Smart QR Scanner Initialized ({entry_type})")
    print(f"  Align Student QR ID Card in front of camera.")
    print(f"  Hotkeys: [q] Quit  |  [c] Toggle Mode")
    print(f"==================================================")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Failed to grab camera frame. Exiting...")
            break

        # Flip horizontally for natural mirror feel
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        current_time = time.time()

        # Step 2: Real-Time Webcam Scanning (Decoding)
        data, points, _ = detector.detectAndDecode(frame)

        if points is not None and len(points) > 0:
            pts = points[0].astype(int)
            # Draw bounding box polygon around QR Finder Patterns
            cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 255), thickness=3)

            # Draw glowing corner markers
            for pt in pts:
                cv2.circle(frame, tuple(pt), 6, (0, 200, 0), -1)

            if data:
                payload = data.strip().upper()
                last_scan = cooldown_dict.get(payload, 0)

                # 3-second cooldown to avoid continuous multi-frame spamming
                if current_time - last_scan > 3.0:
                    cooldown_dict[payload] = current_time
                    result = record_attendance(payload, entry_type=entry_type)

                    last_detected_time = current_time

                    if result["status_code"] == "LOGGED_SUCCESS":
                        std = result["student"]
                        feedback_text = f"SUCCESS: {std['full_name']} ({payload})"
                        feedback_subtext = f"Marked Present at {result['scan_time']} | {std['branch']}"
                        feedback_color = (0, 220, 0) # Green BGR
                        print(f"[ATTENDANCE SUCCESS] {payload} - {std['full_name']} logged at {result['scan_time']}")

                    elif result["status_code"] == "ALREADY_LOGGED":
                        std = result["student"]
                        feedback_text = f"NOTICE: Already Logged Today!"
                        feedback_subtext = f"{std['full_name']} ({payload}) at {result['scan_time']}"
                        feedback_color = (0, 165, 255) # Orange/Amber BGR
                        print(f"[DUPLICATE ALERT] {payload} - {std['full_name']} already marked at {result['scan_time']}")

                    else:
                        feedback_text = f"ERROR: Unrecognized Student QR"
                        feedback_subtext = f"Payload '{payload}' not found in registered database."
                        feedback_color = (0, 0, 240) # Red BGR
                        print(f"[ERROR] QR Payload '{payload}' is not in database.")

        # Reset banner to ready after 4 seconds of inactivity
        if current_time - last_detected_time > 4.0:
            feedback_text = "READY TO SCAN QR ID"
            feedback_subtext = f"Mode: {entry_type} | Press 'q' to quit | 'c' to toggle mode"
            feedback_color = (180, 180, 180)

        # ----------------- Graphical HUD Overlay -----------------
        # Header Bar
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 65), (20, 25, 35), -1)
        # Footer Feedback Card
        cv2.rectangle(overlay, (0, h - 90), (w, h), (20, 25, 35), -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        # Header Title
        cv2.putText(
            frame,
            "SMART QR ATTENDANCE & LIBRARY ENTRY SYSTEM",
            (25, 38),
            cv2.FONT_HERSHEY_DUPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        now_str = datetime.now().strftime("%Y-%m-%d  %I:%M:%S %p")
        cv2.putText(
            frame,
            now_str,
            (w - 320, 38),
            cv2.FONT_HERSHEY_DUPLEX,
            0.55,
            (0, 220, 255),
            1,
            cv2.LINE_AA
        )

        # Status Indicator Light on Footer
        cv2.circle(frame, (35, h - 50), 12, feedback_color, -1)
        cv2.circle(frame, (35, h - 50), 14, (255, 255, 255), 2)

        # Footer Feedback Text
        cv2.putText(
            frame,
            feedback_text,
            (65, h - 55),
            cv2.FONT_HERSHEY_DUPLEX,
            0.72,
            feedback_color,
            2,
            cv2.LINE_AA
        )
        cv2.putText(
            frame,
            feedback_subtext,
            (65, h - 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (210, 215, 225),
            1,
            cv2.LINE_AA
        )

        # Display window
        cv2.imshow("Smart QR Attendance Scanner - Live Feed", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27: # 'q' or ESC
            break
        elif key == ord('c'): # Toggle mode
            if entry_type == "Classroom Attendance":
                entry_type = "Library Entry"
            else:
                entry_type = "Classroom Attendance"
            feedback_subtext = f"Switched to Mode: {entry_type}"
            print(f"[MODE TOGGLE] Active Mode is now: {entry_type}")

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Scanner stopped cleanly.")

 # Status Indicator Light and Footer
if __name__ == "__main__":
    mode = "Classroom Attendance"
    if len(sys.argv) > 1 and sys.argv[1].lower() == "library":
        mode = "Library Entry"
    run_scanner(entry_type=mode)

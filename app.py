"""
Smart QR-Based Student Attendance & Library Entry Management System
Streamlit Dashboard Application
Provides live webcam QR scanning, image upload scanning, student registration,
digital ID card generation, analytics dashboards, CSV/Excel export, and viva guide.
"""

import streamlit as st
import pandas as pd
import numpy as np
import cv2
import os
import io
import time
import subprocess
from datetime import datetime
from PIL import Image

# Import local modules
import database as db
import qr_generator as qrg

# Page configuration
st.set_page_config(
    page_title="Smart QR Attendance & Library System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database schema
db.init_db()

# Custom CSS for rich aesthetics, glassmorphism, and responsive cards
st.markdown("""
<style>
    /* Global styling and Google font */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Main Container Padding */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    /* Header Banner Styling */
    .hero-banner {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0369a1 100%);
        border-radius: 16px;
        padding: 24px 30px;
        color: white;
        margin-bottom: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2);
    }
    .hero-title {
        font-size: 28px;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
        color: #ffffff;
    }
    .hero-subtitle {
        font-size: 15px;
        color: #94a3b8;
        margin-top: 6px;
        font-weight: 400;
    }
    .hero-tags {
        display: flex;
        gap: 8px;
        margin-top: 14px;
        flex-wrap: wrap;
    }
    .hero-badge {
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        color: #38bdf8;
    }

    /* KPI Metric Cards */
    .metric-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 18px 20px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
    }
    .metric-label {
        font-size: 13px;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 800;
        color: #0f172a;
        margin-top: 4px;
    }
    .metric-sub {
        font-size: 12px;
        color: #10b981;
        font-weight: 600;
        margin-top: 2px;
    }

    /* Result Alert Boxes */
    .scan-card-success {
        background: #f0fdf4;
        border: 1.5px solid #22c55e;
        border-radius: 12px;
        padding: 16px 20px;
        margin-top: 15px;
    }
    .scan-card-warning {
        background: #fffbeb;
        border: 1.5px solid #f59e0b;
        border-radius: 12px;
        padding: 16px 20px;
        margin-top: 15px;
    }
    .scan-card-error {
        background: #fef2f2;
        border: 1.5px solid #ef4444;
        border-radius: 12px;
        padding: 16px 20px;
        margin-top: 15px;
    }

    /* Section Headers */
    .section-title {
        font-size: 20px;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Viva Flashcard */
    .viva-box {
        background: #f8fafc;
        border-radius: 12px;
        padding: 18px 22px;
        border-left: 5px solid #0284c7;
        margin-bottom: 16px;
        border-top: 1px solid #e2e8f0;
        border-right: 1px solid #e2e8f0;
        border-bottom: 1px solid #e2e8f0;
    }
    .viva-q {
        font-weight: 700;
        font-size: 15px;
        color: #0369a1;
        margin-bottom: 6px;
    }
    .viva-a {
        font-size: 14px;
        color: #334155;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)


def play_audio_feedback(tone_type: str = "success"):
    """
    Renders HTML5 Web Audio API beep sound directly in the user's browser:
    - High pleasant double chime for attendance success
    - Warning tone for duplicate scan
    - Low buzzer for unregistered ID
    """
    frequencies = {
        "success": "[880, 1174.66]", # A5, D6 high harmonic
        "warning": "[587.33, 440]",   # D5, A4 warning
        "error": "[220, 164.81]"      # A3, E3 low error
    }
    freq_arr = frequencies.get(tone_type, "[880, 1174.66]")
    duration = 0.15 if tone_type == "success" else 0.22

    audio_html = f"""
    <script>
    (function() {{
        try {{
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) return;
            const ctx = new AudioContext();
            const freqs = {freq_arr};
            freqs.forEach((freq, idx) => {{
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(freq, ctx.currentTime + (idx * 0.12));
                gain.gain.setValueAtTime(0.18, ctx.currentTime + (idx * 0.12));
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + (idx * 0.12) + {duration});
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(ctx.currentTime + (idx * 0.12));
                osc.stop(ctx.currentTime + (idx * 0.12) + {duration});
            }});
        }} catch(e) {{
            console.log("Audio feedback muted:", e);
        }}
    }})();
    </script>
    """
    st.components.v1.html(audio_html, height=0, width=0)


def decode_qr_opencv(image_bytes: bytes):
    """Decodes QR code from image bytes using OpenCV's QRCodeDetector."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_cv is None:
        return None, None

    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img_cv)
    return data, points


# ---------------- Sidebar Navigation ----------------
st.sidebar.image("https://img.icons8.com/fluency/96/qr-code.png", width=64)
st.sidebar.title("Smart QR Portal")
st.sidebar.markdown("**Contactless Entry & Attendance**")
st.sidebar.divider()

nav_choice = st.sidebar.radio(
    "Navigation Menu",
    [
        "📸 Live QR Scanner",
        "🪪 Student Registration & ID Cards",
        "📊 Attendance Logs & Analytics",
        "📚 Library Entry Mode",
        "🎓 Viva & Project Presentation Hub"
    ],
    index=0
)

st.sidebar.divider()
st.sidebar.markdown("### System Status")
st.sidebar.success("Database: Connected (SQLite)")
st.sidebar.info("CV Engine: OpenCV 5.0")
st.sidebar.caption("Microproject • Viva Ready")


# ---------------- Header Banner ----------------
st.markdown("""
<div class="hero-banner">
    <h1 class="hero-title">Smart QR-Based Student Attendance & Library Entry System</h1>
    <p class="hero-subtitle">Automated, Contactless Verification Powered by 2D QR Matrix, Computer Vision & Relational DBMS</p>
    <div class="hero-tags">
        <span class="hero-badge">⚡ Sub-Second Scanning</span>
        <span class="hero-badge">🛡️ Duplicate Proxy Prevention</span>
        <span class="hero-badge">📁 One-Click Excel/CSV Export</span>
        <span class="hero-badge">💾 Portable SQLite DB</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ==============================================================================
# TAB 1: LIVE QR SCANNER
# ==============================================================================
if nav_choice == "📸 Live QR Scanner":
    st.markdown('<div class="section-title">📸 Real-Time QR Scanner & Validation Engine</div>', unsafe_allow_html=True)
    st.markdown("Present a student QR pass to mark attendance or library entry. The system validates uniqueness against the database.")

    col_cfg1, col_cfg2 = st.columns([2, 1])
    with col_cfg1:
        entry_type = st.selectbox(
            "Select Entry Session / Context",
            ["Classroom Attendance", "Library Gate Entry"],
            index=0
        )
    with col_cfg2:
        scanner_source = st.radio(
            "Scan Input Mode",
            ["📷 Web Camera", "📁 Upload Image / ID Pass", "⚡ One-Click Demo Scan"],
            horizontal=True
        )

    st.write("")

    scanned_payload = None

    if scanner_source == "📷 Web Camera":
        st.info("Align the QR code on the student's ID card or mobile screen in front of your camera:")
        cam_photo = st.camera_input("Take Camera Snapshot for QR Detection", key="webcam_scanner")
        if cam_photo is not None:
            bytes_data = cam_photo.getvalue()
            payload, pts = decode_qr_opencv(bytes_data)
            if payload and payload.strip():
                scanned_payload = payload.strip().upper()
            else:
                st.warning("⚠️ No QR code detected in the frame. Please hold the QR code steady, well-lit, and closer to the lens.")

    elif scanner_source == "📁 Upload Image / ID Pass":
        uploaded_file = st.file_uploader("Upload Student ID Card or QR Code Image (.png, .jpg, .jpeg)", type=["png", "jpg", "jpeg"])
        if uploaded_file is not None:
            bytes_data = uploaded_file.getvalue()
            col_img1, col_img2 = st.columns([1, 2])
            with col_img1:
                st.image(bytes_data, caption="Uploaded Input Pass", use_container_width=True)
            with col_img2:
                with st.spinner("Decoding 2D matrix payload with OpenCV..."):
                    payload, pts = decode_qr_opencv(bytes_data)
                    if payload and payload.strip():
                        scanned_payload = payload.strip().upper()
                        st.success(f"Decoded QR Payload: **{scanned_payload}**")
                    else:
                        st.error("No valid QR code finder patterns detected in this file.")

    elif scanner_source == "⚡ One-Click Demo Scan":
        st.markdown("**Simulate instant scans with registered demo students (perfect for viva demonstration):**")
        all_std = db.get_all_students()
        if not all_std:
            st.warning("No students registered yet. Click below to load demo student records:")
            if st.button("🚀 Seed Sample Students Now"):
                db.seed_sample_students()
                st.rerun()
        else:
            demo_rolls = [f"{s['roll_no']} — {s['full_name']} ({s['branch']})" for s in all_std]
            selected_demo = st.selectbox("Choose Student to Scan", demo_rolls)
            selected_roll = selected_demo.split(" — ")[0]
            
            c_btn1, c_btn2 = st.columns([1, 2])
            with c_btn1:
                if st.button("📲 Simulate QR Scan Now", type="primary", use_container_width=True):
                    scanned_payload = selected_roll

    # Process and Display Scan Result
    if scanned_payload:
        st.write("---")
        result = db.record_attendance(scanned_payload, entry_type=entry_type)

        if result["status_code"] == "LOGGED_SUCCESS":
            play_audio_feedback("success")
            std = result["student"]
            st.markdown(f"""
            <div class="scan-card-success">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div>
                        <span style="background: #22c55e; color: white; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 12px;">
                            ✓ ATTENDANCE RECORDED
                        </span>
                        <h3 style="margin: 8px 0 2px 0; color: #14532d; font-size: 22px;">{std['full_name']}</h3>
                        <p style="margin: 0; color: #166534; font-weight: 600;">Roll Number: {std['roll_no']}</p>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-size: 13px; color: #15803d; font-weight: 500;">Timestamp:</span>
                        <h4 style="margin: 0; color: #14532d;">{result['scan_time']}</h4>
                        <span style="font-size: 12px; color: #166534;">{result['scan_date']} • {entry_type}</span>
                    </div>
                </div>
                <hr style="border: 0; border-top: 1px solid #bbf7d0; margin: 12px 0;">
                <div style="display: flex; gap: 20px; font-size: 13px; color: #166534;">
                    <span><b>Branch:</b> {std['branch']}</span>
                    <span><b>Semester:</b> {std['semester']}</span>
                    <span><b>Status:</b> Present</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        elif result["status_code"] == "ALREADY_LOGGED":
            play_audio_feedback("warning")
            std = result["student"]
            st.markdown(f"""
            <div class="scan-card-warning">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div>
                        <span style="background: #f59e0b; color: white; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 12px;">
                            ⚠️ DUPLICATE SCAN PREVENTED
                        </span>
                        <h3 style="margin: 8px 0 2px 0; color: #78350f; font-size: 22px;">{std['full_name']}</h3>
                        <p style="margin: 0; color: #92400e; font-weight: 600;">Roll Number: {std['roll_no']}</p>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-size: 13px; color: #92400e; font-weight: 500;">Original Check-in:</span>
                        <h4 style="margin: 0; color: #78350f;">{result['scan_time']}</h4>
                        <span style="font-size: 12px; color: #92400e;">{result['scan_date']}</span>
                    </div>
                </div>
                <hr style="border: 0; border-top: 1px solid #fde68a; margin: 12px 0;">
                <p style="margin: 0; font-size: 13px; color: #92400e;">
                    <b>Database Rule:</b> {result['message']} The composite key constraint prevented duplicate incrementation.
                </p>
            </div>
            """, unsafe_allow_html=True)

        else:
            play_audio_feedback("error")
            st.markdown(f"""
            <div class="scan-card-error">
                <span style="background: #ef4444; color: white; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 12px;">
                    ❌ UNREGISTERED STUDENT
                </span>
                <h3 style="margin: 8px 0 2px 0; color: #7f1d1d; font-size: 20px;">Unrecognized Payload: {scanned_payload}</h3>
                <p style="margin: 0; font-size: 13px; color: #991b1b;">
                    This QR code was decoded, but no matching roll number exists in the <code>students</code> relational table.
                    Please register the student first.
                </p>
            </div>
            """, unsafe_allow_html=True)

    st.write("")
    with st.expander("🖥️ Want to launch the Standalone Native OpenCV Desktop Window?"):
        st.markdown("""
        You can also run the real-time continuous video window with green bounding boxes directly:
        - Open PowerShell or Terminal and execute:
        ```bash
        python scanner.py
        ```
        - Or click below to spawn the OpenCV scanner process on your machine:
        """)
        if st.button("▶️ Launch OpenCV Desktop Window"):
            try:
                subprocess.Popen([os.path.join(".venv", "Scripts", "python.exe"), "scanner.py"])
                st.success("Launched `scanner.py` in background window! Look for the 'Smart QR Attendance Scanner' window on your taskbar.")
            except Exception as e:
                st.error(f"Failed to start desktop scanner process: {e}")


# ==============================================================================
# TAB 2: STUDENT REGISTRATION & ID CARDS
# ==============================================================================
elif nav_choice == "🪪 Student Registration & ID Cards":
    st.markdown('<div class="section-title">🪪 Student Registration & Digital ID Card Generator</div>', unsafe_allow_html=True)
    st.markdown("Register new students to generate high-contrast 2D QR matrices and printable identity passes.")

    reg_col1, reg_col2 = st.columns([1, 1])

    with reg_col1:
        with st.form("student_registration_form"):
            st.subheader("New Student Credentials")
            roll_input = st.text_input("Roll Number (Primary Key)", placeholder="e.g. CSE-2026-099").strip().upper()
            name_input = st.text_input("Full Name", placeholder="e.g. Rohan Sharma").strip()
            branch_input = st.selectbox(
                "Department / Branch",
                [
                    "Computer Science",
                    "Information Technology",
                    "AI & Data Science",
                    "Electronics & Comm",
                    "Mechanical Engg",
                    "Civil Engg",
                    "Electrical Engg"
                ]
            )
            sem_input = st.selectbox(
                "Semester",
                ["Sem 1", "Sem 2", "Sem 3", "Sem 4", "Sem 5", "Sem 6", "Sem 7", "Sem 8"],
                index=5
            )

            submit_reg = st.form_submit_button("Generate QR Pass & Register", type="primary", use_container_width=True)

        if submit_reg:
            if not roll_input or not name_input:
                st.error("Please fill in both Roll Number and Full Name.")
            else:
                success, msg = db.add_student(roll_input, name_input, branch_input, sem_input)
                if success:
                    card_path, card_img = qrg.generate_student_id_card(roll_input, name_input, branch_input, sem_input)
                    db.update_student_qr_path(roll_input, card_path)
                    st.success(f"✓ Registered {name_input} successfully!")
                    st.session_state["latest_card"] = {
                        "roll_no": roll_input,
                        "card_path": card_path,
                        "card_img": card_img
                    }
                else:
                    st.error(f"Registration Failed: {msg}")

    with reg_col2:
        st.subheader("Generated Digital Identity Pass")
        if "latest_card" in st.session_state:
            latest = st.session_state["latest_card"]
            st.image(latest["card_img"], caption=f"ID Pass for {latest['roll_no']}", use_container_width=True)
            card_bytes = qrg.image_to_bytes(latest["card_img"])
            st.download_button(
                label="📥 Download ID Card (.png)",
                data=card_bytes,
                file_name=f"{latest['roll_no']}_id_card.png",
                mime="image/png",
                use_container_width=True
            )
        else:
            st.info("Fill out the registration form to generate a live preview and downloadable ID pass.")

    st.write("---")
    st.markdown('<div class="section-title">👥 Enrolled Student Directory & ID Passes</div>', unsafe_allow_html=True)
    all_students = db.get_all_students()

    col_dir1, col_dir2 = st.columns([3, 1])
    with col_dir1:
        st.markdown(f"Total Enrolled Students: **{len(all_students)}**")
    with col_dir2:
        if st.button("➕ Seed 6 Sample Students", help="Quickly populates sample student records"):
            c = db.seed_sample_students()
            # Generate cards for them
            for s in db.get_all_students():
                cp, _ = qrg.generate_student_id_card(s["roll_no"], s["full_name"], s["branch"], s["semester"])
                db.update_student_qr_path(s["roll_no"], cp)
            st.success(f"Seeded {c} students with QR ID passes!")
            st.rerun()

    if all_students:
        for idx in range(0, len(all_students), 2):
            row_cols = st.columns(2)
            for c_idx in range(2):
                if idx + c_idx < len(all_students):
                    std = all_students[idx + c_idx]
                    with row_cols[c_idx]:
                        with st.container():
                            card_path = std["qr_path"]
                            if not card_path or not os.path.exists(card_path):
                                card_path, card_img = qrg.generate_student_id_card(
                                    std["roll_no"], std["full_name"], std["branch"], std["semester"]
                                )
                                db.update_student_qr_path(std["roll_no"], card_path)
                            else:
                                card_img = Image.open(card_path)

                            st.image(card_img, use_container_width=True)
                            b_dl, b_del = st.columns([3, 1])
                            with b_dl:
                                card_bytes = qrg.image_to_bytes(card_img)
                                st.download_button(
                                    label=f"📥 Download Pass ({std['roll_no']})",
                                    data=card_bytes,
                                    file_name=f"{std['roll_no']}_pass.png",
                                    mime="image/png",
                                    key=f"dl_{std['roll_no']}",
                                    use_container_width=True
                                )
                            with b_del:
                                if st.button("🗑️", key=f"del_{std['roll_no']}", help="Delete student"):
                                    db.delete_student(std["roll_no"])
                                    st.rerun()
                            st.write("")


# ==============================================================================
# TAB 3: ATTENDANCE LOGS & ANALYTICS
# ==============================================================================
elif nav_choice == "📊 Attendance Logs & Analytics":
    st.markdown('<div class="section-title">📊 Attendance Logs & Relational Analytics Dashboard</div>', unsafe_allow_html=True)

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Filter Bar
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1:
        selected_date = st.date_input("Filter Date", value=datetime.now())
        target_date_str = selected_date.strftime("%Y-%m-%d")
    with f_col2:
        branch_filter = st.selectbox("Department", ["All Branches", "Computer Science", "Information Technology", "AI & Data Science", "Electronics & Comm", "Mechanical Engg", "Civil Engg", "Electrical Engg"])
    with f_col3:
        sem_filter = st.selectbox("Semester", ["All Semesters", "Sem 1", "Sem 2", "Sem 3", "Sem 4", "Sem 5", "Sem 6", "Sem 7", "Sem 8"])
    with f_col4:
        type_filter = st.selectbox("Entry Type", ["All Entry Types", "Classroom Attendance", "Library Gate Entry"])

    # Summary Metrics for Selected Date
    summary = db.get_attendance_summary(target_date_str)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Enrolled Students</div>
            <div class="metric-value">{summary['total_enrolled']}</div>
            <div class="metric-sub" style="color: #64748b;">Master Database Total</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Present Today</div>
            <div class="metric-value" style="color: #16a34a;">{summary['total_present']}</div>
            <div class="metric-sub" style="color: #16a34a;">Logged Scans</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Absent Students</div>
            <div class="metric-value" style="color: #dc2626;">{summary['total_absent']}</div>
            <div class="metric-sub" style="color: #dc2626;">Pending Scans</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Attendance Rate</div>
            <div class="metric-value" style="color: #0284c7;">{summary['attendance_rate']}%</div>
            <div class="metric-sub" style="color: #0284c7;">Session Completion</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # Attendance Logs Query
    logs = db.get_attendance_logs(
        target_date=target_date_str,
        branch=branch_filter,
        semester=sem_filter,
        entry_type=type_filter
    )

    tab_logs, tab_roster, tab_charts = st.tabs(["📋 Attendance Audit Logs", "👥 Present vs Absent Roster", "📈 Department Visualizations"])

    with tab_logs:
        if not logs:
            st.info(f"No attendance logs found for date **{target_date_str}** with active filters.")
        else:
            df_logs = pd.DataFrame(logs)
            display_cols = ["log_id", "roll_no", "full_name", "branch", "semester", "scan_date", "check_in_time", "status", "entry_type"]
            df_display = df_logs[display_cols].rename(columns={
                "log_id": "Log ID",
                "roll_no": "Roll Number",
                "full_name": "Student Name",
                "branch": "Branch",
                "semester": "Semester",
                "scan_date": "Date",
                "check_in_time": "Time",
                "status": "Status",
                "entry_type": "Session Type"
            })
            st.dataframe(df_display, use_container_width=True, hide_index=True)

        # One-Click Export Row
        st.write("---")
        exp_col1, exp_col2, exp_col3 = st.columns([1, 1, 2])
        if logs:
            df_export = pd.DataFrame(logs)
            
            # CSV Buffer
            csv_data = df_export.to_csv(index=False).encode('utf-8')
            with exp_col1:
                st.download_button(
                    label="📥 Export Sheet as CSV",
                    data=csv_data,
                    file_name=f"Attendance_Report_{target_date_str}.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True
                )

            # Excel Buffer
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
                df_export.to_excel(writer, index=False, sheet_name="Attendance_Logs")
            excel_data = excel_buf.getvalue()

            with exp_col2:
                st.download_button(
                    label="📊 Export Sheet as Excel (.xlsx)",
                    data=excel_data,
                    file_name=f"Attendance_Report_{target_date_str}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

    with tab_roster:
        st.subheader(f"Classroom Roster Status ({target_date_str})")
        r_col1, r_col2 = st.columns(2)

        with r_col1:
            st.markdown(f"#### ✅ Present ({len(summary['present_students'])})")
            if summary['present_students']:
                df_p = pd.DataFrame(summary['present_students'])[["roll_no", "full_name", "branch", "semester"]]
                st.dataframe(df_p.rename(columns={"roll_no": "Roll No", "full_name": "Name", "branch": "Branch", "semester": "Sem"}), use_container_width=True, hide_index=True)
            else:
                st.caption("No students marked present yet for this date.")

        with r_col2:
            st.markdown(f"#### ❌ Absent ({len(summary['absent_students'])})")
            if summary['absent_students']:
                df_a = pd.DataFrame(summary['absent_students'])[["roll_no", "full_name", "branch", "semester"]]
                st.dataframe(df_a.rename(columns={"roll_no": "Roll No", "full_name": "Name", "branch": "Branch", "semester": "Sem"}), use_container_width=True, hide_index=True)
            else:
                st.success("All enrolled students are present!")

    with tab_charts:
        st.subheader("Visual Analytics")
        if logs:
            df_charts = pd.DataFrame(logs)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Branch-wise Scans**")
                branch_counts = df_charts["branch"].value_counts().reset_index()
                branch_counts.columns = ["Branch", "Count"]
                st.bar_chart(branch_counts.set_index("Branch"))
            with c2:
                st.markdown("**Hourly Check-In Activity**")
                # Parse hour from time string
                df_charts["Hour"] = df_charts["check_in_time"].apply(lambda t: t.split(":")[0] + " " + t.split(" ")[-1])
                hour_counts = df_charts["Hour"].value_counts().reset_index()
                hour_counts.columns = ["Hour", "Scans"]
                st.line_chart(hour_counts.set_index("Hour"))
        else:
            st.info("Log attendance to view real-time graphical charts.")


# ==============================================================================
# TAB 4: LIBRARY ENTRY MANAGEMENT
# ==============================================================================
elif nav_choice == "📚 Library Entry Mode":
    st.markdown('<div class="section-title">📚 Library Entry & Study Hall Gate Management</div>', unsafe_allow_html=True)
    st.markdown("Automated turnstile logging replacing manual paper registers at the library circulation desk.")

    today_str = datetime.now().strftime("%Y-%m-%d")
    lib_logs = db.get_attendance_logs(target_date=today_str, entry_type="Library Gate Entry")

    lib_col1, lib_col2, lib_col3 = st.columns(3)
    with lib_col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Today's Library Visits</div>
            <div class="metric-value" style="color: #6366f1;">{len(lib_logs)}</div>
            <div class="metric-sub">Turnstile Check-ins</div>
        </div>
        """, unsafe_allow_html=True)
    with lib_col2:
        unique_visitors = len(set(l["roll_no"] for l in lib_logs))
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Unique Readers</div>
            <div class="metric-value" style="color: #0284c7;">{unique_visitors}</div>
            <div class="metric-sub">Distinct Student IDs</div>
        </div>
        """, unsafe_allow_html=True)
    with lib_col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Circulation Status</div>
            <div class="metric-value" style="color: #10b981;">ACTIVE</div>
            <div class="metric-sub">Auto-Relational Logging</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.subheader("Recent Library Entry Records")
    if lib_logs:
        df_lib = pd.DataFrame(lib_logs)[["log_id", "roll_no", "full_name", "branch", "check_in_time", "status"]]
        st.dataframe(df_lib.rename(columns={
            "log_id": "Entry ID",
            "roll_no": "Roll Number",
            "full_name": "Student Name",
            "branch": "Department",
            "check_in_time": "Entry Time",
            "status": "Access Status"
        }), use_container_width=True, hide_index=True)
    else:
        st.info("No library entries recorded today yet. Switch to the 'Live QR Scanner' tab and select 'Library Gate Entry' mode to scan.")


# ==============================================================================
# TAB 5: VIVA & PROJECT PRESENTATION HUB
# ==============================================================================
elif nav_choice == "🎓 Viva & Project Presentation Hub":
    st.markdown('<div class="section-title">🎓 Viva & Project Presentation Cheatsheet</div>', unsafe_allow_html=True)
    st.markdown("Ready-to-explain points, relational schema diagrams, and examiner answers for your final evaluation.")

    viva_tab1, viva_tab2, viva_tab3 = st.tabs(["📋 System Workflow (4 Steps)", "🗄️ Database Design (ER Schema)", "💡 Top Viva Q&A"])

    with viva_tab1:
        st.subheader("4-Step Viva Flow (Input → Process → Database → Output)")
        st.markdown("""
        Explain this exact sequence to your examiner to showcase end-to-end understanding:
        """)

        step_col1, step_col2 = st.columns(2)
        with step_col1:
            st.markdown("""
            **Step 1: QR ID Generation (Encoding)**
            - **Input:** Student details (Roll No, Full Name, Branch, Semester).
            - **Engine:** Python's `qrcode` library with `PIL` (Pillow).
            - **Mechanism:** Encodes unique Roll Number (`CSE-2026-042`) into a high-contrast 2D matrix barcode with Level-H error correction (up to 30% error recovery).
            - **Output:** Printable digital identity card pass (`.png`).
            """)
            st.markdown("""
            **Step 2: Real-Time Webcam Scanning (Decoding)**
            - **Input:** Live camera video stream frame-by-frame.
            - **Engine:** OpenCV (`cv2.VideoCapture` & `cv2.QRCodeDetector`).
            - **Mechanism:** Locates the three square **Finder Patterns** (1:1:3:1:1 black-white ratio), computes perspective transformation, and extracts string payload.
            """)

        with step_col2:
            st.markdown("""
            **Step 3: Validation & Database Logging (DBMS Logic)**
            - **Input:** Decoded string payload (`CSE-2026-042`).
            - **Engine:** Python `sqlite3` Relational Database.
            - **Mechanism:** Executes composite duplicate check:
              `SELECT * FROM attendance_logs WHERE roll_no = ? AND scan_date = ?`
            - **Condition:** If record exists → returns *Already Marked Present*. If not → executes `INSERT` with timestamp.
            """)
            st.markdown("""
            **Step 4: Dashboard & Report Export (Output)**
            - **Engine:** Streamlit & Pandas.
            - **Features:** Live present/absent counters, interactive filtering by branch & date, and **one-click export** to CSV and Excel (`.xlsx`).
            """)

    with viva_tab2:
        st.subheader("Relational Database Schema (2 Normalized Tables)")
        st.markdown("""
        You can draw these two normalized tables directly on the board:
        """)

        schema_col1, schema_col2 = st.columns(2)
        with schema_col1:
            st.markdown("""
            #### 1. `students` (Master Entity)
            | Column | Data Type | Constraint | Description |
            | :--- | :--- | :--- | :--- |
            | `roll_no` | `TEXT` | **PRIMARY KEY** | Unique student identifier |
            | `full_name`| `TEXT` | `NOT NULL` | Student full name |
            | `branch` | `TEXT` | `NOT NULL` | Engineering department |
            | `semester` | `TEXT` | `NOT NULL` | Current academic semester |
            | `qr_path` | `TEXT` | - | Local file path to generated pass |
            | `created_at`| `TEXT` | `DEFAULT NOW` | Enrollment timestamp |
            """)

        with schema_col2:
            st.markdown("""
            #### 2. `attendance_logs` (Transaction Entity)
            | Column | Data Type | Constraint | Description |
            | :--- | :--- | :--- | :--- |
            | `log_id` | `INTEGER` | **PK AUTOINCREMENT** | Unique entry log ID |
            | `roll_no` | `TEXT` | **FOREIGN KEY** | References `students(roll_no)` |
            | `scan_date`| `TEXT` | `NOT NULL` | Date of scan (`YYYY-MM-DD`) |
            | `check_in_time`| `TEXT`| `NOT NULL` | Timestamp (`HH:MM:SS AM/PM`) |
            | `status` | `TEXT` | `DEFAULT 'Present'` | Attendance state |
            | `entry_type` | `TEXT` | - | Classroom vs Library Gate |
            """)

        with st.expander("🔍 View Raw SQL DDL Code"):
            st.code("""
-- 1. Students Master Table
CREATE TABLE students (
    roll_no TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    branch TEXT NOT NULL,
    semester TEXT NOT NULL,
    qr_path TEXT,
    created_at TEXT DEFAULT (DATETIME('now', 'localtime'))
);

-- 2. Attendance Transaction Logs Table
CREATE TABLE attendance_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT NOT NULL,
    scan_date TEXT NOT NULL,
    check_in_time TEXT NOT NULL,
    status TEXT DEFAULT 'Present',
    entry_type TEXT DEFAULT 'Classroom Attendance',
    FOREIGN KEY (roll_no) REFERENCES students (roll_no) ON DELETE CASCADE
);

-- Composite Index for Sub-Second Duplicate Verification
CREATE INDEX idx_attendance_lookup 
ON attendance_logs (roll_no, scan_date, entry_type);
            """, language="sql")

    with viva_tab3:
        st.subheader("Top Viva Questions & Examiner-Ready Answers")

        st.markdown("""
        <div class="viva-box">
            <div class="viva-q">Q1: How does your system stop a student from scanning their QR code 5 times in a row?</div>
            <div class="viva-a">
                <b>Answer:</b> We apply a composite uniqueness check in SQL:
                <code>SELECT * FROM attendance_logs WHERE roll_no = ? AND scan_date = CURRENT_DATE AND entry_type = ?</code>.
                If a row already exists for that student on that date, the application displays an <b>"Already Marked Present"</b> alert with their original check-in timestamp instead of inserting a duplicate row.
            </div>
        </div>

        <div class="viva-box">
            <div class="viva-q">Q2: Why did you choose SQLite instead of MySQL or MongoDB for this microproject?</div>
            <div class="viva-a">
                <b>Answer:</b> SQLite is a serverless, ACID-compliant relational database built directly into Python's standard library (<code>sqlite3</code>). It requires zero background server configuration, zero networking ports, and stores all relational tables inside a single portable <code>attendance.db</code> file, making it ideal for standalone college lab deployment.
            </div>
        </div>

        <div class="viva-box">
            <div class="viva-q">Q3: How does OpenCV recognize a QR code even if the card is slightly tilted?</div>
            <div class="viva-a">
                <b>Answer:</b> Every QR code contains three large square <b>Finder Patterns</b> in its top-left, top-right, and bottom-left corners. OpenCV's <code>QRCodeDetector</code> searches for the specific ratio of black-to-white pixels (<b>1:1:3:1:1</b>) within those squares. Once detected, it calculates the geometric perspective transformation (homography matrix) to rectify the tilt before reading the encoded data bits.
            </div>
        </div>

        <div class="viva-box">
            <div class="viva-q">Bonus Q4: What happens if someone scans a random QR code (like a product barcode)?</div>
            <div class="viva-a">
                <b>Answer:</b> The system performs a foreign key integrity check against the <code>students</code> table. If the decoded payload does not exist in the database, it rejects the scan with an <b>"Unrecognized QR Payload"</b> error and logs nothing.
            </div>
        </div>

        <div class="viva-box">
            <div class="viva-q">Bonus Q5: What error correction level is used and why does it matter?</div>
            <div class="viva-a">
                <b>Answer:</b> We use <b>Error Correction Level H (High)</b> from Python's <code>qrcode</code> library, based on Reed-Solomon algebraic codes. This allows the QR code to be decoded accurately even if up to <b>30%</b> of the code surface is smudged, scratched, or occluded.
            </div>
        </div>
        """, unsafe_allow_html=True)


# ---------------- Footer ----------------
st.write("---")
st.markdown("""
<div style="text-align: center; color: #64748b; font-size: 13px;">
    Smart QR-Based Student Attendance & Library Entry Management System • Built with Python, OpenCV, SQLite & Streamlit
</div>
""", unsafe_allow_html=True)

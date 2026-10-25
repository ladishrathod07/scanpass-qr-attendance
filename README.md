# Smart QR-Based Student Attendance & Library Entry Management System

An automated, contactless student attendance and entry management system using 2D Quick Response (QR) codes, Computer Vision (OpenCV), a normalized Relational Database (SQLite), and a modern Web Dashboard (Streamlit).

---

## 1. Project Title & Abstract

- **Title:** Smart QR-Based Student Attendance & Library Entry Management System
- **Abstract:** Manual roll calls and paper-based library logbooks are time-consuming, prone to proxy entries, and difficult to digitize for monthly reporting. This microproject implements an automated, contactless attendance and entry logging system using 2D Quick Response (QR) codes, Computer Vision, and a Relational Database. Each student is assigned a unique QR ID card containing encoded roll number and department metadata. When presented to a webcam, the system decodes the QR payload in real time, validates against duplicate scans within the same session, logs the exact timestamp into an SQLite database, and provides faculty with a one-click CSV/Excel attendance report.

---

## 2. Core Objectives

1. **Eliminate Paper Registers:** Replace manual sign-in sheets with a sub-second webcam scan.
2. **Prevent Duplicate/Proxy Logging:** Enforce a composite database check (`WHERE roll_no = ? AND scan_date = CURRENT_DATE`) so the same student ID cannot be marked present twice on the same date/session.
3. **Automate Record Keeping:** Store structured relational records (`students` and `attendance_logs`) and export filtered attendance sheets to CSV and Excel (`.xlsx`).

---

## 3. System Workflow (4 Steps to Explain in Viva)

```mermaid
graph LR
    A["Step 1: QR ID Generation<br/>(qrcode & Pillow)"] --> B["Step 2: Webcam Scanning<br/>(OpenCV Finder Patterns)"]
    B --> C["Step 3: DBMS Validation<br/>(Composite Duplicate Check)"]
    C --> D["Step 4: Dashboard & Export<br/>(Streamlit, CSV & Excel)"]
```

- **Step 1: QR ID Generation (Encoding):** When a new student registers (Roll No, Name, Branch, Year), Python's `qrcode` library converts their unique Roll Number (e.g., `CSE-2026-042`) into a high-contrast 2D matrix barcode image (`.png`) that can be printed on an ID card or shown on a phone.
- **Step 2: Real-Time Webcam Scanning (Decoding):** The scanner module uses OpenCV (`cv2.VideoCapture` and `cv2.QRCodeDetector`) to capture live video frames, detect the corner finder patterns of the QR code, and extract the encoded Roll Number string instantly.
- **Step 3: Validation & Database Logging (DBMS Logic):** Before inserting a record, the system runs a SQL query on SQLite (`SELECT * FROM attendance_logs WHERE roll_no = ? AND scan_date = ? AND entry_type = ?`) to check if the student was already marked present today. If not, it executes an `INSERT` query with the current date and time stamp.
- **Step 4: Dashboard & Report Export (Output):** The admin screen displays live attendance counts, a searchable table of present/absent students, and "Export CSV" / "Export Excel" buttons using Pandas for faculty grading.

---

## 4. Database Design (ER Schema)

The database uses two normalized tables in SQLite (`attendance.db`):

### 1. `students` Table (Master Entity)
| Column | Data Type | Key Constraints | Purpose |
| :--- | :--- | :--- | :--- |
| `roll_no` | `TEXT` | **PRIMARY KEY** | Unique student identifier (e.g. `CSE-2026-042`) |
| `full_name` | `TEXT` | `NOT NULL` | Student full name |
| `branch` | `TEXT` | `NOT NULL` | Department/Specialization |
| `semester` | `TEXT` | `NOT NULL` | Academic semester |
| `qr_path` | `TEXT` | - | Local file path to generated ID pass image |
| `created_at` | `TEXT` | `DEFAULT CURRENT_TIMESTAMP` | Date and time enrolled |

### 2. `attendance_logs` Table (Transaction Entity)
| Column | Data Type | Key Constraints | Purpose |
| :--- | :--- | :--- | :--- |
| `log_id` | `INTEGER` | **PRIMARY KEY AUTOINCREMENT** | Unique log entry sequence |
| `roll_no` | `TEXT` | **FOREIGN KEY → students(roll_no)** | Links log to master student |
| `scan_date` | `TEXT` | `NOT NULL` | Date of scan (`YYYY-MM-DD`) |
| `check_in_time` | `TEXT` | `NOT NULL` | Exact check-in timestamp (`HH:MM:SS AM/PM`) |
| `status` | `TEXT` | `DEFAULT 'Present'` | Present / Late / Excused |
| `entry_type` | `TEXT` | `DEFAULT 'Classroom Attendance'` | Classroom vs Library Gate Entry |

### Composite Index
```sql
CREATE INDEX idx_attendance_lookup 
ON attendance_logs (roll_no, scan_date, entry_type);
```

---

## 5. Hardware & Software Requirements

- **Programming Language:** Python 3.10+ (Tested on Python 3.14)
- **Libraries Used:**
  - `qrcode[pil]`: Generates and saves student QR code passes.
  - `opencv-python` (`cv2`): Captures webcam frames and decodes QR codes without external scanner hardware.
  - `pandas` & `openpyxl`: Data manipulation and one-click CSV / Excel export.
  - `streamlit`: Clean, modern graphical web dashboard.
  - `sqlite3`: Built into Python; zero-server setup portable relational database.
- **Hardware:** Standard laptop with built-in or USB webcam and 4 GB RAM.

---

## 6. How to Run the Project

### Option A: Modern JavaScript Web App (Recommended UI)
Double-click [`run_js_app.bat`](file:///c:/Users/BeatsVibe/Downloads/Smart%20QR-Based%20Student%20Attendance%20&%20Library%20Entry%20Management%20System/run_js_app.bat) or execute:
```bash
.venv\Scripts\python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```
Open **`http://localhost:8000`** in any web browser.
- **Client-Side In-Browser QR Scanner:** Uses `jsQR` with animated holographic targeting reticle and synthesized Web Audio chime feedback.
- **Student Registration & Printable Pass Preview:** Live card rendering with 1-click download.
- **Dynamic Attendance Roster:** Live present/absent breakdown and instant CSV & Excel export.
- **Library Turnstile Mode:** Real-time occupancy tracker.
- **Viva Presentation Hub:** Interactive 4-step workflow, relational schema diagrams, and top Q&A flashcards.

---

### Option B: Streamlit Web Dashboard
Double-click [`run.bat`](file:///c:/Users/BeatsVibe/Downloads/Smart%20QR-Based%20Student%20Attendance%20&%20Library%20Entry%20Management%20System/run.bat) or execute:
```bash
.venv\Scripts\streamlit run app.py --server.port 8501
```
Open **`http://localhost:8501`** in your browser.

---

### Option C: Standalone Real-Time OpenCV Window
Double-click [`run_scanner.bat`](file:///c:/Users/BeatsVibe/Downloads/Smart%20QR-Based%20Student%20Attendance%20&%20Library%20Entry%20Management%20System/run_scanner.bat) or execute:
```bash
.venv\Scripts\python scanner.py
# Or for library mode:
.venv\Scripts\python scanner.py library
```
- Press `q` or `ESC` to quit.
- Press `c` to toggle between Classroom Attendance and Library Entry.

---

## 7. Project File Structure

```
Smart QR-Based Student Attendance & Library Entry Management System/
│
├── frontend/               # Full JavaScript Frontend
│   ├── index.html          # Semantic HTML5 layout
│   ├── style.css           # Glassmorphism & Cyber Dark UI styling
│   ├── app.js              # Pure Vanilla JS (Camera, jsQR, Web Audio API, REST APIs)
│   └── jsQR.min.js         # Offline client-side QR decoder
│
├── server.py               # FastAPI backend (REST API & static delivery)
├── database.py             # SQLite Relational Database Engine
├── qr_generator.py         # 2D QR Matrix & Digital Student ID Card Generator
├── scanner.py              # Standalone OpenCV Real-Time Webcam Scanner
├── app.py                  # Streamlit Web Dashboard
├── requirements.txt        # Frozen dependencies
│
├── run_js_app.bat          # 1-Click launcher for JavaScript Web App (Port 8000)
├── run.bat                 # 1-Click launcher for Streamlit App (Port 8501)
├── run_scanner.bat         # 1-Click launcher for OpenCV Camera Window
│
├── attendance.db           # SQLite database file
├── static/
│   ├── qr_codes/           # Generated QR codes (.png)
│   └── id_cards/           # Printable Digital Student ID Passes (.png)
└── README.md               # Complete Project & Viva Documentation
```

---

## 8. Top Viva Questions & Ready Answers

### Q1: How does your system stop a student from scanning their QR code 5 times in a row?
**Answer:** We apply a composite uniqueness check in SQL (`WHERE roll_no = ? AND scan_date = CURRENT_DATE AND entry_type = ?`). If a row already exists for that student on that date, the system displays an **"Already Marked Present"** alert with their original check-in timestamp instead of inserting a duplicate row.

### Q2: Why did you choose SQLite instead of MySQL or MongoDB for this microproject?
**Answer:** SQLite is a serverless, ACID-compliant relational database built directly into Python's standard library (`sqlite3`). It requires zero background server configuration, zero networking ports, and stores all relational tables inside a single portable `attendance.db` file, making it ideal for standalone college lab deployment.

### Q3: How does OpenCV recognize a QR code even if the card is slightly tilted?
**Answer:** Every QR code contains three large square **Finder Patterns** in its top-left, top-right, and bottom-left corners. OpenCV's `QRCodeDetector` searches for the specific ratio of black-to-white pixels (**1:1:3:1:1**) within those squares. Once detected, it calculates the geometric perspective transformation (homography matrix) to rectify the tilt before reading the encoded data bits.

### Bonus Q4: What happens if someone scans a random QR code (e.g., from a snack wrapper)?
**Answer:** The system executes a validation query against the `students` master table. If the decoded string does not match any enrolled `roll_no`, it rejects the scan with an **"Unrecognized QR Payload"** notification and does not log attendance.

### Bonus Q5: What error correction level is used in your QR generation?
**Answer:** We configure **Error Correction Level H (High)** using Reed-Solomon algebraic coding. This ensures the QR matrix can be decoded reliably even if up to **30%** of the pass is scratched, smudged, or occluded.

---

## 9. Deploying to Vercel (1-Click Cloud Deployment)

1. Go to [Vercel](https://vercel.com/) and click **"Add New Project"**.
2. Import your GitHub repository (`scanpass-qr-attendance`).
3. Leave **Framework Preset** as **Other** (Vercel automatically detects `vercel.json` and Python backend in `api/index.py`).
4. Click **Deploy**.
5. Once deployment completes, your live web portal with camera scanner, real-time KPI metrics, student registration, and CSV/Excel downloads is accessible anywhere on the internet!

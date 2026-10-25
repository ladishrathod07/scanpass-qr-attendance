"""
Database Management Module for Smart QR-Based Student Attendance & Library Entry Management System
Handles SQLite database connection, schema setup, CRUD operations, duplicate checks, and report queries.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

import shutil
import tempfile

IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
DEFAULT_DIR = os.path.dirname(os.path.abspath(__file__))

if IS_VERCEL:
    TMP_DIR = tempfile.gettempdir()
    DB_PATH = os.path.join(TMP_DIR, "attendance.db")
    repo_db = os.path.join(DEFAULT_DIR, "attendance.db")
    if os.path.exists(repo_db) and not os.path.exists(DB_PATH):
        try:
            shutil.copy2(repo_db, DB_PATH)
        except Exception:
            pass
else:
    DB_PATH = os.path.join(DEFAULT_DIR, "attendance.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Creates a connection to the SQLite database and returns it with row_factory enabled."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """
    Initializes the database schema with normalized relational tables:
    1. students: roll_no (PK), full_name, branch, semester, qr_path, created_at
    2. attendance_logs: log_id (PK AUTOINCREMENT), roll_no (FK), scan_date, check_in_time, status, entry_type
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. Students Master Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            roll_no TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            branch TEXT NOT NULL,
            semester TEXT NOT NULL,
            qr_path TEXT,
            created_at TEXT DEFAULT (DATETIME('now', 'localtime'))
        )
    """)

    # 2. Attendance Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT NOT NULL,
            scan_date TEXT NOT NULL,
            check_in_time TEXT NOT NULL,
            status TEXT DEFAULT 'Present',
            entry_type TEXT DEFAULT 'Classroom Attendance',
            FOREIGN KEY (roll_no) REFERENCES students (roll_no) ON DELETE CASCADE
        )
    """)

    # Index for fast duplicate-lookup by roll_no, scan_date, and entry_type
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_attendance_lookup 
        ON attendance_logs (roll_no, scan_date, entry_type)
    """)

    conn.commit()
    conn.close()

    # Automatically populate sample students if table is empty
    try:
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM students")
        count = cur.fetchone()[0]
        conn.close()
        if count == 0:
            seed_sample_students(db_path)
    except Exception:
        pass


def add_student(
    roll_no: str,
    full_name: str,
    branch: str,
    semester: str,
    qr_path: Optional[str] = None,
    db_path: str = DB_PATH
) -> Tuple[bool, str]:
    """
    Registers a new student into the students table.
    Returns (True, message) if successful, or (False, error_message) if roll_no already exists.
    """
    roll_no = roll_no.strip().upper()
    full_name = full_name.strip()
    branch = branch.strip()
    semester = semester.strip()

    if not roll_no or not full_name:
        return False, "Roll number and Full Name are required."

    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO students (roll_no, full_name, branch, semester, qr_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (roll_no, full_name, branch, semester, qr_path)
        )
        conn.commit()
        return True, f"Student {full_name} ({roll_no}) registered successfully."
    except sqlite3.IntegrityError:
        return False, f"Student with Roll No '{roll_no}' already exists in database."
    except Exception as e:
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def update_student_qr_path(roll_no: str, qr_path: str, db_path: str = DB_PATH) -> bool:
    """Updates the QR code file path for a registered student."""
    roll_no = roll_no.strip().upper()
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE students SET qr_path = ? WHERE roll_no = ?",
        (qr_path, roll_no)
    )
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

# Main Function For Backup Student Data
def get_student(roll_no: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves student record by Roll No."""
    roll_no = roll_no.strip().upper()
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_students(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves all registered students ordered by roll_no."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students ORDER BY roll_no ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_student(roll_no: str, db_path: str = DB_PATH) -> Tuple[bool, str]:
    """Deletes student and their associated attendance logs."""
    roll_no = roll_no.strip().upper()
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance_logs WHERE roll_no = ?", (roll_no,))
    cursor.execute("DELETE FROM students WHERE roll_no = ?", (roll_no,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    if success:
        return True, f"Student {roll_no} deleted successfully."
    return False, f"Student {roll_no} not found."


def record_attendance(
    roll_no: str,
    entry_type: str = "Classroom Attendance",
    status: str = "Present",
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Core DBMS Attendance Logic:
    1. Validates if roll_no exists in students table.
    2. Runs composite uniqueness query:
       SELECT * FROM attendance_logs WHERE roll_no = ? AND scan_date = ? AND entry_type = ?
    3. If row exists: Returns duplicate status with original timestamp.
    4. If not exists: Performs INSERT with current date and time.
    """
    roll_no = roll_no.strip().upper()
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%I:%M:%S %p")

    student = get_student(roll_no, db_path=db_path)
    if not student:
        return {
            "success": False,
            "status_code": "NOT_REGISTERED",
            "message": f"Unrecognized QR Payload: '{roll_no}' is not registered in the system.",
            "student": None,
            "scan_time": current_time,
            "scan_date": current_date,
            "entry_type": entry_type
        }

    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Step 3 Check: Composite duplicate scan validation
    cursor.execute(
        """
        SELECT * FROM attendance_logs 
        WHERE roll_no = ? AND scan_date = ? AND entry_type = ?
        """,
        (roll_no, current_date, entry_type)
    )
    existing_record = cursor.fetchone()

    if existing_record:
        conn.close()
        return {
            "success": False,
            "status_code": "ALREADY_LOGGED",
            "message": f"Already marked {existing_record['status']} today at {existing_record['check_in_time']}.",
            "student": student,
            "scan_time": existing_record["check_in_time"],
            "scan_date": current_date,
            "entry_type": entry_type,
            "log_id": existing_record["log_id"]
        }

    # Record new attendance
    cursor.execute(
        """
        INSERT INTO attendance_logs (roll_no, scan_date, check_in_time, status, entry_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (roll_no, current_date, current_time, status, entry_type)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return {
        "success": True,
        "status_code": "LOGGED_SUCCESS",
        "message": f"Marked {status} successfully at {current_time}.",
        "student": student,
        "scan_time": current_time,
        "scan_date": current_date,
        "entry_type": entry_type,
        "log_id": new_id
    }


def get_attendance_logs(
    target_date: Optional[str] = None,
    branch: Optional[str] = None,
    semester: Optional[str] = None,
    entry_type: Optional[str] = None,
    db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    """
    Retrieves attendance logs joined with student master details.
    Supports optional filtering by scan_date, branch, semester, and entry_type.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    query = """
        SELECT 
            a.log_id,
            a.roll_no,
            s.full_name,
            s.branch,
            s.semester,
            a.scan_date,
            a.check_in_time,
            a.status,
            a.entry_type
        FROM attendance_logs a
        JOIN students s ON a.roll_no = s.roll_no
        WHERE 1=1
    """
    params: List[Any] = []

    if target_date:
        query += " AND a.scan_date = ?"
        params.append(target_date)
    if branch and branch != "All Branches":
        query += " AND s.branch = ?"
        params.append(branch)
    if semester and semester != "All Semesters":
        query += " AND s.semester = ?"
        params.append(semester)
    if entry_type and entry_type != "All Entry Types":
        query += " AND a.entry_type = ?"
        params.append(entry_type)

    query += " ORDER BY a.log_id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attendance_summary(target_date: Optional[str] = None, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Computes summary metrics for a given date (defaults to today):
    - Total Enrolled Students
    - Total Present Today
    - Total Absent Today
    - Overall Attendance Percentage
    - List of Present Students
    - List of Absent Students
    """
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    all_students = get_all_students(db_path)
    total_enrolled = len(all_students)

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT roll_no 
        FROM attendance_logs 
        WHERE scan_date = ? AND status = 'Present'
        """,
        (target_date,)
    )
    present_roll_nos = {r["roll_no"] for r in cursor.fetchall()}
    conn.close()

    present_students = [s for s in all_students if s["roll_no"] in present_roll_nos]
    absent_students = [s for s in all_students if s["roll_no"] not in present_roll_nos]

    total_present = len(present_students)
    total_absent = len(absent_students)
    rate = round((total_present / total_enrolled * 100), 1) if total_enrolled > 0 else 0.0

    return {
        "date": target_date,
        "total_enrolled": total_enrolled,
        "total_present": total_present,
        "total_absent": total_absent,
        "attendance_rate": rate,
        "present_students": present_students,
        "absent_students": absent_students
    }


def seed_sample_students(db_path: str = DB_PATH) -> int:
    """Populates initial sample students for immediate testing and viva demo."""
    sample_students = [
        ("CSE-2026-042", "Aarav Sharma", "Computer Science", "Sem 6"),
        ("CSE-2026-043", "Priya Patel", "Computer Science", "Sem 6"),
        ("IT-2026-015", "Rohan Verma", "Information Technology", "Sem 4"),
        ("AIDS-2026-008", "Sneha Kulkarni", "AI & Data Science", "Sem 4"),
        ("ECE-2026-027", "Vikram Singh", "Electronics & Comm", "Sem 6"),
        ("MECH-2026-011", "Ananya Deshmukh", "Mechanical Engg", "Sem 2"),
    ]
    added_count = 0
    for roll, name, branch, sem in sample_students:
        success, _ = add_student(roll, name, branch, sem, db_path=db_path)
        if success:
            added_count += 1
    return added_count


# Initialize on import
init_db()

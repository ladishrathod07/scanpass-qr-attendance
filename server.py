"""
FastAPI Server for Smart QR-Based Student Attendance & Library Entry System
Serves the JavaScript Frontend UI and provides full REST API endpoints.
"""

import os
import io
import cv2
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database as db
import qr_generator as qrg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Ensure required directories exist
os.makedirs(FRONTEND_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Initialize database
db.init_db()

app = FastAPI(
    title="Smart QR Attendance & Library Entry API",
    description="Contactless Student Attendance & Entry Management System API",
    version="2.0.0"
)

# Enable CORS for flexible development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static asset folders
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


# ----------------- Request Models -----------------
class StudentCreate(BaseModel):
    roll_no: str
    full_name: str
    branch: str
    semester: str


class AttendanceScan(BaseModel):
    roll_no: str
    entry_type: str = "Classroom Attendance"


# ----------------- Frontend Route -----------------
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h2>Frontend index.html is being prepared...</h2>")


# ----------------- REST API Endpoints -----------------

@app.get("/api/stats")
async def get_system_stats(target_date: Optional[str] = None):
    """Returns real-time KPI metrics for dashboard."""
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    summary = db.get_attendance_summary(target_date)
    lib_logs = db.get_attendance_logs(target_date=target_date, entry_type="Library Gate Entry")
    
    return {
        "date": target_date,
        "total_enrolled": summary["total_enrolled"],
        "total_present": summary["total_present"],
        "total_absent": summary["total_absent"],
        "attendance_rate": summary["attendance_rate"],
        "library_visits": len(lib_logs),
        "library_unique_readers": len(set(l["roll_no"] for l in lib_logs))
    }


@app.get("/api/students")
async def list_students():
    """Returns all enrolled students."""
    students = db.get_all_students()
    return {"students": students, "count": len(students)}


@app.post("/api/students")
async def register_student(student: StudentCreate):
    """Registers a new student and generates high-contrast QR pass."""
    success, msg = db.add_student(
        student.roll_no,
        student.full_name,
        student.branch,
        student.semester
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    
    card_path, _ = qrg.generate_student_id_card(
        student.roll_no,
        student.full_name,
        student.branch,
        student.semester
    )
    db.update_student_qr_path(student.roll_no, card_path)
    
    saved_std = db.get_student(student.roll_no)
    return {
        "success": True,
        "message": msg,
        "student": saved_std,
        "card_url": f"/static/id_cards/{student.roll_no}_card.png",
        "qr_url": f"/static/qr_codes/{student.roll_no}.png"
    }


@app.delete("/api/students/{roll_no}")
async def remove_student(roll_no: str):
    """Deletes student and associated records."""
    success, msg = db.delete_student(roll_no)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/students/seed")
async def seed_students():
    """Seeds sample students with ready-to-use ID passes."""
    c = db.seed_sample_students()
    students = db.get_all_students()
    for s in students:
        cp, _ = qrg.generate_student_id_card(s["roll_no"], s["full_name"], s["branch"], s["semester"])
        db.update_student_qr_path(s["roll_no"], cp)
    return {"success": True, "seeded_count": c, "total_students": len(students)}


@app.post("/api/attendance/scan")
async def process_attendance_scan(scan: AttendanceScan):
    """
    Core DBMS Attendance Verification:
    - Validates payload against students table
    - Checks composite duplicate: SELECT * WHERE roll_no = ? AND scan_date = ? AND entry_type = ?
    - Inserts attendance or returns duplicate warning
    """
    result = db.record_attendance(
        roll_no=scan.roll_no,
        entry_type=scan.entry_type
    )
    return result


@app.get("/api/attendance/logs")
async def get_logs(
    date: Optional[str] = Query(None),
    branch: Optional[str] = Query(None),
    semester: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None)
):
    """Returns filtered attendance logs."""
    logs = db.get_attendance_logs(
        target_date=date,
        branch=branch,
        semester=semester,
        entry_type=entry_type
    )
    return {"logs": logs, "count": len(logs)}


@app.get("/api/attendance/summary")
async def get_summary(date: Optional[str] = Query(None)):
    """Returns present vs absent breakdown and metrics."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    return db.get_attendance_summary(date)


@app.post("/api/attendance/decode-image")
async def decode_image_file(file: UploadFile = File(...)):
    """
    Decodes QR code from an uploaded image using OpenCV QRCodeDetector server-side.
    """
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img_cv is None:
        raise HTTPException(status_code=400, detail="Invalid image file format.")
    
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img_cv)
    
    if not data or not data.strip():
        return {
            "success": False,
            "message": "No valid QR code finder patterns detected in image.",
            "payload": None
        }
    
    payload = data.strip().upper()
    return {
        "success": True,
        "message": f"Successfully decoded payload: {payload}",
        "payload": payload
    }


@app.get("/api/attendance/export/csv")
async def export_attendance_csv(date: Optional[str] = Query(None)):
    """Exports attendance logs as a CSV file."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    logs = db.get_attendance_logs(target_date=date)
    if not logs:
        # Return empty template
        df = pd.DataFrame(columns=["log_id", "roll_no", "full_name", "branch", "semester", "scan_date", "check_in_time", "status", "entry_type"])
    else:
        df = pd.DataFrame(logs)
    
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=Attendance_Report_{date}.csv"}
    )


@app.get("/api/attendance/export/excel")
async def export_attendance_excel(date: Optional[str] = Query(None)):
    """Exports attendance logs as an Excel (.xlsx) file."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    logs = db.get_attendance_logs(target_date=date)
    if not logs:
        df = pd.DataFrame(columns=["log_id", "roll_no", "full_name", "branch", "semester", "scan_date", "check_in_time", "status", "entry_type"])
    else:
        df = pd.DataFrame(logs)
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance_Logs")
    
    excel_bytes = buf.getvalue()
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Attendance_Report_{date}.xlsx"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

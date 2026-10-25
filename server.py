"""
FastAPI Server for Smart QR-Based Student Attendance & Library Entry System
Serves the JavaScript Frontend UI and provides full REST API endpoints.
"""

import os
import io
import tempfile
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    import cv2
except Exception:
    cv2 = None

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database as db
import qr_generator as qrg

IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TMP_STATIC_DIR = os.path.join(tempfile.gettempdir(), "static")

# Ensure required directories exist
if not IS_VERCEL:
    os.makedirs(FRONTEND_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)
else:
    os.makedirs(TMP_STATIC_DIR, exist_ok=True)
    os.makedirs(os.path.join(TMP_STATIC_DIR, "qr_codes"), exist_ok=True)
    os.makedirs(os.path.join(TMP_STATIC_DIR, "id_cards"), exist_ok=True)

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


# ----------------- Frontend & Static Routes -----------------
@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
@app.get("/api/", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>Frontend index.html is being prepared...</h2>")


@app.get("/frontend/{file_path:path}")
async def serve_frontend_file(file_path: str):
    fpath = os.path.join(FRONTEND_DIR, file_path)
    if os.path.exists(fpath):
        media_type = "text/plain"
        if fpath.endswith(".css"): media_type = "text/css"
        elif fpath.endswith(".js"): media_type = "application/javascript"
        elif fpath.endswith(".html"): media_type = "text/html"
        with open(fpath, "rb") as f:
            return Response(content=f.read(), media_type=media_type)
    raise HTTPException(status_code=404, detail="Frontend file not found")


@app.get("/static/{file_path:path}")
async def serve_static_file(file_path: str):
    # Check /tmp/static first (newly generated files in serverless environment)
    tmp_path = os.path.join(TMP_STATIC_DIR, file_path)
    if os.path.exists(tmp_path):
        with open(tmp_path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")
    
    # Check project static folder
    repo_path = os.path.join(STATIC_DIR, file_path)
    if os.path.exists(repo_path):
        with open(repo_path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")
    
    raise HTTPException(status_code=404, detail="Static asset not found")


# ----------------- Request Models -----------------
class StudentCreate(BaseModel):
    roll_no: str
    full_name: str
    branch: str
    semester: str


class AttendanceScan(BaseModel):
    roll_no: str
    entry_type: str = "Classroom Attendance"


# ----------------- REST API Endpoints -----------------

@app.get("/api/stats")
@app.get("/stats")
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
@app.get("/students")
async def list_students():
    """Returns all enrolled students."""
    students = db.get_all_students()
    return {"students": students, "count": len(students)}


@app.post("/api/students")
@app.post("/students")
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
    
    card_path, card_img = qrg.generate_student_id_card(
        student.roll_no,
        student.full_name,
        student.branch,
        student.semester
    )
    db.update_student_qr_path(student.roll_no, card_path)
    
    saved_std = db.get_student(student.roll_no)
    card_b64 = qrg.get_card_base64(card_img)
    return {
        "success": True,
        "message": msg,
        "student": saved_std,
        "card_base64": card_b64,
        "card_url": f"/api/students/{student.roll_no}/card",
        "qr_url": f"/api/students/{student.roll_no}/qr"
    }


@app.get("/api/students/{roll_no}/card")
@app.get("/students/{roll_no}/card")
async def get_student_card_image(roll_no: str):
    """Dynamically serves or generates student ID card image."""
    std = db.get_student(roll_no)
    if not std:
        raise HTTPException(status_code=404, detail="Student not found")
    
    safe_fn = "".join(c if c.isalnum() or c in "-_" else "_" for c in roll_no)
    possible_paths = [
        os.path.join(TMP_STATIC_DIR, "id_cards", f"{safe_fn}_card.png"),
        os.path.join(STATIC_DIR, "id_cards", f"{safe_fn}_card.png"),
        os.path.join(BASE_DIR, "public", "static", "id_cards", f"{safe_fn}_card.png"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            with open(p, "rb") as f:
                return Response(content=f.read(), media_type="image/png")
    
    # Generate on the fly in memory if file is not found
    _, card_img = qrg.generate_student_id_card(
        std["roll_no"],
        std["full_name"],
        std["branch"],
        std["semester"]
    )
    img_bytes = qrg.get_card_bytes(card_img)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/students/{roll_no}/qr")
@app.get("/students/{roll_no}/qr")
async def get_student_qr_image(roll_no: str):
    """Dynamically serves or generates student QR code image."""
    safe_fn = "".join(c if c.isalnum() or c in "-_" else "_" for c in roll_no)
    possible_paths = [
        os.path.join(TMP_STATIC_DIR, "qr_codes", f"{safe_fn}.png"),
        os.path.join(STATIC_DIR, "qr_codes", f"{safe_fn}.png"),
        os.path.join(BASE_DIR, "public", "static", "qr_codes", f"{safe_fn}.png"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            with open(p, "rb") as f:
                return Response(content=f.read(), media_type="image/png")
    
    qr_img = qrg.generate_qr_image(roll_no)
    img_bytes = qrg.get_card_bytes(qr_img)
    return Response(content=img_bytes, media_type="image/png")


@app.delete("/api/students/{roll_no}")
@app.delete("/students/{roll_no}")
async def remove_student(roll_no: str):
    """Deletes student and associated records."""
    success, msg = db.delete_student(roll_no)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/students/seed")
@app.post("/students/seed")
async def seed_students():
    """Seeds sample students with ready-to-use ID passes."""
    c = db.seed_sample_students()
    students = db.get_all_students()
    for s in students:
        cp, _ = qrg.generate_student_id_card(s["roll_no"], s["full_name"], s["branch"], s["semester"])
        db.update_student_qr_path(s["roll_no"], cp)
    return {"success": True, "seeded_count": c, "total_students": len(students)}


@app.post("/api/attendance/scan")
@app.post("/attendance/scan")
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
@app.get("/attendance/logs")
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
@app.get("/attendance/summary")
async def get_summary(date: Optional[str] = Query(None)):
    """Returns present vs absent breakdown and metrics."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    return db.get_attendance_summary(date)


@app.post("/api/attendance/decode-image")
@app.post("/attendance/decode-image")
async def decode_image_file(file: UploadFile = File(...)):
    """
    Decodes QR code from an uploaded image using OpenCV QRCodeDetector server-side.
    """
    if cv2 is None:
        return {
            "success": False,
            "message": "Server-side OpenCV is not available in cloud serverless mode. Image is processed automatically in-browser.",
            "payload": None
        }
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
@app.get("/attendance/export/csv")
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
@app.get("/attendance/export/excel")
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

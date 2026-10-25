"""
QR Code & Digital Student ID Card Generator Module
Generates high-contrast 2D Quick Response matrices and printable Student ID Cards with metadata.
"""

import os
import io
import qrcode
import tempfile
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, Tuple

IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if IS_VERCEL:
    STATIC_DIR = os.path.join(tempfile.gettempdir(), "static")
else:
    STATIC_DIR = os.path.join(BASE_DIR, "static")

QR_DIR = os.path.join(STATIC_DIR, "qr_codes")
CARD_DIR = os.path.join(STATIC_DIR, "id_cards")

os.makedirs(QR_DIR, exist_ok=True)
os.makedirs(CARD_DIR, exist_ok=True)


def generate_qr_image(data_payload: str, box_size: int = 10, border: int = 3) -> Image.Image:
    """
    Step 1 (Encoding): Generates high-contrast 2D QR matrix for given payload string.
    Uses Error Correction Level H (up to 30% damage recovery) for reliable camera scanning.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data_payload.strip().upper())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img


def save_student_qr(roll_no: str) -> Tuple[str, Image.Image]:
    """Generates and saves a standalone QR code image to static/qr_codes/<roll_no>.png."""
    roll_no = roll_no.strip().upper()
    img = generate_qr_image(roll_no, box_size=10, border=3)
    safe_filename = "".join(c if c.isalnum() or c in "-_" else "_" for c in roll_no)
    file_path = os.path.join(QR_DIR, f"{safe_filename}.png")
    img.save(file_path, "PNG")
    return file_path, img


def get_default_font(size: int = 16):
    """Attempts to load standard TrueType fonts; falls back to default if unavailable."""
    font_candidates = [
        "arial.ttf",
        "segoeui.ttf",
        "tahoma.ttf",
        "calibri.ttf",
        "DejaVuSans.ttf",
        "Helvetica.ttf"
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def generate_student_id_card(
    roll_no: str,
    full_name: str,
    branch: str,
    semester: str
) -> Tuple[str, Image.Image]:
    """
    Generates a sleek, high-resolution printable Digital Student ID Card (680 x 420 px).
    Includes:
    - College / Campus Header Banner
    - Student Full Name, Roll No, Branch, Semester
    - Embedded High-Contrast QR Code
    - Microchip & Security Strip aesthetic
    - Save to static/id_cards/<roll_no>_card.png
    """
    roll_no = roll_no.strip().upper()
    full_name = full_name.strip()
    branch = branch.strip()
    semester = semester.strip()

    width, height = 700, 420
    card = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(card)

    # 1. Background gradient / header block
    # Deep Navy to Indigo header
    header_height = 95
    for y in range(header_height):
        ratio = y / header_height
        r = int(15 * (1 - ratio) + 30 * ratio)
        g = int(23 * (1 - ratio) + 41 * ratio)
        b = int(42 * (1 - ratio) + 59 * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Accent cyan line under header
    draw.rectangle([(0, header_height), (width, header_height + 4)], fill=(14, 165, 233))

    # Header Text
    font_title = get_default_font(22)
    font_sub = get_default_font(13)
    draw.text((30, 22), "ACADEMIC IDENTIFICATION CARD", fill=(255, 255, 255), font=font_title)
    draw.text((30, 56), "STUDENT ATTENDANCE & LIBRARY ENTRY PASS", fill=(148, 163, 184), font=font_sub)

    # Security Chip Graphic
    chip_x, chip_y = width - 110, 20
    draw.rounded_rectangle([chip_x, chip_y, chip_x + 70, chip_y + 55], radius=8, fill=(245, 158, 11), outline=(217, 119, 6), width=2)
    draw.line([(chip_x + 20, chip_y + 10), (chip_x + 50, chip_y + 10)], fill=(217, 119, 6), width=2)
    draw.line([(chip_x + 20, chip_y + 27), (chip_x + 50, chip_y + 27)], fill=(217, 119, 6), width=2)
    draw.line([(chip_x + 20, chip_y + 45), (chip_x + 50, chip_y + 45)], fill=(217, 119, 6), width=2)

    # 2. Main Card Content Area
    font_label = get_default_font(12)
    font_val = get_default_font(18)
    font_roll = get_default_font(24)

    # Student Name
    draw.text((35, 120), "FULL NAME", fill=(100, 116, 139), font=font_label)
    draw.text((35, 138), full_name, fill=(15, 23, 42), font=font_val)

    # Roll No with Highlight Box
    draw.text((35, 185), "ROLL NUMBER", fill=(100, 116, 139), font=font_label)
    draw.rounded_rectangle([(35, 205), (380, 255)], radius=6, fill=(241, 245, 249), outline=(203, 213, 225), width=1)
    draw.text((45, 215), roll_no, fill=(2, 132, 199), font=font_roll)

    # Branch
    draw.text((35, 275), "DEPARTMENT / BRANCH", fill=(100, 116, 139), font=font_label)
    draw.text((35, 295), branch, fill=(15, 23, 42), font=font_val)

    # Semester
    draw.text((250, 275), "SEMESTER", fill=(100, 116, 139), font=font_label)
    draw.text((250, 295), semester, fill=(15, 23, 42), font=font_val)

    # 3. Embedded QR Code on right side
    qr_img = generate_qr_image(roll_no, box_size=6, border=2)
    qr_img = qr_img.resize((210, 210), Image.Resampling.LANCZOS)

    qr_box_x, qr_box_y = 445, 120
    # QR Container Card
    draw.rounded_rectangle([qr_box_x - 10, qr_box_y - 10, qr_box_x + 220, qr_box_y + 220], radius=10, fill=(248, 250, 252), outline=(226, 232, 240), width=2)
    card.paste(qr_img, (qr_box_x, qr_box_y))

    # QR Scan helper caption
    font_tiny = get_default_font(11)
    draw.text((qr_box_x + 12, qr_box_y + 225), "SCAN PAYLOAD FOR ATTENDANCE", fill=(100, 116, 139), font=font_tiny)

    # 4. Footer Bar
    footer_y = height - 42
    draw.rectangle([(0, footer_y), (width, height)], fill=(241, 245, 249))
    draw.line([(0, footer_y), (width, footer_y)], fill=(226, 232, 240))
    draw.text((35, footer_y + 12), "AUTHORIZED CAMPUS CREDENTIAL • 2D QR VALIDATED", fill=(100, 116, 139), font=font_tiny)
    draw.text((width - 170, footer_y + 12), "STATUS: ACTIVE MEMBER", fill=(22, 163, 74), font=font_tiny)

    # Card outer border
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(203, 213, 225), width=2)

    # Save to disk
    safe_filename = "".join(c if c.isalnum() or c in "-_" else "_" for c in roll_no)
    card_path = os.path.join(CARD_DIR, f"{safe_filename}_card.png")
    card.save(card_path, "PNG")

    # Also save standalone QR code
    save_student_qr(roll_no)

    return card_path, card


def image_to_bytes(img: Image.Image, format: str = "PNG") -> bytes:
    """Converts a PIL Image to raw byte buffer for instant Streamlit downloads."""
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()

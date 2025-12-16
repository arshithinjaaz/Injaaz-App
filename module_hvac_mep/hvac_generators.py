"""
Optional generator wrapper for HVAC & MEP reports.
Placeholders included so the application can generate simple files.
Replace these placeholders with your real generators (xlsxwriter/reportlab code)
if and when you copy them from the old repo.
"""
import os
import time
import json

def create_excel_report(data, output_dir):
    """
    Create a simple placeholder .xlsx-like file (binary blob).
    Return the basename of the file created.
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = int(time.time())
    basename = f"hvac_report_{ts}.xlsx"
    path = os.path.join(output_dir, basename)
    # Placeholder content; replace with real workbook generation
    with open(path, "wb") as f:
        payload = f"HVAC Excel Placeholder\nData: {json.dumps(data) if data else '{}'}\n".encode("utf-8")
        f.write(payload)
    return basename

def create_pdf_report(data, output_dir):
    """
    Create a simple placeholder .pdf-like file.
    Return the basename of the file created.
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = int(time.time())
    basename = f"hvac_report_{ts}.pdf"
    path = os.path.join(output_dir, basename)
    # Placeholder content; replace with real PDF generation
    with open(path, "wb") as f:
        payload = f"HVAC PDF Placeholder\nData: {json.dumps(data) if data else '{}'}\n".encode("utf-8")
        f.write(payload)
    return basename
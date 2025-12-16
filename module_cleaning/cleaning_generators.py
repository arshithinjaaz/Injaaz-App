"""
Placeholder/wrapper for Cleaning report generation.
Replace with your real generators or import them here.
"""
import os
import time

def create_excel_report(data, output_dir):
    basename = f"cleaning_report_{int(time.time())}.xlsx"
    path = os.path.join(output_dir, basename)
    with open(path, "wb") as f:
        f.write(b"CLEANING EXCEL PLACEHOLDER")
    return basename

def create_pdf_report(data, output_dir):
    basename = f"cleaning_report_{int(time.time())}.pdf"
    path = os.path.join(output_dir, basename)
    with open(path, "wb") as f:
        f.write(b"CLEANING PDF PLACEHOLDER")
    return basename
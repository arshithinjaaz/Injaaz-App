"""
Placeholder / wrapper for civil report generators.
Replace with your real generator code or import the original files here.
"""
import os
import time

def create_excel_report(data, output_dir):
    basename = f"civil_report_{int(time.time())}.xlsx"
    path = os.path.join(output_dir, basename)
    with open(path, "wb") as f:
        f.write(b"CIVIL EXCEL PLACEHOLDER")
    return basename

def create_pdf_report(data, output_dir):
    basename = f"civil_report_{int(time.time())}.pdf"
    path = os.path.join(output_dir, basename)
    with open(path, "wb") as f:
        f.write(b"CIVIL PDF PLACEHOLDER")
    return basename
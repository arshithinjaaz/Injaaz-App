"""
Optional generator wrapper for HVAC & MEP reports.
If you have existing generator functions from the old repo,
copy them into this file (or keep this wrapper and import from old file paths).
This file exports create_excel_report and create_pdf_report.

Both functions accept:
- data: dict (submission data)
- output_dir: path to directory where output files should be written

They must return the basename of the generated file (e.g. "jobid_report.xlsx").
"""
import os
import json
import time

def create_excel_report(data, output_dir):
    # Replace with your real generator. This is a placeholder.
    basename = f"hvac_report_{int(time.time())}.xlsx"
    path = os.path.join(output_dir, basename)
    with open(path, "wb") as f:
        f.write(b"HVAC EXCEL PLACEHOLDER")
    return basename

def create_pdf_report(data, output_dir):
    # Replace with your real generator. This is a placeholder.
    basename = f"hvac_report_{int(time.time())}.pdf"
    path = os.path.join(output_dir, basename)
    with open(path, "wb") as f:
        f.write(b"HVAC PDF PLACEHOLDER")
    return basename
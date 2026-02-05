"""
Apply reversed header to Commencement Form: heading on the left, logo on the right.
Inserts a 1x2 table at the top and removes the old centered header paragraphs.

Run from project root: python scripts/commencement_header_logo_left_right.py
"""
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH


def add_header_table_to_commencement(doc_path, logo_path=None, backup=True):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if logo_path is None:
        logo_path = os.path.join(base, "static", "logo.png")
    if not os.path.isfile(doc_path):
        raise FileNotFoundError(f"Template not found: {doc_path}")
    if not os.path.isfile(logo_path):
        raise FileNotFoundError(f"Logo not found: {logo_path}")

    if backup:
        backup_dir = os.path.join(os.path.dirname(doc_path), "templates")
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, "Commencement Form - INJAAZ (before header).docx")
        shutil.copy2(doc_path, backup_path)
        print(f"Backed up to: {backup_path}")

    doc = Document(doc_path)
    body = doc._element.body

    # If there's already a header table (e.g. from a previous run with broken image), remove it
    had_existing_table = False
    first = body[0] if len(body) else None
    if first is not None:
        tag = first.tag.split("}")[-1] if "}" in first.tag else first.tag
        if tag == "tbl":
            body.remove(first)
            had_existing_table = True

    # Build header table IN THE SAME DOC so the logo is embedded in this docx package
    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    # Left column wide enough for "Commencement Form" on one line; right column for logo at right end
    try:
        table.rows[0].cells[0].width = Cm(6.5)
        table.rows[0].cells[1].width = Cm(11)
    except Exception:
        pass
    FORM_FONT = "Calibri"
    # Left cell: "Commencement Form" on one line (bold, single line)
    left_cell = table.rows[0].cells[0]
    left_cell.text = ""
    p_left = left_cell.paragraphs[0]
    p_left.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_left.paragraph_format.keep_together = True
    run = p_left.add_run("Commencement Form")
    run.bold = True
    run.font.size = Pt(16)
    run.font.name = FORM_FONT
    # Right cell: logo flush right (paragraph right-aligned, wide cell)
    right_cell = table.rows[0].cells[1]
    for p in right_cell.paragraphs:
        p.clear()
    p_right = right_cell.paragraphs[0]
    p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_right = p_right.add_run()
    run_right.add_picture(logo_path, width=Cm(1.8))
    tbl_element = table._tbl

    # Table was appended at end; move it to the beginning
    body.remove(tbl_element)
    body.insert(0, tbl_element)

    # On first run (no existing table): remove old header paragraphs (7 paras: empty/INJAAZ/Commencement/empty)
    if not had_existing_table:
        to_remove = []
        for i in range(1, min(8, len(body))):
            child = body[i]
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "p":
                to_remove.append(child)
        for el in to_remove:
            body.remove(el)

    doc.save(doc_path)
    print("Header updated: heading left, logo right. Saved:", doc_path)


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    doc_path = os.path.join(base, "HR Documents", "Commencement Form - INJAAZ.DOCX")
    add_header_table_to_commencement(doc_path, backup=True)


if __name__ == "__main__":
    main()

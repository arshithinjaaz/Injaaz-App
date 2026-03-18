import os
import sys
import json
import base64
import sqlite3
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from module_hvac_mep.hvac_generators import (
    create_pdf_report as create_hvac_pdf,
    create_excel_report as create_hvac_excel,
)
from module_civil.civil_generators import (
    create_pdf_report as create_civil_pdf,
    create_excel_report as create_civil_excel,
)
from module_cleaning.cleaning_generators import (
    create_pdf_report as create_cleaning_pdf,
    create_excel_report as create_cleaning_excel,
)


def _is_noisy_name(name):
    if not name:
        return True
    v = str(name).strip().lower()
    if len(v) < 4:
        return True
    noisy_tokens = ("sdf", "dfg", "asdf", "test", "xxx", "qwe")
    return any(t in v for t in noisy_tokens)


def _latest_form_data(conn, module_type):
    cur = conn.cursor()
    row = cur.execute(
        "SELECT form_data FROM submissions WHERE module_type=? ORDER BY id DESC LIMIT 1",
        (module_type,),
    ).fetchone()
    if not row:
        return {}
    raw = row[0]
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def _create_png(path, title, subtitle, bg_rgb):
    from PIL import Image, ImageDraw, ImageFont

    w, h = 1280, 720
    img = Image.new("RGB", (w, h), color=bg_rgb)
    draw = ImageDraw.Draw(img)
    font_title = ImageFont.load_default()
    font_sub = ImageFont.load_default()

    draw.rectangle([(28, 28), (w - 28, h - 28)], outline=(255, 255, 255), width=4)
    draw.rectangle([(42, 42), (w - 42, 128)], fill=(17, 84, 53))
    draw.text((58, 70), title, fill=(255, 255, 255), font=font_title)
    draw.text((58, 160), subtitle, fill=(255, 255, 255), font=font_sub)
    draw.text((58, 188), "Auto-generated preview image for report rendering test", fill=(240, 240, 240), font=font_sub)
    draw.text((58, 216), "INJAAZ FACILITY MANAGEMENT", fill=(220, 220, 220), font=font_sub)
    img.save(path, format="PNG")


def _create_signature_png(path, signer_name):
    from PIL import Image, ImageDraw, ImageFont

    w, h = 900, 260
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    draw.rectangle([(12, 12), (w - 12, h - 12)], outline=(32, 32, 32), width=2)
    draw.text((34, 40), f"Digitally Signed: {signer_name}", fill=(20, 20, 20), font=font)
    draw.text((34, 82), "/s/ " + signer_name, fill=(17, 84, 53), font=font)
    draw.text((34, 122), "INJAAZ APPROVAL STAMP", fill=(64, 64, 64), font=font)
    draw.text((34, 162), "Valid for internal workflow preview", fill=(64, 64, 64), font=font)
    img.save(path, format="PNG")


def _to_data_uri(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return "data:image/png;base64," + b64


def _prepare_media(output_dir):
    media_dir = os.path.join(output_dir, "auto_media")
    os.makedirs(media_dir, exist_ok=True)

    p_hvac_1 = os.path.join(media_dir, "hvac_photo_1.png")
    p_hvac_2 = os.path.join(media_dir, "hvac_photo_2.png")
    p_civil_1 = os.path.join(media_dir, "civil_photo_1.png")
    p_civil_2 = os.path.join(media_dir, "civil_photo_2.png")
    p_clean_1 = os.path.join(media_dir, "cleaning_photo_1.png")
    p_clean_2 = os.path.join(media_dir, "cleaning_photo_2.png")

    _create_png(p_hvac_1, "HVAC Site Photo", "AHU filter bank before replacement", (38, 70, 83))
    _create_png(p_hvac_2, "HVAC Site Photo", "FCU drain tray and seal check", (31, 55, 65))
    _create_png(p_civil_1, "Civil Site Photo", "Facade crack marking and prep", (98, 67, 36))
    _create_png(p_civil_2, "Civil Site Photo", "Waterproof touch-up area", (82, 59, 30))
    _create_png(p_clean_1, "Cleaning Site Photo", "Lobby surface sanitation check", (44, 67, 85))
    _create_png(p_clean_2, "Cleaning Site Photo", "Washroom deep-clean scope", (34, 54, 72))

    sig_supervisor = os.path.join(media_dir, "sig_supervisor.png")
    sig_ops = os.path.join(media_dir, "sig_operations_manager.png")
    sig_bd = os.path.join(media_dir, "sig_business_development.png")
    sig_proc = os.path.join(media_dir, "sig_procurement.png")
    sig_gm = os.path.join(media_dir, "sig_general_manager.png")

    _create_signature_png(sig_supervisor, "Supervisor - A. Rahman")
    _create_signature_png(sig_ops, "Operations Manager - M. Khan")
    _create_signature_png(sig_bd, "Business Development - S. Ali")
    _create_signature_png(sig_proc, "Procurement - R. Nair")
    _create_signature_png(sig_gm, "General Manager - K. Hassan")

    media = {
        "dir": media_dir,
        "photos": {
            "hvac": [{"url": _to_data_uri(p_hvac_1)}, {"url": _to_data_uri(p_hvac_2)}],
            "civil": [{"url": _to_data_uri(p_civil_1)}, {"url": _to_data_uri(p_civil_2)}],
            "cleaning": [{"url": _to_data_uri(p_clean_1)}, {"url": _to_data_uri(p_clean_2)}],
        },
        "signatures": {
            "supervisor": _to_data_uri(sig_supervisor),
            "operations_manager": _to_data_uri(sig_ops),
            "business_dev": _to_data_uri(sig_bd),
            "procurement": _to_data_uri(sig_proc),
            "general_manager": _to_data_uri(sig_gm),
        },
    }
    return media


def main():
    output_dir = os.path.join("generated", "inspection_materials_preview")
    os.makedirs(output_dir, exist_ok=True)
    today = str(date.today())

    db_path = os.path.join(os.path.dirname(__file__), "..", "injaaz.db")
    conn = sqlite3.connect(os.path.abspath(db_path))
    hvac_fd = _latest_form_data(conn, "hvac_mep")
    civil_fd = _latest_form_data(conn, "civil")
    cleaning_fd = _latest_form_data(conn, "cleaning")
    conn.close()

    media = _prepare_media(output_dir)

    hvac_site = hvac_fd.get("site_name")
    if _is_noisy_name(hvac_site):
        hvac_site = "Injaaz Facility - Marina Residence"

    civil_project = civil_fd.get("project_name")
    if _is_noisy_name(civil_project):
        civil_project = "Injaaz Civil Works - Block A"

    civil_location = civil_fd.get("location")
    if _is_noisy_name(civil_location):
        civil_location = "Dubai Marina"

    cleaning_project = cleaning_fd.get("project_name")
    if _is_noisy_name(cleaning_project):
        cleaning_project = "Work Injaaz - Residential Tower"

    hvac_sample_data = {
        "site_name": hvac_site,
        "visit_date": hvac_fd.get("visit_date") or today,
        "tech_signature": media["signatures"]["supervisor"],
        "supervisor_signature": media["signatures"]["supervisor"],
        "supervisor_comments": "Inspection reviewed. Materials and quantities are confirmed.",
        "operations_manager_signature": media["signatures"]["operations_manager"],
        "operations_manager_comments": "Approved for execution. Coordinate procurement by priority.",
        "business_dev_signature": media["signatures"]["business_dev"],
        "business_dev_comments": "Commercial scope aligned with service requirements.",
        "procurement_signature": media["signatures"]["procurement"],
        "procurement_comments": "All listed items available under current supplier framework.",
        "general_manager_signature": media["signatures"]["general_manager"],
        "general_manager_comments": "Final approval granted for this inspection work package.",
        "items": [
            {
                "asset": "AHU-01",
                "system": "HVAC",
                "description": "Air Handling Unit filter replacement",
                "quantity": "2",
                "brand": "Daikin",
                "specification": "HEPA H13",
                "comments": "Replace due to dust load",
                "photos": media["photos"]["hvac"],
            },
            {
                "asset": "FCU-12",
                "system": "HVAC",
                "description": "Drain tray cleaning and sealant touch-up",
                "quantity": "1",
                "brand": "Carrier",
                "specification": "OEM compliant",
                "comments": "Minor corrosion noted",
                "photos": media["photos"]["hvac"],
            },
        ],
        "materials_required": [
            {
                "id": "mat-hvac-001",
                "name": "Air Filter 24x24x2",
                "brand": "Camfil",
                "uom": "PCS",
                "unit_price": 42.5,
                "quantity": 6,
                "department": "HVAC",
            },
            {
                "id": "mat-elec-012",
                "name": "Cable Tie UV Resistant 300mm",
                "brand": "3M",
                "uom": "PACK",
                "unit_price": 18.0,
                "quantity": 2,
                "department": "Electrical",
            },
            {
                "id": "mat-plumb-033",
                "name": "PVC Drain Cleaner",
                "brand": "Bostik",
                "uom": "LTR",
                "unit_price": 12.0,
                "quantity": 3,
                "department": "Plumbing",
            },
        ],
    }

    civil_sample_data = {
        "project_name": civil_project,
        "visit_date": civil_fd.get("visit_date") or today,
        "location": civil_location,
        "inspector_name": "Ahmed Rahman",
        "description_of_work": "External facade patching and internal crack rectification",
        "area": "General",
        "area_other": "Facade and basement waterproofing zones",
        "inspector_signature": media["signatures"]["supervisor"],
        "supervisor_signature": media["signatures"]["supervisor"],
        "supervisor_comments": "Civil quantities and quality requirements confirmed.",
        "operations_manager_signature": media["signatures"]["operations_manager"],
        "operations_manager_comments": "Execution sequence approved.",
        "business_dev_signature": media["signatures"]["business_dev"],
        "business_dev_comments": "Client-facing commitments aligned to this scope.",
        "procurement_signature": media["signatures"]["procurement"],
        "procurement_comments": "Materials can be dispatched in one batch.",
        "general_manager_signature": media["signatures"]["general_manager"],
        "general_manager_comments": "Approved for immediate implementation.",
        "work_items": [
            {
                "description": "Facade crack filling (north elevation)",
                "quantity": "1",
                "material": "Repair Mortar",
                "material_qty": "8 bags",
                "price": "N/A",
                "labour": "2 technicians",
                "comments": "Need scaffold access",
                "photos": media["photos"]["civil"],
            },
            {
                "description": "Basement wall waterproof touch-up",
                "quantity": "1",
                "material": "Waterproof Coating",
                "material_qty": "12 liters",
                "price": "N/A",
                "labour": "1 technician",
                "comments": "Area to be dried before application",
                "photos": media["photos"]["civil"],
            },
        ],
        "materials_required": [
            {
                "id": "civil-mat-001",
                "name": "Repair Mortar M20",
                "brand": "Sika",
                "uom": "BAG",
                "unit_price": 33.0,
                "quantity": 8,
                "department": "Civil",
            },
            {
                "id": "civil-mat-002",
                "name": "Waterproof Coating",
                "brand": "Fosroc",
                "uom": "LTR",
                "unit_price": 19.5,
                "quantity": 12,
                "department": "Civil",
            },
            {
                "id": "civil-mat-003",
                "name": "Joint Sealant",
                "brand": "Bostik",
                "uom": "TUBE",
                "unit_price": 9.0,
                "quantity": 15,
                "department": "Civil",
            },
        ],
    }

    cleaning_sample_data = {
        "project_name": cleaning_project,
        "date_of_visit": cleaning_fd.get("date_of_visit") or today,
        "technician_name": "Ravi Kumar",
        "tech_signature": media["signatures"]["supervisor"],
        "supervisor_signature": media["signatures"]["supervisor"],
        "supervisor_comments": "Cleaning checklist reviewed and approved.",
        "operations_manager_signature": media["signatures"]["operations_manager"],
        "operations_manager_comments": "Manpower and schedule approved.",
        "business_dev_signature": media["signatures"]["business_dev"],
        "business_dev_comments": "Service outcome aligns with client expectations.",
        "procurement_signature": media["signatures"]["procurement"],
        "procurement_comments": "Consumables available and reserved for this site.",
        "general_manager_signature": media["signatures"]["general_manager"],
        "general_manager_comments": "Final sign-off complete.",
        "facility_floor": "24",
        "facility_ground_parking": "1",
        "facility_basement": "2",
        "facility_podium": "1",
        "facility_gym_room": "1",
        "facility_swimming_pool": "1",
        "facility_washroom_male": "12",
        "facility_washroom_female": "10",
        "facility_changing_room": "2",
        "facility_play_kids_place": "1",
        "facility_garbage_room": "2",
        "facility_floor_chute_room": "4",
        "facility_staircase": "6",
        "facility_floor_service_room": "4",
        "facility_cleaner_count": "14",
        "scope_offices": "True",
        "scope_toilets": "True",
        "scope_hallways": "True",
        "scope_kitchen": "True",
        "scope_exterior": "False",
        "scope_special_care": "True",
        "deep_clean_required": "Yes",
        "deep_clean_areas": "Lobby and podium restrooms",
        "waste_disposal_required": "Yes",
        "waste_disposal_method": "Segregated disposal via approved vendor",
        "restricted_access": "Server room and control room",
        "pest_control": "Monthly treatment required",
        "working_hours": "6:00 AM - 4:00 PM",
        "required_team_size": "6",
        "site_access_requirements": "Security clearance for all staff",
        "general_comments": "Priority focus on high-touch surfaces and washrooms.",
        "photos": media["photos"]["cleaning"],
        "materials_required": [
            {
                "id": "clean-mat-001",
                "name": "Disinfectant Cleaner",
                "brand": "Diversey",
                "uom": "LTR",
                "unit_price": 14.0,
                "quantity": 20,
                "department": "Cleaning",
            },
            {
                "id": "clean-mat-002",
                "name": "Microfiber Mop Head",
                "brand": "Vileda",
                "uom": "PCS",
                "unit_price": 11.0,
                "quantity": 18,
                "department": "Cleaning",
            },
            {
                "id": "clean-mat-003",
                "name": "Garbage Bag 120L",
                "brand": "Falcon",
                "uom": "ROLL",
                "unit_price": 7.5,
                "quantity": 25,
                "department": "Cleaning",
            },
        ],
    }

    hvac_pdf_path = create_hvac_pdf(hvac_sample_data, output_dir)
    hvac_excel_path = create_hvac_excel(hvac_sample_data, output_dir)
    civil_pdf_path = create_civil_pdf(civil_sample_data, output_dir)
    civil_excel_path = create_civil_excel(civil_sample_data, output_dir)
    cleaning_pdf_path = create_cleaning_pdf(cleaning_sample_data, output_dir)
    cleaning_excel_path = create_cleaning_excel(cleaning_sample_data, output_dir)

    print("MEDIA_DIR:", os.path.abspath(media["dir"]))
    print("HVAC_PDF:", os.path.abspath(hvac_pdf_path))
    print("HVAC_EXCEL:", os.path.abspath(hvac_excel_path))
    print("CIVIL_PDF:", os.path.abspath(civil_pdf_path))
    print("CIVIL_EXCEL:", os.path.abspath(civil_excel_path))
    print("CLEANING_PDF:", os.path.abspath(cleaning_pdf_path))
    print("CLEANING_EXCEL:", os.path.abspath(cleaning_excel_path))


if __name__ == "__main__":
    main()

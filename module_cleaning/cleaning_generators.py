"""
Placeholder/wrapper for Cleaning report generation.
Replace with your real generators or import them here.
"""
import logging
import os
import sys
import time
from datetime import datetime, timedelta

# Dubai timezone offset (Gulf Standard Time, UTC+4)
DUBAI_OFFSET = timedelta(hours=4)

def get_dubai_time():
    """Get current time in Dubai timezone (GST - Gulf Standard Time, UTC+4)"""
    utc_now = datetime.utcnow()
    return utc_now + DUBAI_OFFSET

def format_dubai_datetime(dt=None, format_str='%Y-%m-%d %H:%M:%S'):
    """Format datetime in Dubai timezone (GST, UTC+4)"""
    if dt is None:
        dt = get_dubai_time()
    elif isinstance(dt, datetime):
        # Assume UTC if naive, add Dubai offset
        if dt.tzinfo is None:
            dt = dt + DUBAI_OFFSET
        else:
            # Convert to UTC first, then add Dubai offset
            from datetime import timezone as dt_timezone
            utc_dt = dt.astimezone(dt_timezone.utc).replace(tzinfo=None)
            dt = utc_dt + DUBAI_OFFSET
    else:
        dt = get_dubai_time()
    return dt.strftime(format_str)
from io import BytesIO

import base64
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, inch
from reportlab.platypus import (Image, PageBreak, SimpleDocTemplate, Spacer,
                                  Table, TableStyle, Paragraph)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from common.utils import get_image_for_pdf

logger = logging.getLogger(__name__)

# Try importing PIL for better image handling
try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("PIL/Pillow not available - signature aspect ratio may not be perfectly preserved")

# Try importing professional PDF service, fall back if unavailable
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.services.professional_pdf_service import (
        create_professional_pdf,
        create_header_with_logo,
        create_info_table,
        create_data_table,
        add_photo_grid,
        add_signatures_section,
        add_section_heading,
        add_item_heading,
        add_paragraph,
        get_professional_styles
    )
    USE_PROFESSIONAL_PDF = True
    logger.info("✅ Professional PDF service loaded successfully")
except Exception as e:
    logger.warning(f"⚠️ Professional PDF service not available: {e}. Using basic PDF generation.")
    USE_PROFESSIONAL_PDF = False

def create_excel_report(data, output_dir):
    """Generate Cleaning Assessment Excel report with professional formatting."""
    try:
        # Import professional Excel service
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app.services.professional_excel_service import (
            create_professional_excel_workbook,
            add_logo_and_title,
            add_info_section,
            add_data_table,
            add_section_header,
            finalize_workbook
        )
        
        logger.info(f"Creating professional Cleaning Excel report in {output_dir}")
        
        # Generate filename
        project_name = data.get('project_name', 'Unknown_Project').replace(' ', '_')
        timestamp = get_dubai_time().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"Cleaning_Assessment_{project_name}_{timestamp}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        # Create professional workbook
        wb, ws = create_professional_excel_workbook(
            title="Site Assessment Report - Cleaning",
            sheet_name="Assessment Report"
        )
        
        # Add logo and title (span across all columns)
        current_row = add_logo_and_title(
            ws,
            title="CLEANING ASSESSMENT REPORT",
            subtitle=f"Project: {project_name.replace('_', ' ')}",
            max_columns=4
        )
        
        # Project & Client Details Section (span across all columns)
        project_info = [
            ('Project Name', data.get('project_name', 'N/A')),
            ('Date of Visit', data.get('date_of_visit', 'N/A')),
            ('Report Generated', format_dubai_datetime() + ' (GST)')
        ]
        
        current_row = add_info_section(ws, project_info, current_row, title="Project & Client Details", max_columns=4)
        
        # Facility Areas Section (span across all columns)
        facility_data = [
            ('Floor', data.get('facility_floor', 'N/A')),
            ('Ground Parking', data.get('facility_ground_parking', 'N/A')),
            ('Basement', data.get('facility_basement', 'N/A')),
            ('Podium', data.get('facility_podium', 'N/A')),
            ('Gym Room', data.get('facility_gym_room', 'N/A')),
            ('Swimming Pool', data.get('facility_swimming_pool', 'N/A')),
            ('Washroom (Male)', data.get('facility_washroom_male', 'N/A')),
            ('Washroom (Female)', data.get('facility_washroom_female', 'N/A')),
            ('Changing Room', data.get('facility_changing_room', 'N/A')),
            ('Kids Play Area', data.get('facility_play_kids_place', 'N/A')),
            ('Garbage Room', data.get('facility_garbage_room', 'N/A')),
            ('Floor Chute Room', data.get('facility_floor_chute_room', 'N/A')),
            ('Staircase', data.get('facility_staircase', 'N/A')),
            ('Floor Service Room', data.get('facility_floor_service_room', 'N/A')),
            ('Cleaner Count', data.get('facility_cleaner_count', 'N/A'))
        ]
        
        current_row = add_info_section(ws, facility_data, current_row, title="Facility Area Counts", max_columns=4)
        
        # Cleaning Scope Section (span across all columns)
        scope_data = [
            ('Offices', '✓' if data.get('scope_offices') == 'True' else '✗'),
            ('Toilets/Washrooms', '✓' if data.get('scope_toilets') == 'True' else '✗'),
            ('Corridors/Hallways', '✓' if data.get('scope_hallways') == 'True' else '✗'),
            ('Kitchen/Pantry', '✓' if data.get('scope_kitchen') == 'True' else '✗'),
            ('Building Exterior', '✓' if data.get('scope_exterior') == 'True' else '✗'),
            ('Special Care Areas', '✓' if data.get('scope_special_care') == 'True' else '✗')
        ]
        
        current_row = add_info_section(ws, scope_data, current_row, title="Cleaning Requirements & Scope", max_columns=4)
        
        # Deep Cleaning Section (span across all columns)
        deep_clean_data = [
            ('Deep Cleaning Required', data.get('deep_clean_required', 'No')),
            ('Areas to Deep Clean', data.get('deep_clean_areas', 'N/A'))
        ]
        
        current_row = add_info_section(ws, deep_clean_data, current_row, title="Deep Cleaning", max_columns=4)
        
        # Waste Disposal Section (span across all columns)
        waste_disposal_data = [
            ('Waste Disposal Required', data.get('waste_disposal_required', 'No')),
            ('Method of Disposal', data.get('waste_disposal_method', 'N/A'))
        ]
        
        current_row = add_info_section(ws, waste_disposal_data, current_row, title="Waste Disposal", max_columns=4)
        
        # Special Considerations Section (span across all columns)
        special_considerations_data = [
            ('Restricted Access Areas', data.get('restricted_access', 'N/A')),
            ('Pest Control Needed', data.get('pest_control', 'N/A'))
        ]
        
        current_row = add_info_section(ws, special_considerations_data, current_row, title="Special Considerations", max_columns=4)
        
        # Safety & Staffing Section (span across all columns)
        safety_data = [
            ('Working Hours', data.get('working_hours', 'N/A')),
            ('Required Team Size', str(data.get('required_team_size', 'N/A'))),
            ('Site Access Requirements', data.get('site_access_requirements', 'N/A'))
        ]
        
        current_row = add_info_section(ws, safety_data, current_row, title="Safety & Staffing", max_columns=4)
        
        # General Comments Section (span across all columns)
        comments_data = [
            ('Comments', data.get('general_comments', 'N/A'))
        ]
        
        current_row = add_info_section(ws, comments_data, current_row, title="General Comments", max_columns=4)
        
        # Signatures Section - REMOVED from Excel (images/signatures not needed in Excel)
        # Excel reports should only contain data, not images or signatures
        
        # Finalize formatting
        finalize_workbook(ws)
        
        # Save workbook
        wb.save(excel_path)
        
        if not os.path.exists(excel_path):
            raise Exception(f"Excel file not created at {excel_path}")
        
        logger.info(f"✅ Professional Cleaning Excel report created: {excel_path}")
        return excel_path
        
    except Exception as e:
        logger.error(f"❌ Cleaning Excel generation error: {str(e)}")
        raise


def create_pdf_report(data, output_dir):
    """Generate comprehensive professional Cleaning Assessment PDF report."""
    try:
        logger.info(f"Creating professional Cleaning PDF report in {output_dir}")
        logger.info(f"📊 PDF Generator - Data keys: {list(data.keys())}")
        logger.info(f"📸 PDF Generator - Photos key exists: {'photos' in data}")
        logger.info(f"📸 PDF Generator - Photos value type: {type(data.get('photos', None))}")
        logger.info(f"📸 PDF Generator - Photos count: {len(data.get('photos', [])) if data.get('photos') else 0}")
        
        # Generate filename
        project_name = data.get('project_name', 'Unknown_Project').replace(' ', '_')
        timestamp = get_dubai_time().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"Cleaning_Assessment_{project_name}_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
        story = []
        styles = get_professional_styles()
        
        # HEADER WITH LOGO
        create_header_with_logo(
            story,
            "CLEANING ASSESSMENT REPORT",
            f"Project: {data.get('project_name', 'N/A')}"
        )
        
        # PROJECT & CLIENT DETAILS
        add_section_heading(story, "Project & Client Details")
        
        project_info_data = [
            ['Project Name:', data.get('project_name', 'N/A')],
            ['Date of Visit:', data.get('date_of_visit', 'N/A')],
            ['Supervisor:', data.get('technician_name', 'N/A')],
        ]
        
        story.append(create_info_table(project_info_data))
        story.append(Spacer(1, 0.3*inch))
        
        # FACILITY AREA COUNTS
        add_section_heading(story, "Facility Area Counts")
        facility_data = [
            ['Floor:', data.get('facility_floor', 'N/A')],
            ['Ground Parking:', str(data.get('facility_ground_parking', 'N/A'))],
            ['Basement:', str(data.get('facility_basement', 'N/A'))],
            ['Podium:', str(data.get('facility_podium', 'N/A'))],
            ['Gym Room:', str(data.get('facility_gym_room', 'N/A'))],
            ['Swimming Pool:', str(data.get('facility_swimming_pool', 'N/A'))],
            ['Washroom (Male):', str(data.get('facility_washroom_male', 'N/A'))],
            ['Washroom (Female):', str(data.get('facility_washroom_female', 'N/A'))],
            ['Changing Room:', str(data.get('facility_changing_room', 'N/A'))],
            ['Kids Play Area:', str(data.get('facility_play_kids_place', 'N/A'))],
            ['Garbage Room:', str(data.get('facility_garbage_room', 'N/A'))],
            ['Floor Chute Room:', str(data.get('facility_floor_chute_room', 'N/A'))],
            ['Staircase:', str(data.get('facility_staircase', 'N/A'))],
            ['Floor Service Room:', str(data.get('facility_floor_service_room', 'N/A'))],
            ['Cleaner Count:', str(data.get('facility_cleaner_count', 'N/A'))],
        ]
        story.append(create_info_table(facility_data))
        story.append(Spacer(1, 0.3*inch))
        
        # CLEANING REQUIREMENTS & SCOPE
        add_section_heading(story, "Cleaning Requirements & Scope")
        scope_data = [
            ['Offices:', '✓' if data.get('scope_offices') == 'True' else '✗'],
            ['Toilets/Washrooms:', '✓' if data.get('scope_toilets') == 'True' else '✗'],
            ['Corridors/Hallways:', '✓' if data.get('scope_hallways') == 'True' else '✗'],
            ['Kitchen/Pantry:', '✓' if data.get('scope_kitchen') == 'True' else '✗'],
            ['Building Exterior:', '✓' if data.get('scope_exterior') == 'True' else '✗'],
            ['Special Care Areas:', '✓' if data.get('scope_special_care') == 'True' else '✗'],
        ]
        story.append(create_info_table(scope_data))
        story.append(Spacer(1, 0.3*inch))
        
        # DEEP CLEANING
        add_section_heading(story, "Deep Cleaning")
        deep_clean_data = [
            ['Deep Cleaning Required:', data.get('deep_clean_required', 'No')],
            ['Areas to Deep Clean:', data.get('deep_clean_areas', 'N/A')],
        ]
        story.append(create_info_table(deep_clean_data))
        story.append(Spacer(1, 0.3*inch))
        
        # WASTE DISPOSAL
        add_section_heading(story, "Waste Disposal")
        waste_disposal_data = [
            ['Waste Disposal Required:', data.get('waste_disposal_required', 'No')],
            ['Method of Disposal:', data.get('waste_disposal_method', 'N/A')],
        ]
        story.append(create_info_table(waste_disposal_data))
        story.append(Spacer(1, 0.3*inch))
        
        # SPECIAL CONSIDERATIONS
        add_section_heading(story, "Special Considerations")
        special_considerations_data = [
            ['Restricted Access Areas:', data.get('restricted_access', 'N/A')],
            ['Pest Control Needed:', data.get('pest_control', 'N/A')],
        ]
        story.append(create_info_table(special_considerations_data))
        story.append(Spacer(1, 0.3*inch))
        
        # SAFETY & STAFFING
        add_section_heading(story, "Safety & Staffing")
        safety_data = [
            ['Working Hours:', data.get('working_hours', 'N/A')],
            ['Required Team Size:', str(data.get('required_team_size', 'N/A'))],
            ['Site Access Requirements:', data.get('site_access_requirements', 'N/A')],
        ]
        story.append(create_info_table(safety_data))
        story.append(Spacer(1, 0.3*inch))
        
        # GENERAL COMMENTS
        add_section_heading(story, "General Comments")
        comments = data.get('general_comments', 'No comments provided.')
        add_paragraph(story, comments)
        story.append(Spacer(1, 0.3*inch))
        
        # PHOTOS
        photos = data.get('photos', [])
        logger.info(f"📸 PDF Generator: Looking for photos in data")
        logger.info(f"📸 PDF Generator: photos key exists: {'photos' in data}")
        logger.info(f"📸 PDF Generator: photos value: {photos}")
        logger.info(f"📸 PDF Generator: photos type: {type(photos)}")
        logger.info(f"📸 PDF Generator: photos length: {len(photos) if photos else 0}")
        
        if photos:
            logger.info(f"📸 PDF Generator: Processing {len(photos)} photos")
            # Ensure photos are in the correct format (list of dicts with 'url' key)
            formatted_photos = []
            for idx, photo in enumerate(photos):
                if isinstance(photo, dict):
                    photo_url = photo.get('url')
                    if photo_url:
                        formatted_photos.append(photo)
                        logger.info(f"📸 PDF Generator: Photo {idx + 1}: {photo_url[:80]}...")
                    else:
                        logger.warning(f"📸 PDF Generator: Photo {idx + 1} has no URL: {photo}")
                elif isinstance(photo, str):
                    # If it's a string URL, convert to dict format
                    formatted_photos.append({'url': photo, 'is_cloud': True})
                    logger.info(f"📸 PDF Generator: Photo {idx + 1} (string): {photo[:80]}...")
                else:
                    logger.warning(f"📸 PDF Generator: Photo {idx + 1} has unexpected format: {type(photo)}")
            
            if formatted_photos:
                add_section_heading(story, f"Site Photos ({len(formatted_photos)} total)")
                add_photo_grid(story, formatted_photos)
            else:
                logger.warning("📸 PDF Generator: No valid photos found after formatting")
        else:
            logger.warning("📸 PDF Generator: No photos found in data")
        
        # SIGNATURES PAGE - Professional format with all reviewer signatures
        # Extract all reviewer data similar to HVAC module
        signatures = {}
        
        # Get nested data dict if it exists
        nested_data = data.get('data') if isinstance(data.get('data'), dict) else {}
        
        # Extract supervisor signature - try multiple paths
        supervisor_sig = data.get('supervisor_signature', '') or data.get('tech_signature', '')
        if not supervisor_sig:
            supervisor_sig_raw = data.get('supervisor_signature')
            if supervisor_sig_raw is not None and supervisor_sig_raw != '' and supervisor_sig_raw != 'None':
                supervisor_sig = supervisor_sig_raw
            elif nested_data and nested_data.get('supervisor_signature'):
                supervisor_sig = nested_data.get('supervisor_signature')
            elif isinstance(data.get('form_data'), dict):
                form_data_dict = data.get('form_data', {})
                if form_data_dict.get('supervisor_signature'):
                    supervisor_sig = form_data_dict.get('supervisor_signature')
        
        # Extract supervisor comments
        supervisor_comments = data.get('supervisor_comments', '')
        if not supervisor_comments:
            supervisor_comments_raw = data.get('supervisor_comments')
            if supervisor_comments_raw is not None and supervisor_comments_raw != 'None':
                supervisor_comments = supervisor_comments_raw
            elif nested_data and nested_data.get('supervisor_comments'):
                supervisor_comments = nested_data.get('supervisor_comments')
            elif isinstance(data.get('form_data'), dict):
                form_data_dict = data.get('form_data', {})
                if form_data_dict.get('supervisor_comments'):
                    supervisor_comments = form_data_dict.get('supervisor_comments')
        
        if supervisor_comments is None:
            supervisor_comments = ''
        
        # Handle supervisor signature format
        if supervisor_sig:
            if isinstance(supervisor_sig, dict) and supervisor_sig.get('url'):
                signatures['Supervisor'] = supervisor_sig
            elif isinstance(supervisor_sig, str) and (supervisor_sig.startswith('data:image') or supervisor_sig.startswith('http') or supervisor_sig.startswith('/')):
                signatures['Supervisor'] = supervisor_sig
        
        # Extract Operations Manager data
        operations_manager_comments = None
        operations_manager_comments_raw = data.get('operations_manager_comments')
        if operations_manager_comments_raw is not None and operations_manager_comments_raw != 'None' and operations_manager_comments_raw != '':
            operations_manager_comments = operations_manager_comments_raw
        elif nested_data and nested_data.get('operations_manager_comments'):
            operations_manager_comments = nested_data.get('operations_manager_comments')
        elif isinstance(data.get('form_data'), dict):
            form_data_dict = data.get('form_data', {})
            if form_data_dict.get('operations_manager_comments'):
                operations_manager_comments = form_data_dict.get('operations_manager_comments')
        
        if operations_manager_comments is None:
            operations_manager_comments = ''
        
        # Extract Operations Manager signature
        opman_sig = None
        opman_sig_raw = data.get('operations_manager_signature') or data.get('opMan_signature')
        if opman_sig_raw is not None and opman_sig_raw != '' and opman_sig_raw != 'None':
            opman_sig = opman_sig_raw
        elif nested_data:
            opman_sig_raw = nested_data.get('operations_manager_signature') or nested_data.get('opMan_signature')
            if opman_sig_raw is not None and opman_sig_raw != '' and opman_sig_raw != 'None':
                opman_sig = opman_sig_raw
        elif isinstance(data.get('form_data'), dict):
            form_data_dict = data.get('form_data', {})
            opman_sig_raw = form_data_dict.get('operations_manager_signature') or form_data_dict.get('opMan_signature')
            if opman_sig_raw is not None and opman_sig_raw != '' and opman_sig_raw != 'None':
                opman_sig = opman_sig_raw
        
        if opman_sig:
            if isinstance(opman_sig, dict) and opman_sig.get('url'):
                signatures['Operations Manager'] = opman_sig
            elif isinstance(opman_sig, str) and (opman_sig.startswith('data:image') or opman_sig.startswith('http') or opman_sig.startswith('/')):
                signatures['Operations Manager'] = opman_sig
        
        # Extract Business Development data
        business_dev_comments = None
        supervisor_comments_for_validation = supervisor_comments
        business_dev_comments_raw = data.get('business_dev_comments') or data.get('business_development_comments')
        if business_dev_comments_raw is not None and business_dev_comments_raw != 'None' and business_dev_comments_raw != '':
            if business_dev_comments_raw != supervisor_comments_for_validation:
                business_dev_comments = business_dev_comments_raw
        elif nested_data:
            business_dev_comments_raw = nested_data.get('business_dev_comments') or nested_data.get('business_development_comments')
            if business_dev_comments_raw is not None and business_dev_comments_raw != 'None' and business_dev_comments_raw != '':
                if business_dev_comments_raw != supervisor_comments_for_validation:
                    business_dev_comments = business_dev_comments_raw
        elif isinstance(data.get('form_data'), dict):
            form_data_dict = data.get('form_data', {})
            business_dev_comments_raw = form_data_dict.get('business_dev_comments') or form_data_dict.get('business_development_comments')
            if business_dev_comments_raw is not None and business_dev_comments_raw != 'None' and business_dev_comments_raw != '':
                if business_dev_comments_raw != supervisor_comments_for_validation:
                    business_dev_comments = business_dev_comments_raw
        
        if business_dev_comments is None:
            business_dev_comments = ''
        
        # Extract Business Development signature
        business_dev_sig = None
        business_dev_sig_raw = data.get('business_dev_signature') or data.get('businessDevSignature')
        if business_dev_sig_raw is not None and business_dev_sig_raw != 'None' and business_dev_sig_raw != '':
            business_dev_sig = business_dev_sig_raw
        elif nested_data:
            business_dev_sig_raw = nested_data.get('business_dev_signature') or nested_data.get('businessDevSignature')
            if business_dev_sig_raw is not None and business_dev_sig_raw != 'None' and business_dev_sig_raw != '':
                business_dev_sig = business_dev_sig_raw
        elif isinstance(data.get('form_data'), dict):
            form_data_dict = data.get('form_data', {})
            business_dev_sig_raw = form_data_dict.get('business_dev_signature') or form_data_dict.get('businessDevSignature')
            if business_dev_sig_raw is not None and business_dev_sig_raw != 'None' and business_dev_sig_raw != '':
                business_dev_sig = business_dev_sig_raw
        
        if business_dev_sig:
            if isinstance(business_dev_sig, dict) and business_dev_sig.get('url'):
                signatures['Business Development'] = business_dev_sig
            elif isinstance(business_dev_sig, str) and (business_dev_sig.startswith('data:image') or business_dev_sig.startswith('http') or business_dev_sig.startswith('/')):
                signatures['Business Development'] = business_dev_sig
        
        # Extract Procurement data
        procurement_comments = None
        procurement_comments_raw = data.get('procurement_comments')
        if procurement_comments_raw is not None and procurement_comments_raw != 'None' and procurement_comments_raw != '':
            procurement_comments = procurement_comments_raw
        elif nested_data:
            procurement_comments_raw = nested_data.get('procurement_comments')
            if procurement_comments_raw is not None and procurement_comments_raw != 'None' and procurement_comments_raw != '':
                procurement_comments = procurement_comments_raw
        elif isinstance(data.get('form_data'), dict):
            form_data_dict = data.get('form_data', {})
            procurement_comments_raw = form_data_dict.get('procurement_comments')
            if procurement_comments_raw is not None and procurement_comments_raw != 'None' and procurement_comments_raw != '':
                procurement_comments = procurement_comments_raw
        
        if procurement_comments is None:
            procurement_comments = ''
        
        # Extract Procurement signature
        procurement_sig = None
        procurement_sig_raw = data.get('procurement_signature') or data.get('procurementSignature')
        if procurement_sig_raw is not None and procurement_sig_raw != 'None' and procurement_sig_raw != '':
            procurement_sig = procurement_sig_raw
        elif nested_data:
            procurement_sig_raw = nested_data.get('procurement_signature') or nested_data.get('procurementSignature')
            if procurement_sig_raw is not None and procurement_sig_raw != 'None' and procurement_sig_raw != '':
                procurement_sig = procurement_sig_raw
        elif isinstance(data.get('form_data'), dict):
            form_data_dict = data.get('form_data', {})
            procurement_sig_raw = form_data_dict.get('procurement_signature') or form_data_dict.get('procurementSignature')
            if procurement_sig_raw is not None and procurement_sig_raw != 'None' and procurement_sig_raw != '':
                procurement_sig = procurement_sig_raw
        
        if procurement_sig:
            if isinstance(procurement_sig, dict) and procurement_sig.get('url'):
                signatures['Procurement'] = procurement_sig
            elif isinstance(procurement_sig, str) and (procurement_sig.startswith('data:image') or procurement_sig.startswith('http') or procurement_sig.startswith('/')):
                signatures['Procurement'] = procurement_sig
        
        # Extract General Manager data
        general_manager_comments = data.get('general_manager_comments', '') or (nested_data.get('general_manager_comments') if nested_data else '') or ''
        general_manager_sig = data.get('general_manager_signature', '') or data.get('generalManagerSignature', '')
        if general_manager_sig:
            if isinstance(general_manager_sig, dict) and general_manager_sig.get('url'):
                signatures['General Manager'] = general_manager_sig
            elif isinstance(general_manager_sig, str) and (general_manager_sig.startswith('data:image') or general_manager_sig.startswith('http')):
                signatures['General Manager'] = general_manager_sig
        
        # Helper function to add comment and signature together for a reviewer (same as HVAC)
        def add_reviewer_section(role_name, comments, signature_data, always_show_signature=False):
            """Add comments and signature together for a reviewer with aspect-ratio-preserved signatures"""
            has_content = False
            
            if comments and comments.strip():
                add_section_heading(story, f"{role_name} Comments")
                add_paragraph(story, comments)
                story.append(Spacer(1, 0.1*inch))
                has_content = True
            
            if signature_data or always_show_signature:
                styles = get_professional_styles()
                sig_rows = []
                
                if signature_data:
                    try:
                        from common.utils import get_image_for_pdf
                        from PIL import Image as PILImage
                        
                        img_data, is_url = get_image_for_pdf(signature_data)
                        if img_data:
                            max_width = 2.5 * inch
                            max_height = 1.2 * inch
                            
                            try:
                                if is_url:
                                    img_data.seek(0)
                                    pil_img = PILImage.open(img_data)
                                else:
                                    pil_img = PILImage.open(img_data)
                                
                                orig_width, orig_height = pil_img.size
                                
                                width_ratio = max_width / orig_width
                                height_ratio = max_height / orig_height
                                scale_ratio = min(width_ratio, height_ratio)
                                
                                final_width = orig_width * scale_ratio
                                final_height = orig_height * scale_ratio
                                
                                original_ratio = orig_width / orig_height if orig_height > 0 else 1
                                final_ratio = final_width / final_height if final_height > 0 else 1
                                
                                if is_url:
                                    img_data.seek(0)
                                    sig_img = Image(img_data, width=final_width, height=final_height)
                                else:
                                    sig_img = Image(img_data, width=final_width, height=final_height)
                                
                                logger.info(f"✅ {role_name} signature aspect ratio: Original={orig_width}x{orig_height} (ratio={original_ratio:.3f}), Final={final_width:.2f}x{final_height:.2f} (ratio={final_ratio:.3f}), Scale={scale_ratio:.3f}")
                                
                                if abs(original_ratio - final_ratio) > 0.01:
                                    logger.warning(f"⚠️ {role_name} signature aspect ratio mismatch! Original={original_ratio:.3f}, Final={final_ratio:.3f}")
                            except Exception as pil_error:
                                logger.warning(f"PIL image processing failed for {role_name}, using fallback: {pil_error}")
                                if is_url:
                                    img_data.seek(0)
                                    sig_img = Image(img_data)
                                else:
                                    sig_img = Image(img_data)
                                
                                if hasattr(sig_img, 'imageWidth') and hasattr(sig_img, 'imageHeight'):
                                    orig_width = sig_img.imageWidth
                                    orig_height = sig_img.imageHeight
                                    if orig_width > 0 and orig_height > 0:
                                        width_ratio = max_width / orig_width
                                        height_ratio = max_height / orig_height
                                        scale_ratio = min(width_ratio, height_ratio)
                                        final_width = orig_width * scale_ratio
                                        final_height = orig_height * scale_ratio
                                        sig_img.drawWidth = final_width
                                        sig_img.drawHeight = final_height
                                    else:
                                        sig_img.drawWidth = max_width
                                else:
                                    sig_img.drawWidth = max_width
                            
                            sig_rows.append([
                                Paragraph(f"<b>{role_name} Signature:</b>", styles['Normal']),
                                sig_img
                            ])
                        else:
                            sig_rows.append([
                                Paragraph(f"<b>{role_name} Signature:</b>", styles['Normal']),
                                Paragraph("Signature not available", styles['Small'])
                            ])
                    except Exception as e:
                        logger.error(f"Error processing {role_name} signature: {str(e)}")
                        sig_rows.append([
                            Paragraph(f"<b>{role_name} Signature:</b>", styles['Normal']),
                            Paragraph("Error loading signature", styles['Small'])
                        ])
                else:
                    sig_rows.append([
                        Paragraph(f"<b>{role_name} Signature:</b>", styles['Normal']),
                        Paragraph("<i>Not signed</i>", styles['Small'])
                    ])
                
                if sig_rows:
                    sig_table = Table(sig_rows, colWidths=[2*inch, 3.5*inch])
                    sig_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('GRID', (0, 0), (-1, -1), 0.75, colors.HexColor('#125435')),
                        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F5E9')),
                        ('TOPPADDING', (0, 0), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ]))
                    story.append(sig_table)
                    story.append(Spacer(1, 0.15*inch))
                    has_content = True
            
            return has_content
        
        # Check if Operations Manager has approved
        om_has_approved = False
        if data.get('operations_manager_approved_at') or data.get('operations_manager_id'):
            om_has_approved = True
        if data.get('workflow_status'):
            workflow_status = str(data.get('workflow_status'))
            if 'operations_manager_approved' in workflow_status or 'bd_procurement' in workflow_status:
                om_has_approved = True
        
        # Check if BD has approved
        bd_has_approved = False
        if data.get('business_dev_approved_at') or data.get('business_dev_id'):
            bd_has_approved = True
        if data.get('workflow_status'):
            workflow_status = str(data.get('workflow_status'))
            if 'bd_procurement' in workflow_status or 'general_manager' in workflow_status:
                bd_has_approved = True
        
        # Check if Procurement has approved
        procurement_has_approved = False
        if data.get('procurement_approved_at') or data.get('procurement_id'):
            procurement_has_approved = True
        if data.get('workflow_status'):
            workflow_status = str(data.get('workflow_status'))
            if 'bd_procurement' in workflow_status or 'general_manager' in workflow_status:
                procurement_has_approved = True
        
        # Add reviewer sections in workflow order
        # 1. Supervisor - ALWAYS show
        supervisor_comments_display = supervisor_comments if supervisor_comments and supervisor_comments.strip() else None
        supervisor_sig_display = signatures.get('Supervisor')
        add_reviewer_section("Supervisor", supervisor_comments_display, supervisor_sig_display, always_show_signature=True)
        
        # 2. Operations Manager - show if approved or has data
        if operations_manager_comments or signatures.get('Operations Manager') or om_has_approved:
            add_reviewer_section("Operations Manager", operations_manager_comments, signatures.get('Operations Manager'), always_show_signature=True)
        
        # 3. Business Development - show if approved or has data
        if business_dev_comments or signatures.get('Business Development') or bd_has_approved:
            add_reviewer_section("Business Development", business_dev_comments, signatures.get('Business Development'), always_show_signature=True)
        
        # 4. Procurement - show if approved or has data
        if procurement_comments or signatures.get('Procurement') or procurement_has_approved:
            add_reviewer_section("Procurement", procurement_comments, signatures.get('Procurement'), always_show_signature=True)
        
        # 5. General Manager - show if has data
        if general_manager_comments or signatures.get('General Manager'):
            add_reviewer_section("General Manager", general_manager_comments, signatures.get('General Manager'), always_show_signature=True)
        
        # Build professional PDF with logo and branding
        create_professional_pdf(
            pdf_path, 
            story, 
            report_title=f"Cleaning Assessment - {data.get('project_name', 'N/A')}"
        )
        
        logger.info(f"✅ Professional Cleaning PDF created successfully: {pdf_path}")
        return pdf_path
        
    except Exception as e:
        logger.error(f"❌ PDF generation error: {str(e)}")
        raise
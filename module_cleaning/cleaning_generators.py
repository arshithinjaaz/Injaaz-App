"""
Placeholder/wrapper for Cleaning report generation.
Replace with your real generators or import them here.
"""
import logging
import os
import sys
import time
from datetime import datetime
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
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
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
            ('Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
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
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
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
        
        # SIGNATURES - Professional format
        tech_sig = data.get('tech_signature', {})
        supervisor_sig = data.get('supervisor_signature', {})
        
        signatures = {}
        
        # Handle inspector signature - can be dict with url or string
        if tech_sig:
            if isinstance(tech_sig, dict) and tech_sig.get('url'):
                signatures['Inspector'] = tech_sig
            elif isinstance(tech_sig, str) and tech_sig.startswith('data:image'):
                signatures['Inspector'] = {'url': tech_sig, 'is_cloud': False}
        
        # Handle supervisor signature (if present) - can be dict with url or string
        if supervisor_sig:
            if isinstance(supervisor_sig, dict) and supervisor_sig.get('url'):
                signatures['Supervisor'] = supervisor_sig
            elif isinstance(supervisor_sig, str) and supervisor_sig.startswith('data:image'):
                signatures['Supervisor'] = {'url': supervisor_sig, 'is_cloud': False}
        
        # Always show signature section
        if not signatures:
            signatures = {
                'Inspector': None
            }
        
        add_signatures_section(story, signatures)
        
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
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
            add_signature_section,
            finalize_workbook
        )
        
        logger.info(f"Creating professional Cleaning Excel report in {output_dir}")
        
        # Generate filename
        site_name = data.get('client_name', 'Unknown_Client').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"Cleaning_Assessment_{site_name}_{timestamp}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        # Create professional workbook
        wb, ws = create_professional_excel_workbook(
            title="Site Assessment Report - Cleaning",
            sheet_name="Assessment Report"
        )
        
        # Add logo and title
        current_row = add_logo_and_title(
            ws,
            title="SITE ASSESSMENT REPORT - CLEANING",
            subtitle=f"Client: {site_name.replace('_', ' ')}"
        )
        
        # Site Information Section
        site_info = [
            ('Client Name', data.get('client_name', 'N/A')),
            ('Site Location', data.get('site_location', 'N/A')),
            ('Assessment Date', data.get('assessment_date', 'N/A')),
            ('Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        ]
        
        current_row = add_info_section(ws, site_info, current_row, title="Site Information")
        
        # Project & Client Details Section
        client_details = [
            ('Project Name', data.get('project_name', 'N/A')),
            ('Site Address', data.get('site_address', 'N/A')),
            ('Date of Visit', data.get('date_of_visit', 'N/A')),
            ('Key Person', data.get('key_person_name', 'N/A')),
            ('Contact Number', data.get('contact_number', 'N/A'))
        ]
        
        current_row = add_info_section(ws, client_details, current_row, title="Project & Client Details")
        
        # Site Count & Operations Section
        operations_data = [
            ('Room Count', str(data.get('room_count', 'N/A'))),
            ('Current Team Size', str(data.get('current_team_size', 'N/A'))),
            ('Lift Count', str(data.get('lift_count_total', 'N/A'))),
            ('Team Description', data.get('current_team_desc', 'N/A'))
        ]
        
        current_row = add_info_section(ws, operations_data, current_row, title="Site Count & Current Operations")
        
        # Facility Areas Section
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
        
        current_row = add_info_section(ws, facility_data, current_row, title="Facility Area Counts")
        
        # Cleaning Scope Section
        scope_data = [
            ('Offices', '✓' if data.get('scope_offices') == 'True' else '✗'),
            ('Toilets/Washrooms', '✓' if data.get('scope_toilets') == 'True' else '✗'),
            ('Corridors/Hallways', '✓' if data.get('scope_hallways') == 'True' else '✗'),
            ('Kitchen/Pantry', '✓' if data.get('scope_kitchen') == 'True' else '✗'),
            ('Building Exterior', '✓' if data.get('scope_exterior') == 'True' else '✗'),
            ('Special Care Areas', '✓' if data.get('scope_special_care') == 'True' else '✗')
        ]
        
        current_row = add_info_section(ws, scope_data, current_row, title="Cleaning Requirements & Scope")
        
        # Deep Cleaning Section
        deep_clean_data = [
            ('Deep Cleaning Required', data.get('deep_clean_required', 'No')),
            ('Areas to Deep Clean', data.get('deep_clean_areas', 'N/A'))
        ]
        
        current_row = add_info_section(ws, deep_clean_data, current_row, title="Deep Cleaning")
        
        # Safety & Staffing Section
        safety_data = [
            ('Working Hours', data.get('working_hours', 'N/A')),
            ('Required Team Size', data.get('required_team_size', 'N/A')),
            ('Site Access Requirements', data.get('site_access_requirements', 'N/A')),
            ('Equipment Condition', data.get('facility_equipment_condition', 'N/A')),
            ('Required Equipment', data.get('required_equipment', 'N/A')),
            ('High-Risk Areas', data.get('high_risk_areas', 'N/A')),
            ('Safety Measures/PPE', data.get('suggested_safety_ppe', 'N/A'))
        ]
        
        current_row = add_info_section(ws, safety_data, current_row, title="Safety & Staffing")
        
        # General Comments Section
        comments_data = [
            ('Comments', data.get('general_comments', 'N/A'))
        ]
        
        current_row = add_info_section(ws, comments_data, current_row, title="General Comments")
        
        # Signatures Section
        signatures = {}
        tech_sig = data.get('tech_signature', '')
        contact_sig = data.get('contact_signature', '')
        
        if tech_sig:
            signatures['Technician'] = tech_sig
        else:
            signatures['Technician'] = None
            
        if contact_sig:
            signatures['Contact Person'] = contact_sig
        else:
            signatures['Contact Person'] = None
        
        current_row = add_signature_section(ws, signatures, current_row)
        
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
        ws.merge_cells(f'A{row}:D{row}')
        row += 1
        
        ws[f'A{row}'] = data.get('general_comments', 'No comments provided.')
        ws.merge_cells(f'A{row}:D{row}')
        ws[f'A{row}'].alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[row].height = 60
        
        # Adjust column widths
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['D'].width = 20
        
        # Save workbook
        wb.save(excel_path)
        
        if not os.path.exists(excel_path):
            raise Exception(f"Excel file not created at {excel_path}")
        
        logger.info(f"✅ Excel report created: {excel_path}")
        return excel_path
        
    except Exception as e:
        logger.error(f"❌ Excel generation error: {str(e)}")
        raise


def create_pdf_report(data, output_dir):
    """Generate comprehensive professional Cleaning Assessment PDF report."""
    try:
        logger.info(f"Creating professional Cleaning PDF report in {output_dir}")
        
        # Generate filename
        site_name = data.get('client_name', 'Unknown_Client').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"Cleaning_Assessment_{site_name}_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
        story = []
        styles = get_professional_styles()
        
        # HEADER WITH LOGO
        create_header_with_logo(
            story,
            "SITE ASSESSMENT REPORT",
            "Cleaning Services"
        )
        
        # PROJECT & CLIENT DETAILS
        story.append(Paragraph("Project & Client Details", heading_style))
        
        client_info = [
            ['Client Name:', data.get('client_name', 'N/A')],
            ['Project Name:', data.get('project_name', 'N/A')],
            ['Site Address:', data.get('site_address', 'N/A')],
            ['Date of Visit:', data.get('date_of_visit', 'N/A')],
            ['Key Person:', data.get('key_person_name', 'N/A')],
            ['Contact Number:', data.get('contact_number', 'N/A')],
        ]
        
        client_table = Table(client_info, colWidths=[4*cm, 12*cm])
        client_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F5E9')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(client_table)
        story.append(Spacer(1, 0.3*inch))
        
        # SITE COUNT & OPERATIONS
        story.append(Paragraph("Site Count & Current Operations", heading_style))
        operations_data = [
            ['Room Count:', str(data.get('room_count', 'N/A'))],
            ['Current Team Size:', str(data.get('current_team_size', 'N/A'))],
            ['Lift Count:', str(data.get('lift_count_total', 'N/A'))],
            ['Team Description:', str(data.get('current_team_desc', 'N/A'))],
        ]
        
        ops_table = Table(operations_data, colWidths=[4*cm, 12*cm])
        ops_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F5E9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(ops_table)
        story.append(Spacer(1, 0.3*inch))
        
        # GENERAL COMMENTS
        add_section_heading(story, "General Comments")
        comments = data.get('general_comments', 'No comments provided.')
        add_paragraph(story, comments)
        story.append(Spacer(1, 0.3*inch))
        
        # PHOTOS
        photos = data.get('photos', [])
        if photos:
            add_section_heading(story, f"Site Photos ({len(photos)} total)")
            add_photo_grid(story, photos)
        
        # SIGNATURES - Professional format
        tech_sig = data.get('tech_signature', {})
        contact_sig = data.get('contact_signature', {})
        
        signatures = {}
        
        # Handle tech signature - can be dict with url or string
        if tech_sig:
            if isinstance(tech_sig, dict) and tech_sig.get('url'):
                signatures['Technician'] = tech_sig
            elif isinstance(tech_sig, str) and tech_sig.startswith('data:image'):
                signatures['Technician'] = {'url': tech_sig, 'is_cloud': False}
        
        # Handle contact signature - can be dict with url or string
        if contact_sig:
            if isinstance(contact_sig, dict) and contact_sig.get('url'):
                signatures['Contact Person'] = contact_sig
            elif isinstance(contact_sig, str) and contact_sig.startswith('data:image'):
                signatures['Contact Person'] = {'url': contact_sig, 'is_cloud': False}
        
        # Always show signature section
        if not signatures:
            signatures = {
                'Technician': None,
                'Contact Person': None
            }
        
        add_signatures_section(story, signatures)
        
        # Build professional PDF with logo and branding
        create_professional_pdf(
            pdf_path, 
            story, 
            report_title=f"Cleaning Assessment - {data.get('client_name', 'N/A')}"
        )
        
        logger.info(f"✅ Professional Cleaning PDF created successfully: {pdf_path}")
        return pdf_path
        
    except Exception as e:
        logger.error(f"❌ PDF generation error: {str(e)}")
        raise
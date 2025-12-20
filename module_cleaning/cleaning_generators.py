"""
Placeholder/wrapper for Cleaning report generation.
Replace with your real generators or import them here.
"""
import logging
import os
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

logger = logging.getLogger(__name__)

def create_excel_report(data, output_dir):
    """Generate Cleaning Assessment Excel report."""
    try:
        logger.info(f"Creating Excel report in {output_dir}")
        
        # Generate filename
        site_name = data.get('client_name', 'Unknown_Client').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"Cleaning_Assessment_{site_name}_{timestamp}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Assessment Report"
        
        # Styles
        header_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill(start_color="125435", end_color="125435", fill_type="solid")
        subheader_font = Font(bold=True, size=12)
        subheader_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        row = 1
        
        # Title
        ws.merge_cells(f'A{row}:D{row}')
        cell = ws[f'A{row}']
        cell.value = "SITE ASSESSMENT REPORT - CLEANING"
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[row].height = 25
        row += 2
        
        # Project & Client Details
        ws[f'A{row}'] = "PROJECT & CLIENT DETAILS"
        ws[f'A{row}'].font = subheader_font
        ws[f'A{row}'].fill = subheader_fill
        ws.merge_cells(f'A{row}:D{row}')
        row += 1
        
        details = [
            ('Client Name:', data.get('client_name', 'N/A')),
            ('Project Name:', data.get('project_name', 'N/A')),
            ('Site Address:', data.get('site_address', 'N/A')),
            ('Date of Visit:', data.get('date_of_visit', 'N/A')),
            ('Key Person:', data.get('key_person_name', 'N/A')),
            ('Contact Number:', data.get('contact_number', 'N/A')),
        ]
        
        for label, value in details:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = value
            ws.merge_cells(f'B{row}:D{row}')
            row += 1
        
        row += 1
        
        # Site Count & Operations
        ws[f'A{row}'] = "SITE COUNT & CURRENT OPERATIONS"
        ws[f'A{row}'].font = subheader_font
        ws[f'A{row}'].fill = subheader_fill
        ws.merge_cells(f'A{row}:D{row}')
        row += 1
        
        operations = [
            ('Room Count:', data.get('room_count', 'N/A')),
            ('Current Team Size:', data.get('current_team_size', 'N/A')),
            ('Lift Count:', data.get('lift_count_total', 'N/A')),
            ('Team Description:', data.get('current_team_desc', 'N/A')),
        ]
        
        for label, value in operations:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = value
            ws.merge_cells(f'B{row}:D{row}')
            row += 1
        
        row += 1
        
        # Facility Areas
        ws[f'A{row}'] = "FACILITY AREA COUNTS"
        ws[f'A{row}'].font = subheader_font
        ws[f'A{row}'].fill = subheader_fill
        ws.merge_cells(f'A{row}:D{row}')
        row += 1
        
        facilities = [
            ('Floor:', data.get('facility_floor', 'N/A')),
            ('Ground Parking:', data.get('facility_ground_parking', 'N/A')),
            ('Basement:', data.get('facility_basement', 'N/A')),
            ('Podium:', data.get('facility_podium', 'N/A')),
            ('Gym Room:', data.get('facility_gym_room', 'N/A')),
            ('Swimming Pool:', data.get('facility_swimming_pool', 'N/A')),
            ('Washroom (Male):', data.get('facility_washroom_male', 'N/A')),
            ('Washroom (Female):', data.get('facility_washroom_female', 'N/A')),
            ('Changing Room:', data.get('facility_changing_room', 'N/A')),
            ('Kids Play Area:', data.get('facility_play_kids_place', 'N/A')),
            ('Garbage Room:', data.get('facility_garbage_room', 'N/A')),
            ('Floor Chute Room:', data.get('facility_floor_chute_room', 'N/A')),
            ('Staircase:', data.get('facility_staircase', 'N/A')),
            ('Floor Service Room:', data.get('facility_floor_service_room', 'N/A')),
            ('Cleaner Count:', data.get('facility_cleaner_count', 'N/A')),
        ]
        
        for label, value in facilities:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = value
            row += 1
        
        row += 1
        
        # Cleaning Scope
        ws[f'A{row}'] = "CLEANING REQUIREMENTS & SCOPE"
        ws[f'A{row}'].font = subheader_font
        ws[f'A{row}'].fill = subheader_fill
        ws.merge_cells(f'A{row}:D{row}')
        row += 1
        
        scope_items = [
            ('Offices', data.get('scope_offices', 'False')),
            ('Toilets/Washrooms', data.get('scope_toilets', 'False')),
            ('Corridors/Hallways', data.get('scope_hallways', 'False')),
            ('Kitchen/Pantry', data.get('scope_kitchen', 'False')),
            ('Building Exterior', data.get('scope_exterior', 'False')),
            ('Special Care Areas', data.get('scope_special_care', 'False')),
        ]
        
        for label, value in scope_items:
            ws[f'A{row}'] = label
            ws[f'B{row}'] = '✓' if value == 'True' else '✗'
            row += 1
        
        row += 1
        
        # Deep Cleaning
        ws[f'A{row}'] = "DEEP CLEANING"
        ws[f'A{row}'].font = subheader_font
        ws[f'A{row}'].fill = subheader_fill
        ws.merge_cells(f'A{row}:D{row}')
        row += 1
        
        ws[f'A{row}'] = 'Deep Cleaning Required:'
        ws[f'A{row}'].font = Font(bold=True)
        ws[f'B{row}'] = data.get('deep_clean_required', 'No')
        row += 1
        
        ws[f'A{row}'] = 'Areas to Deep Clean:'
        ws[f'A{row}'].font = Font(bold=True)
        ws[f'B{row}'] = data.get('deep_clean_areas', 'N/A')
        ws.merge_cells(f'B{row}:D{row}')
        row += 2
        
        # Safety & Staffing
        ws[f'A{row}'] = "SAFETY & STAFFING"
        ws[f'A{row}'].font = subheader_font
        ws[f'A{row}'].fill = subheader_fill
        ws.merge_cells(f'A{row}:D{row}')
        row += 1
        
        safety_items = [
            ('Working Hours:', data.get('working_hours', 'N/A')),
            ('Required Team Size:', data.get('required_team_size', 'N/A')),
            ('Site Access Requirements:', data.get('site_access_requirements', 'N/A')),
            ('Equipment Condition:', data.get('facility_equipment_condition', 'N/A')),
            ('Required Equipment:', data.get('required_equipment', 'N/A')),
            ('High-Risk Areas:', data.get('high_risk_areas', 'N/A')),
            ('Safety Measures/PPE:', data.get('suggested_safety_ppe', 'N/A')),
        ]
        
        for label, value in safety_items:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = value
            ws.merge_cells(f'B{row}:D{row}')
            row += 1
        
        row += 1
        
        # General Comments
        ws[f'A{row}'] = "GENERAL COMMENTS"
        ws[f'A{row}'].font = subheader_font
        ws[f'A{row}'].fill = subheader_fill
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
    """Generate comprehensive Cleaning Assessment PDF report."""
    try:
        logger.info(f"Creating PDF report in {output_dir}")
        
        # Generate filename
        site_name = data.get('client_name', 'Unknown_Client').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"Cleaning_Assessment_{site_name}_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
        # Create PDF document
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#125435'),
            spaceAfter=0.3*inch,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#125435'),
            spaceAfter=0.2*inch,
            spaceBefore=0.3*inch,
            fontName='Helvetica-Bold'
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#1a7a4d'),
            spaceAfter=0.15*inch,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=0.1*inch
        )
        
        # TITLE
        story.append(Paragraph("SITE ASSESSMENT REPORT", title_style))
        story.append(Paragraph("Cleaning Services", subheading_style))
        story.append(Spacer(1, 0.2*inch))
        
        # PROJECT & CLIENT DETAILS
        story.append(Paragraph("Project & Client Details", heading_style))
        
        client_info = [
            ['Client Name:', data.get('client_name', 'N/A')],
            ['Project Name:', data.get('project_name', 'N/A')],
            ['Site Address:', data.get('site_address', 'N/A')],
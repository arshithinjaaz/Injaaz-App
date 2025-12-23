"""
Civil report generators for Excel and PDF.
"""
import os
import logging
import sys
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
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
    """Generate Civil Works Excel report with professional formatting."""
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
        
        logger.info(f"Creating professional Civil Excel report in {output_dir}")
        
        # Extract data from fields dict (FormData submission)
        fields = data.get('fields', {})
        files = data.get('files', [])
        
        project_name = fields.get('project_name', ['Unknown_Project'])[0] if isinstance(fields.get('project_name'), list) else fields.get('project_name', 'Unknown_Project')
        project_name = project_name.replace(' ', '_') if project_name else 'Unknown_Project'
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"Civil_{project_name}_{timestamp}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        # Create professional workbook
        wb, ws = create_professional_excel_workbook(
            title="Civil Works Inspection Report",
            sheet_name="Civil Works Report"
        )
        
        # Add logo and title
        current_row = add_logo_and_title(
            ws,
            title="CIVIL WORKS INSPECTION REPORT",
            subtitle=f"Project: {project_name.replace('_', ' ')}"
        )
        
        # Project Information Section
        project_info = [
            ('Project Name', project_name.replace('_', ' ')),
            ('Date', fields.get('date', ['N/A'])[0] if isinstance(fields.get('date'), list) else fields.get('date', 'N/A')),
            ('Location', fields.get('location', ['N/A'])[0] if isinstance(fields.get('location'), list) else fields.get('location', 'N/A')),
            ('Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('Total Files', str(len(files)))
        ]
        
        current_row = add_info_section(ws, project_info, current_row, title="Project Information")
        
        # Work Items Section - Reconstruct from FormData parallel arrays
        def ensure_list(val):
            if val is None:
                return []
            return [val] if isinstance(val, str) else val
        
        descriptions = ensure_list(fields.get('description', []))
        quantities = ensure_list(fields.get('quantity', []))
        materials = ensure_list(fields.get('material', []))
        prices = ensure_list(fields.get('price', []))
        labours = ensure_list(fields.get('labour', []))
        
        max_items = max(len(descriptions), len(quantities), len(materials), len(prices), len(labours))
        
        if max_items > 0:
            current_row = add_section_header(ws, "Work Items", current_row)
            
            headers = ['#', 'Description', 'Quantity', 'Material', 'Price', 'Labour']
            table_data = []
            
            for i in range(max_items):
                table_data.append([
                    str(i + 1),
                    descriptions[i] if i < len(descriptions) else '',
                    quantities[i] if i < len(quantities) else '',
                    materials[i] if i < len(materials) else '',
                    prices[i] if i < len(prices) else '',
                    labours[i] if i < len(labours) else ''
                ])
            
            col_widths = {
                'A': 6,
                'B': 40,
                'C': 12,
                'D': 20,
                'E': 12,
                'F': 12
            }
            
            current_row = add_data_table(ws, headers, table_data, current_row, col_widths=col_widths)
        
        # Signatures Section
        signatures = {}
        tech_sig = data.get('tech_signature', '') or data.get('op_signature', '')
        op_sig = data.get('op_signature', '')
        
        if tech_sig:
            signatures['Technical Engineer'] = tech_sig
        else:
            signatures['Technical Engineer'] = None
            
        if op_sig:
            signatures['Operation/Maintenance'] = op_sig
        else:
            signatures['Operation/Maintenance'] = None
        
        current_row = add_signature_section(ws, signatures, current_row)
        
        # Finalize formatting
        finalize_workbook(ws)
        
        # Save workbook
        wb.save(excel_path)
        
        if not os.path.exists(excel_path):
            raise Exception(f"Excel file not created at {excel_path}")
        
        logger.info(f"✅ Professional Civil Excel report created: {excel_path}")
        return excel_path
        
    except Exception as e:
        logger.error(f"❌ Civil Excel generation error: {str(e)}")
        raise
        work_descriptions = ensure_list(fields.get('work_desc[]'))
        work_quantities = ensure_list(fields.get('work_qty[]'))
        work_materials = ensure_list(fields.get('material[]'))
        work_prices = ensure_list(fields.get('price[]'))
        work_labours = ensure_list(fields.get('labour[]'))
        
        num_items = len(work_descriptions) if work_descriptions else 0
        
        for idx in range(num_items):
            ws.cell(row=row, column=1, value=idx + 1)
            ws.cell(row=row, column=2, value=work_descriptions[idx] if idx < len(work_descriptions) else '')
            ws.cell(row=row, column=3, value=work_quantities[idx] if idx < len(work_quantities) else '')
            ws.cell(row=row, column=4, value=work_materials[idx] if idx < len(work_materials) else '')
            ws.cell(row=row, column=5, value=work_prices[idx] if idx < len(work_prices) else '')
            ws.cell(row=row, column=6, value=work_labours[idx] if idx < len(work_labours) else '')
            
            for col in range(1, 7):
                ws.cell(row=row, column=col).border = border
                ws.cell(row=row, column=col).alignment = Alignment(vertical='top', wrap_text=True)
            
            row += 1
        
        # Column widths
        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 30
        ws.column_dimensions['C'].width = 12
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 12
        ws.column_dimensions['F'].width = 12
        
        wb.save(excel_path)
        logger.info(f"✅ Civil Excel report created: {excel_path}")
        return os.path.basename(excel_path)
        
    except Exception as e:
        logger.error(f"❌ Civil Excel generation error: {str(e)}")
        raise

def create_pdf_report(data, output_dir):
    """Generate professional Civil Works PDF report with branding."""
    try:
        logger.info(f"Creating professional Civil PDF report in {output_dir}")
        
        # Extract data
        fields = data.get('fields', {})
        files = data.get('files', [])
        
        def get_field(name, default='N/A'):
            val = fields.get(name, default)
            return val[0] if isinstance(val, list) and val else (val or default)
        
        project_name = get_field('project_name', 'Unknown_Project')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"Civil_{project_name.replace(' ', '_')}_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
        # Container for PDF elements
        story = []
        styles = get_professional_styles()
        
        # HEADER WITH LOGO
        create_header_with_logo(
            story,
            "CIVIL WORKS INSPECTION REPORT",
            f"Project: {project_name}"
        )
        
        # PROJECT INFORMATION
        add_section_heading(story, "Project Information")
        
        project_data = [
            ['Project Name:', get_field('project_name')],
            ['Location:', get_field('location')],
            ['Visit Date:', get_field('visit_date')],
            ['Inspector:', get_field('inspector_name')],
            ['Manager:', get_field('manager_name')],
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Total Photos:', str(len(files))]
        ]
        
        project_table = create_info_table(project_data)
        story.append(project_table)
        story.append(Spacer(1, 0.3*inch))
        
        # WORK ITEMS - Reconstruct from FormData parallel arrays
        add_section_heading(story, "Work Items")
        
        # Extract work item parallel arrays
        def ensure_list(val):
            if val is None:
                return []
            return [val] if isinstance(val, str) else val
        
        work_descriptions = ensure_list(fields.get('work_desc[]'))
        work_quantities = ensure_list(fields.get('work_qty[]'))
        work_materials = ensure_list(fields.get('material[]'))
        work_prices = ensure_list(fields.get('price[]'))
        work_labours = ensure_list(fields.get('labour[]'))
        
        num_items = len(work_descriptions) if work_descriptions else 0
        
        if num_items > 0:
            for idx in range(num_items):
                add_item_heading(story, f"Work Item {idx + 1}")
                
                item_data = [
                    ['Description:', work_descriptions[idx] if idx < len(work_descriptions) else 'N/A'],
                    ['Quantity:', work_quantities[idx] if idx < len(work_quantities) else 'N/A'],
                    ['Material:', work_materials[idx] if idx < len(work_materials) else 'N/A'],
                    ['Price:', work_prices[idx] if idx < len(work_prices) else 'N/A'],
                    ['Labour:', work_labours[idx] if idx < len(work_labours) else 'N/A']
                ]
                
                item_table = create_info_table(item_data, col_widths=[1.8*inch, 4.2*inch])
                story.append(item_table)
                story.append(Spacer(1, 0.2*inch))
        else:
            add_paragraph(story, "No work items recorded.")
        
        # PHOTOS SECTION - Show all uploaded photos
        if files:
            story.append(Spacer(1, 0.2*inch))
            add_section_heading(story, f"Attached Photos ({len(files)} total)")
            add_photo_grid(story, files)
        else:
            add_paragraph(story, "No photos attached.")
        
        # SIGNATURES SECTION - Professional format
        tech_sig = get_field('tech_signature', None)
        op_sig = get_field('op_signature', None)
        
        signatures = {}
        
        # Handle tech signature - can be dict with url or string
        if tech_sig:
            if isinstance(tech_sig, dict) and tech_sig.get('url'):
                signatures['Technical Engineer'] = tech_sig
            elif isinstance(tech_sig, str) and tech_sig.startswith('data:image'):
                signatures['Technical Engineer'] = {'url': tech_sig, 'is_cloud': False}
        
        # Handle op signature - can be dict with url or string
        if op_sig:
            if isinstance(op_sig, dict) and op_sig.get('url'):
                signatures['Operation/Maintenance'] = op_sig
            elif isinstance(op_sig, str) and op_sig.startswith('data:image'):
                signatures['Operation/Maintenance'] = {'url': op_sig, 'is_cloud': False}
        
        # Always show signature section
        if not signatures:
            signatures = {
                'Technical Engineer': None,
                'Operation/Maintenance': None
            }
        
        add_signatures_section(story, signatures)
        
        # Build professional PDF with logo and branding
        create_professional_pdf(
            pdf_path, 
            story, 
            report_title=f"Civil Works - {project_name}"
        )
        
        logger.info(f"✅ Professional Civil PDF created successfully: {pdf_path}")
        return os.path.basename(pdf_path)
        
    except Exception as e:
        logger.error(f"❌ Civil PDF generation error: {str(e)}")
        raise

import logging
import os
import json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
import base64
from common.utils import get_image_for_pdf

logger = logging.getLogger(__name__)

# Try importing professional PDF service, fall back if unavailable
try:
    import sys
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
    """Generate HVAC/MEP Excel report with professional formatting."""
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
        
        logger.info(f"Creating professional Excel report in {output_dir}")
        
        # Generate filename
        site_name = data.get('site_name', 'Unknown_Site').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"HVAC_MEP_{site_name}_{timestamp}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        # Create professional workbook
        wb, ws = create_professional_excel_workbook(
            title="HVAC & MEP Inspection Report",
            sheet_name="HVAC MEP Inspection"
        )
        
        # Add logo and title (span across all 8 columns)
        current_row = add_logo_and_title(
            ws,
            title="HVAC & MEP INSPECTION REPORT",
            subtitle=f"Site: {data.get('site_name', 'N/A')}",
            max_columns=8
        )
        
        # Site Information Section (span across all 8 columns)
        site_info = [
            ('Site Name', data.get('site_name', 'N/A')),
            ('Visit Date', data.get('visit_date', 'N/A')),
            ('Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('Total Items', str(len(data.get('items', []))))
        ]
        
        current_row = add_info_section(ws, site_info, current_row, title="Site Information", max_columns=8)
        
        # Items data
        items = data.get('items', [])
        
        # Inspection Items Table
        items = data.get('items', [])
        if items:
            current_row = add_section_header(ws, "Inspection Items", current_row, span_columns=8)
            
            # Prepare table data with all fields (no photos)
            headers = ['#', 'Asset', 'System', 'Description', 'Quantity', 'Brand', 'Specification', 'Comments']
            table_data = []
            
            for idx, item in enumerate(items, 1):
                table_data.append([
                    str(idx),
                    item.get('asset', 'N/A'),
                    item.get('system', 'N/A'),
                    item.get('description', 'N/A'),
                    str(item.get('quantity', 'N/A')),
                    item.get('brand', 'N/A'),
                    item.get('specification', 'N/A'),
                    item.get('comments', 'N/A')
                ])
            
            # Column widths for inspection items
            col_widths = {
                'A': 6,   # #
                'B': 18,  # Asset
                'C': 18,  # System
                'D': 25,  # Description
                'E': 10,  # Quantity
                'F': 15,  # Brand
                'G': 20,  # Specification
                'H': 30   # Comments
            }
            
            current_row = add_data_table(
                ws, headers, table_data, current_row,
                title=None, col_widths=col_widths
            )
        
        # Signatures Section - REMOVED from Excel (images/signatures not needed in Excel)
        
        # Finalize formatting
        finalize_workbook(ws)
        
        # Save workbook
        wb.save(excel_path)
        
        if not os.path.exists(excel_path):
            raise Exception(f"Excel file not created at {excel_path}")
        
        logger.info(f"✅ Professional Excel report created: {excel_path}")
        return excel_path
        
    except Exception as e:
        logger.error(f"❌ Excel generation error: {str(e)}")
        raise

def create_pdf_report(data, output_dir):
    """Generate comprehensive HVAC/MEP PDF report with professional branding."""
    try:
        logger.info(f"Creating professional HVAC/MEP PDF report in {output_dir}")
        
        # Generate filename
        site_name = data.get('site_name', 'Unknown_Site').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"HVAC_MEP_{site_name}_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
        # Container for PDF elements
        story = []
        styles = get_professional_styles()
        
        # HEADER WITH LOGO
        create_header_with_logo(
            story,
            "HVAC & MEP INSPECTION REPORT",
            f"Site: {data.get('site_name', 'N/A')}"
        )
        
        # Horizontal line separator
        story.append(Spacer(1, 0.1*inch))
        
        # SITE INFORMATION
        add_section_heading(story, "Site Information")
        
        site_info_data = [
            ['Site Name:', data.get('site_name', 'N/A')],
            ['Visit Date:', data.get('visit_date', 'N/A')],
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Total Items Inspected:', str(len(data.get('items', [])))]
        ]
        
        site_table = create_info_table(site_info_data)
        story.append(site_table)
        story.append(Spacer(1, 0.3*inch))
        
        # INSPECTION ITEMS
        items = data.get('items', [])
        
        if items:
            add_section_heading(story, "Inspection Items")
            
            for idx, item in enumerate(items, 1):
                # Item header
                add_item_heading(story, f"Item {idx}: {item.get('asset', 'N/A')}")
                
                # Item details table - All fields
                item_details = [
                    ['Asset Name:', item.get('asset', 'N/A')],
                    ['System Type:', item.get('system', 'N/A')],
                    ['Description:', item.get('description', 'N/A')],
                    ['Quantity:', str(item.get('quantity', 'N/A'))],
                    ['Brand:', item.get('brand', 'N/A')],
                    ['Specification:', item.get('specification', 'N/A')],
                    ['Comments:', item.get('comments', 'N/A')],
                    ['Photos Attached:', str(len(item.get('photos', [])))]
                ]
                
                item_table = create_info_table(item_details, col_widths=[1.8*inch, 4.2*inch])
                story.append(item_table)
                story.append(Spacer(1, 0.15*inch))
                
                # PHOTOS - Support both cloud URLs and local paths
                photos = item.get('photos', [])
                
                if photos:
                    add_paragraph(story, f"<b>Attached Photos ({len(photos)} total):</b>")
                    story.append(Spacer(1, 0.1*inch))
                    add_photo_grid(story, photos)
                
                # Add page break after each item (except last)
                if idx < len(items):
                    story.append(PageBreak())
        
        else:
            add_paragraph(story, "No inspection items recorded.")
        
        # SIGNATURES PAGE - Professional format with all signatures
        signatures = {}
        
        # Check for supervisor signature (new workflow field)
        supervisor_sig = data.get('supervisor_signature', '') or data.get('tech_signature', '')
        supervisor_comments = data.get('supervisor_comments', '')
        
        if supervisor_sig:
            if isinstance(supervisor_sig, dict) and supervisor_sig.get('url'):
                signatures['Supervisor'] = supervisor_sig
            elif isinstance(supervisor_sig, str) and (supervisor_sig.startswith('data:image') or supervisor_sig.startswith('http')):
                signatures['Supervisor'] = supervisor_sig
        
        # Check for both 'opMan_signature' (with capital M) and 'opman_signature' (all lowercase)
        opman_sig = data.get('opMan_signature', '') or data.get('opman_signature', '')
        if opman_sig:
            if isinstance(opman_sig, dict) and opman_sig.get('url'):
                signatures['Operations Manager'] = opman_sig
            elif isinstance(opman_sig, str) and (opman_sig.startswith('data:image') or opman_sig.startswith('http')):
                signatures['Operations Manager'] = opman_sig
        
        # Add supervisor comments before signatures if available
        if supervisor_comments:
            add_section_heading(story, "Supervisor Comments")
            add_paragraph(story, supervisor_comments)
            story.append(Spacer(1, 0.1*inch))
        
        # Always add signature section (only show sections that have signatures or are expected)
        # For initial supervisor submissions, only show supervisor signature
        # For reviewed forms, show both supervisor and operations manager
        if not signatures:
            # If no signatures at all, show supervisor as expected
            signatures = {'Supervisor': None}
        elif 'Supervisor' not in signatures:
            # If we have some signatures but no supervisor, add supervisor slot
            signatures['Supervisor'] = None
        
        # Only add "Operations Manager" slot if there's actually an operations manager signature
        # This prevents showing "Operations Manager: Not signed" on initial supervisor submissions
        if opman_sig and 'Operations Manager' not in signatures:
            signatures['Operations Manager'] = None
        
        add_signatures_section(story, signatures)
        
        # Build professional PDF with logo and branding
        create_professional_pdf(
            pdf_path, 
            story, 
            report_title=f"HVAC/MEP Inspection - {data.get('site_name', 'N/A')}"
        )
        
        logger.info(f"✅ Professional HVAC/MEP PDF created successfully: {pdf_path}")
        return pdf_path
        
    except Exception as e:
        logger.error(f"❌ PDF generation error: {str(e)}")
        raise
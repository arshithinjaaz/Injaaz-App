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
        
        # Add logo and title
        current_row = add_logo_and_title(
            ws,
            title="HVAC & MEP INSPECTION REPORT",
            subtitle=f"Site: {data.get('site_name', 'N/A')}"
        )
        
        # Site Information Section
        site_info = [
            ('Site Name', data.get('site_name', 'N/A')),
            ('Visit Date', data.get('visit_date', 'N/A')),
            ('Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('Total Items', str(len(data.get('items', []))))
        ]
        
        current_row = add_info_section(ws, site_info, current_row, title="Site Information")
        
        # Items data
        items = data.get('items', [])
        
        # Inspection Items Table
        items = data.get('items', [])
        if items:
            current_row = add_section_header(ws, "Inspection Items", current_row)
            
            # Prepare table data
            headers = ['#', 'Asset', 'System', 'Description', 'Photos']
            table_data = []
            
            for idx, item in enumerate(items, 1):
                photos = item.get('photos', [])
                table_data.append([
                    str(idx),
                    item.get('asset', 'N/A'),
                    item.get('system', 'N/A'),
                    item.get('description', 'N/A'),
                    str(len(photos))
                ])
            
            # Column widths for inspection items
            col_widths = {
                'A': 6,
                'B': 22,
                'C': 22,
                'D': 50,
                'E': 12
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
                
                # Item details table
                item_details = [
                    ['Asset Name:', item.get('asset', 'N/A')],
                    ['System Type:', item.get('system', 'N/A')],
                    ['Description:', item.get('description', 'N/A')],
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
        
        # Handle signatures - they can be dict with url, or string (data URI or URL)
        tech_sig = data.get('tech_signature', '')
        if tech_sig:
            if isinstance(tech_sig, dict) and tech_sig.get('url'):
                signatures['Technician'] = tech_sig
            elif isinstance(tech_sig, str) and (tech_sig.startswith('data:image') or tech_sig.startswith('http')):
                signatures['Technician'] = tech_sig
        
        # Check for both 'opMan_signature' (with capital M) and 'opman_signature' (all lowercase)
        opman_sig = data.get('opMan_signature', '') or data.get('opman_signature', '')
        if opman_sig:
            if isinstance(opman_sig, dict) and opman_sig.get('url'):
                signatures['Operation Manager'] = opman_sig
            elif isinstance(opman_sig, str) and (opman_sig.startswith('data:image') or opman_sig.startswith('http')):
                signatures['Operation Manager'] = opman_sig
        
        # Always add signature section (shows "Not signed" if no signatures)
        if not signatures:
            signatures = {
                'Technician': None,
                'Operation Manager': None
            }
        
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
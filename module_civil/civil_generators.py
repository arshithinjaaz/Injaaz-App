"""
Civil report generators for Excel and PDF.
"""
import os
import logging
import sys
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
            finalize_workbook
        )
        
        logger.info(f"Creating professional Civil Excel report in {output_dir}")
        
        # Extract data - data is already in the correct format from submit_with_urls
        project_name = data.get('project_name', 'Unknown_Project')
        project_name = project_name.replace(' ', '_') if project_name else 'Unknown_Project'
        
        # Collect all photos from work items
        work_items = data.get('work_items', [])
        logger.info(f"📸 Processing {len(work_items)} work items for Excel")
        all_photos = []
        for idx, item in enumerate(work_items):
            photos = item.get('photos', [])
            logger.info(f"  Work item {idx + 1}: {len(photos)} photos")
            all_photos.extend(photos)
        logger.info(f"📸 Total photos collected: {len(all_photos)}")
        
        timestamp = get_dubai_time().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"Civil_{project_name}_{timestamp}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        # Create professional workbook
        wb, ws = create_professional_excel_workbook(
            title="Civil Works Inspection Report",
            sheet_name="Civil Works Report"
        )
        
        # Add logo and title (span across all 7 columns)
        current_row = add_logo_and_title(
            ws,
            title="CIVIL WORKS INSPECTION REPORT",
            subtitle=f"Project: {project_name.replace('_', ' ')}",
            max_columns=7
        )
        
        # Project Information Section (span across all 7 columns)
        project_info = [
            ('Project Name', data.get('project_name', 'N/A')),
            ('Visit Date', data.get('visit_date', 'N/A')),
            ('Location', data.get('location', 'N/A')),
            ('Inspector', data.get('inspector_name', 'N/A')),
            ('Report Generated', format_dubai_datetime() + ' (GST)'),
            ('Total Items', str(len(work_items)))
        ]
        
        current_row = add_info_section(ws, project_info, current_row, title="Project Information", max_columns=7)
        
        # Work Items Section - Use work_items array directly (Photos column removed)
        if work_items:
            current_row = add_section_header(ws, "Work Items", current_row, span_columns=7)
            
            headers = ['#', 'Description', 'Quantity', 'Material', 'Material Qty', 'Price', 'Labour']
            table_data = []
            
            for idx, item in enumerate(work_items, 1):
                table_data.append([
                    str(idx),
                    item.get('description', 'N/A'),
                    item.get('quantity', 'N/A'),
                    item.get('material', 'N/A'),
                    item.get('material_qty', 'N/A'),
                    item.get('price', 'N/A'),
                    item.get('labour', 'N/A')
                ])
            
            col_widths = {
                'A': 6,   # #
                'B': 35,  # Description
                'C': 12,  # Quantity
                'D': 20,  # Material
                'E': 12,  # Material Qty
                'F': 12,  # Price
                'G': 15   # Labour
            }
            
            current_row = add_data_table(ws, headers, table_data, current_row, col_widths=col_widths)
        
        # Signatures Section - REMOVED from Excel (images/signatures not needed in Excel)
        
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

def create_pdf_report(data, output_dir):
    """Generate professional Civil Works PDF report with branding."""
    try:
        logger.info(f"Creating professional Civil PDF report in {output_dir}")
        
        # Handle data structure - could be direct form_data or wrapped in submission dict
        if 'form_data' in data:
            # Data from database (wrapped in submission dict)
            form_data = data.get('form_data', {})
            project_name = form_data.get('project_name') or data.get('site_name', 'Unknown_Project')
            work_items = form_data.get('work_items', [])
            # Extract other fields from form_data
            inspector_name = form_data.get('inspector_name', 'N/A')
            description_of_work = form_data.get('description_of_work', 'N/A')
            location = form_data.get('location', 'N/A')
            visit_date = form_data.get('visit_date') or data.get('visit_date', 'N/A')
            inspector_signature = form_data.get('supervisor_signature', '') or form_data.get('inspector_signature', {})
            supervisor_comments = form_data.get('supervisor_comments', '')
        else:
            # Direct form_data (from submit_with_urls)
            form_data = data
            project_name = data.get('project_name', 'Unknown_Project')
            work_items = data.get('work_items', [])
            inspector_name = data.get('inspector_name', 'N/A')
            description_of_work = data.get('description_of_work', 'N/A')
            location = data.get('location', 'N/A')
            visit_date = data.get('visit_date', 'N/A')
            inspector_signature = data.get('supervisor_signature', '') or data.get('inspector_signature', {})
            supervisor_comments = data.get('supervisor_comments', '')
        
        timestamp = get_dubai_time().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"Civil_{project_name.replace(' ', '_')}_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
        # Collect all photos from work items
        logger.info(f"📸 Processing {len(work_items)} work items for PDF")
        logger.info(f"📸 Full data structure keys: {list(data.keys())}")
        all_photos = []
        for idx, item in enumerate(work_items):
            photos = item.get('photos', [])
            logger.info(f"  Work item {idx + 1}: {len(photos)} photos")
            logger.info(f"    Work item keys: {list(item.keys())}")
            for pidx, photo in enumerate(photos):
                if isinstance(photo, dict):
                    photo_url = photo.get('url', 'NO URL KEY')
                    logger.info(f"    Photo {pidx + 1} (dict): url={photo_url[:80] if photo_url else 'NONE'}..., is_cloud={photo.get('is_cloud', 'N/A')}")
                else:
                    logger.info(f"    Photo {pidx + 1} (not dict): {str(photo)[:80]}...")
            all_photos.extend(photos)
        logger.info(f"📸 Total photos collected: {len(all_photos)}")
        if len(all_photos) == 0:
            logger.warning("⚠️ NO PHOTOS FOUND! Checking data structure...")
            logger.warning(f"   Work items: {work_items}")
            logger.warning(f"   First work item structure: {work_items[0] if work_items else 'NO ITEMS'}")
        
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
            ['Project Name:', data.get('project_name', 'N/A')],
            ['Location:', data.get('location', 'N/A')],
            ['Visit Date:', data.get('visit_date', 'N/A')],
            ['Inspector:', data.get('inspector_name', 'N/A')],
            ['Description of Work:', data.get('description_of_work', 'N/A')],
            ['Report Generated:', format_dubai_datetime() + ' (GST)'],
            ['Total Photos:', str(len(all_photos))]
        ]
        
        project_table = create_info_table(project_data)
        story.append(project_table)
        story.append(Spacer(1, 0.3*inch))
        
        # WORK ITEMS - Use work_items array directly
        add_section_heading(story, "Work Items")
        
        if work_items:
            for idx, item in enumerate(work_items, 1):
                add_item_heading(story, f"Work Item {idx}")
                
                item_data = [
                    ['Description:', item.get('description', 'N/A')],
                    ['Quantity:', item.get('quantity', 'N/A')],
                    ['Material:', item.get('material', 'N/A')],
                    ['Material Quantity:', item.get('material_qty', 'N/A')],
                    ['Price:', item.get('price', 'N/A')],
                    ['Labour:', item.get('labour', 'N/A')],
                    ['Photos:', str(len(item.get('photos', [])))]
                ]
                
                item_table = create_info_table(item_data, col_widths=[1.8*inch, 4.2*inch])
                story.append(item_table)
                
                # Add photos for this work item
                photos = item.get('photos', [])
                logger.info(f"    Adding photos for work item {idx}: {len(photos)} photos")
                if photos:
                    story.append(Spacer(1, 0.15*inch))
                    add_paragraph(story, f"<b>Photos for Work Item {idx} ({len(photos)} total):</b>")
                    story.append(Spacer(1, 0.1*inch))
                    logger.info(f"    Calling add_photo_grid with {len(photos)} photos")
                    add_photo_grid(story, photos)
                else:
                    logger.warning(f"    ⚠️ No photos found for work item {idx}")
                
                # Add page break after each item (except last)
                if idx < len(work_items):
                    story.append(PageBreak())
        else:
            add_paragraph(story, "No work items recorded.")
        
        # PHOTOS SECTION - Show all photos if not already shown per item
        if all_photos and not work_items:
            story.append(Spacer(1, 0.2*inch))
            add_section_heading(story, f"Attached Photos ({len(all_photos)} total)")
            add_photo_grid(story, all_photos)
        elif not all_photos:
            story.append(Spacer(1, 0.2*inch))
            add_paragraph(story, "No photos attached.")
        
        # SUPERVISOR COMMENTS - Show before signatures if available
        if supervisor_comments:
            add_section_heading(story, "Supervisor Comments")
            add_paragraph(story, supervisor_comments)
            story.append(Spacer(1, 0.1*inch))
        
        # SIGNATURES SECTION - Supervisor signature
        signatures = {}
        
        # Handle supervisor/inspector signature - can be dict with url or string
        if inspector_signature:
            if isinstance(inspector_signature, dict) and inspector_signature.get('url'):
                signatures['Supervisor'] = inspector_signature
            elif isinstance(inspector_signature, str) and (inspector_signature.startswith('data:image') or inspector_signature.startswith('http')):
                signatures['Supervisor'] = {'url': inspector_signature, 'is_cloud': False}
        
        # Always show supervisor signature section
        if not signatures:
            signatures = {'Supervisor': None}
        
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

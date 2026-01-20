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
        
        # SIGNATURES PAGE - Professional format with all reviewer signatures
        # Extract all reviewer data similar to HVAC module
        signatures = {}
        
        # Get nested data dict if it exists
        nested_data = data.get('data') if isinstance(data.get('data'), dict) else {}
        
        # Extract supervisor signature - try multiple paths
        supervisor_sig = None
        if inspector_signature:
            supervisor_sig = inspector_signature
        else:
            supervisor_sig_raw = data.get('supervisor_signature')
            if supervisor_sig_raw is not None and supervisor_sig_raw != '' and supervisor_sig_raw != 'None':
                supervisor_sig = supervisor_sig_raw
            elif nested_data and nested_data.get('supervisor_signature'):
                supervisor_sig = nested_data.get('supervisor_signature')
            elif isinstance(data.get('form_data'), dict):
                form_data_dict = data.get('form_data', {})
                if form_data_dict.get('supervisor_signature'):
                    supervisor_sig = form_data_dict.get('supervisor_signature')
        
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
            report_title=f"Civil Works - {project_name}"
        )
        
        logger.info(f"✅ Professional Civil PDF created successfully: {pdf_path}")
        return os.path.basename(pdf_path)
        
    except Exception as e:
        logger.error(f"❌ Civil PDF generation error: {str(e)}")
        raise

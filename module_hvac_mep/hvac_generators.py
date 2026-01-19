import logging
import os
import json
from datetime import datetime, timedelta, timezone as dt_timezone
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

# Dubai timezone offset (Gulf Standard Time, UTC+4)
DUBAI_OFFSET = timedelta(hours=4)

def get_dubai_time():
    """Get current time in Dubai timezone (GST - Gulf Standard Time, UTC+4)"""
    # Get UTC time and add 4 hours for Dubai time
    utc_now = datetime.utcnow()
    dubai_time = utc_now + DUBAI_OFFSET
    return dubai_time

def format_dubai_datetime(dt=None, format_str='%Y-%m-%d %H:%M:%S'):
    """Format datetime in Dubai timezone (GST, UTC+4)"""
    if dt is None:
        dt = get_dubai_time()
    elif isinstance(dt, datetime):
        # If datetime has timezone info, convert to UTC first, then add Dubai offset
        if dt.tzinfo is not None:
            # Convert to UTC
            utc_dt = dt.astimezone(dt_timezone.utc).replace(tzinfo=None)
        else:
            # Assume UTC if naive
            utc_dt = dt
        # Add Dubai offset (UTC+4)
        dt = utc_dt + DUBAI_OFFSET
    else:
        # If not datetime, get current Dubai time
        dt = get_dubai_time()
    return dt.strftime(format_str)

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
        timestamp = get_dubai_time().strftime('%Y%m%d_%H%M%S')
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
            ('Report Generated', format_dubai_datetime() + ' (GST)'),
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
        timestamp = get_dubai_time().strftime('%Y%m%d_%H%M%S')
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
            ['Report Generated:', format_dubai_datetime() + ' (GST)'],
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
        
        # Get nested data dict if it exists (extract once to avoid f-string issues)
        nested_data = data.get('data') if isinstance(data.get('data'), dict) else {}
        
        # Check for supervisor signature (new workflow field)
        # Try multiple paths: direct key, nested in data, or fallback to tech_signature
        supervisor_sig = None
        supervisor_sig_path = None
        
        # Check direct path first
        if data.get('supervisor_signature'):
            supervisor_sig = data.get('supervisor_signature')
            supervisor_sig_path = 'direct (supervisor_signature)'
        # Check nested in data
        elif nested_data and nested_data.get('supervisor_signature'):
            supervisor_sig = nested_data.get('supervisor_signature')
            supervisor_sig_path = 'nested (data.supervisor_signature)'
        # Fallback to tech_signature
        elif data.get('tech_signature'):
            supervisor_sig = data.get('tech_signature')
            supervisor_sig_path = 'fallback (tech_signature)'
        
        # Convert empty strings to None
        if supervisor_sig == '' or supervisor_sig == 'None':
            supervisor_sig = None
        
        supervisor_comments = (
            data.get('supervisor_comments') or 
            (nested_data.get('supervisor_comments') if nested_data else '') or
            ''
        )
        
        # Check for Operations Manager comments (try multiple paths)
        operations_manager_comments = (
            data.get('operations_manager_comments') or 
            data.get('opMan_comments') or
            data.get('opman_comments') or
            data.get('operationsManagerComments') or
            (nested_data.get('operations_manager_comments') if nested_data else '') or
            (nested_data.get('opMan_comments') if nested_data else '') or
            (nested_data.get('opman_comments') if nested_data else '') or
            (nested_data.get('operationsManagerComments') if nested_data else '') or
            ''
        )
        
        # Log Operations Manager comments detection for debugging
        logger.info(f"🔍 Checking Operations Manager comments in PDF generation:")
        logger.info(f"  - Direct operations_manager_comments: {bool(data.get('operations_manager_comments'))} (value: {str(data.get('operations_manager_comments', ''))[:50] if data.get('operations_manager_comments') else 'None'})")
        logger.info(f"  - Nested in data: {bool(nested_data.get('operations_manager_comments') if nested_data else False)}")
        logger.info(f"  - Final operations_manager_comments length: {len(str(operations_manager_comments)) if operations_manager_comments else 0}")
        if operations_manager_comments:
            logger.info(f"  - Operations Manager comments found: {str(operations_manager_comments)[:100]}...")
        else:
            logger.warning(f"  - ⚠️ No Operations Manager comments found in data")
        
        # Check for Business Development comments
        business_dev_comments = (
            data.get('business_dev_comments') or 
            data.get('business_development_comments') or
            (nested_data.get('business_dev_comments') if nested_data else '') or
            (nested_data.get('business_development_comments') if nested_data else '') or
            ''
        )
        
        # Check for Procurement comments
        procurement_comments = (
            data.get('procurement_comments') or
            (nested_data.get('procurement_comments') if nested_data else '') or
            ''
        )
        
        # Check for General Manager comments
        general_manager_comments = (
            data.get('general_manager_comments') or
            (nested_data.get('general_manager_comments') if nested_data else '') or
            ''
        )
        
        # Log signature detection for debugging
        logger.info(f"🔍 Checking supervisor signature in PDF generation:")
        logger.info(f"  - Direct supervisor_signature: {bool(data.get('supervisor_signature'))} (value type: {type(data.get('supervisor_signature'))})")
        logger.info(f"  - Nested in data: {bool(nested_data.get('supervisor_signature') if nested_data else False)}")
        logger.info(f"  - Found supervisor_sig via: {supervisor_sig_path}")
        logger.info(f"  - Final supervisor_sig type: {type(supervisor_sig)}, length: {len(str(supervisor_sig)) if supervisor_sig else 0}")
        if supervisor_sig:
            logger.info(f"  - Signature preview: {str(supervisor_sig)[:100]}...")
        
        if supervisor_sig:
            # Handle different signature formats
            if isinstance(supervisor_sig, dict):
                # Dictionary format with 'url' key
                if supervisor_sig.get('url'):
                    signatures['Supervisor'] = supervisor_sig
                    logger.debug("✅ Found supervisor signature in dict format with URL")
            elif isinstance(supervisor_sig, str):
                # String format - check if it's a valid image data URL or HTTP URL
                sig_str = supervisor_sig.strip()
                if sig_str and (sig_str.startswith('data:image') or sig_str.startswith('http://') or sig_str.startswith('https://') or sig_str.startswith('/')):
                    signatures['Supervisor'] = sig_str
                    logger.debug(f"✅ Found supervisor signature as string (starts with: {sig_str[:50]}...)")
                elif sig_str:
                    # Might be a base64 string without data: prefix, try it anyway
                    logger.warning(f"⚠️ Supervisor signature doesn't match expected format: {sig_str[:50]}...")
                    signatures['Supervisor'] = sig_str
            else:
                logger.warning(f"⚠️ Supervisor signature has unexpected type: {type(supervisor_sig)}")
        
        # Check for Operations Manager signature (try multiple key variations)
        logger.info(f"🔍 Checking Operations Manager signature in PDF generation:")
        logger.info(f"  - data.get('operations_manager_signature'): {bool(data.get('operations_manager_signature'))}")
        logger.info(f"  - data.get('opMan_signature'): {bool(data.get('opMan_signature'))}")
        logger.info(f"  - data.get('opman_signature'): {bool(data.get('opman_signature'))}")
        logger.info(f"  - data.get('data') is dict: {isinstance(data.get('data'), dict)}")
        if nested_data:
            logger.info(f"  - nested_data.get('operations_manager_signature'): {bool(nested_data.get('operations_manager_signature'))}")
            logger.info(f"  - nested_data.get('opMan_signature'): {bool(nested_data.get('opMan_signature'))}")
            logger.info(f"  - nested_data.get('opman_signature'): {bool(nested_data.get('opman_signature'))}")
        
        # Try all possible paths for Operations Manager signature
        opman_sig = None
        opman_sig_path = None
        
        # Check direct paths first
        if data.get('operations_manager_signature'):
            opman_sig = data.get('operations_manager_signature')
            opman_sig_path = 'direct (operations_manager_signature)'
        elif data.get('opMan_signature'):
            opman_sig = data.get('opMan_signature')
            opman_sig_path = 'direct (opMan_signature)'
        elif data.get('opman_signature'):
            opman_sig = data.get('opman_signature')
            opman_sig_path = 'direct (opman_signature)'
        # Check nested paths
        elif nested_data and nested_data.get('operations_manager_signature'):
            opman_sig = nested_data.get('operations_manager_signature')
            opman_sig_path = 'nested (data.operations_manager_signature)'
        elif nested_data and nested_data.get('opMan_signature'):
            opman_sig = nested_data.get('opMan_signature')
            opman_sig_path = 'nested (data.opMan_signature)'
        elif nested_data and nested_data.get('opman_signature'):
            opman_sig = nested_data.get('opman_signature')
            opman_sig_path = 'nested (data.opman_signature)'
        
        if opman_sig:
            logger.info(f"✅ Found Operations Manager signature via: {opman_sig_path}")
            logger.info(f"  - Signature type: {type(opman_sig)}")
            if isinstance(opman_sig, str):
                logger.info(f"  - Signature length: {len(opman_sig)}")
                logger.info(f"  - Signature preview: {opman_sig[:100]}...")
            
            if isinstance(opman_sig, dict) and opman_sig.get('url'):
                signatures['Operations Manager'] = opman_sig
                logger.info("✅ Added Operations Manager signature to signatures dict (dict format with URL)")
            elif isinstance(opman_sig, str) and (opman_sig.startswith('data:image') or opman_sig.startswith('http') or opman_sig.startswith('/')):
                signatures['Operations Manager'] = opman_sig
                logger.info(f"✅ Added Operations Manager signature to signatures dict (string format, length: {len(opman_sig)})")
            else:
                logger.warning(f"⚠️ Operations Manager signature found but format unexpected: {type(opman_sig)}")
                # Try to add it anyway if it's not empty
                if opman_sig and str(opman_sig).strip():
                    signatures['Operations Manager'] = opman_sig
                    logger.info("⚠️ Added Operations Manager signature despite unexpected format")
        else:
            logger.warning("⚠️ Operations Manager signature not found in any path")
            logger.warning(f"  - Available keys in data: {list(data.keys())[:20]}")
            if nested_data:
                logger.warning(f"  - Available keys in nested_data: {list(nested_data.keys())[:20]}")
        
        # Check for Business Development signature (try multiple key variations)
        logger.info(f"🔍 Checking Business Development signature in PDF generation:")
        logger.info(f"  - data.get('business_dev_signature'): {bool(data.get('business_dev_signature'))}")
        logger.info(f"  - data.get('businessDevSignature'): {bool(data.get('businessDevSignature'))}")
        if nested_data:
            logger.info(f"  - data.get('data').get('business_dev_signature'): {bool(nested_data.get('business_dev_signature'))}")
        
        business_dev_sig = (
            data.get('business_dev_signature') or 
            data.get('businessDevSignature', '') or
            nested_data.get('business_dev_signature') or
            nested_data.get('businessDevSignature')
        )
        if business_dev_sig:
            if isinstance(business_dev_sig, dict) and business_dev_sig.get('url'):
                signatures['Business Development'] = business_dev_sig
                logger.info("✅ Found Business Development signature in dict format with URL")
            elif isinstance(business_dev_sig, str) and (business_dev_sig.startswith('data:image') or business_dev_sig.startswith('http') or business_dev_sig.startswith('/')):
                signatures['Business Development'] = business_dev_sig
                logger.info(f"✅ Found Business Development signature as string (length: {len(business_dev_sig)})")
            else:
                logger.warning(f"⚠️ Business Development signature found but format unexpected: {type(business_dev_sig)}")
        else:
            logger.debug("ℹ️ Business Development signature not found (may not be approved yet)")
        
        # Check for Procurement signature
        procurement_sig = data.get('procurement_signature', '') or data.get('procurementSignature', '')
        if procurement_sig:
            if isinstance(procurement_sig, dict) and procurement_sig.get('url'):
                signatures['Procurement'] = procurement_sig
            elif isinstance(procurement_sig, str) and (procurement_sig.startswith('data:image') or procurement_sig.startswith('http')):
                signatures['Procurement'] = procurement_sig
        
        # Check for General Manager signature
        general_manager_sig = data.get('general_manager_signature', '') or data.get('generalManagerSignature', '')
        if general_manager_sig:
            if isinstance(general_manager_sig, dict) and general_manager_sig.get('url'):
                signatures['General Manager'] = general_manager_sig
            elif isinstance(general_manager_sig, str) and (general_manager_sig.startswith('data:image') or general_manager_sig.startswith('http')):
                signatures['General Manager'] = general_manager_sig
        
        # Helper function to add comment and signature together for a reviewer
        def add_reviewer_section(role_name, comments, signature_data):
            """Add comments and signature together for a reviewer"""
            has_content = False
            
            if comments and comments.strip():
                add_section_heading(story, f"{role_name} Comments")
                add_paragraph(story, comments)
                story.append(Spacer(1, 0.1*inch))
                has_content = True
            
            if signature_data:
                # Add signature section for this reviewer
                styles = get_professional_styles()
                sig_rows = []
                
                try:
                    from common.utils import get_image_for_pdf
                    img_data, is_url = get_image_for_pdf(signature_data)
                    if img_data:
                        sig_img = Image(img_data)
                        sig_img._restrictSize(2.5*inch, 1.2*inch)
                        sig_rows.append([
                            Paragraph(f"<b>{role_name}:</b>", styles['Normal']),
                            sig_img
                        ])
                    else:
                        sig_rows.append([
                            Paragraph(f"<b>{role_name}:</b>", styles['Normal']),
                            Paragraph("Signature not available", styles['Small'])
                        ])
                except Exception as e:
                    logger.error(f"Error processing {role_name} signature: {str(e)}")
                    sig_rows.append([
                        Paragraph(f"<b>{role_name}:</b>", styles['Normal']),
                        Paragraph("Error loading signature", styles['Small'])
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
        
        # Add reviewer sections in workflow order: comments + signature together for each
        # 1. Supervisor
        if supervisor_comments or signatures.get('Supervisor'):
            add_reviewer_section("Supervisor", supervisor_comments, signatures.get('Supervisor'))
        
        # 2. Operations Manager
        ops_mgr_comments = operations_manager_comments.strip() if operations_manager_comments and operations_manager_comments.strip() else None
        ops_mgr_sig = signatures.get('Operations Manager')
        logger.info(f"🔍 Operations Manager section check:")
        logger.info(f"  - Comments present: {bool(ops_mgr_comments)}")
        logger.info(f"  - Signature present: {bool(ops_mgr_sig)}")
        logger.info(f"  - Signature type: {type(ops_mgr_sig) if ops_mgr_sig else 'None'}")
        if ops_mgr_sig and isinstance(ops_mgr_sig, str):
            logger.info(f"  - Signature length: {len(ops_mgr_sig)}")
        
        if ops_mgr_comments or ops_mgr_sig:
            logger.info(f"✅ Adding Operations Manager section to PDF (comments: {bool(ops_mgr_comments)}, signature: {bool(ops_mgr_sig)})")
            add_reviewer_section("Operations Manager", ops_mgr_comments, ops_mgr_sig)
        else:
            logger.warning("⚠️ Skipping Operations Manager section - no comments or signature")
        
        # 3. Business Development
        if business_dev_comments or signatures.get('Business Development'):
            add_reviewer_section("Business Development", business_dev_comments, signatures.get('Business Development'))
        
        # 4. Procurement
        if procurement_comments or signatures.get('Procurement'):
            add_reviewer_section("Procurement", procurement_comments, signatures.get('Procurement'))
        
        # 5. General Manager
        if general_manager_comments or signatures.get('General Manager'):
            add_reviewer_section("General Manager", general_manager_comments, signatures.get('General Manager'))
        
        # Add document signed timestamp if any signatures exist
        if any(signatures.values()):
            styles = get_professional_styles()
            story.append(Spacer(1, 0.15*inch))
            story.append(Paragraph(
                f"<i>Document signed on: {format_dubai_datetime(format_str='%B %d, %Y at %H:%M')} (GST)</i>",
                styles['Small']
            ))
        
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
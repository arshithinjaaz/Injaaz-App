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

def create_excel_report(data, output_dir):
    """Generate HVAC/MEP Excel report with openpyxl."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        
        logger.info(f"Creating Excel report in {output_dir}")
        
        # Generate filename
        site_name = data.get('site_name', 'Unknown_Site').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"HVAC_MEP_{site_name}_{timestamp}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        # Create workbook and worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = "HVAC MEP Inspection"
        
        # Define styles
        header_fill = PatternFill(start_color="125435", end_color="125435", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=12)
        title_font = Font(bold=True, size=16, color="125435")
        label_font = Font(bold=True, size=10)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Title
        ws['A1'] = "HVAC & MEP INSPECTION REPORT"
        ws['A1'].font = title_font
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:F1')
        
        # Site Information
        row = 3
        ws[f'A{row}'] = "Site Information"
        ws[f'A{row}'].font = Font(bold=True, size=12, color="125435")
        row += 1
        
        site_info = [
            ('Site Name:', data.get('site_name', 'N/A')),
            ('Visit Date:', data.get('visit_date', 'N/A')),
            ('Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('Total Items:', str(len(data.get('items', []))))
        ]
        
        for label, value in site_info:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = label_font
            ws[f'B{row}'] = value
            row += 1
        
        row += 1
        
        # Items Header
        ws[f'A{row}'] = "Inspection Items"
        ws[f'A{row}'].font = Font(bold=True, size=12, color="125435")
        row += 2
        
        # Column headers
        headers = ['#', 'Asset Name', 'System Type', 'Description', 'Photos Count']
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_num)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border
        
        row += 1
        
        # Items data
        items = data.get('items', [])
        for idx, item in enumerate(items, 1):
            photos = item.get('photos', [])
            
            ws.cell(row=row, column=1, value=idx)
            ws.cell(row=row, column=2, value=item.get('asset', 'N/A'))
            ws.cell(row=row, column=3, value=item.get('system', 'N/A'))
            ws.cell(row=row, column=4, value=item.get('description', 'N/A'))
            ws.cell(row=row, column=5, value=len(photos))
            
            # Apply borders
            for col in range(1, 6):
                ws.cell(row=row, column=col).border = border
                ws.cell(row=row, column=col).alignment = Alignment(vertical='top', wrap_text=True)
            
            row += 1
        
        # Adjust column widths
        ws.column_dimensions['A'].width = 5
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 40
        ws.column_dimensions['E'].width = 12
        
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
    """Generate comprehensive HVAC/MEP PDF report with ALL images."""
    try:
        logger.info(f"Creating PDF report in {output_dir}")
        
        # Generate filename
        site_name = data.get('site_name', 'Unknown_Site').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"HVAC_MEP_{site_name}_{timestamp}.pdf"
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
        
        # Container for PDF elements
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
        story.append(Paragraph("HVAC & MEP INSPECTION REPORT", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # SITE INFORMATION
        story.append(Paragraph("Site Information", heading_style))
        
        site_info_data = [
            ['Site Name:', data.get('site_name', 'N/A')],
            ['Visit Date:', data.get('visit_date', 'N/A')],
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Total Items:', str(len(data.get('items', [])))]
        ]
        
        site_table = Table(site_info_data, colWidths=[2*inch, 4*inch])
        site_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(site_table)
        story.append(Spacer(1, 0.3*inch))
        
        # INSPECTION ITEMS
        items = data.get('items', [])
        
        if items:
            story.append(Paragraph("Inspection Items", heading_style))
            
            for idx, item in enumerate(items, 1):
                # Item header
                story.append(Paragraph(f"Item {idx}: {item.get('asset', 'N/A')}", subheading_style))
                
                # Item details table
                item_details = [
                    ['Asset:', item.get('asset', 'N/A')],
                    ['System:', item.get('system', 'N/A')],
                    ['Description:', item.get('description', 'N/A')],
                    ['Photos:', str(len(item.get('photos', [])))]
                ]
                
                item_table = Table(item_details, colWidths=[1.5*inch, 4.5*inch])
                item_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f9fafb')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
                ]))
                
                story.append(item_table)
                story.append(Spacer(1, 0.15*inch))
                
                # PHOTOS - Support both cloud URLs and local paths
                photos = item.get('photos', [])
                
                if photos:
                    story.append(Paragraph(f"Photos ({len(photos)} total)", normal_style))
                    
                    # Process photos in rows of 2
                    photo_rows = []
                    for i in range(0, len(photos), 2):
                        row_photos = photos[i:i+2]
                        photo_row = []
                        
                        for photo_item in row_photos:
                            try:
                                img_data, is_url = get_image_for_pdf(photo_item)
                                if img_data:
                                    img = Image(img_data, width=2.5*inch, height=2*inch)
                                    photo_row.append(img)
                                else:
                                    photo_row.append(Paragraph(f"Image not available", normal_style))
                            except Exception as e:
                                logger.error(f"Error loading photo {photo_item}: {str(e)}")
                                photo_row.append(Paragraph(f"Error loading image", normal_style))
                        
                        # If odd number of photos, add empty cell
                        if len(photo_row) == 1:
                            photo_row.append('')
                        
                        photo_rows.append(photo_row)
                    
                    # Create photo table
                    if photo_rows:
                        photo_table = Table(photo_rows, colWidths=[2.8*inch, 2.8*inch])
                        photo_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 5),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                            ('TOPPADDING', (0, 0), (-1, -1), 5),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                        ]))
                        story.append(photo_table)
                        story.append(Spacer(1, 0.2*inch))
                
                # Add page break after each item (except last)
                if idx < len(items):
                    story.append(PageBreak())
        
        else:
            story.append(Paragraph("No inspection items recorded.", normal_style))
        
        # SIGNATURES PAGE - WITH PROPER ASPECT RATIO
        story.append(PageBreak())
        story.append(Paragraph("Signatures", heading_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Technician Signature
        tech_signature = data.get('tech_signature', '')
        story.append(Paragraph("Technician Signature:", subheading_style))
        
        try:
            img_data, is_url = get_image_for_pdf(tech_signature)
            if img_data:
                sig_img = Image(img_data)
                sig_img._restrictSize(3*inch, 1.5*inch)  # Max size, keeps aspect ratio
                story.append(sig_img)
            else:
                story.append(Paragraph("Not signed", normal_style))
        except Exception as e:
            logger.error(f"❌ Error processing tech signature: {str(e)}")
            story.append(Paragraph("Signature not available", normal_style))
        
        story.append(Spacer(1, 0.3*inch))
        
        # Manager Signature
        manager_signature = data.get('opman_signature', '')
        story.append(Paragraph("Operation Manager Signature:", subheading_style))
        
        try:
            img_data, is_url = get_image_for_pdf(manager_signature)
            if img_data:
                sig_img = Image(img_data)
                sig_img._restrictSize(3*inch, 1.5*inch)  # Max size, keeps aspect ratio
                story.append(sig_img)
            else:
                story.append(Paragraph("Not signed", normal_style))
        except Exception as e:
            logger.error(f"❌ Error processing manager signature: {str(e)}")
            story.append(Paragraph("Signature not available", normal_style))
        
        # Footer
        story.append(Spacer(1, 0.5*inch))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        story.append(Paragraph(
            f"Generated by Injaaz Platform • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            footer_style
        ))
        
        # Build PDF
        doc.build(story)
        
        if not os.path.exists(pdf_path):
            raise Exception(f"PDF file not created at {pdf_path}")
        
        logger.info(f"✅ PDF report created successfully: {pdf_path}")
        return pdf_path
        
    except Exception as e:
        logger.error(f"❌ PDF generation error: {str(e)}")
        raise
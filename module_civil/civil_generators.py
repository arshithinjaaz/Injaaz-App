"""
Civil report generators for Excel and PDF.
"""
import os
import logging
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

def create_excel_report(data, output_dir):
    """Generate Civil Works Excel report."""
    try:
        logger.info(f"Creating Civil Excel report in {output_dir}")
        
        # Extract data from fields dict (FormData submission)
        fields = data.get('fields', {})
        files = data.get('files', [])
        
        project_name = fields.get('project_name', ['Unknown_Project'])[0] if isinstance(fields.get('project_name'), list) else fields.get('project_name', 'Unknown_Project')
        project_name = project_name.replace(' ', '_') if project_name else 'Unknown_Project'
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"Civil_{project_name}_{timestamp}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Civil Works Report"
        
        # Styles
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
        ws['A1'] = "CIVIL WORKS INSPECTION REPORT"
        ws['A1'].font = title_font
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:E1')
        
        # Project Information
        row = 3
        ws[f'A{row}'] = "Project Information"
        ws[f'A{row}'].font = Font(bold=True, size=12, color="125435")
        row += 1
        
        # Extract form fields (they come as lists from FormData)
        def get_field(name, default='N/A'):
            val = fields.get(name, default)
            return val[0] if isinstance(val, list) and val else (val or default)
        
        project_info = [
            ('Project Name:', get_field('project_name')),
            ('Location:', get_field('location')),
            ('Visit Date:', get_field('visit_date')),
            ('Inspector:', get_field('inspector_name')),
            ('Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('Total Photos:', str(len(files)))
        ]
        
        for label, value in project_info:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = label_font
            ws[f'B{row}'] = value
            row += 1
        
        row += 1
        
        # Work Items - Reconstruct from FormData parallel arrays
        ws[f'A{row}'] = "Work Items"
        ws[f'A{row}'].font = Font(bold=True, size=12, color="125435")
        row += 2
        
        headers = ['#', 'Description', 'Quantity', 'Material', 'Price', 'Labour']
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_num)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border
        
        row += 1
        
        # Extract work item parallel arrays from FormData
        # Handle both single value (string) and multiple values (list)
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
    """Generate Civil Works PDF report with photos."""
    try:
        logger.info(f"Creating Civil PDF report in {output_dir}")
        
        project_name = data.get('project_name', 'Unknown_Project').replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"Civil_{project_name}_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
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
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=0.1*inch
        )
        
        # Title
        story.append(Paragraph("CIVIL WORKS INSPECTION REPORT", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Project Information
        story.append(Paragraph("Project Information", heading_style))
        
        # Extract form fields (they come as lists from FormData)
        fields = data.get('fields', {})
        files = data.get('files', [])
        
        def get_field(name, default='N/A'):
            val = fields.get(name, default)
            return val[0] if isinstance(val, list) and val else (val or default)
        
        project_data = [
            ['Project Name:', get_field('project_name')],
            ['Location:', get_field('location')],
            ['Visit Date:', get_field('visit_date')],
            ['Inspector:', get_field('inspector_name')],
            ['Manager:', get_field('manager_name')],
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Total Photos:', str(len(files))]
        ]
        
        project_table = Table(project_data, colWidths=[2*inch, 4*inch])
        project_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f9fafb')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(project_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Work Items - Reconstruct from FormData parallel arrays
        story.append(Paragraph("Work Items", heading_style))
        
        # Extract work item parallel arrays
        # Handle both single value (string) and multiple values (list)
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
                story.append(Paragraph(f"Item {idx + 1}", 
                                     ParagraphStyle('ItemHeader', parent=heading_style, fontSize=12)))
                
                item_data = [
                    ['Description:', work_descriptions[idx] if idx < len(work_descriptions) else 'N/A'],
                    ['Quantity:', work_quantities[idx] if idx < len(work_quantities) else 'N/A'],
                    ['Material:', work_materials[idx] if idx < len(work_materials) else 'N/A'],
                    ['Price:', work_prices[idx] if idx < len(work_prices) else 'N/A'],
                    ['Labour:', work_labours[idx] if idx < len(work_labours) else 'N/A']
                ]
                
                item_table = Table(item_data, colWidths=[1.5*inch, 4.5*inch])
                item_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f9fafb')),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                
                story.append(item_table)
                story.append(Spacer(1, 0.15*inch))
        
        # Photos Section - Show all uploaded photos
        if files:
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph(f"Attached Photos ({len(files)} total)", heading_style))
            
            photo_rows = []
            for i in range(0, len(files), 2):
                row_files = files[i:i+2]
                photo_row = []
                
                for photo_item in row_files:
                    try:
                        # photo_item has {url: ..., is_cloud: True/False}
                        img_data, is_url = get_image_for_pdf(photo_item)
                        if img_data:
                            img = Image(img_data, width=2.5*inch, height=2*inch)
                            photo_row.append(img)
                        else:
                            photo_row.append(Paragraph("Image not available", normal_style))
                    except Exception as e:
                        logger.error(f"Error loading photo: {e}")
                        photo_row.append(Paragraph("Error loading image", normal_style))
                
                if len(photo_row) == 1:
                    photo_row.append('')
                
                photo_rows.append(photo_row)
            
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
        else:
            story.append(Paragraph("No photos attached.", normal_style))
        
        # Signatures Section
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("Signatures", heading_style))
        
        tech_sig = get_field('tech_signature', None)
        op_sig = get_field('op_signature', None)
        
        sig_data = []
        if tech_sig and tech_sig.startswith('data:image'):
            try:
                sig_item = {'url': tech_sig, 'is_cloud': False}
                img_data, _ = get_image_for_pdf(sig_item)
                if img_data:
                    tech_img = Image(img_data, width=2*inch, height=1*inch)
                    sig_data.append([Paragraph('<b>Technical Engineer:</b>', normal_style), tech_img])
                else:
                    sig_data.append([Paragraph('<b>Technical Engineer:</b>', normal_style), Paragraph('Signature not available', normal_style)])
            except Exception as e:
                logger.error(f"Error loading tech signature: {e}")
                sig_data.append([Paragraph('<b>Technical Engineer:</b>', normal_style), Paragraph('Error loading signature', normal_style)])
        else:
            sig_data.append([Paragraph('<b>Technical Engineer:</b>', normal_style), Paragraph('Not signed', normal_style)])
        
        if op_sig and op_sig.startswith('data:image'):
            try:
                sig_item = {'url': op_sig, 'is_cloud': False}
                img_data, _ = get_image_for_pdf(sig_item)
                if img_data:
                    op_img = Image(img_data, width=2*inch, height=1*inch)
                    sig_data.append([Paragraph('<b>Operation/Maintenance:</b>', normal_style), op_img])
                else:
                    sig_data.append([Paragraph('<b>Operation/Maintenance:</b>', normal_style), Paragraph('Signature not available', normal_style)])
            except Exception as e:
                logger.error(f"Error loading op signature: {e}")
                sig_data.append([Paragraph('<b>Operation/Maintenance:</b>', normal_style), Paragraph('Error loading signature', normal_style)])
        else:
            sig_data.append([Paragraph('<b>Operation/Maintenance:</b>', normal_style), Paragraph('Not signed', normal_style)])
        
        if sig_data:
            sig_table = Table(sig_data, colWidths=[2*inch, 3*inch])
            sig_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(sig_table)
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"✅ Civil PDF report created: {pdf_path}")
        return os.path.basename(pdf_path)
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"✅ Civil PDF report created: {pdf_path}")
        return os.path.basename(pdf_path)
        
    except Exception as e:
        logger.error(f"❌ Civil PDF generation error: {str(e)}")
        raise
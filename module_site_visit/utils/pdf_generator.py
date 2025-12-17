"""
PDF report generator for HVAC/MEP site visits
"""
import os
import time
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
import logging

logger = logging.getLogger(__name__)

def generate_visit_pdf(visit_info, processed_items, output_dir):
    """Generate PDF report for HVAC/MEP site visit."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = int(time.time())
        filename = f"hvac_mep_report_{timestamp}.pdf"
        filepath = os.path.join(output_dir, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f4788'),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        story.append(Paragraph("HVAC/MEP Site Visit Report", title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Visit information table
        info_data = [
            ['Building Name:', visit_info.get('building_name', '')],
            ['Address:', visit_info.get('building_address', '')],
            ['Visit Date:', visit_info.get('visit_date', '')],
            ['Technician:', visit_info.get('technician_name', '')],
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 0.5*inch))
        
        # Items section
        story.append(Paragraph("Inspection Items", styles['Heading2']))
        story.append(Spacer(1, 0.2*inch))
        
        for idx, item in enumerate(processed_items, 1):
            item_title = f"Item {idx}: {item.get('asset', 'N/A')}"
            story.append(Paragraph(item_title, styles['Heading3']))
            
            item_data = [
                ['System:', item.get('system', '')],
                ['Description:', item.get('description', '')],
                ['Quantity:', item.get('quantity', '')],
                ['Brand:', item.get('brand', '')],
                ['Comments:', item.get('comments', '')],
            ]
            
            item_table = Table(item_data, colWidths=[1.5*inch, 4.5*inch])
            item_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            
            story.append(item_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Add images
            for img_path in item.get('image_paths', [])[:3]:
                if os.path.exists(img_path):
                    try:
                        img = Image(img_path, width=4*inch, height=3*inch)
                        story.append(img)
                        story.append(Spacer(1, 0.1*inch))
                    except Exception as e:
                        logger.warning(f"Could not add image: {e}")
            
            story.append(Spacer(1, 0.3*inch))
        
        doc.build(story)
        logger.info(f"PDF report created: {filepath}")
        
        return filepath, filename
        
    except Exception as e:
        logger.error(f"Failed to create PDF report: {str(e)}")
        raise

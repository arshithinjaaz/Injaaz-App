"""
Professional PDF Service with Branding, Logo, and Signatures
Provides reusable components for all module PDFs
"""
import os
import logging
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm, mm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph, 
                                Spacer, Image, PageBreak, Frame, PageTemplate)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from common.utils import get_image_for_pdf

logger = logging.getLogger(__name__)

# Company branding colors
PRIMARY_COLOR = colors.HexColor('#125435')      # Dark green
SECONDARY_COLOR = colors.HexColor('#1a7a4d')    # Medium green
ACCENT_COLOR = colors.HexColor('#E8F5E9')       # Light green
HEADER_BG = colors.HexColor('#125435')
TABLE_HEADER_BG = colors.HexColor('#125435')
TABLE_ALT_ROW = colors.HexColor('#f9fafb')
BORDER_COLOR = colors.HexColor('#e5e7eb')

# Logo path
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'logo.png')


class NumberedCanvas(canvas.Canvas):
    """Custom canvas to add header, footer, and page numbers"""
    
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.report_title = kwargs.get('report_title', 'Injaaz Report')
        
    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
        
    def save(self):
        """Add page info to each page (page x of y)"""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
        
    def draw_page_decorations(self, page_count):
        """Draw header and footer on each page"""
        # Header line
        self.setStrokeColor(PRIMARY_COLOR)
        self.setLineWidth(2)
        self.line(1.5*cm, A4[1] - 1.5*cm, A4[0] - 1.5*cm, A4[1] - 1.5*cm)
        
        # Logo in header (if exists)
        if os.path.exists(LOGO_PATH):
            try:
                self.drawImage(LOGO_PATH, 1.5*cm, A4[1] - 1.4*cm, 
                             width=1.2*cm, height=1.2*cm, preserveAspectRatio=True, mask='auto')
            except Exception as e:
                logger.warning(f"Could not load logo: {e}")
        
        # Company name in header
        self.setFont('Helvetica-Bold', 10)
        self.setFillColor(PRIMARY_COLOR)
        self.drawString(3*cm, A4[1] - 1.2*cm, "INJAAZ PLATFORM")
        
        # Footer
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.5)
        self.line(1.5*cm, 1.5*cm, A4[0] - 1.5*cm, 1.5*cm)
        
        # Page number
        self.setFont('Helvetica', 8)
        self.setFillColor(colors.grey)
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 1.5*cm, 1.2*cm, page_text)
        
        # Timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        self.drawString(1.5*cm, 1.2*cm, f"Generated: {timestamp}")
        
        # Report title in footer
        self.drawCentredString(A4[0] / 2, 1.2*cm, self.report_title)


def get_professional_styles():
    """Return professional styled paragraph styles"""
    styles = getSampleStyleSheet()
    
    custom_styles = {
        'MainTitle': ParagraphStyle(
            'MainTitle',
            parent=styles['Heading1'],
            fontSize=16,  # Reduced from 18 for compact layout
            textColor=PRIMARY_COLOR,
            spaceAfter=0.08*inch,  # Reduced spacing
            spaceBefore=0,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ),
        'Subtitle': ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=10,  # Reduced from 11
            textColor=SECONDARY_COLOR,
            spaceAfter=0.12*inch,  # Reduced spacing
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ),
        'SectionHeading': ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=13,  # Reduced from 14
            textColor=PRIMARY_COLOR,
            spaceAfter=0.08*inch,  # Reduced spacing
            spaceBefore=0.12*inch,  # Reduced spacing
            fontName='Helvetica-Bold',
            borderPadding=3,  # Reduced from 4
            borderColor=PRIMARY_COLOR,
            borderWidth=1,
            borderRadius=3,
            backColor=ACCENT_COLOR,
            leftIndent=4,  # Reduced from 5
        ),
        'ItemHeading': ParagraphStyle(
            'ItemHeading',
            parent=styles['Heading3'],
            fontSize=11,  # Reduced from 12
            textColor=SECONDARY_COLOR,
            spaceAfter=0.06*inch,  # Reduced spacing
            spaceBefore=0.08*inch,  # Reduced spacing
            fontName='Helvetica-Bold'
        ),
        'Normal': ParagraphStyle(
            'ProfessionalNormal',
            parent=styles['Normal'],
            fontSize=9,  # Reduced from 10 for compact layout
            spaceAfter=0.06*inch,  # Reduced spacing
            leading=13  # Reduced from 14
        ),
        'Small': ParagraphStyle(
            'Small',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
    }
    
    return custom_styles


def create_header_with_logo(story, title, subtitle=None):
    """Add professional header with logo to PDF story"""
    styles = get_professional_styles()
    
    # Logo and title row - compact layout
    header_data = []
    
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image(LOGO_PATH, width=0.9*inch, height=0.9*inch)
            title_para = Paragraph(f"<b>{title}</b>", styles['MainTitle'])
            header_data.append([logo, title_para])
        except Exception as e:
            logger.warning(f"Could not load logo: {e}")
            header_data.append([Paragraph(f"<b>{title}</b>", styles['MainTitle'])])
    else:
        header_data.append([Paragraph(f"<b>{title}</b>", styles['MainTitle'])])
    
    if header_data and len(header_data[0]) == 2:
        header_table = Table(header_data, colWidths=[1.2*inch, 5*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
    else:
        story.append(Paragraph(f"<b>{title}</b>", styles['MainTitle']))
    
    if subtitle:
        story.append(Paragraph(subtitle, styles['Subtitle']))
    
    story.append(Spacer(1, 0.12*inch))  # Reduced spacing for compact layout
    return story


def create_info_table(data_list, col_widths=None):
    """Create a professional styled information table
    
    Args:
        data_list: List of [label, value] pairs
        col_widths: Optional column widths
    """
    if not col_widths:
        col_widths = [2*inch, 4*inch]
    
    table = Table(data_list, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), ACCENT_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.75, PRIMARY_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    return table


def create_data_table(headers, rows, col_widths=None):
    """Create a professional data table with headers
    
    Args:
        headers: List of header strings
        rows: List of row data lists
        col_widths: Optional column widths
    """
    table_data = [headers] + rows
    
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, TABLE_ALT_ROW]),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.75, BORDER_COLOR),
        ('LINEABOVE', (0, 0), (-1, 0), 1.5, PRIMARY_COLOR),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, PRIMARY_COLOR),
        
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    return table


def add_photo_grid(story, photos, photos_per_row=None, photo_width=None, photo_height=None):
    """Add a grid of photos to the story - optimized for 20+ images
    
    Args:
        story: PDF story list
        photos: List of photo items (URLs or base64)
        photos_per_row: Number of photos per row (auto-calculated if None based on photo count)
        photo_width: Width of each photo (auto-calculated if None)
        photo_height: Height of each photo (auto-calculated if None)
    """
    styles = get_professional_styles()
    
    if not photos:
        return story
    
    photo_count = len(photos)
    
    # Auto-adjust layout based on number of photos for better handling of 20+ images
    if photos_per_row is None:
        if photo_count > 20:
            photos_per_row = 4  # 4 photos per row for 20+ images
        elif photo_count > 10:
            photos_per_row = 3  # 3 photos per row for 10-20 images
        else:
            photos_per_row = 2  # 2 photos per row for <10 images
    
    # Auto-adjust photo size based on number per row
    if photo_width is None or photo_height is None:
        if photos_per_row == 4:
            photo_width = 1.7*inch  # Smaller for 4 per row
            photo_height = 1.3*inch
        elif photos_per_row == 3:
            photo_width = 2.2*inch  # Medium for 3 per row
            photo_height = 1.65*inch
        else:
            photo_width = 2.5*inch  # Standard for 2 per row
            photo_height = 2*inch
    
    photo_rows = []
    for i in range(0, len(photos), photos_per_row):
        row_photos = photos[i:i+photos_per_row]
        photo_row = []
        
        for photo_item in row_photos:
            try:
                img_data, is_url = get_image_for_pdf(photo_item)
                if img_data:
                    img = Image(img_data, width=photo_width, height=photo_height)
                    photo_row.append(img)
                else:
                    photo_row.append(Paragraph("Image not available", styles['Small']))
            except Exception as e:
                logger.error(f"Error loading photo: {str(e)}")
                photo_row.append(Paragraph("Error loading image", styles['Small']))
        
        # Pad row if needed
        while len(photo_row) < photos_per_row:
            photo_row.append('')
        
        photo_rows.append(photo_row)
    
    # Add photos in batches to avoid memory issues with many images
    if photo_rows:
        col_widths = [photo_width + 0.15*inch] * photos_per_row
        photo_table = Table(photo_rows, colWidths=col_widths)
        photo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ]))
        story.append(photo_table)
        story.append(Spacer(1, 0.15*inch))  # Reduced spacing
    
    return story


def add_signatures_section(story, signatures_dict):
    """Add professional signatures section
    
    Args:
        story: PDF story list
        signatures_dict: Dict with signature info, e.g.:
            {
                'Technician': signature_data,
                'Manager': signature_data,
                'Inspector': signature_data
            }
    """
    styles = get_professional_styles()
    
    story.append(PageBreak())
    story.append(Paragraph("Signatures & Approval", styles['SectionHeading']))
    story.append(Spacer(1, 0.15*inch))  # Reduced spacing
    
    sig_rows = []
    
    for role, sig_data in signatures_dict.items():
        if not sig_data:
            sig_rows.append([
                Paragraph(f"<b>{role}:</b>", styles['Normal']),
                Paragraph("Not signed", styles['Small'])
            ])
            continue
        
        try:
            img_data, is_url = get_image_for_pdf(sig_data)
            if img_data:
                sig_img = Image(img_data)
                sig_img._restrictSize(2.5*inch, 1.2*inch)  # Max size, keeps aspect ratio
                sig_rows.append([
                    Paragraph(f"<b>{role}:</b>", styles['Normal']),
                    sig_img
                ])
            else:
                sig_rows.append([
                    Paragraph(f"<b>{role}:</b>", styles['Normal']),
                    Paragraph("Signature not available", styles['Small'])
                ])
        except Exception as e:
            logger.error(f"Error processing {role} signature: {str(e)}")
            sig_rows.append([
                Paragraph(f"<b>{role}:</b>", styles['Normal']),
                Paragraph("Error loading signature", styles['Small'])
            ])
    
    if sig_rows:
        sig_table = Table(sig_rows, colWidths=[2*inch, 3.5*inch])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.75, PRIMARY_COLOR),
            ('BACKGROUND', (0, 0), (0, -1), ACCENT_COLOR),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(sig_table)
    
    # Add signature date
    story.append(Spacer(1, 0.15*inch))  # Reduced spacing
    story.append(Paragraph(
        f"<i>Document signed on: {datetime.now().strftime('%B %d, %Y at %H:%M')}</i>",
        styles['Small']
    ))
    
    return story


def create_professional_pdf(pdf_path, story, report_title="Injaaz Report"):
    """Build the PDF with professional styling
    
    Args:
        pdf_path: Output path for PDF
        story: List of flowables (content)
        report_title: Title for footer
    """
    try:
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2.2*cm,
            bottomMargin=2*cm,
            title=report_title,
            author="Injaaz Platform"
        )
        
        # Build with custom canvas for headers/footers
        doc.build(
            story,
            canvasmaker=lambda *args, **kwargs: NumberedCanvas(
                *args, 
                **kwargs, 
                report_title=report_title
            )
        )
        
        if not os.path.exists(pdf_path):
            raise Exception(f"PDF file not created at {pdf_path}")
        
        # Verify PDF file is not empty and has valid structure
        file_size = os.path.getsize(pdf_path)
        if file_size == 0:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            raise Exception(f"PDF file is empty at {pdf_path}")
        
        # Verify PDF header (should start with %PDF)
        try:
            with open(pdf_path, 'rb') as f:
                header = f.read(8)
                if not header.startswith(b'%PDF'):
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                    raise Exception(f"PDF file has invalid header at {pdf_path} (expected %PDF, got {header[:8]})")
        except Exception as e:
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except:
                    pass
            raise Exception(f"Failed to verify PDF file: {str(e)}")
        
        logger.info(f"✅ Professional PDF created: {pdf_path} ({file_size} bytes)")
        return pdf_path
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"❌ PDF creation failed: {str(e)}")
        logger.error(f"❌ PDF creation traceback:\n{error_details}")
        raise


def add_section_heading(story, text):
    """Add a section heading"""
    styles = get_professional_styles()
    story.append(Paragraph(text, styles['SectionHeading']))
    return story


def add_item_heading(story, text):
    """Add an item heading"""
    styles = get_professional_styles()
    story.append(Paragraph(text, styles['ItemHeading']))
    return story


def add_paragraph(story, text):
    """Add a normal paragraph"""
    styles = get_professional_styles()
    story.append(Paragraph(text, styles['Normal']))
    return story

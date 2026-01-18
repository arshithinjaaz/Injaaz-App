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
    styles = get_professional_styles()

    # Wrap long text values in Paragraphs so they word-wrap nicely
    table_data = []
    for row in data_list:
        new_row = []
        for col_idx, cell in enumerate(row):
            # Convert plain strings to Paragraphs for better wrapping
            if isinstance(cell, str):
                # First column is typically the label – make it bold
                if col_idx == 0:
                    new_row.append(Paragraph(f"<b>{cell}</b>", styles['Normal']))
                else:
                    new_row.append(Paragraph(cell, styles['Normal']))
            else:
                new_row.append(cell)
        table_data.append(new_row)

    if not col_widths:
        col_widths = [2*inch, 4*inch]
    
    table = Table(table_data, colWidths=col_widths)
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
    styles = get_professional_styles()

    # Build table data with Paragraphs so long text wraps instead of overflowing
    table_data = []

    # Header row – bold text
    header_cells = []
    for header in headers:
        if isinstance(header, str):
            header_cells.append(Paragraph(f"<b>{header}</b>", styles['Normal']))
        else:
            header_cells.append(header)
    table_data.append(header_cells)

    # Data rows
    for row in rows:
        new_row = []
        for cell in row:
            if isinstance(cell, str):
                new_row.append(Paragraph(cell, styles['Normal']))
            else:
                new_row.append(cell)
        table_data.append(new_row)
    
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
    
    # Auto-adjust layout - use more photos per row for smaller, compact display
    if photos_per_row is None:
        if photo_count > 15:
            photos_per_row = 4  # 4 photos per row for 15+ images
        elif photo_count > 6:
            photos_per_row = 3  # 3 photos per row for 6-15 images
        else:
            photos_per_row = 3  # Default to 3 per row for better space usage
    
    # Smaller photo sizes for compact display while maintaining visibility
    if photo_width is None or photo_height is None:
        if photos_per_row == 4:
            photo_width = 1.4*inch  # Compact size for 4 per row
            photo_height = 1.05*inch  # Maintain 4:3 aspect ratio
        elif photos_per_row == 3:
            photo_width = 1.8*inch  # Compact size for 3 per row
            photo_height = 1.35*inch  # Maintain 4:3 aspect ratio
        else:
            photo_width = 1.8*inch  # Compact size for 2 per row
            photo_height = 1.35*inch  # Maintain 4:3 aspect ratio
    
    photo_rows = []
    for i in range(0, len(photos), photos_per_row):
        row_photos = photos[i:i+photos_per_row]
        photo_row = []
        
        for photo_item in row_photos:
            try:
                img_data, is_url = get_image_for_pdf(photo_item)
                if img_data:
                    # Calculate proper dimensions while preserving aspect ratio for best visibility
                    from reportlab.lib import utils
                    import io
                    
                    try:
                        # Get image dimensions - handle both file paths and BytesIO streams
                        if isinstance(img_data, str):
                            # Local file path
                            img_reader = utils.ImageReader(img_data)
                            orig_width, orig_height = img_reader.getSize()
                            img_source = img_data
                        else:
                            # BytesIO stream - read dimensions without consuming
                            img_data.seek(0)
                            temp_reader = utils.ImageReader(img_data)
                            orig_width, orig_height = temp_reader.getSize()
                            # Reset stream for actual image creation
                            img_data.seek(0)
                            img_source = img_data
                        
                        # Calculate scale to fit within our target size while preserving aspect ratio
                        if orig_width > 0 and orig_height > 0:
                            width_scale = photo_width / orig_width
                            height_scale = photo_height / orig_height
                            scale = min(width_scale, height_scale)  # Use smaller scale to fit both dimensions
                            
                            # Calculate final dimensions
                            final_width = orig_width * scale
                            final_height = orig_height * scale
                            
                            # Create image with calculated dimensions (ReportLab Image doesn't have preserveAspectRatio param)
                            img = Image(img_source, width=final_width, height=final_height)
                        else:
                            # Fallback to fixed size if dimensions are invalid
                            logger.warning(f"Invalid image dimensions: {orig_width}x{orig_height}, using fixed size")
                            img = Image(img_source, width=photo_width, height=photo_height)
                        
                        photo_row.append(img)
                    except Exception as img_error:
                        logger.error(f"Error processing image: {img_error}")
                        import traceback
                        logger.error(traceback.format_exc())
                        # Final fallback: try simple image creation
                        try:
                            if isinstance(img_data, str):
                                img = Image(img_data, width=photo_width, height=photo_height)
                            else:
                                img_data.seek(0)
                                img = Image(img_data, width=photo_width, height=photo_height)
                            photo_row.append(img)
                        except Exception as final_error:
                            logger.error(f"Final fallback also failed: {final_error}")
                            photo_row.append(Paragraph("Error loading image", styles['Small']))
                else:
                    logger.warning(f"get_image_for_pdf returned None for photo_item: {photo_item}")
                    photo_row.append(Paragraph("Image not available", styles['Small']))
            except Exception as e:
                logger.error(f"Error loading photo: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                photo_row.append(Paragraph("Error loading image", styles['Small']))
        
        # Pad row if needed
        while len(photo_row) < photos_per_row:
            photo_row.append('')
        
        photo_rows.append(photo_row)
    
    # Add photos in batches to avoid memory issues with many images
    if photo_rows:
        col_widths = [photo_width + 0.1*inch] * photos_per_row  # Reduced padding for compact display
        photo_table = Table(photo_rows, colWidths=col_widths)
        photo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ]))
        story.append(photo_table)
        story.append(Spacer(1, 0.1*inch))  # Reduced spacing between photo grids
    
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
    
    # No page break - let signatures flow with content
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

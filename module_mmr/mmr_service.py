"""
MMR Service – Excel parsing and professional report generation.
Handles: Reactive Workorder Details sheet with columns:
  WorkOrder No, Reported Date, Priority, Work Description, Client,
  Reported By, Service Group, Assigned Date, Work Start Date, Closed By,
  Status, Contract, BaseUnit, Space
"""
import os
import logging
from io import BytesIO
from datetime import datetime

import pandas as pd
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as XLImage
from openpyxl.drawing.xdr import XDRPositiveSize2D
from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
from openpyxl.utils.units import pixels_to_EMU

logger = logging.getLogger(__name__)

EXPECTED_COLS = [
    'WorkOrder No', 'Reported Date', 'Priority', 'Work Description',
    'Client', 'Reported By', 'Service Group', 'Assigned Date',
    'Work Start Date', 'Closed By', 'Status', 'Contract', 'BaseUnit', 'Space'
]

PRIMARY   = "125435"
SECONDARY = "2E7D32"
ACCENT    = "E8F5E9"
WHITE     = "FFFFFF"
ALT_ROW   = "F9FAFB"
BORDER    = "D1D5DB"

LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'static', 'logo.png'
)

# ──────────────────────────────────────────────────────────────────────────────
# Parsing
# ──────────────────────────────────────────────────────────────────────────────

def parse_excel(file_path: str) -> pd.DataFrame:
    """Read the 'Reactive Workorder Details' sheet and normalise values."""
    try:
        df = pd.read_excel(file_path, sheet_name='Reactive Workorder Details')
    except Exception:
        # Fall back to active sheet if named sheet not found
        df = pd.read_excel(file_path)

    df.columns = [str(c).strip() for c in df.columns]

    # Drop completely empty rows
    df = df.dropna(how='all')

    # Normalise string columns
    for col in ['Client', 'Service Group', 'Status', 'Contract',
                'BaseUnit', 'Space', 'Priority', 'Reported By', 'Closed By']:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str).str.strip()

    # Normalise work order number – keep only rows with a numeric WO number
    # (trailing metadata rows like parmFromDate / parmToDate are discarded)
    if 'WorkOrder No' in df.columns:
        df = df[df['WorkOrder No'].notna()]
        df['WorkOrder No'] = df['WorkOrder No'].astype(str).str.strip()
        df = df[df['WorkOrder No'].str.match(r'^\d+$')]  # digits-only

    # Parse dates
    for col in ['Reported Date', 'Assigned Date', 'Work Start Date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    return df.reset_index(drop=True)


def df_to_rows(df: pd.DataFrame) -> list:
    """Convert DataFrame to JSON-serialisable list of dicts."""
    rows = []
    for _, row in df.iterrows():
        r = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                r[col] = ''
            elif isinstance(val, pd.Timestamp):
                r[col] = val.strftime('%Y-%m-%d')
            else:
                r[col] = str(val).strip()
        rows.append(r)
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard aggregation
# ──────────────────────────────────────────────────────────────────────────────

def compute_dashboard(df: pd.DataFrame) -> dict:
    """Return all aggregated stats needed by the front-end dashboard."""

    def count_by(col: str) -> dict:
        if col not in df.columns:
            return {}
        series = df[col].replace('', None).dropna()
        return {str(k): int(v) for k, v in series.value_counts().items()}

    def uniq(col: str) -> list:
        if col not in df.columns:
            return []
        vals = df[col].replace('', None).dropna().unique().tolist()
        return sorted([str(v) for v in vals])

    return {
        'total': len(df),
        'by_client':        count_by('Client'),
        'by_contract':      count_by('Contract'),
        'by_service_group': count_by('Service Group'),
        'by_space':         count_by('Space'),
        'by_status':        count_by('Status'),
        'by_priority':      count_by('Priority'),
        'filters': {
            'clients':        uniq('Client'),
            'contracts':      uniq('Contract'),
            'service_groups': uniq('Service Group'),
            'spaces':         uniq('Space'),
            'statuses':       uniq('Status'),
            'priorities':     uniq('Priority'),
        }
    }


# ──────────────────────────────────────────────────────────────────────────────
# Excel report generation
# ──────────────────────────────────────────────────────────────────────────────

def _normalise_space(val: str) -> str:
    """Map raw Space values (including typos) to clean labels."""
    v = val.strip().lower()
    if v in ('chargebale', 'chargeable'):
        return 'Chargeable'
    if v in ('non-chargebale', 'non-chargeable', 'non chargebale', 'non chargeable'):
        return 'Non-Chargeable'
    return val.strip() or 'Unknown'


def format_chargeable_summary_for_email(df: pd.DataFrame) -> str:
    """Build a plain-text chargeable table for email body.
    Rows: Service Groups. Cols: Chargeable (Resolved+Pending), Non-Chargeable (Resolved+Pending).
    """
    required = {'Space', 'Status', 'Service Group'}
    if not required.issubset(set(df.columns)):
        return ''
    work = df.copy()
    work['_space'] = work['Space'].apply(_normalise_space)
    work['_status'] = work['Status'].apply(_normalise_status_bucket)

    agg = (
        work.groupby('Service Group', dropna=False)
        .apply(lambda g: pd.Series({
            'chg_res': len(g[(g['_space'] == 'Chargeable') & (g['_status'] == 'Resolved')]),
            'chg_pen': len(g[(g['_space'] == 'Chargeable') & (g['_status'] == 'Pending')]),
            'nchg_res': len(g[(g['_space'] == 'Non-Chargeable') & (g['_status'] == 'Resolved')]),
            'nchg_pen': len(g[(g['_space'] == 'Non-Chargeable') & (g['_status'] == 'Pending')]),
        }), include_groups=False)
        .reset_index()
    )
    agg['Service Group'] = agg['Service Group'].fillna('').astype(str).str.strip()
    agg = agg.sort_values('Service Group')
    if len(agg) == 0:
        return ''

    sg_w = 28
    num_w = 8
    sep = ' | '
    h1 = 'Service Group'.ljust(sg_w) + sep
    h1 += 'Chg Res'.rjust(num_w) + sep + 'Chg Pend'.rjust(num_w) + sep
    h1 += 'NChg Res'.rjust(num_w) + sep + 'NChg Pend'.rjust(num_w)
    rule = '-' * (sg_w + 4 * (num_w + len(sep)))

    lines = ['Chargeable Summary by Service Group:', rule, h1, rule]
    for _, row in agg.iterrows():
        sg = (str(row['Service Group'] or '')[:sg_w]).ljust(sg_w)
        chg_res = int(row['chg_res'])
        chg_pen = int(row['chg_pen'])
        nchg_res = int(row['nchg_res'])
        nchg_pen = int(row['nchg_pen'])
        lines.append(sg + sep + str(chg_res).rjust(num_w) + sep + str(chg_pen).rjust(num_w) +
                     sep + str(nchg_res).rjust(num_w) + sep + str(nchg_pen).rjust(num_w))

    tot_chg_res = int(agg['chg_res'].sum())
    tot_chg_pen = int(agg['chg_pen'].sum())
    tot_nchg_res = int(agg['nchg_res'].sum())
    tot_nchg_pen = int(agg['nchg_pen'].sum())
    lines.append(rule)
    lines.append('Total'.ljust(sg_w) + sep +
                 str(tot_chg_res).rjust(num_w) + sep + str(tot_chg_pen).rjust(num_w) +
                 sep + str(tot_nchg_res).rjust(num_w) + sep + str(tot_nchg_pen).rjust(num_w))
    lines.append(rule)
    return '\n'.join(lines)


def _normalise_status_bucket(val: str) -> str:
    """Bucket raw Status into Resolved / Pending."""
    v = val.strip().lower()
    if v in ('resolved', 'closed', 'completed', 'done'):
        return 'Resolved'
    return 'Pending'


# Clients whose contracts must each get their own sheet instead of one
# combined client sheet.  Matching is case-insensitive / fuzzy.
_SPLIT_CLIENTS = {'aqaar community mangement', 'aqar community management',
                  'aqaar community management'}


def _is_split_client(client: str) -> bool:
    return client.strip().lower() in _SPLIT_CLIENTS


def generate_report_excel(df: pd.DataFrame) -> bytes:
    """Build a professional multi-sheet Excel report and return raw bytes.

    Sheet layout:
      1. All Work Orders
      2–N. Client sheets (one per client, all their contracts combined)
           Exception: "Aqar Community Management" → one sheet per *contract*
      Last. Chargeable / Non-Chargeable Analysis (filterable summary table)
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Sheet 1 – All Work Orders
    _write_data_sheet(wb, df, 'All Work Orders')

    # Sheet 2 – Dashboard (KPI + charts)
    _write_dashboard_sheet(wb, df)

    # Client-wise sheets
    clients = sorted(df['Client'].replace('', None).dropna().unique().tolist())
    for client in clients:
        client_df = df[df['Client'] == client]
        if _is_split_client(client):
            # Split into per-contract sheets
            contracts = sorted(
                client_df['Contract'].replace('', None).dropna().unique().tolist()
            )
            for contract in contracts:
                name = str(contract)[:31]
                _write_data_sheet(
                    wb,
                    client_df[client_df['Contract'] == contract].copy(),
                    name,
                )
        else:
            name = str(client)[:31]
            _write_data_sheet(wb, client_df.copy(), name)

    # Chargeable / Non-Chargeable Analysis (filterable summary)
    _write_chargeable_analysis(wb, df)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# Styling helpers
# ──────────────────────────────────────────────────────────────────────────────

def _thin(color=BORDER):
    return Side(style='thin', color=color)

def _border(color=BORDER):
    s = _thin(color)
    return Border(left=s, right=s, top=s, bottom=s)

def _header_fill():
    return PatternFill(start_color=PRIMARY, end_color=PRIMARY, fill_type='solid')

def _section_fill():
    return PatternFill(start_color=ACCENT, end_color=ACCENT, fill_type='solid')

def _alt_fill():
    return PatternFill(start_color=ALT_ROW, end_color=ALT_ROW, fill_type='solid')

def _write_logo_header(ws, title: str, span_cols: int) -> int:
    """Writes logo + title block; returns next free row number.
    Logo is centered in column A. Title centered per design."""
    ws.row_dimensions[1].height = 48
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 18
    ws.merge_cells('A1:A3')
    col_a = ws.column_dimensions.get('A')
    col_a_width = col_a.width if col_a and col_a.width is not None else None
    if col_a_width is None:
        ws.column_dimensions['A'].width = 12
        col_a_width = 12

    if os.path.exists(LOGO_PATH):
        try:
            img = XLImage(LOGO_PATH)
            img.width = 72
            img.height = 72
            p2e = pixels_to_EMU
            size = XDRPositiveSize2D(p2e(72), p2e(72))
            cell_w_px = col_a_width * 7.5
            cell_h_px = (48 + 18 + 18) * (96 / 72)
            col_off = p2e(max(0, (cell_w_px - 72) / 2))
            row_off = p2e(max(0, (cell_h_px - 72) / 2))
            marker = AnchorMarker(col=0, colOff=col_off, row=0, rowOff=row_off)
            img.anchor = OneCellAnchor(_from=marker, ext=size)
            ws.add_image(img)
        except Exception:
            pass

    end = get_column_letter(span_cols)
    title_cell = ws.cell(row=1, column=2, value=title)
    title_cell.font = Font(bold=True, size=16, color=PRIMARY, name='Calibri')
    title_cell.alignment = Alignment(horizontal='left', vertical='center')
    if span_cols > 2:
        ws.merge_cells(f'B1:{end}1')

    sub_cell = ws.cell(row=2, column=2, value='INJAAZ PLATFORM – Report Generation')
    sub_cell.font = Font(bold=True, size=9, color=SECONDARY, name='Calibri')
    sub_cell.alignment = Alignment(horizontal='left', vertical='center')
    if span_cols > 2:
        ws.merge_cells(f'B2:{end}2')

    date_cell = ws.cell(row=3, column=2, value=f'Generated: {datetime.now().strftime("%d %b %Y  %H:%M")}')
    date_cell.font = Font(size=8, color='888888', italic=True, name='Calibri')
    date_cell.alignment = Alignment(horizontal='left', vertical='center')
    if span_cols > 2:
        ws.merge_cells(f'B3:{end}3')

    return 5  # first data row (row 4 is a spacer)


def _style_header_row(ws, row_num: int, num_cols: int):
    ws.row_dimensions[row_num].height = 32
    for c in range(1, num_cols + 1):
        cell = ws.cell(row=row_num, column=c)
        cell.font = Font(bold=True, color=WHITE, size=10, name='Calibri')
        cell.fill = _header_fill()
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = _border(PRIMARY)


def _style_data_row(ws, row_num: int, num_cols: int, alt: bool = False):
    ws.row_dimensions[row_num].height = 22
    for c in range(1, num_cols + 1):
        cell = ws.cell(row=row_num, column=c)
        cell.font = Font(size=9, name='Calibri')
        cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=False)
        cell.fill = _alt_fill() if alt else PatternFill(fill_type=None)
        cell.border = _border()


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard sheet – cell-based visuals (renders in Protected View / email)
# ──────────────────────────────────────────────────────────────────────────────

_BAR_CHAR = '\u2588'  # █  full-block used for in-cell bar charts
_BAR_MAX_LEN = 30     # max blocks in the longest bar


def _write_bar_section(ws, current_row, title, counts: dict, bar_color=PRIMARY):
    """Write a titled horizontal-bar section using coloured █ characters.

    Layout (columns A–D):
        A: label   B: bar (█ chars)   C: count   D: % share

    Returns the next free row.
    """
    if not counts:
        return current_row

    # Section title
    ws.merge_cells(f'A{current_row}:D{current_row}')
    t = ws.cell(row=current_row, column=1, value=title)
    t.font = Font(bold=True, size=11, color=PRIMARY, name='Calibri')
    t.fill = _section_fill()
    t.alignment = Alignment(horizontal='left', vertical='center')
    t.border = _border()
    for c in range(2, 5):
        ws.cell(row=current_row, column=c).fill = _section_fill()
        ws.cell(row=current_row, column=c).border = _border()
    ws.row_dimensions[current_row].height = 26
    current_row += 1

    max_val = max(counts.values()) if counts else 1
    total_val = sum(counts.values())

    for ri, (name, cnt) in enumerate(counts.items()):
        bar_len = round(cnt / max_val * _BAR_MAX_LEN) if max_val else 0
        pct = round(cnt / total_val * 100, 1) if total_val else 0

        # Label
        lbl = ws.cell(row=current_row, column=1, value=str(name))
        lbl.font = Font(size=9, name='Calibri', color='333333')
        lbl.alignment = Alignment(horizontal='right', vertical='center')
        lbl.border = _border()
        lbl.fill = _alt_fill() if ri % 2 else PatternFill(fill_type=None)

        # Bar
        bar = ws.cell(row=current_row, column=2, value=_BAR_CHAR * bar_len)
        bar.font = Font(size=9, name='Calibri', color=bar_color)
        bar.alignment = Alignment(horizontal='left', vertical='center')
        bar.border = _border()
        bar.fill = _alt_fill() if ri % 2 else PatternFill(fill_type=None)

        # Count
        cv = ws.cell(row=current_row, column=3, value=cnt)
        cv.font = Font(bold=True, size=9, name='Calibri', color=PRIMARY)
        cv.alignment = Alignment(horizontal='center', vertical='center')
        cv.border = _border()
        cv.fill = _alt_fill() if ri % 2 else PatternFill(fill_type=None)

        # Percentage
        pv = ws.cell(row=current_row, column=4, value=f'{pct}%')
        pv.font = Font(size=9, name='Calibri', color='888888')
        pv.alignment = Alignment(horizontal='center', vertical='center')
        pv.border = _border()
        pv.fill = _alt_fill() if ri % 2 else PatternFill(fill_type=None)

        ws.row_dimensions[current_row].height = 20
        current_row += 1

    return current_row + 1  # blank spacer row


def _write_summary_table(ws, current_row, title, data: list, headers: list,
                         *, col_start=1):
    """Write a small summary table.  `data` is a list of row-tuples.

    Returns the next free row.
    """
    num_cols = len(headers)
    end_col = col_start + num_cols - 1

    # Title
    ws.merge_cells(
        start_row=current_row, start_column=col_start,
        end_row=current_row, end_column=end_col,
    )
    t = ws.cell(row=current_row, column=col_start, value=title)
    t.font = Font(bold=True, size=11, color=PRIMARY, name='Calibri')
    t.fill = _section_fill()
    t.alignment = Alignment(horizontal='left', vertical='center')
    for c in range(col_start, end_col + 1):
        ws.cell(row=current_row, column=c).fill = _section_fill()
        ws.cell(row=current_row, column=c).border = _border()
    ws.row_dimensions[current_row].height = 26
    current_row += 1

    # Headers
    for ci, h in enumerate(headers, col_start):
        cell = ws.cell(row=current_row, column=ci, value=h)
        cell.font = Font(bold=True, color=WHITE, size=9, name='Calibri')
        cell.fill = _header_fill()
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = _border(PRIMARY)
    ws.row_dimensions[current_row].height = 24
    current_row += 1

    # Data rows
    for ri, row_data in enumerate(data):
        for ci, val in enumerate(row_data, col_start):
            cell = ws.cell(row=current_row, column=ci, value=val)
            cell.font = Font(size=9, name='Calibri')
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = _border()
            cell.fill = _alt_fill() if ri % 2 else PatternFill(fill_type=None)
        # First column left-aligned (label)
        ws.cell(row=current_row, column=col_start).alignment = Alignment(
            horizontal='left', vertical='center')
        ws.row_dimensions[current_row].height = 20
        current_row += 1

    return current_row + 1


def _write_dashboard_sheet(wb: openpyxl.Workbook, df: pd.DataFrame):
    """Cell-based visual dashboard — two-panel layout, always renders.

    LEFT  (A–D): Bar sections (Client, Contract, Service Group)
    RIGHT (F–H): Chargeable + Priority summary tables
    """
    ws = wb.create_sheet('Dashboard')

    # ── Column widths ────────────────────────────────────────────────
    # Left panel: A=label, B=bar, C=count, D=%
    ws.column_dimensions['A'].width = 28
    ws.column_dimensions['B'].width = 40
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 10
    # Gutter
    ws.column_dimensions['E'].width = 3
    # Right panel: F=label, G=count, H=share
    ws.column_dimensions['F'].width = 22
    ws.column_dimensions['G'].width = 12
    ws.column_dimensions['H'].width = 12

    # ── Header ───────────────────────────────────────────────────────
    TOTAL_COLS = 8  # A–H
    current_row = _write_logo_header(ws, 'Dashboard Overview', TOTAL_COLS)

    # ── KPI CARDS (full width, 4 per row across A–H) ────────────────
    total   = len(df)
    pending = len(df[df['Status'].str.lower() == 'pending'])    if 'Status'   in df.columns else 0
    p1      = len(df[df['Priority'].str.upper() == 'P1'])       if 'Priority' in df.columns else 0
    p3      = len(df[df['Priority'].str.upper() == 'P3'])       if 'Priority' in df.columns else 0
    n_cli   = df['Client'].replace('', None).dropna().nunique() if 'Client'   in df.columns else 0
    n_ctr   = df['Contract'].replace('', None).dropna().nunique() if 'Contract' in df.columns else 0

    kpis = [
        (total,   'WORK ORDERS',  PRIMARY),
        (pending, 'PENDING',      SECONDARY),
        (p1,      'PRIORITY P1',  'E65100'),
        (p3,      'PRIORITY P3',  '43A047'),
        (n_cli,   'CLIENTS',      PRIMARY),
        (n_ctr,   'CONTRACTS',    PRIMARY),
    ]

    kpi_bg = PatternFill(start_color='F0FAF4', end_color='F0FAF4', fill_type='solid')
    kpi_bdr = Border(
        left=Side(style='thin', color='C8E6C9'),
        right=Side(style='thin', color='C8E6C9'),
        top=Side(style='thin', color='C8E6C9'),
        bottom=Side(style='thin', color='C8E6C9'),
    )

    # 2 rows × 3 KPIs each — columns A, C, F (with merge for wider cards)
    kpi_cols = [
        (1, 2),   # merge A:B
        (3, 4),   # merge C:D
        (6, 8),   # merge F:H  (skip E gutter)
    ]
    for batch in range(2):
        vr = current_row
        lr = current_row + 1
        for slot, (sc, ec) in enumerate(kpi_cols):
            idx = batch * 3 + slot
            if idx >= len(kpis):
                break
            val, label, clr = kpis[idx]
            ws.merge_cells(start_row=vr, start_column=sc, end_row=vr, end_column=ec)
            ws.merge_cells(start_row=lr, start_column=sc, end_row=lr, end_column=ec)

            v = ws.cell(row=vr, column=sc, value=val)
            v.font = Font(bold=True, size=26, color=clr, name='Calibri')
            v.alignment = Alignment(horizontal='center', vertical='bottom')

            lb = ws.cell(row=lr, column=sc, value=label)
            lb.font = Font(bold=True, size=8, color='777777', name='Calibri')
            lb.alignment = Alignment(horizontal='center', vertical='top')

            for r in (vr, lr):
                for c in range(sc, ec + 1):
                    ws.cell(row=r, column=c).fill = kpi_bg
                    ws.cell(row=r, column=c).border = kpi_bdr

        ws.row_dimensions[vr].height = 48
        ws.row_dimensions[lr].height = 18
        current_row += 2

    current_row += 1  # spacer

    # ── Remember where the two-panel area starts ─────────────────────
    panel_start = current_row

    # ── LEFT PANEL: Bar sections (columns A–D) ──────────────────────
    def _counts(col, max_items=20):
        if col not in df.columns:
            return {}
        s = df[col].replace('', None).dropna().value_counts().head(max_items)
        return {str(k): int(v) for k, v in s.items()}

    current_row = _write_bar_section(
        ws, current_row, 'WORK ORDERS BY CLIENT',
        _counts('Client'), bar_color=PRIMARY)

    current_row = _write_bar_section(
        ws, current_row, 'WORK ORDERS BY CONTRACT',
        _counts('Contract'), bar_color=SECONDARY)

    current_row = _write_bar_section(
        ws, current_row, 'BY SERVICE GROUP',
        _counts('Service Group'), bar_color='43A047')

    # ── RIGHT PANEL: Summary tables (columns F–H) ───────────────────
    right_row = panel_start
    RC = 6  # column F

    # Chargeable vs Non-Chargeable
    if 'Space' in df.columns:
        space_counts = df['Space'].apply(_normalise_space).value_counts()
        total_space = space_counts.sum()
        rows = []
        for name, cnt in space_counts.items():
            pct = round(cnt / total_space * 100, 1) if total_space else 0
            rows.append((str(name), cnt, f'{pct}%'))
        rows.append(('Total', total_space, '100%'))
        right_row = _write_summary_table(
            ws, right_row, 'CHARGEABLE vs NON-CHARGEABLE',
            rows, ['Type', 'Count', 'Share'], col_start=RC)

    # Work Orders by Priority
    if 'Priority' in df.columns:
        prio_counts = df['Priority'].replace('', None).dropna().value_counts()
        total_prio = prio_counts.sum()
        rows = []
        for name, cnt in prio_counts.items():
            pct = round(cnt / total_prio * 100, 1) if total_prio else 0
            rows.append((str(name), int(cnt), f'{pct}%'))
        rows.append(('Total', int(total_prio), '100%'))
        right_row = _write_summary_table(
            ws, right_row, 'WORK ORDERS BY PRIORITY',
            rows, ['Priority', 'Count', 'Share'], col_start=RC)

    # Status breakdown
    if 'Status' in df.columns:
        status_counts = df['Status'].replace('', None).dropna().value_counts()
        total_st = status_counts.sum()
        rows = []
        for name, cnt in status_counts.items():
            pct = round(cnt / total_st * 100, 1) if total_st else 0
            rows.append((str(name), int(cnt), f'{pct}%'))
        rows.append(('Total', int(total_st), '100%'))
        right_row = _write_summary_table(
            ws, right_row, 'WORK ORDERS BY STATUS',
            rows, ['Status', 'Count', 'Share'], col_start=RC)

    # ── Print settings ───────────────────────────────────────────────
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1


# ──────────────────────────────────────────────────────────────────────────────
# Sheet writers
# ──────────────────────────────────────────────────────────────────────────────

def _write_data_sheet(wb: openpyxl.Workbook, df: pd.DataFrame, title: str):
    ws = wb.create_sheet(title)

    cols = [c for c in EXPECTED_COLS if c in df.columns]
    n = len(cols)
    if n == 0:
        ws.cell(row=1, column=1, value='No data')
        return

    current_row = _write_logo_header(ws, title, n)

    # Header
    for ci, col in enumerate(cols, 1):
        ws.cell(row=current_row, column=ci, value=col)
    _style_header_row(ws, current_row, n)
    ws.freeze_panes = ws.cell(row=current_row + 1, column=1)
    current_row += 1

    # Data
    for ri, (_, row) in enumerate(df.iterrows()):
        for ci, col in enumerate(cols, 1):
            val = row.get(col, '')
            if pd.isna(val):
                val = ''
            elif isinstance(val, pd.Timestamp):
                val = val.strftime('%Y-%m-%d')
            ws.cell(row=current_row, column=ci, value=str(val).strip())
        _style_data_row(ws, current_row, n, alt=(ri % 2 == 1))
        current_row += 1

    # Auto-width (keep col A at least 12 for centered logo)
    for ci, col in enumerate(cols, 1):
        max_len = max(len(col), 8)
        for row in ws.iter_rows(min_row=6, max_row=min(ws.max_row, 200),
                                 min_col=ci, max_col=ci):
            for cell in row:
                if cell.value:
                    max_len = max(max_len, min(len(str(cell.value)), 60))
        w = min(max_len + 4, 60)
        if ci == 1:
            w = max(w, 12)
        ws.column_dimensions[get_column_letter(ci)].width = w

    # Print settings
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.oddFooter.right.text = "Page &P of &N"


def _write_chargeable_analysis(wb: openpyxl.Workbook, df: pd.DataFrame):
    """Chargeable / Non-Chargeable summary with Client dropdown (AutoFilter).

    One flat table with columns:
        Client | Contract | Service Group |
        Chargeable Resolved | Chargeable Pending |
        Non-Chargeable Resolved | Non-Chargeable Pending | Total

    Excel AutoFilter on every column gives the user a click-to-filter
    dropdown on the Client (and every other) column.
    """
    from openpyxl.worksheet.datavalidation import DataValidation

    ws = wb.create_sheet('Chargeable Analysis')

    required = {'Space', 'Status', 'Contract', 'Service Group', 'Client'}
    if not required.issubset(set(df.columns)):
        ws.cell(row=1, column=1, value='Insufficient columns for chargeable analysis')
        return

    work = df.copy()
    work['_space']  = work['Space'].apply(_normalise_space)
    work['_status'] = work['Status'].apply(_normalise_status_bucket)

    DATA_COLS = [
        ('Chargeable',     'Resolved'),
        ('Chargeable',     'Pending'),
        ('Non-Chargeable', 'Resolved'),
        ('Non-Chargeable', 'Pending'),
    ]

    HEADERS = [
        'Client', 'Contract', 'Service Group',
        'Chargeable\nResolved', 'Chargeable\nPending',
        'Non-Chargeable\nResolved', 'Non-Chargeable\nPending',
        'Total',
    ]
    NUM_COLS = len(HEADERS)
    col_widths = [28, 28, 26, 16, 16, 18, 18, 10]
    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    # Accent fills
    chg_fill  = PatternFill(start_color='E8F5E9', end_color='E8F5E9', fill_type='solid')
    nchg_fill = PatternFill(start_color='FFF3E0', end_color='FFF3E0', fill_type='solid')
    total_fill = PatternFill(start_color='E3F2FD', end_color='E3F2FD', fill_type='solid')

    current_row = _write_logo_header(ws, 'Chargeable / Non-Chargeable Analysis', NUM_COLS)

    # ── Category sub-header row ──────────────────────────────────────
    for c in range(1, NUM_COLS + 1):
        ws.cell(row=current_row, column=c).border = _border()

    # Merge cells A-C (blank area above Client/Contract/ServiceGroup)
    ws.merge_cells(f'A{current_row}:C{current_row}')

    # Chargeable group header (D-E)
    ws.merge_cells(f'D{current_row}:E{current_row}')
    ch = ws.cell(row=current_row, column=4, value='Chargeable')
    ch.font = Font(bold=True, size=10, color=SECONDARY, name='Calibri')
    ch.fill = chg_fill
    ch.alignment = Alignment(horizontal='center', vertical='center')
    ch.border = _border()
    ws.cell(row=current_row, column=5).fill = chg_fill
    ws.cell(row=current_row, column=5).border = _border()

    # Non-Chargeable group header (F-G)
    ws.merge_cells(f'F{current_row}:G{current_row}')
    nc = ws.cell(row=current_row, column=6, value='Non-Chargeable')
    nc.font = Font(bold=True, size=10, color='E65100', name='Calibri')
    nc.fill = nchg_fill
    nc.alignment = Alignment(horizontal='center', vertical='center')
    nc.border = _border()
    ws.cell(row=current_row, column=7).fill = nchg_fill
    ws.cell(row=current_row, column=7).border = _border()

    ws.cell(row=current_row, column=8).fill = total_fill
    ws.cell(row=current_row, column=8).border = _border()
    ws.row_dimensions[current_row].height = 22
    current_row += 1

    # ── Column header row ────────────────────────────────────────────
    short_headers = [
        'Client', 'Contract', 'Service Group',
        'Resolved', 'Pending', 'Resolved', 'Pending', 'Total',
    ]
    header_row = current_row
    for ci, h in enumerate(short_headers, 1):
        cell = ws.cell(row=current_row, column=ci, value=h)
        cell.font = Font(bold=True, color=WHITE, size=9, name='Calibri')
        cell.fill = _header_fill()
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = _border(PRIMARY)
    ws.row_dimensions[current_row].height = 28
    current_row += 1

    # ── Build aggregation: Client × Contract × Service Group ─────────
    group_keys = ['Client', 'Contract', 'Service Group']
    combos = (
        work.groupby(group_keys)
            .apply(lambda g: pd.Series({
                'chg_res':  len(g[(g['_space'] == 'Chargeable')     & (g['_status'] == 'Resolved')]),
                'chg_pen':  len(g[(g['_space'] == 'Chargeable')     & (g['_status'] == 'Pending')]),
                'nchg_res': len(g[(g['_space'] == 'Non-Chargeable') & (g['_status'] == 'Resolved')]),
                'nchg_pen': len(g[(g['_space'] == 'Non-Chargeable') & (g['_status'] == 'Pending')]),
            }), include_groups=False)
            .reset_index()
            .sort_values(group_keys)
    )

    # Write data rows
    prev_client = None
    for ri, (_, row) in enumerate(combos.iterrows()):
        client  = str(row['Client']).strip()
        contract = str(row['Contract']).strip()
        sg      = str(row['Service Group']).strip()
        counts  = [int(row['chg_res']), int(row['chg_pen']),
                   int(row['nchg_res']), int(row['nchg_pen'])]
        total   = sum(counts)

        ws.cell(row=current_row, column=1, value=client)
        ws.cell(row=current_row, column=2, value=contract)
        ws.cell(row=current_row, column=3, value=sg)
        for ci, val in enumerate(counts, 4):
            ws.cell(row=current_row, column=ci, value=val)
        ws.cell(row=current_row, column=NUM_COLS, value=total)

        _style_data_row(ws, current_row, NUM_COLS, alt=(ri % 2 == 1))

        # Visual separator: bold + light fill when client changes
        if client != prev_client:
            c1 = ws.cell(row=current_row, column=1)
            c1.font = Font(bold=True, size=9, color=PRIMARY, name='Calibri')
            c1.fill = _section_fill()
            prev_client = client

        current_row += 1

    last_data_row = current_row - 1
    first_data_row = header_row + 1

    # ── Grand Total row (SUBTOTAL so it updates when user filters) ────
    grand_total_row = current_row
    ws.cell(row=grand_total_row, column=1, value='GRAND TOTAL')
    ws.merge_cells(f'A{grand_total_row}:C{grand_total_row}')
    # Use SUBTOTAL(109, ...) so filtering shows sum of visible rows only
    for ci in range(4, NUM_COLS + 1):
        col_letter = get_column_letter(ci)
        ws.cell(row=grand_total_row, column=ci, value=f'=SUBTOTAL(109,{col_letter}{first_data_row}:{col_letter}{last_data_row})')

    for c in range(1, NUM_COLS + 1):
        cell = ws.cell(row=grand_total_row, column=c)
        cell.font = Font(bold=True, size=10, color=WHITE, name='Calibri')
        cell.fill = PatternFill(start_color=SECONDARY, end_color=SECONDARY, fill_type='solid')
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = _border(SECONDARY)
    ws.cell(row=grand_total_row, column=1).alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[grand_total_row].height = 28

    # ── AutoFilter (dropdown arrows on every column) ─────────────────
    end_col = get_column_letter(NUM_COLS)
    ws.auto_filter.ref = f'A{header_row}:{end_col}{last_data_row}'

    # Freeze panes just below the header row so it stays visible
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    # ── Column widths ────────────────────────────────────────────────
    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    # Print settings
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.oddFooter.right.text = "Page &P of &N"

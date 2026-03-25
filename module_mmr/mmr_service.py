"""
MMR Service – Excel parsing and professional report generation.
Handles: Reactive Workorder Details sheet with columns:
  WorkOrder No, Reported Date, Priority, Work Description, Client,
  Reported By, Service Group, Assigned Date, Work Start Date, Closed By,
  Status, Contract, BaseUnit, Space
"""
import os
import logging
import zipfile
from io import BytesIO
from datetime import datetime

import re
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
# Report date extraction (from parmToDate or Reported Date)
# ──────────────────────────────────────────────────────────────────────────────

def get_report_date_from_excel(file_path: str):
    """Extract report date from CAFM Excel. Tries parmToDate first, else max(Reported Date).
    Returns datetime or None."""
    try:
        df_raw = pd.read_excel(file_path, sheet_name='Reactive Workorder Details', header=None)
        # parmToDate is in col 0, value in next row
        for i in range(len(df_raw) - 1):
            val = df_raw.iloc[i, 0]
            if pd.notna(val) and str(val).strip().lower() == 'parmtodate':
                next_val = df_raw.iloc[i + 1, 0]
                if pd.notna(next_val):
                    dt = pd.to_datetime(next_val, errors='coerce')
                    if pd.notna(dt):
                        return dt.to_pydatetime()
                break
        # Fallback: max Reported Date from parsed data
        df = pd.read_excel(file_path, sheet_name='Reactive Workorder Details')
        if 'Reported Date' in df.columns:
            df['Reported Date'] = pd.to_datetime(df['Reported Date'], errors='coerce')
            max_d = df['Reported Date'].max()
            if pd.notna(max_d):
                return max_d.to_pydatetime()
    except Exception:
        pass
    return None


def get_report_date_from_df(df: pd.DataFrame):
    """Get report date from DataFrame (max of Reported Date). Returns datetime or None."""
    r = get_report_date_range_from_df(df)
    return r[1] if r else None  # max date


def get_report_date_range_from_df(df: pd.DataFrame, exclude_today: bool = True) -> tuple | None:
    """Get (min, max, n_unique) Reported Date from DataFrame. Excludes today (save date) by default.
    Returns (min_dt, max_dt, count_of_unique_dates) or None."""
    if df is None or df.empty or 'Reported Date' not in df.columns:
        return None
    try:
        from datetime import date
        work = df.copy()
        work['Reported Date'] = pd.to_datetime(work['Reported Date'], errors='coerce')
        work = work.dropna(subset=['Reported Date'])
        if work.empty:
            return None
        if exclude_today:
            today = date.today()
            work = work[work['Reported Date'].dt.date < today]
            if work.empty:
                return None
        min_d = work['Reported Date'].min()
        max_d = work['Reported Date'].max()
        n_unique = work['Reported Date'].dt.date.nunique()
        if pd.notna(min_d) and pd.notna(max_d):
            return (min_d.to_pydatetime(), max_d.to_pydatetime(), int(n_unique))
    except Exception:
        pass
    return None


def split_df_by_month(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Split a DataFrame into (month_label, sub_df) chunks by Reported Date year-month.

    Returns a list sorted chronologically, e.g.:
      [('January 2026', <df>), ('February 2026', <df>), ...]
    Rows with no parseable Reported Date are grouped under 'Unknown'.
    """
    if df is None or df.empty:
        return []

    work = df.copy()
    work['Reported Date'] = pd.to_datetime(work['Reported Date'], errors='coerce')

    known = work.dropna(subset=['Reported Date']).copy()
    unknown = work[work['Reported Date'].isna()].copy()

    chunks: list[tuple[str, pd.DataFrame]] = []
    if not known.empty:
        known['_ym'] = known['Reported Date'].dt.to_period('M')
        for period, grp in known.groupby('_ym', sort=True):
            label = period.strftime('%B %Y')
            grp = grp.drop(columns=['_ym'])
            chunks.append((label, grp.reset_index(drop=True)))
    if not unknown.empty:
        chunks.append(('Unknown', unknown.reset_index(drop=True)))
    return chunks


def generate_monthly_zip(df: pd.DataFrame) -> tuple[bytes, list[str]]:
    """Generate one Excel report per calendar month and return a ZIP archive.

    Returns:
        (zip_bytes, list_of_filenames_inside_zip)
    """
    months = split_df_by_month(df)
    if not months:
        raise ValueError('No data to generate monthly reports from.')

    buf = BytesIO()
    filenames: list[str] = []

    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for label, month_df in months:
            excel_bytes = generate_report_excel(month_df)
            fname = f'Daily Report – {label}.xlsx'
            zf.writestr(fname, excel_bytes)
            filenames.append(fname)

    buf.seek(0)
    return buf.getvalue(), filenames


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

    return _normalise_parsed_df(df)


def parse_saved_report_excel(file_path: str) -> pd.DataFrame:
    """Parse a saved report Excel (from report folder). Reads 'All Work Orders' sheet.
    Header is at row 5 (1-based), data starts at row 6. Pandas header=4 = 0-based row 4 = 5th row."""
    try:
        df = pd.read_excel(file_path, sheet_name='All Work Orders', header=4)
    except Exception:
        return pd.DataFrame()
    return _normalise_parsed_df(df)


def _normalise_parsed_df(df: pd.DataFrame) -> pd.DataFrame:
    """Common normalisation for parsed Excel data."""
    df.columns = [str(c).strip() for c in df.columns]

    # Drop completely empty rows (copy avoids SettingWithCopyWarning on chained assignment)
    df = df.dropna(how='all').copy()

    # Normalise string columns
    for col in ['Client', 'Service Group', 'Status', 'Contract',
                'BaseUnit', 'Space', 'Priority', 'Reported By', 'Closed By']:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str).str.strip()

    # Normalise work order number – keep rows with valid WO formats:
    # - Pure numeric: 10017690
    # - Manual prefix: Manual - 10017703
    # (trailing metadata rows like parmFromDate / parmToDate are discarded)
    if 'WorkOrder No' in df.columns:
        df = df[df['WorkOrder No'].notna()]
        df['WorkOrder No'] = df['WorkOrder No'].astype(str).str.strip()
        # Match digits-only OR "Manual - " + digits
        wo_valid = df['WorkOrder No'].str.match(r'^(?:\d+|Manual\s*-\s*\d+)$', case=False, na=False)
        df = df[wo_valid]

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


def rows_to_df(rows: list) -> pd.DataFrame:
    """Convert list of dicts (from frontend) back to DataFrame. Handles date strings."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    date_cols = ['Reported Date', 'Assigned Date', 'Work Start Date']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


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

    # Chargeable/Non-Chargeable: use resolved logic (Space + BaseUnit when Space empty)
    if 'Space' in df.columns and 'BaseUnit' in df.columns:
        resolved = _get_resolved_chargeable_series(df)
        by_space = {str(k): int(v) for k, v in resolved.value_counts().items()}
        spaces_filter = sorted(resolved.unique().astype(str).tolist())
    else:
        by_space = {str(k): int(v) for k, v in
                    (df['Space'].apply(_normalise_space).value_counts().items())} if 'Space' in df.columns else {}
        spaces_filter = uniq('Space')

    return {
        'total': len(df),
        'by_client':        count_by('Client'),
        'by_contract':      count_by('Contract'),
        'by_service_group': count_by('Service Group'),
        'by_space':         by_space,
        'by_status':        count_by('Status'),
        'by_priority':      count_by('Priority'),
        'filters': {
            'clients':        uniq('Client'),
            'contracts':      uniq('Contract'),
            'service_groups': uniq('Service Group'),
            'spaces':         spaces_filter,
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


# Projects where AC/HVAC complaints are always Non-Chargeable (Garden City only)
_AC_NON_CHARGEABLE_PROJECTS = ('garden',)

# Clients/contracts where all base units are Chargeable (office / internal sites).
_ALL_BASEUNITS_CHARGEABLE_CLIENTS = ('askaan', 'ajman holding', 'injaaz')

# BaseUnit keywords that indicate Non-Chargeable (common areas, not apartment numbers).
# Applied uniformly for ALL projects (Askaan, Saqr, Orient, Garden, others).
_NON_CHARGEABLE_BASEUNIT_KEYWORDS = (
    'common area', 'commonarea', 'floor', 'general area', 'corridor', 'corridord',
    'roof top', 'rooftop', 'ground floor', 'groundfloor',
    'parking', 'telephone room', 'cctv room', 'electricity room', 'electrical room',
    'generator room', 'pump room', 'storage', 'lobby', 'basement', 'roof',
)

# CAFM often uses "Elevator system" or the typo "Elevater system". Use elevat(or|er)
# so we do not match unrelated words like "elevation".
_ELEVATOR_SERVICE_GROUP_RE = re.compile(r'elevat(or|er)', re.IGNORECASE)


def _resolve_chargeable(space_val: str, base_unit_val: str, client_val: str,
                       service_group_val: str = '', contract_val: str = '') -> str:
    """
    Resolve Chargeable vs Non-Chargeable.
    - Facade Cleaning service group: always Non-Chargeable.
    - Elevator system (service group: elevator / common CAFM typo elevater): always Non-Chargeable.
    - Garden City only: all AC/HVAC complaints = Non-Chargeable.
    - Askaan, Ajman Holding, Injaaz: all base units = Chargeable.
    - Else: BaseUnit apartment = Chargeable; common area = Non-Chargeable; fallback to Space.
    """
    client = (client_val or '').strip().lower()
    contract = (contract_val or '').strip().lower()
    combined = f'{client} {contract}'
    sg = (service_group_val or '').strip().lower()

    # Facade Cleaning is always Non-Chargeable regardless of client or base unit
    if 'facade cleaning' in sg:
        return 'Non-Chargeable'

    # Elevator system: always Non-Chargeable (before client-wide Chargeable rules).
    # Match "Elevator" and CAFM typo "Elevater"; not "elevation" (civil works).
    if _ELEVATOR_SERVICE_GROUP_RE.search(sg):
        return 'Non-Chargeable'

    # Garden City only: AC/HVAC complaints are always Non-Chargeable
    if any(p in combined for p in _AC_NON_CHARGEABLE_PROJECTS):
        if 'hvac' in sg or 'ac' in sg or 'air conditioning' in sg or 'airconditioning' in sg:
            return 'Non-Chargeable'

    # Askaan, Ajman Holding, Injaaz office: all base units are Chargeable
    if any(p in combined for p in _ALL_BASEUNITS_CHARGEABLE_CLIENTS):
        return 'Chargeable'

    base_unit = (base_unit_val or '').strip().lower()
    space = (space_val or '').strip().lower()

    # BaseUnit has content: derive from it (takes precedence over Space)
    if base_unit:
        for kw in _NON_CHARGEABLE_BASEUNIT_KEYWORDS:
            if kw in base_unit:
                return 'Non-Chargeable'
        # Apartment number or flat/unit/apt/villa = Chargeable
        if re.search(r'\d+', base_unit) or any(
            x in base_unit for x in ('flat', 'unit', 'apt', 'apartment', 'villa')
        ):
            return 'Chargeable'
        # Anything else (not apartment) = Non-Chargeable
        return 'Non-Chargeable'

    # BaseUnit empty: use Space
    if space and space not in ('unknown',):
        n = _normalise_space(space_val)
        if n in ('Chargeable', 'Non-Chargeable'):
            return n
    return 'Non-Chargeable'


def _get_resolved_chargeable_series(df: pd.DataFrame) -> pd.Series:
    """Return a Series of Chargeable/Non-Chargeable per row for chargeable analysis."""
    space_col = df['Space'] if 'Space' in df.columns else pd.Series([''] * len(df))
    base_col = df['BaseUnit'] if 'BaseUnit' in df.columns else pd.Series([''] * len(df))
    client_col = df['Client'] if 'Client' in df.columns else pd.Series([''] * len(df))
    contract_col = df['Contract'] if 'Contract' in df.columns else pd.Series([''] * len(df))
    sg_col = df['Service Group'] if 'Service Group' in df.columns else pd.Series([''] * len(df))
    return pd.Series([
        _resolve_chargeable(
            space_col.iat[i] if i < len(space_col) else '',
            base_col.iat[i] if i < len(base_col) else '',
            client_col.iat[i] if i < len(client_col) else '',
            sg_col.iat[i] if i < len(sg_col) else '',
            contract_col.iat[i] if i < len(contract_col) else '',
        )
        for i in range(len(df))
    ], index=df.index)


def format_chargeable_summary_for_email(df: pd.DataFrame) -> str:
    """Build a plain-text chargeable table for email body.
    Rows: Service Groups. Cols: Chargeable (Resolved+Pending), Non-Chargeable (Resolved+Pending).
    """
    required = {'Space', 'Status', 'Service Group'}
    if not required.issubset(set(df.columns)):
        return ''
    work = df.copy()
    work['_space'] = _get_resolved_chargeable_series(df)
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


# Tower display names and matching patterns (Client or Contract)
# Askaan + Saqr treated as one project; Orient/Garden get - TFM suffix
_TOWER_CONFIG = [
    ('Askaan + Saqr Projects', ['askaan', 'saqr']),
    ('Orient Tower - TFM', ['orient']),
    ('Garden City - TFM', ['garden']),
    ('C1 Tower', ['c1 tower', 'c1']),
]
def _tower_for_row(client: str, contract: str) -> str | None:
    """Return tower display name if row belongs to a known tower, else None."""
    c = (client or '').strip().lower()
    t = (contract or '').strip().lower()
    combined = f'{c} {t}'
    for display_name, patterns in _TOWER_CONFIG:
        if any(p in combined for p in patterns):
            return display_name
    return None


def format_per_tower_chargeable_html_for_email(df: pd.DataFrame) -> str:
    """Build HTML tables for email body: one table per tower (Askaan+Saqr, Orient, Garden, C1).
    Each table: Service Name | Chargeable Resolved | Chargeable Pending | Total row | Grand total.
    Uses resolved chargeable logic (Garden City AC = Non-Chargeable). Inline CSS for email compatibility.
    """
    required = {'Space', 'Status', 'Service Group', 'Client', 'Contract'}
    if not required.issubset(set(df.columns)):
        return ''
    work = df.copy()
    work['_space'] = _get_resolved_chargeable_series(df)
    work['_status'] = work['Status'].apply(_normalise_status_bucket)
    work['_tower'] = work.apply(lambda r: _tower_for_row(r.get('Client'), r.get('Contract')), axis=1)
    work = work[work['_space'] == 'Chargeable']
    work = work[work['_tower'].notna()]

    if len(work) == 0:
        return ''

    tables_html = []
    for display_name, _ in _TOWER_CONFIG:
        tower_df = work[work['_tower'] == display_name]
        if len(tower_df) == 0:
            continue
        agg = (
            tower_df.groupby('Service Group', dropna=False)
            .apply(lambda g: pd.Series({
                'resolved': len(g[g['_status'] == 'Resolved']),
                'pending': len(g[g['_status'] == 'Pending']),
            }), include_groups=False)
            .reset_index()
        )
        agg['Service Group'] = agg['Service Group'].fillna('').astype(str).str.strip()
        agg = agg.sort_values('Service Group')
        resolved_total = int(agg['resolved'].sum())
        pending_total = int(agg['pending'].sum())
        grand_total = resolved_total + pending_total

        rows_html = []
        _pad = '2px 4px'
        _cell = f'padding:{_pad};border:1px solid #0d3d24;font-size:10px;text-align:center'
        _hdr = f'background:#{ACCENT};font-weight:bold'
        for _, r in agg.iterrows():
            sg = (r['Service Group'] or '').strip()
            if not sg:
                continue
            res = int(r['resolved'])
            pen = int(r['pending'])
            bg = '#ffffff' if len(rows_html) % 2 == 0 else '#f8faf8'
            rows_html.append(
                f'<tr style="background:{bg}">'
                f'<td style="{_cell}">{sg}</td>'
                f'<td style="{_cell}">{res or ""}</td>'
                f'<td style="{_cell}">{pen or ""}</td>'
                f'</tr>'
            )

        header_bg = f'#{PRIMARY}'
        _sub = f'{_cell};border:1px solid #0d3d24;{_hdr}'
        table = (
            f'<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:10px;width:100%;max-width:420px;margin:0 0 8px 0">'
            f'<tr><td colspan="3" style="padding:4px 6px;background:{header_bg};color:#fff;font-weight:bold;text-align:center;border:1px solid #0d3d24;font-size:11px">{display_name}</td></tr>'
            f'<tr>'
            f'<td style="{_sub}">Service Name</td>'
            f'<td colspan="2" style="{_sub}">Chargeable</td>'
            f'</tr>'
            f'<tr>'
            f'<td style="{_sub}"></td>'
            f'<td style="{_sub}">Resolved</td>'
            f'<td style="{_sub}">Pending</td>'
            f'</tr>'
            + ''.join(rows_html)
            + f'<tr style="background:{header_bg};color:#fff;font-weight:bold">'
            f'<td style="{_cell}">Total</td>'
            f'<td style="{_cell}">{resolved_total}</td>'
            f'<td style="{_cell}">{pending_total}</td>'
            f'</tr>'
            f'<tr><td style="{_cell};border:1px solid #0d3d24"></td><td colspan="2" style="{_cell};{_hdr};border:1px solid #0d3d24">{grand_total}</td></tr>'
            f'</table>'
        )
        tables_html.append(table)

    if not tables_html:
        return ''
    # Stack tables vertically with line break between each
    return '<br><br>'.join(tables_html)


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

    # Populate Space with resolved Chargeable/Non-Chargeable (from BaseUnit when empty)
    work = df.copy()
    if 'Space' in work.columns and 'BaseUnit' in work.columns:
        work['Space'] = _get_resolved_chargeable_series(work)

    # Sheet 1 – All Work Orders
    _write_data_sheet(wb, work, 'All Work Orders')

    # Sheet 2 – Dashboard (KPI + charts)
    _write_dashboard_sheet(wb, work)

    # Client-wise sheets
    clients = sorted(work['Client'].replace('', None).dropna().unique().tolist())
    for client in clients:
        client_df = work[work['Client'] == client]
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
    _write_chargeable_analysis(wb, work)

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
    Logo is centered in column A with a little padding."""
    _LOGO_PADDING_PX = 6
    ws.row_dimensions[1].height = 48
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 18
    ws.merge_cells('A1:A3')
    col_a = ws.column_dimensions.get('A')
    col_a_width = col_a.width if col_a and col_a.width is not None else None
    if col_a_width is None:
        ws.column_dimensions['A'].width = 14
        col_a_width = 14

    if os.path.exists(LOGO_PATH):
        try:
            img = XLImage(LOGO_PATH)
            img.width = 72
            img.height = 72
            p2e = pixels_to_EMU
            size = XDRPositiveSize2D(p2e(72), p2e(72))
            cell_w_px = col_a_width * 7.5
            cell_h_px = (48 + 18 + 18) * (96 / 72)
            col_off_px = _LOGO_PADDING_PX + max(0, (cell_w_px - 2 * _LOGO_PADDING_PX - 72) / 2)
            row_off_px = _LOGO_PADDING_PX + max(0, (cell_h_px - 2 * _LOGO_PADDING_PX - 72) / 2)
            marker = AnchorMarker(col=0, colOff=p2e(col_off_px), row=0, rowOff=p2e(row_off_px))
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

    # Chargeable vs Non-Chargeable (resolved from Space + BaseUnit when Space empty)
    if 'Space' in df.columns:
        if 'BaseUnit' in df.columns:
            space_counts = _get_resolved_chargeable_series(df).value_counts()
        else:
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

    # Auto-width (keep col A at least 14 for centered logo with padding)
    for ci, col in enumerate(cols, 1):
        max_len = max(len(col), 8)
        for row in ws.iter_rows(min_row=6, max_row=min(ws.max_row, 200),
                                 min_col=ci, max_col=ci):
            for cell in row:
                if cell.value:
                    max_len = max(max_len, min(len(str(cell.value)), 60))
        w = min(max_len + 4, 60)
        if ci == 1:
            w = max(w, 14)
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
    work['_space']  = _get_resolved_chargeable_series(df)
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

    # Blank row between data and totals so Excel AutoFilter does NOT include totals
    # (Excel extends filter to contiguous rows; blank row breaks contiguity)
    blank_row = current_row
    current_row += 1
    ws.row_dimensions[blank_row].height = 6

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

    # ── Chargeable Total & Non-Chargeable Total rows (below grand total) ───
    gt = grand_total_row
    d_l, e_l, f_l, g_l = get_column_letter(4), get_column_letter(5), get_column_letter(6), get_column_letter(7)
    chg_total_row = gt + 1
    ws.cell(row=chg_total_row, column=1, value='Chargeable Total')
    ws.merge_cells(f'A{chg_total_row}:C{chg_total_row}')
    ws.merge_cells(f'D{chg_total_row}:E{chg_total_row}')
    ws.cell(row=chg_total_row, column=4, value=f'={d_l}{gt}+{e_l}{gt}')
    ws.merge_cells(f'F{chg_total_row}:G{chg_total_row}')
    ws.cell(row=chg_total_row, column=6, value='')
    ws.cell(row=chg_total_row, column=8, value=f'={d_l}{gt}+{e_l}{gt}')
    for c in range(1, NUM_COLS + 1):
        cell = ws.cell(row=chg_total_row, column=c)
        cell.font = Font(bold=True, size=9, name='Calibri')
        cell.fill = chg_fill
        cell.alignment = Alignment(horizontal='center' if c > 3 else 'left', vertical='center')
        cell.border = _border()
    ws.cell(row=chg_total_row, column=1).alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[chg_total_row].height = 22

    nchg_total_row = gt + 2
    ws.cell(row=nchg_total_row, column=1, value='Non-Chargeable Total')
    ws.merge_cells(f'A{nchg_total_row}:C{nchg_total_row}')
    ws.merge_cells(f'D{nchg_total_row}:E{nchg_total_row}')
    ws.cell(row=nchg_total_row, column=4, value='')
    ws.merge_cells(f'F{nchg_total_row}:G{nchg_total_row}')
    ws.cell(row=nchg_total_row, column=6, value=f'={f_l}{gt}+{g_l}{gt}')
    ws.cell(row=nchg_total_row, column=8, value=f'={f_l}{gt}+{g_l}{gt}')
    for c in range(1, NUM_COLS + 1):
        cell = ws.cell(row=nchg_total_row, column=c)
        cell.font = Font(bold=True, size=9, name='Calibri')
        cell.fill = nchg_fill
        cell.alignment = Alignment(horizontal='center' if c > 3 else 'left', vertical='center')
        cell.border = _border()
    ws.cell(row=nchg_total_row, column=1).alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[nchg_total_row].height = 22

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

"""
PDF Engine — ReportLab
Accepts flat lineItems, accessories, notes, and optional logo URL from Bubble.
"""

import io
import urllib.request
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, Image
)

BLUE   = colors.HexColor('#1a5fa8')
LGRAY  = colors.HexColor('#f0f0f0')
MGRAY  = colors.HexColor('#cccccc')
DGRAY  = colors.HexColor('#666666')
BLACK  = colors.HexColor('#111111')
WHITE  = colors.white
ALT    = colors.HexColor('#fafafa')

PAGE_W, PAGE_H = letter
MARGIN    = 0.5 * inch
CONTENT_W = PAGE_W - 2 * MARGIN   # 540 pt

COL_W      = [83, 83, 88, 100, 100, 24, 62]
COL_LABELS = ['Window Name', 'Fabric Cut Info', 'Tube & Bottom Bar',
              'Headrail', 'Control Info', 'Qty', 'Hardware']


def S(size=7, bold=False, color=BLACK, align=TA_LEFT):
    return ParagraphStyle('_',
        fontName    = 'Helvetica-Bold' if bold else 'Helvetica',
        fontSize    = size,
        leading     = size * 1.38,
        textColor   = color,
        alignment   = align,
        spaceAfter  = 0,
        spaceBefore = 0,
    )


def P(txt, style=None):
    if style is None:
        style = S()
    return Paragraph(str(txt or '').replace('\n', '<br/>'), style)


def tbl_style():
    return TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  LGRAY),
        ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
        ('BOX',           (0,0), (-1,-1), 0.5, MGRAY),
        ('INNERGRID',     (0,0), (-1,-1), 0.4, MGRAY),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 4),
        ('RIGHTPADDING',  (0,0), (-1,-1), 4),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, ALT]),
    ])


def fetch_logo(logo_url, max_width=140, max_height=50):
    """
    Downloads logo from URL and returns a ReportLab Image flowable.
    Scales it to fit within max_width x max_height while keeping aspect ratio.
    Returns None if download fails so PDF still generates without logo.
    """
    try:
        req = urllib.request.Request(
            logo_url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            img_data = response.read()

        img_buffer = io.BytesIO(img_data)
        img = Image(img_buffer)

        # Scale to fit within max dimensions, keep aspect ratio
        orig_w = img.imageWidth
        orig_h = img.imageHeight
        ratio  = min(max_width / orig_w, max_height / orig_h)
        img.drawWidth  = orig_w * ratio
        img.drawHeight = orig_h * ratio
        return img

    except Exception as e:
        print(f"Logo fetch failed ({logo_url}): {e} — falling back to text logo")
        return None


def build_logo_block(logo_url=None):
    """
    Returns a logo Table flowable.
    If logo_url is provided and downloads successfully → renders the image.
    Otherwise → falls back to the styled text logo.
    """
    logo_img = None
    if logo_url:
        logo_img = fetch_logo(logo_url)

    if logo_img:
        # Image logo — just the image, no border box needed
        logo_tbl = Table(
            [[logo_img]],
            colWidths=[CONTENT_W]
        )
        logo_tbl.setStyle(TableStyle([
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        return logo_tbl

    else:
        # Text fallback logo with blue border
        logo_tbl = Table([
            [P('<font color="#1a5fa8"><b>Rightlook Blinds</b></font>',
               ParagraphStyle('_', fontName='Helvetica-Bold', fontSize=13,
                              textColor=BLUE, leading=16)), ''],
            [P('BLINDS SHADES &amp; SHUTTERS',
               ParagraphStyle('_', fontName='Helvetica', fontSize=6.5,
                              textColor=colors.HexColor('#999999'), leading=9)), ''],
        ], colWidths=[130, CONTENT_W - 130])
        logo_tbl.setStyle(TableStyle([
            ('BOX',           (0,0), (0,-1), 1, BLUE),
            ('SPAN',          (1,0), (1,1)),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 8),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ]))
        return logo_tbl


def group_line_items(line_items):
    if not line_items:
        return []
    first = line_items[0]
    if 'groupName' in first and 'rows' in first:
        return line_items
    seen   = {}
    groups = []
    for row in line_items:
        fabric    = row.get('fabricName') or row.get('fabricInfo', 'Unknown Fabric')
        group_key = fabric.split('\n')[0].strip()
        if group_key not in seen:
            seen[group_key] = len(groups)
            groups.append({'groupName': fabric, 'rows': []})
        groups[seen[group_key]]['rows'].append(row)
    for g in groups:
        count      = len(g['rows'])
        g['skins'] = f"{count} {'skin' if count == 1 else 'skins'}"
    return groups


def build_group(group):
    items = []
    h = Table(
        [[P(group.get('groupName', ''), S(10, bold=True)),
          P(group.get('skins', ''),     S(10, bold=True, align=TA_RIGHT))]],
        colWidths=[CONTENT_W * 0.78, CONTENT_W * 0.22]
    )
    h.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
    ]))
    items.append(h)
    rows = [[P(lbl, S(7, bold=True)) for lbl in COL_LABELS]]
    for r in group.get('rows', []):
        rows.append([
            P(r.get('windowName',  ''), S(7)),
            P(r.get('fabricInfo',  ''), S(7)),
            P(r.get('tubeBar',     ''), S(7)),
            P(r.get('headrail',    ''), S(7)),
            P(r.get('controlInfo', ''), S(7)),
            P(r.get('qty',         ''), S(7, align=TA_CENTER)),
            P(r.get('hardware',    ''), S(7)),
        ])
    t = Table(rows, colWidths=COL_W, repeatRows=1, splitByRow=True, hAlign='LEFT')
    t.setStyle(tbl_style())
    items.append(t)
    items.append(Spacer(1, 10))
    return items


def build_pdf_from_data(order, line_items, accessories, output,
                        notes=None, logo_url=None):
    doc = BaseDocTemplate(output, pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN)
    frame = Frame(MARGIN, MARGIN, CONTENT_W, PAGE_H - 2 * MARGIN,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='main', frames=[frame])])
    story = []

    # ── Logo (image or text fallback) ─────────────────────────────────────────
    story.append(build_logo_block(logo_url))
    story.append(Spacer(1, 14))

    # ── Title ─────────────────────────────────────────────────────────────────
    story.append(P('Cut Sheet', S(22)))
    story.append(Spacer(1, 10))

    # ── Order header ──────────────────────────────────────────────────────────
    half = CONTENT_W / 2
    pairs = [
        [('Customer Name',             order.get('customerName',   '')),
         ('Order Name',                order.get('orderName',      ''))],
        [('Email',                     order.get('email',          '')),
         ('Oder ID',                   order.get('orderId',        ''))],
        [('Phone',                     order.get('phone',          '')),
         ('Entered Date',              order.get('enteredDate',    ''))],
        [('Weight (Ordered Fabric)',   order.get('weightFabric',   '')),
         ('Weight (Ordered Hardware)', order.get('weightHardware', ''))],
    ]
    meta_rows = []
    for (ll, lv), (rl, rv) in pairs:
        meta_rows.append([
            P(ll, S(8, color=DGRAY)), P(lv, S(8, bold=True)),
            P(rl, S(8, color=DGRAY)), P(rv, S(8, bold=True)),
        ])
    meta = Table(meta_rows, colWidths=[108, half-108, 138, half-138])
    meta.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING',    (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
    ]))
    story.append(meta)
    story.append(Spacer(1, 14))

    # ── Line item groups ──────────────────────────────────────────────────────
    groups = group_line_items(line_items)
    for group in groups:
        for flowable in build_group(group):
            story.append(flowable)

    # ── Accessories (optional) ────────────────────────────────────────────────
    if accessories:
        story.append(Spacer(1, 4))
        story.append(P(f'Order Accessories ({len(accessories)})', S(9, bold=True)))
        story.append(Spacer(1, 5))
        ACC_W = [120, 155, 85, 85, 95]
        acc_rows = [[P(h, S(8, bold=True)) for h in
                     ['Part Name', 'Part Ref-Code', 'Cost/Unit', '# of Units', 'Cost']]]
        for a in accessories:
            acc_rows.append([
                P(a.get('partName', ''), S(8)),
                P(a.get('partRef',  ''), S(8)),
                P(a.get('costUnit', ''), S(8)),
                P(a.get('units',    ''), S(8)),
                P(a.get('cost',     ''), S(8)),
            ])
        acc_t = Table(acc_rows, colWidths=ACC_W, repeatRows=1,
                      splitByRow=True, hAlign='LEFT')
        acc_t.setStyle(tbl_style())
        story.append(acc_t)

    # ── Notes (optional) ──────────────────────────────────────────────────────
    if notes:
        story.append(Spacer(1, 14))
        story.append(P('Notes', S(9, bold=True)))
        story.append(Spacer(1, 5))
        NOTES_W = [CONTENT_W * 0.30, CONTENT_W * 0.70]
        notes_rows = [[P('Product Name', S(8, bold=True)),
                       P('Note',         S(8, bold=True))]]
        for n in notes:
            notes_rows.append([
                P(n.get('product_name', ''), S(8, bold=True)),
                P(n.get('note_text',    ''), S(8)),
            ])
        notes_t = Table(notes_rows, colWidths=NOTES_W, repeatRows=1,
                        splitByRow=True, hAlign='LEFT')
        notes_t.setStyle(tbl_style())
        story.append(notes_t)

    doc.build(story)

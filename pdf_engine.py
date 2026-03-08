"""
PDF Engine — ReportLab
Accepts flat lineItems list (as Bubble sends it) and auto-groups by fabricName.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle
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

# 7 columns summing to 540 pt
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


def group_line_items(line_items):
    """
    Accepts EITHER:
      A) Flat list: each item has windowName, fabricName, fabricInfo, tubeBar,
                    headrail, controlInfo, qty, hardware
         → auto-groups by fabricName, skins = count of rows in group

      B) Pre-grouped list: each item has groupName, skins, rows[]
         → used as-is
    """
    if not line_items:
        return []

    # Detect format by checking first item
    first = line_items[0]
    if 'groupName' in first and 'rows' in first:
        # Already grouped — use as-is
        return line_items

    # Flat format — group by fabricName, preserving order
    seen   = {}   # fabricName → index in groups list
    groups = []

    for row in line_items:
        fabric = row.get('fabricName') or row.get('fabricInfo', 'Unknown Fabric')
        # Use first line of fabricName as group key
        group_key = fabric.split('\n')[0].strip()

        if group_key not in seen:
            seen[group_key] = len(groups)
            groups.append({
                'groupName': fabric,   # full fabric name as heading
                'rows':      []
            })

        groups[seen[group_key]]['rows'].append(row)

    # Set skins count now that rows are grouped
    for g in groups:
        count = len(g['rows'])
        g['skins'] = f"{count} {'skin' if count == 1 else 'skins'}"

    return groups


def build_group(group):
    items = []

    # Heading: fabric name left, skins right
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

    # Table header + data rows
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


def build_pdf_from_data(order, line_items, accessories, output):
    doc = BaseDocTemplate(output, pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN)

    frame = Frame(MARGIN, MARGIN, CONTENT_W, PAGE_H - 2 * MARGIN,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='main', frames=[frame])])

    story = []

    # ── Logo ──────────────────────────────────────────────────────────────────
    logo = Table([
        [P('<font color="#1a5fa8"><b>Rightlook Blinds</b></font>',
           ParagraphStyle('_', fontName='Helvetica-Bold', fontSize=13,
                          textColor=BLUE, leading=16)), ''],
        [P('BLINDS SHADES &amp; SHUTTERS',
           ParagraphStyle('_', fontName='Helvetica', fontSize=6.5,
                          textColor=colors.HexColor('#999999'), leading=9)), ''],
    ], colWidths=[130, CONTENT_W - 130])
    logo.setStyle(TableStyle([
        ('BOX',           (0,0), (0,-1), 1, BLUE),
        ('SPAN',          (1,0), (1,1)),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(logo)
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

    # ── Line item groups (auto-grouped from flat list) ────────────────────────
    groups = group_line_items(line_items)
    for group in groups:
        for flowable in build_group(group):
            story.append(flowable)

    # ── Accessories ───────────────────────────────────────────────────────────
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

    doc.build(story)

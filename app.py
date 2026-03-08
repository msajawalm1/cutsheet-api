"""
Fabric Cut Sheet — Flask API
Accepts flat form-style parameters (most reliable for Bubble workflows)
POST /generate-pdf
GET  /health
"""

import io
import json
import base64
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from pdf_engine import build_pdf_from_data

app = Flask(__name__)
CORS(app)


def fix_bubble_json(s):
    """Fix literal newlines and smart quotes inside JSON string values."""
    result = []
    in_string   = False
    escape_next = False
    for ch in s:
        if escape_next:
            result.append(ch); escape_next = False
        elif ch == '\\' and in_string:
            result.append(ch); escape_next = True
        elif ch == '"':
            in_string = not in_string; result.append(ch)
        elif ch in ('\u201c', '\u201d') and in_string:
            result.append('\\"')
        elif ch == '\n' and in_string:
            result.append('\\n')
        elif ch == '\r' and in_string:
            result.append('\\r')
        else:
            result.append(ch)
    return ''.join(result)


INVISIBLE_CHARS = ['\u2060', '\u200b', '\u200c', '\u200d', '\ufeff', '\u00ad']

def clean_str(v):
    if not isinstance(v, str):
        return v
    for ch in INVISIBLE_CHARS:
        v = v.replace(ch, '')
    return v.strip()

def normalize(row):
    if not isinstance(row, dict):
        return row
    cleaned = {}
    for k, v in row.items():
        key = 'hardware' if k.strip() == 'Hardware' else k.strip()
        cleaned[key] = clean_str(v)
    return cleaned


def parse_list_field(value):
    """Parse a list field regardless of how Bubble sends it."""
    if not value:
        return []
    if isinstance(value, list):
        if all(isinstance(x, dict) for x in value):
            return [normalize(x) for x in value]
        combined = ''.join(
            item if isinstance(item, str) else json.dumps(item)
            for item in value
        ).strip()
    elif isinstance(value, str):
        combined = value.strip()
    else:
        return []

    if not combined or combined in ('[]', 'null', 'undefined'):
        return []

    fixed = fix_bubble_json(combined)
    if fixed.startswith('{'):
        fixed = '[' + fixed + ']'

    try:
        parsed = json.loads(fixed)
        return [normalize(item) for item in parsed if isinstance(item, dict)]
    except json.JSONDecodeError:
        return []


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "Fabric Cut Sheet API"})


@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    """
    Accepts BOTH:
      A) application/json  — nested JSON body (Initialize mode)
      B) application/x-www-form-urlencoded — flat params (Bubble workflow mode)

    Flat param names:
      customerName, orderName, email, orderId, phone,
      enteredDate, weightFabric, weightHardware,
      lineItems, accessories, notes, logoUrl
    """

    # ── Detect content type and extract data ──────────────────────────────────
    content_type = request.content_type or ''

    if 'application/json' in content_type:
        # JSON body (Initialize / manual test)
        try:
            raw = request.get_json(force=True, silent=True) or {}
        except Exception:
            raw = {}

        # Support both nested {"order":{...}, "lineItems":[...]}
        # and flat {"customerName":"...", "lineItems":[...]}
        if 'order' in raw and isinstance(raw['order'], (dict, str)):
            order_raw = raw['order']
            if isinstance(order_raw, str):
                order_raw = json.loads(fix_bubble_json(order_raw))
            order = order_raw
        else:
            order = {
                'customerName':   raw.get('customerName',   ''),
                'orderName':      raw.get('orderName',      ''),
                'email':          raw.get('email',          ''),
                'orderId':        raw.get('orderId',        ''),
                'phone':          raw.get('phone',          ''),
                'enteredDate':    raw.get('enteredDate',    ''),
                'weightFabric':   raw.get('weightFabric',   ''),
                'weightHardware': raw.get('weightHardware', ''),
            }

        line_items  = parse_list_field(raw.get('lineItems'))
        accessories = parse_list_field(raw.get('accessories'))
        notes       = parse_list_field(raw.get('notes'))
        logo_url    = raw.get('logoUrl') or None

    else:
        # Form / plain body (Bubble workflow sends this)
        # Try to parse as JSON first with force, then fall back to form
        raw_body = request.get_data(as_text=True).strip()

        if raw_body.startswith('{'):
            # It's JSON but sent with wrong content-type
            try:
                raw = json.loads(fix_bubble_json(raw_body))
            except Exception:
                raw = {}

            if 'order' in raw and isinstance(raw['order'], dict):
                order = raw['order']
            else:
                order = {k: raw.get(k, '') for k in
                         ['customerName','orderName','email','orderId',
                          'phone','enteredDate','weightFabric','weightHardware']}

            line_items  = parse_list_field(raw.get('lineItems'))
            accessories = parse_list_field(raw.get('accessories'))
            notes       = parse_list_field(raw.get('notes'))
            logo_url    = raw.get('logoUrl') or None

        else:
            # True form-encoded
            f = request.form
            order = {
                'customerName':   f.get('customerName',   ''),
                'orderName':      f.get('orderName',      ''),
                'email':          f.get('email',          ''),
                'orderId':        f.get('orderId',        ''),
                'phone':          f.get('phone',          ''),
                'enteredDate':    f.get('enteredDate',    ''),
                'weightFabric':   f.get('weightFabric',   ''),
                'weightHardware': f.get('weightHardware', ''),
            }
            line_items  = parse_list_field(f.get('lineItems'))
            accessories = parse_list_field(f.get('accessories'))
            notes       = parse_list_field(f.get('notes'))
            logo_url    = f.get('logoUrl') or None

    # ── Validate ──────────────────────────────────────────────────────────────
    if not any(order.values()):
        return jsonify({"success": False, "error": "Missing order fields"}), 400
    if not line_items:
        return jsonify({"success": False,
                        "error": "Missing or empty lineItems — check your Bubble workflow is passing data"}), 400

    # ── Generate PDF ──────────────────────────────────────────────────────────
    try:
        pdf_buffer = io.BytesIO()
        build_pdf_from_data(
            order       = order,
            line_items  = line_items,
            accessories = accessories,
            notes       = notes,
            logo_url    = logo_url,
            output      = pdf_buffer,
        )
        pdf_buffer.seek(0)
        pdf_base64 = base64.b64encode(pdf_buffer.read()).decode('utf-8')
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

    filename = f"Fabric_Cut_Sheet_{order.get('orderName','Order').replace(' ','_')}.pdf"

    return jsonify({
        "success":    True,
        "filename":   filename,
        "pdf_base64": pdf_base64,
        "mime_type":  "application/pdf"
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)


@app.route('/debug', methods=['POST'])
def debug():
    """
    Temporary debug endpoint — call this from Bubble instead of /generate-pdf
    to see exactly what Bubble is sending (content-type, body, params).
    Remove after debugging.
    """
    return jsonify({
        "content_type": request.content_type,
        "raw_body_preview": request.get_data(as_text=True)[:500],
        "form_keys": list(request.form.keys()),
        "json_keys": list((request.get_json(force=True, silent=True) or {}).keys()),
    })

"""
Fabric Cut Sheet — Flask API
POST /generate-pdf  →  returns JSON with base64-encoded PDF (Bubble-compatible)
GET  /health        →  health check
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
    """
    Fixes two issues Bubble introduces into JSON strings:
      1. Literal newlines inside string values     → escaped to \\n
      2. Smart/curly quotes " " inside values      → escaped to \\"
    """
    result = []
    in_string   = False
    escape_next = False

    for ch in s:
        if escape_next:
            result.append(ch)
            escape_next = False
        elif ch == '\\' and in_string:
            result.append(ch)
            escape_next = True
        elif ch == '"':                           # standard JSON quote
            in_string = not in_string
            result.append(ch)
        elif ch in ('\u201c', '\u201d') and in_string:
            result.append('\\"')                  # smart quote → escaped quote
        elif ch == '\n' and in_string:
            result.append('\\n')                  # literal newline → \\n
        elif ch == '\r' and in_string:
            result.append('\\r')
        else:
            result.append(ch)

    return ''.join(result)


def normalize(row):
    """Fix capitalisation issues from Bubble (e.g. Hardware → hardware)."""
    if not isinstance(row, dict):
        return row
    return {('hardware' if k.strip() == 'Hardware' else k.strip()): v
            for k, v in row.items()}


def parse_list_field(value):
    """
    Handles every format Bubble can send a list in:
      1. Proper list of dicts:           [{...}, {...}]          ← new Bubble format
      2. List of JSON strings:           ["{...}", "{...}"]
      3. List with ONE combined string:  ["{...},{...},{...}"]
      4. A single JSON string of array:  "[{...},{...}]"
    """
    if value is None:
        return []

    # Already a proper list of dicts — just normalize keys
    if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
        return [normalize(x) for x in value]

    # Build a single combined string from whatever we received
    if isinstance(value, list):
        combined = ''.join(
            item if isinstance(item, str) else json.dumps(item)
            for item in value
        ).strip()
    elif isinstance(value, str):
        combined = value.strip()
    else:
        return []

    if not combined:
        return []

    # Fix Bubble's encoding issues
    fixed = fix_bubble_json(combined)

    # If it starts with { it's one or more objects — wrap in array
    if fixed.startswith('{'):
        fixed = '[' + fixed + ']'

    parsed = json.loads(fixed)
    return [normalize(item) for item in parsed if isinstance(item, dict)]


def parse_dict_field(value):
    """Parse a single dict field (e.g. 'order')."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return json.loads(fix_bubble_json(value))
    return value


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "Fabric Cut Sheet API"})


@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    if not request.is_json:
        return jsonify({"success": False, "error": "Content-Type must be application/json"}), 400

    data = request.get_json()

    try:
        order       = parse_dict_field(data.get('order'))
        line_items  = parse_list_field(data.get('lineItems'))
        accessories = parse_list_field(data.get('accessories'))
        notes       = parse_list_field(data.get('notes'))
        logo_url    = data.get('logoUrl') or None
    except (ValueError, json.JSONDecodeError) as e:
        return jsonify({"success": False, "error": f"Could not parse request data: {str(e)}"}), 400

    if not order:
        return jsonify({"success": False, "error": "Missing or empty 'order' field"}), 400
    if not line_items:
        return jsonify({"success": False, "error": "Missing or empty 'lineItems' field"}), 400

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

    order_name = order.get('orderName', 'Cut_Sheet') if isinstance(order, dict) else 'Cut_Sheet'
    filename   = f"Fabric_Cut_Sheet_{order_name.replace(' ', '_')}.pdf"

    return jsonify({
        "success":    True,
        "filename":   filename,
        "pdf_base64": pdf_base64,
        "mime_type":  "application/pdf"
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

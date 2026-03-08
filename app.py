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


def parse_field(value):
    """
    Bubble sometimes sends lists/dicts as JSON strings instead of real objects.
    This ensures we always get a proper Python object regardless.
    """
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value          # already parsed — use as-is
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return json.loads(value)   # parse the string into a real object
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse field as JSON: {e}\nValue received: {value[:200]}")
    return value


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "Fabric Cut Sheet API"})


@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    if not request.is_json:
        return jsonify({"success": False, "error": "Content-Type must be application/json"}), 400

    data = request.get_json()

    # ── Parse every field — handles both real objects and JSON strings ─────────
    try:
        order       = parse_field(data.get('order'))
        line_items  = parse_field(data.get('lineItems'))
        accessories = parse_field(data.get('accessories')) or []
        notes       = parse_field(data.get('notes'))       or []
        logo_url    = data.get('logoUrl') or None
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    # ── Validate required fields ───────────────────────────────────────────────
    if not order:
        return jsonify({"success": False, "error": "Missing or empty 'order' field"}), 400
    if not line_items:
        return jsonify({"success": False, "error": "Missing or empty 'lineItems' field"}), 400

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

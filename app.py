"""
Fabric Cut Sheet — Flask API
==============================
POST /generate-pdf   →  accepts JSON, returns PDF file download
GET  /health         →  health check (used by Render/Railway)
"""

import io
import traceback
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pdf_engine import build_pdf_from_data

app = Flask(__name__)
CORS(app)  # Allow Bubble (cross-origin) to call this API


# ─────────────────────────────────────────────────────────────────────────────
#  HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "Fabric Cut Sheet API"})


# ─────────────────────────────────────────────────────────────────────────────
#  GENERATE PDF
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    """
    Expects JSON body:
    {
        "order": {
            "customerName":   "...",
            "orderName":      "...",
            "email":          "...",
            "orderId":        "...",
            "phone":          "...",
            "enteredDate":    "...",
            "weightFabric":   "...",
            "weightHardware": "..."
        },
        "lineItems": [
            {
                "groupName": "...",
                "skins": "...",
                "rows": [
                    {
                        "windowName":  "...",
                        "fabricInfo":  "...",
                        "tubeBar":     "...",
                        "headrail":    "...",
                        "controlInfo": "...",
                        "qty":         "...",
                        "hardware":    "..."
                    }
                ]
            }
        ],
        "accessories": [
            {
                "partName": "...",
                "partRef":  "...",
                "costUnit": "...",
                "units":    "...",
                "cost":     "..."
            }
        ]
    }
    """

    # ── Parse request ─────────────────────────────────────────────────────────
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data = request.get_json()

    # ── Validate required fields ──────────────────────────────────────────────
    if not data.get('order'):
        return jsonify({"error": "Missing 'order' field"}), 400
    if not data.get('lineItems'):
        return jsonify({"error": "Missing 'lineItems' field"}), 400

    # ── Generate PDF into memory (no disk write needed) ───────────────────────
    try:
        pdf_buffer = io.BytesIO()
        build_pdf_from_data(
            order       = data['order'],
            line_items  = data['lineItems'],
            accessories = data.get('accessories', []),
            output      = pdf_buffer
        )
        pdf_buffer.seek(0)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500

    # ── Build filename ────────────────────────────────────────────────────────
    order_name = data['order'].get('orderName', 'Cut_Sheet')
    filename   = f"Fabric_Cut_Sheet_{order_name.replace(' ', '_')}.pdf"

    # ── Return PDF as file download ───────────────────────────────────────────
    return send_file(
        pdf_buffer,
        mimetype            = 'application/pdf',
        as_attachment       = True,
        download_name       = filename
    )


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
